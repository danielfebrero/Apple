#!/usr/bin/env python3
"""Independent saved-artifact verification using merged Float64 matrices.

No PyTorch/PEFT forward call, model hub, or Core ML prediction is used here.
Coremltools supplies protobuf types; the bounded evaluator uses NumPy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from safetensors.numpy import load_file
from coremltools.proto import Model_pb2

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))
from apple_firmware_runtime.protobuf_cpu import mil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--coreai-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    r = args.results
    checks = json.loads((r / "SHA256.json").read_text())
    for f in checks:
        p = r / f["path"]
        assert p.stat().st_size == f["size"] and hashlib.sha256(p.read_bytes()).hexdigest() == f["sha256"]
    base = dict(np.load(r / "base.npz", allow_pickle=False))
    adapter = dict(np.load(r / "adapters.npz", allow_pickle=False))
    vectors = dict(np.load(r / "vectors.npz", allow_pickle=False))
    torch_outputs = dict(np.load(r / "torch-outputs.npz", allow_pickle=False))
    refs = {}
    for name in ("base", "adapter_1", "adapter_2"):
        # Merge matrices in Float64 first; this differs from the experiment's
        # two-branch layer computation and exposes orientation/scaling mistakes.
        w = {i: base[f"linear{i}.weight"].astype(np.float64) for i in (1, 2)}
        if name != "base":
            saved = load_file(str(r / name / "adapter_model.safetensors"))
            for i in (1, 2):
                for key, role in (("a", "A"), ("b", "B")):
                    assert np.array_equal(saved[f"base_model.model.linear{i}.lora_{role}.weight"], adapter[f"{name}_{key}{i}"])
                w[i] += 2.0 * (adapter[f"{name}_b{i}"].astype(np.float64) @ adapter[f"{name}_a{i}"].astype(np.float64))
        x = vectors["inputs"].astype(np.float64)
        h = np.maximum(np.einsum("bi,ji->bj", x, w[1]) + base["linear1.bias"], 0)
        refs[name] = np.einsum("bi,ji->bj", h, w[2]) + base["linear2.bias"]
        assert np.max(np.abs(refs[name] - vectors[name])) < 1e-12
    errors = {}
    for p in sorted(r.glob("*.mlpackage")):
        model_path = p / "Data/com.apple.CoreML/model.mlmodel"
        spec = Model_pb2.Model.FromString(model_path.read_bytes())
        for function in sorted(spec.mlProgram.functions):
            selected = Model_pb2.Model()
            selected.CopyFrom(spec)
            selected.mlProgram.ClearField("functions")
            selected.mlProgram.functions["main"].CopyFrom(spec.mlProgram.functions[function])
            if spec.description.functions:
                desc = next(f for f in spec.description.functions if f.name == function)
                selected.description.Clear()
                selected.description.input.extend(desc.input)
                selected.description.output.extend(desc.output)
            block = next(iter(selected.mlProgram.functions["main"].block_specializations.values()))
            output = block.outputs[0]
            name = function if p.name.startswith("multifunction") else p.stem
            key = f"adapter_{name[7]}" if name.startswith("merged_") else name
            actual = np.concatenate([mil(selected, {"x": row[None]}, model_path.parent)[output] for row in vectors["inputs"]])
            err = float(np.max(np.abs(actual - refs[key])))
            assert err < 3e-5
            errors[f"{p.name}/{function}"] = err
    for name, actual in torch_outputs.items():
        key = f"adapter_{name[-1]}" if name.startswith("merged_") else name
        err = float(np.max(np.abs(actual - refs[key])))
        assert err < 3e-5
        errors[f"saved_torch/{name}"] = err
    coreai = dict(np.load(args.coreai_results / "native-outputs.npz", allow_pickle=False))
    for name, actual in coreai.items():
        err = float(np.max(np.abs(actual - refs[name])))
        assert err < 3e-5
        errors[f"native_coreai/{name}"] = err
    cli = json.loads((args.coreai_results / "cli-predict.json").read_text())
    actual = np.asarray(cli["outputs"]["y"]["data"], dtype=np.float64).reshape(1, 16)
    err = float(np.max(np.abs(actual - refs["adapter_1"][1:2])))
    assert err < 3e-5
    errors["native_coreai/verified_cli"] = err
    report = json.loads((r / "report.json").read_text())
    combined = Model_pb2.Model.FromString((r / "multifunction_adapter.mlpackage/Data/com.apple.CoreML/model.mlmodel").read_bytes())
    blobs = {}
    for function in ("adapter_1", "adapter_2"):
        ops = next(iter(combined.mlProgram.functions[function].block_specializations.values())).operations
        blobs[function] = {o.outputs[0].name: (o.attributes["val"].blobFileValue.fileName,
                            o.attributes["val"].blobFileValue.offset) for o in ops
                            if o.type == "const" and o.attributes["val"].WhichOneof("value") == "blobFileValue"}
    shared = [n for n, ref in blobs["adapter_1"].items() if blobs["adapter_2"].get(n) == ref]
    assert sum("base_layer_weight" in n for n in shared) == 2
    assert report["apple_coreml_predict"]["status"] == "unavailable"
    result = {"status": "PASS", "hashes_verified": len(checks), "numerical_comparisons": len(errors),
        "errors_vs_independent_float64": errors, "max_abs_error": max(errors.values()),
        "tolerance_max_abs": 3e-5, "shared_blob_names_same_offsets": shared,
        "reference": "Float64 fused matrices with einsum; independent from PyTorch and the experiment's unfused reference",
        "Core_ML_Linux_inference": False, "AFM_inference": False}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
