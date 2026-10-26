#!/usr/bin/env python3
"""Execute the controlled LoRA arithmetic in Apple's Linux Core AI runtime.

Hand-author an AIProgram from saved synthetic arrays; this is NOT a Core ML
converter, NOT an AFM adapter loader and NOT an inference on Apple weights.
The four LoRA matrices are normal tensor inputs so they can change per call.
"""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
from typing import Annotated

import numpy as np
from coreai.authoring import AIModelAsset, AIProgram, Module, TensorSpec
from coreai._compiler.dialects import coreai as ops
from coreai._compiler.ir import Value
from coreai.runtime import NDArray


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    base = dict(np.load(args.results / "base.npz", allow_pickle=False))
    adapters = dict(np.load(args.results / "adapters.npz", allow_pickle=False))
    vectors = dict(np.load(args.results / "vectors.npz", allow_pickle=False))
    asset_path = args.output / "controlled-dynamic-lora.aimodel"
    module = Module.create()
    with module:
        @ops.graph
        def main(
            x: Annotated[Value, TensorSpec(shape=[1, 64], dtype=np.float32)],
            a1: Annotated[Value, TensorSpec(shape=[64, 4], dtype=np.float32)],
            b1: Annotated[Value, TensorSpec(shape=[4, 48], dtype=np.float32)],
            a2: Annotated[Value, TensorSpec(shape=[48, 4], dtype=np.float32)],
            b2: Annotated[Value, TensorSpec(shape=[4, 16], dtype=np.float32)],
        ) -> Annotated[Value, TensorSpec(shape=[1, 16], dtype=np.float32, name="y")]:
            def layer(x, i, a, b):
                w = ops.constant(np.ascontiguousarray(base[f"linear{i}.weight"].T))
                bias = ops.constant(base[f"linear{i}.bias"][None])
                y = ops.add(ops.batch_matmul(x, w), bias)
                delta = ops.batch_matmul(ops.batch_matmul(x, a), b)
                scale = ops.constant(np.full((1, base[f"linear{i}.bias"].size), 2, np.float32))
                return ops.add(y, ops.mul(delta, scale))
            h = ops.relu(layer(x, 1, a1, b1))
            return layer(h, 2, a2, b2)
    AIProgram(module).save_asset(asset_path)
    asset = AIModelAsset.load(asset_path)
    errors, outputs = {}, {}
    async with asset.executable() as model:
        function = model.load_function("main")
        for name in ("base", "adapter_1", "adapter_2"):
            params = {k: np.zeros(shape, np.float32) if name == "base" else
                      np.ascontiguousarray(adapters[f"{name}_{k}"].T)
                      for k, shape in (("a1", (64, 4)), ("b1", (4, 48)),
                                       ("a2", (48, 4)), ("b2", (4, 16)))}
            rows = []
            for row in vectors["inputs"]:
                inputs = {"x": NDArray(np.ascontiguousarray(row[None]))}
                inputs.update({k: NDArray(v) for k, v in params.items()})
                rows.append((await function(inputs))["y"].numpy().copy())
            actual = np.concatenate(rows)
            expected = vectors[name]
            err = float(np.max(np.abs(actual - expected)))
            assert err < 3e-5, (name, err)
            errors[name] = err
            outputs[name] = actual
    np.savez(args.output / "native-outputs.npz", **outputs)
    files = [{"path": str(p.relative_to(asset_path)), "size": p.stat().st_size,
              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(asset_path.rglob("*")) if p.is_file()]
    # Integrate via the existing verified catalogue/store/CLI, without widening
    # the firmware catalogue or its supported formats.
    catalogue = {"schema_version": 1, "models": [{
        "id": "controlled-dynamic-lora", "label": "Controlled synthetic dynamic LoRA", "scope": "demonstration",
        "format": "coreai_asset", "availability": "local_generated", "source_layout": "directory",
        "source_path": asset_path.name, "entrypoint": "main", "files": files,
    }]}
    (args.output / "manifest.json").write_text(json.dumps(catalogue, indent=2) + "\n")
    cli_input = {"x": vectors["inputs"][1:2].tolist()}
    cli_input.update({k: adapters[f"adapter_1_{k}"].T.tolist() for k in ("a1", "b1", "a2", "b2")})
    (args.output / "input.json").write_text(json.dumps(cli_input) + "\n")
    report = {"platform": platform.platform(), "python": sys.version,
        "versions": {k: importlib.metadata.version(k) for k in ("coreai-core", "numpy")},
        "scope": "synthetic trained LoRA arrays, hand-authored Core AI graph, ordinary dynamic tensor inputs",
        "heldout_inputs": len(vectors["inputs"]), "native_vs_independent_numpy64_max_abs": errors,
        "weights_embedded": "controlled base only", "adapter_matrix_orientation": "transposed from PEFT",
        "asset_files": files, "apple_coreai_native_inference": True,
        "apple_coreml_inference": False, "AFM_inference": False, "pretrained_apple_weights": False}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
