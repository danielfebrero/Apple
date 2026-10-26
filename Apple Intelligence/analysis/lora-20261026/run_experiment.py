#!/usr/bin/env python3
"""Controlled PEFT/Core ML experiment. No Apple model weights or model downloads.

Writes a new output directory; validates saved ML Program bytes with the existing
bounded NumPy evaluator. That evaluator is NOT Apple's Core ML runtime.
"""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
import numpy as np
import torch
from torch import nn
from peft import LoraConfig, PeftModel, get_peft_model
import coremltools as ct

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))
from apple_firmware_runtime.protobuf_cpu import mil, value
from coremltools.proto import Model_pb2


class Base(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear1 = nn.Linear(64, 48)
        self.linear2 = nn.Linear(48, 16)

    def forward(self, x):
        return self.linear2(torch.relu(self.linear1(x)))


def reference(x, base, adapter=None, scale=2.0):
    """Independent Float64 math, with PyTorch/PEFT-free array operations."""
    h = np.asarray(x, dtype=np.float64)
    for i in (1, 2):
        w = base[f"linear{i}.weight"].astype(np.float64)
        b = base[f"linear{i}.bias"].astype(np.float64)
        y = h @ w.T + b
        if adapter is not None:
            a, bb = adapter[f"a{i}"], adapter[f"b{i}"]
            y += scale * ((h @ a.astype(np.float64).T) @ bb.astype(np.float64).T)
        h = np.maximum(y, 0) if i == 1 else y
    return h


def get_adapter(model):
    out = {}
    for i in (1, 2):
        layer = getattr(model.base_model.model, f"linear{i}")
        out[f"a{i}"] = layer.lora_A["default"].weight.detach().numpy().copy()
        out[f"b{i}"] = layer.lora_B["default"].weight.detach().numpy().copy()
    return out


def convert(model, path, target=ct.target.iOS18):
    traced = torch.jit.trace(model.eval(), torch.zeros(1, 64))
    converted = ct.convert(
        traced, inputs=[ct.TensorType(name="x", shape=(1, 64))],
        outputs=[ct.TensorType(name="y")], minimum_deployment_target=target,
        compute_precision=ct.precision.FLOAT32, skip_model_load=True,
    )
    converted.save(str(path))
    return converted


def saved_function(path, function="main"):
    """Read saved protobuf; select one function ONLY inside this lab harness.

    This is not a change to the production runtime's single-function contract.
    All blob references still refer to the original package weights.
    """
    p = path / "Data/com.apple.CoreML/model.mlmodel"
    spec = Model_pb2.Model.FromString(p.read_bytes())
    selected = Model_pb2.Model()
    selected.CopyFrom(spec)
    selected.mlProgram.ClearField("functions")
    selected.mlProgram.functions["main"].CopyFrom(spec.mlProgram.functions[function])
    if spec.description.functions:
        desc = next(d for d in spec.description.functions if d.name == function)
        selected.description.Clear()
        selected.description.input.extend(desc.input)
        selected.description.output.extend(desc.output)
    ops = next(iter(spec.mlProgram.functions[function].block_specializations.values())).operations
    blobs = []
    for op in ops:
        if op.type == "const" and op.attributes["val"].WhichOneof("value") == "blobFileValue":
            v = op.attributes["val"]
            arr = value(v, p.parent)
            blobs.append({"name": op.outputs[0].name, "shape": list(arr.shape),
                          "dtype": str(arr.dtype), "data_sha256": hashlib.sha256(arr.tobytes()).hexdigest(),
                          "file": v.blobFileValue.fileName, "offset": v.blobFileValue.offset})
    return selected, p.parent, {"specification_version": spec.specificationVersion,
        "functions": sorted(spec.mlProgram.functions), "default_function": spec.description.defaultFunctionName,
        "op_counts": {k: sum(o.type == k for o in ops) for k in sorted({o.type for o in ops})},
        "blobs": blobs}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    out = args.output
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(20261026)
    rng = np.random.default_rng(20261026)
    base = Base().eval()
    base_arrays = {k: v.detach().numpy().copy() for k, v in base.state_dict().items()}
    np.savez(out / "base.npz", **base_arrays)
    train_x = rng.normal(size=(96, 64)).astype(np.float32)
    test_x = rng.normal(size=(12, 64)).astype(np.float32)
    test_x[0] = 0
    training, adapters, models = {}, {}, {"base": base}
    for index in (1, 2):
        name = f"adapter_{index}"
        model = get_peft_model(copy.deepcopy(base), LoraConfig(
            target_modules=["linear1", "linear2"], r=4, lora_alpha=8,
            lora_dropout=0.0, bias="none"))
        # PEFT's B=0 initialization must not be mistaken for a useful adapter.
        initial_delta = float(np.max(np.abs(model(torch.from_numpy(test_x)).detach().numpy()
                                           - base(torch.from_numpy(test_x)).detach().numpy())))
        assert initial_delta == 0
        teacher = {f"{k}{i}": rng.normal(0, 0.07, (4, n) if k == "a" else (m, 4)).astype(np.float32)
                   for i, n, m in ((1, 64, 48), (2, 48, 16)) for k in ("a", "b")}
        target = torch.from_numpy(reference(train_x, base_arrays, teacher).astype(np.float32))
        optimizer = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=0.01)
        x = torch.from_numpy(train_x)
        loss_before = float(torch.mean((model(x) - target) ** 2).detach())
        for _ in range(180):
            optimizer.zero_grad()
            loss = torch.mean((model(x) - target) ** 2)
            loss.backward()
            optimizer.step()
        model.eval()
        loss_after = float(torch.mean((model(x) - target) ** 2).detach())
        assert loss_after < loss_before * 0.1
        for k, v in base_arrays.items():
            layer, param = k.split(".")
            assert np.array_equal(getattr(getattr(model.base_model.model, layer).base_layer, param).detach().numpy(), v)
        adapters[name] = get_adapter(model)
        model.save_pretrained(out / name)
        models[name] = model
        merged = copy.deepcopy(model).merge_and_unload(safe_merge=True)
        models[f"merged_{index}"] = merged.eval()
        torch_delta = float(np.max(np.abs(model(torch.from_numpy(test_x)).detach().numpy()
                                      - base(torch.from_numpy(test_x)).detach().numpy())))
        assert torch_delta > 0.01
        training[name] = {"initial_delta_from_base": initial_delta, "mse_before": loss_before,
            "mse_after": loss_after, "steps": 180, "test_delta_from_base": torch_delta,
            "frozen_base_unchanged": True, "rank": 4, "alpha": 8, "scale": 2.0,
            "parameter_shapes": {k: list(v.shape) for k, v in adapters[name].items()}}
    np.savez(out / "adapters.npz", **{f"{name}_{k}": v for name, a in adapters.items() for k, v in a.items()})
    refs = {"base": reference(test_x, base_arrays)}
    refs.update({name: reference(test_x, base_arrays, a) for name, a in adapters.items()})
    np.savez(out / "vectors.npz", inputs=test_x, **refs)
    # PEFT can switch named adapters at runtime. A traced graph captures the
    # selected path; converting that graph does not export the Python switch.
    switch = PeftModel.from_pretrained(copy.deepcopy(base), out / "adapter_1")
    switch.load_adapter(out / "adapter_2", adapter_name="second")
    switch.eval()
    switch.set_adapter("default")
    frozen_trace = torch.jit.trace(switch, torch.zeros(1, 64))
    switch.set_adapter("second")
    switched = switch(torch.from_numpy(test_x)).detach().numpy()
    traced_after_switch = frozen_trace(torch.from_numpy(test_x)).detach().numpy()
    assert np.max(np.abs(switched - refs["adapter_2"])) < 3e-5
    assert np.max(np.abs(traced_after_switch - refs["adapter_1"])) < 3e-5
    with switch.disable_adapter():
        disabled = switch(torch.from_numpy(test_x)).detach().numpy()
    assert np.max(np.abs(disabled - refs["base"])) < 3e-5
    packages, info, comparisons, torch_outputs = {}, {}, {}, {}
    for name, model in models.items():
        path = out / f"{name}.mlpackage"
        packages[name] = convert(model, path)
        spec, weights, info[name] = saved_function(path)
        expected = refs[f"adapter_{name[-1]}"] if name.startswith("merged") else refs[name]
        torch_y = model(torch.from_numpy(test_x)).detach().numpy()
        torch_outputs[name] = torch_y
        mil_y = np.concatenate([mil(spec, {"x": row[None]}, weights)["y"] for row in test_x])
        torch_error = float(np.max(np.abs(torch_y - expected)))
        mil_error = float(np.max(np.abs(mil_y - expected)))
        assert torch_error < 3e-5 and mil_error < 3e-5
        comparisons[name] = {"torch_vs_numpy64_max_abs": torch_error,
                             "saved_mil_numpy_vs_numpy64_max_abs": mil_error}
    np.savez(out / "torch-outputs.npz", **torch_outputs)
    # iOS18 is the multifunction requirement, not a universal LoRA minimum.
    older = out / "merged_1_ios15.mlpackage"
    convert(models["merged_1"], older, ct.target.iOS15)
    spec, weights, info["merged_1_ios15"] = saved_function(older)
    actual = np.concatenate([mil(spec, {"x": row[None]}, weights)["y"] for row in test_x])
    err = float(np.max(np.abs(actual - refs["adapter_1"])))
    assert err < 3e-5
    comparisons["merged_1_ios15"] = {"saved_mil_numpy_vs_numpy64_max_abs": err}
    for group in ("adapter", "merged"):
        desc = ct.utils.MultiFunctionDescriptor()
        for i in (1, 2):
            desc.add_function(str(out / f"{group}_{i}.mlpackage"), "main", f"adapter_{i}")
        desc.default_function_name = "adapter_1"
        path = out / f"multifunction_{group}.mlpackage"
        ct.utils.save_multifunction(desc, str(path))
        for i in (1, 2):
            name = f"adapter_{i}"
            spec, weights, details = saved_function(path, name)
            info[f"multifunction_{group}/{name}"] = details
            actual = np.concatenate([mil(spec, {"x": row[None]}, weights)["y"] for row in test_x])
            err = float(np.max(np.abs(actual - refs[name])))
            assert err < 3e-5
            comparisons[f"multifunction_{group}/{name}"] = {"saved_mil_numpy_vs_numpy64_max_abs": err}
    # An adapter with the same dimensions does not define/restore its base.
    wrong = {k: v.copy() for k, v in base_arrays.items()}
    wrong["linear1.weight"] += 0.125
    wrong_delta = float(np.max(np.abs(reference(test_x, wrong, adapters["adapter_1"]) - refs["adapter_1"])))
    assert wrong_delta > 0.1
    try:
        packages["adapter_1"].predict({"x": test_x[1:2]})
    except Exception as exc:
        predict = {"status": "unavailable", "exception_type": type(exc).__name__, "message": str(exc)}
    else:
        raise AssertionError("Unexpected Core ML runtime on this Linux lab")
    sizes = {p.name: sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
             for p in out.glob("*.mlpackage")}
    weight_sizes = {p.name: sum(f.stat().st_size for f in p.rglob("weight.bin"))
                    for p in out.glob("*.mlpackage")}
    report = {"purpose": "synthetic LoRA/PEFT conversion; not AFM execution", "platform": platform.platform(),
        "python": sys.version, "versions": {k: importlib.metadata.version(k) for k in
            ("torch", "peft", "coremltools", "numpy", "transformers", "protobuf", "safetensors")},
        "seed": 20261026, "base_shapes": {k: list(v.shape) for k, v in base_arrays.items()},
        "training": training, "comparisons": comparisons, "packages": info,
        "package_bytes": sizes, "weight_blob_bytes": weight_sizes,
        "wrong_base_output_delta_max_abs": wrong_delta, "apple_coreml_predict": predict,
        "peft_switching": {"adapter_2_vs_reference_max_abs": float(np.max(np.abs(switched - refs["adapter_2"]))),
            "disabled_vs_base_max_abs": float(np.max(np.abs(disabled - refs["base"]))),
            "trace_remains_adapter_1_max_abs": float(np.max(np.abs(traced_after_switch - refs["adapter_1"]))),
            "trace_vs_active_adapter_2_max_abs": float(np.max(np.abs(traced_after_switch - switched)))},
        "apple_runtime_parity_verified": False, "afm_weights_acquired": False,
        "coreml_inference_on_linux": False, "heldout_inputs": 12}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    hashes = [{"path": str(p.relative_to(out)), "size": p.stat().st_size,
               "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in sorted(out.rglob("*")) if p.is_file()]
    (out / "SHA256.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "comparisons": comparisons, "package_bytes": sizes,
                      "apple_coreml_predict": predict}, indent=2))


if __name__ == "__main__":
    main()
