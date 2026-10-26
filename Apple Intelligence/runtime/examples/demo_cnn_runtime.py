#!/usr/bin/env python3
"""Run two real quantized firmware CNNs on synthetic embedding tensors.

These are embedding-to-score models. Text preprocessing, class names, calibrated
probabilities and image input are not reconstructed or inferred.
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
from coremltools.proto import Model_pb2
from apple_firmware_runtime.backends import protobuf_cpu
from apple_firmware_runtime.catalog import Catalog
from apple_firmware_runtime.store import Store

MODEL_IDS = ("m-6c123b9c8ab2f00ccad0", "m-ddd4e3cc19480fcb7ac3")


def f32(v):
    return struct.unpack("<f", struct.pack("<f", v))[0]


def scalar_dequantize(w, shape):
    """Independent Python unsigned-byte decoder with one Float32 rounding."""
    q = w.quantization
    if q.numberOfBits != 8 or q.WhichOneof("QuantizationType") != "linearQuantization":
        raise ValueError("Reference requires uint8 linear fixture coefficients")
    scale, bias = list(q.linearQuantization.scale), list(q.linearQuantization.bias)
    channels = shape[0] if len(shape) > 1 else 1
    if len(w.rawValue) != math.prod(shape) or len(scale) != len(bias) or len(scale) not in (1, channels):
        raise ValueError("Unexpected fixture quantization dimensions")
    per_channel = math.prod(shape) // channels
    return [f32(v * scale[0 if len(scale) == 1 else i // per_channel]
                + bias[0 if len(bias) == 1 else i // per_channel]) for i, v in enumerate(w.rawValue)]


def constant_cnn_reference(spec, fill):
    """Scalar math for spatially constant input, independent of NumPy/runtime.

    VALID, zero-padding-free convolutions preserve spatial constancy within each
    channel. Max pooling then keeps that value. This reduces the real CNN's
    reference computation without assuming equal channels or dropping weights.
    Nonconstant convolution/window ordering is tested separately.
    """
    shape = list(spec.description.input[0].type.multiArrayType.shape)
    if shape != [1, 512, 1, 256]: raise ValueError("Unexpected USEN fixture input")
    values = [float(fill)] * 512
    for layer in spec.neuralNetwork.layers:
        kind = layer.WhichOneof("layer"); op = getattr(layer, kind)
        if kind == "squeeze":
            axes = set(a % len(shape) for a in op.axes)
            if any(shape[i] != 1 for i in axes): raise ValueError("Invalid reference squeeze")
            shape = [v for i, v in enumerate(shape) if i not in axes]
        elif kind == "expandDims":
            rank = len(shape) + len(op.axes)
            for axis in sorted(a % rank for a in op.axes): shape.insert(axis, 1)
        elif kind == "convolution":
            if (len(shape) != 4 or shape[0] != 1 or shape[1] != len(values) or op.nGroups != 1
                    or op.isDeconvolution or list(op.dilationFactor) != [1, 1]
                    or op.WhichOneof("ConvolutionPaddingType") != "valid"
                    or any(b.startEdgeSize or b.endEdgeSize for b in op.valid.paddingAmounts.borderAmounts)):
                raise ValueError("Reference requires ungrouped unpadded fixture convolution")
            kh, kw = op.kernelSize; sh, sw = op.stride
            weights = scalar_dequantize(op.weights, (op.outputChannels, op.kernelChannels, kh, kw))
            biases = scalar_dequantize(op.bias, (op.outputChannels,))
            count = len(values) * kh * kw
            values = [f32(math.fsum([biases[o]] + [weights[o * count + j] * values[j // (kh * kw)]
                                                   for j in range(count)])) for o in range(op.outputChannels)]
            shape = [1, op.outputChannels, (shape[2] - kh) // sh + 1, (shape[3] - kw) // sw + 1]
        elif kind == "activation":
            if op.WhichOneof("NonlinearityType") != "ReLU": raise ValueError("Unexpected reference activation")
            values = [max(0., v) for v in values]
        elif kind == "pooling":
            if (op.type != 0 or op.globalPooling or op.WhichOneof("PoolingPaddingType") != "valid"
                    or any(b.startEdgeSize or b.endEdgeSize for b in op.valid.paddingAmounts.borderAmounts)):
                raise ValueError("Reference requires fixture VALID max pooling")
            kh, kw = op.kernelSize; sh, sw = op.stride
            shape[-2:] = [(shape[-2] - kh) // sh + 1, (shape[-1] - kw) // sw + 1]
        elif kind == "reshapeStatic":
            if list(op.targetShape) != [-1, 576] or math.prod(shape) != 576:
                raise ValueError("Unexpected fixture final reshape")
            shape = [1, 576]
        elif kind == "innerProduct":
            if shape != [1, op.inputChannels] or op.inputChannels % len(values):
                raise ValueError("Unexpected fixture dense dimensions")
            weights = scalar_dequantize(op.weights, (op.outputChannels, op.inputChannels))
            biases = scalar_dequantize(op.bias, (op.outputChannels,))
            repeats = op.inputChannels // len(values)
            values = [f32(math.fsum([biases[o]] + [weights[o * op.inputChannels + j] * values[j // repeats]
                                                   for j in range(op.inputChannels)]))
                      for o in range(op.outputChannels)]
            shape = [1, op.outputChannels]
        else: raise ValueError(f"Unexpected reference fixture layer: {kind}")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parents[2] / "models/manifest.json")
    parser.add_argument("--state", type=Path, default=Path(__file__).resolve().parents[1] / ".state/cnn-demo")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = Catalog(args.catalog); store = Store(args.state / "store")
    args.state.mkdir(parents=True, exist_ok=True)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "manifest_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
              "input_semantics": "Synthetic constant embedding tensors; no text/image preprocessing or class labels inferred",
              "independent_reference_method": "Python uint8 decoding and scalar Float64/math.fsum on each real coefficient; Float32 rounding between layers",
              "independent_reference_tolerance": {"atol": 2e-5, "rtol": 2e-5},
              "apple_runtime_parity_verified": False, "models": []}
    for model_id in MODEL_IDS:
        model = catalog.models[model_id]; store.import_model(model)
        integrity = store.verify(model); bundle = store.bundle(model)
        path, = [bundle / f["path"] for f in model.files if f["path"].endswith(".mlmodel")]
        spec = Model_pb2.Model(); spec.ParseFromString(path.read_bytes())
        row = {"model": model.summary(), "integrity": integrity, "demos": []}
        report["models"].append(row)
        for fill in (0, 1):
            inputs = {"inp": {"shape": [1, 512, 1, 256], "data": [fill] * (512 * 256)}}
            raw = json.dumps(inputs, separators=(",", ":")) + "\n"
            input_path = args.state / f"{model_id}-{'zero' if fill == 0 else 'one'}.json"
            input_path.write_text(raw)
            store.verify(model); result = protobuf_cpu(model, bundle, inputs)
            expected = constant_cnn_reference(spec, fill)
            observed = result["outputs"]["linear_0"]["data"]
            if len(observed) != len(expected) or any(abs(a - b) > 2e-5 + 2e-5 * abs(b)
                                                     for a, b in zip(observed, expected)):
                raise AssertionError("Real CNN differs from independent scalar reference")
            row["demos"].append({"fill": fill, "input_file": str(input_path),
                                  "input_sha256": hashlib.sha256(raw.encode()).hexdigest(), "result": result,
                                  "independent_reference": expected,
                                  "max_absolute_error": max(abs(a - b) for a, b in zip(observed, expected))})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"models_executed": len(report["models"]), "demos": 4, "output": str(args.output)}))


if __name__ == "__main__": main()
