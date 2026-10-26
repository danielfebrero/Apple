#!/usr/bin/env python3
"""Run the real firmware TTE model and check its LSTM with independent scalar math.

The inputs are synthetic feature tensors, not measurements or calibrated battery
predictions. This checks CPU mathematics, not parity with an Apple runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from coremltools.proto import Model_pb2
from apple_firmware_runtime.backends import protobuf_cpu
from apple_firmware_runtime.catalog import Catalog
from apple_firmware_runtime.protobuf_cpu import evaluate
from apple_firmware_runtime.store import Store

MODEL_ID = "m-42c503b700dcb5d958aa"


def scalar_lstm_reference(args):
    """Float64 Python/math.fsum reference, without runtime math or NumPy BLAS."""
    x, h, c, wi, wh, bias = (args[k].tolist() for k in
                             ("x", "initial_h", "initial_c", "weight_ih", "weight_hh", "bias"))
    hidden = len(h[0])
    sequence = []
    def logistic(v):
        if v >= 0: return 1 / (1 + math.exp(-v))
        z = math.exp(v)
        return z / (1 + z)
    for step in x:
        next_h, next_c = [], []
        for batch, xt in enumerate(step):
            gates = [math.fsum([b] + [w * v for w, v in zip(wrow, xt)]
                              + [w * v for w, v in zip(rrow, h[batch])])
                     for wrow, rrow, b in zip(wi, wh, bias)]
            ci, hi = [], []
            for k in range(hidden):
                state = (logistic(gates[hidden + k]) * c[batch][k]
                         + logistic(gates[k]) * math.tanh(gates[3 * hidden + k]))
                ci.append(state)
                hi.append(logistic(gates[2 * hidden + k]) * math.tanh(state))
            next_h.append(hi); next_c.append(ci)
        h, c = next_h, next_c
        sequence.append(h)
    return tuple(np.asarray(a, dtype=np.float64) for a in (sequence, h, c))


def independent_tte_lstm_args(spec, model_dir, fill):
    """Decode actual FP32 coefficients with struct, separately from value()."""
    block = next(iter(spec.mlProgram.functions["main"].block_specializations.values()))
    constants = {o.outputs[0].name: o.attributes["val"] for o in block.operations if o.type == "const"}
    op, = [o for o in block.operations if o.type == "lstm"]
    allowed = {"x", "weight_ih", "weight_hh", "bias", "initial_h", "initial_c", "direction",
               "output_sequence", "recurrent_activation", "cell_activation", "activation"}
    if set(op.inputs) != allowed: raise ValueError("Unexpected TTE LSTM variant")
    for name, expected in (("direction", "forward"), ("recurrent_activation", "sigmoid"),
                           ("cell_activation", "tanh"), ("activation", "tanh")):
        v = constants[op.inputs[name].arguments[0].name]
        if list(v.immediateValue.tensor.strings.values) != [expected]:
            raise ValueError("Unexpected TTE LSTM activation/direction")
    sequence_flag = constants[op.inputs["output_sequence"].arguments[0].name]
    if list(sequence_flag.immediateValue.tensor.bools.values) != [True]:
        raise ValueError("Expected the complete TTE LSTM sequence")
    result = {}
    for name in ("weight_ih", "weight_hh", "bias", "initial_h", "initial_c"):
        val = constants[op.inputs[name].arguments[0].name]
        shape = [d.constant.size for d in val.type.tensorType.dimensions]
        ref = val.blobFileValue
        # The runtime/store validates containment and integrity before this fixture reference.
        blob = (model_dir / ref.fileName.removeprefix("@model_path/")).read_bytes()
        magic, typ, size, offset = struct.unpack_from("<IIQQ", blob, ref.offset)
        if magic != 0xDEADBEEF or typ != 2 or size != math.prod(shape) * 4:
            raise ValueError("Expected the TTE Float32 blob fixture")
        result[name] = np.asarray(struct.unpack_from("<" + "f" * (size // 4), blob, offset),
                                  dtype=np.float32).reshape(shape)
    temporal, = [f for f in spec.description.input if f.name == "temporal_features"]
    batch, steps, channels = temporal.type.multiArrayType.shape
    result.update(x=np.full((steps, batch, channels), fill, dtype=np.float16).astype(np.float32),
                  output_sequence=np.asarray(True))
    return result


def evaluate_tte_lstm_prefix(spec, inputs, model_dir):
    """Expose the original LSTM's outputs, retaining its actual graph prefix.

    This exercises production constant decoding, input casts and bindings; only
    downstream layers and the output description are removed for observation.
    """
    prefix = Model_pb2.Model(); prefix.CopyFrom(spec)
    block = next(iter(prefix.mlProgram.functions["main"].block_specializations.values()))
    index, = [i for i, op in enumerate(block.operations) if op.type == "lstm"]
    names = [o.name for o in block.operations[index].outputs]
    del block.operations[index + 1:]
    del prefix.description.output[:]
    for name in names: prefix.description.output.add().name = name
    outputs = evaluate(prefix, inputs, model_dir)
    return tuple(outputs[name] for name in names)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parents[2] / "models/manifest.json")
    parser.add_argument("--state", type=Path, default=Path(__file__).resolve().parents[1] / ".state/tte-demo")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = Catalog(args.catalog)
    model = catalog.models[MODEL_ID]
    args.state.mkdir(parents=True, exist_ok=True)
    store = Store(args.state / "store")
    store.import_model(model)
    integrity = store.verify(model)
    bundle = store.bundle(model)
    path, = [bundle / f["path"] for f in model.files if f["path"].endswith(".mlmodel")]
    spec = Model_pb2.Model(); spec.ParseFromString(path.read_bytes())
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "model": model.summary(), "integrity": integrity,
              "manifest_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
              "input_semantics": "Synthetic zero/one features, without battery/app preprocessing",
              "independent_lstm_method": "Original graph prefix versus struct-decoded coefficients and Python Float64/math.fsum recurrence",
              "independent_lstm_tolerance": {"atol": 2e-6, "rtol": 2e-5},
              "apple_runtime_parity_verified": False, "demos": []}
    for fill in (0, 1):
        inputs = {"temporal_features": {"shape": [1, 19, 5], "data": [fill] * 95},
                  "static_features": {"shape": [1, 10], "data": [fill] * 10}}
        input_path = args.state / f"tte-{'zero' if fill == 0 else 'one'}.json"
        raw = json.dumps(inputs, separators=(",", ":")) + "\n"
        input_path.write_text(raw)
        # Store hashes are rechecked immediately before each full inference.
        store.verify(model)
        result = protobuf_cpu(model, bundle, inputs)
        lstm_args = independent_tte_lstm_args(spec, path.parent, fill)
        actual = evaluate_tte_lstm_prefix(spec, inputs, path.parent)
        expected = scalar_lstm_reference(lstm_args)
        checks = []
        for name, observed, reference in zip(("sequence", "hidden", "cell"), actual, expected):
            np.testing.assert_allclose(observed, reference, atol=2e-6, rtol=2e-5)
            checks.append({"name": name, "shape": list(observed.shape), "values_compared": observed.size,
                           "max_absolute_error": float(np.max(np.abs(observed - reference))),
                           "scalar_reference_sum": math.fsum(reference.reshape(-1)),
                           "scalar_reference_first4": reference.reshape(-1)[:4].tolist()})
        report["demos"].append({"fill": fill, "input_file": str(input_path),
                                "input_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                                "result": result, "independent_lstm_check": checks})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"model_id": MODEL_ID, "executed": len(report["demos"]),
                      "independent_lstm_values_compared": sum(c["values_compared"] for d in report["demos"]
                                                                for c in d["independent_lstm_check"]),
                      "output": str(args.output)}))


if __name__ == "__main__": main()
