#!/usr/bin/env python3
"""Reproduce numeric demos of every uncompiled catalogue candidate, with honest failures."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apple_firmware_runtime.catalog import Catalog, RuntimeFailure
from apple_firmware_runtime.store import Store
from apple_firmware_runtime.backends import protobuf_cpu
from apple_firmware_runtime.protobuf_cpu import Model_pb2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parents[2] / "models/manifest.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=Path(__file__).resolve().parents[1] / ".state/cpu-demos")
    args = parser.parse_args()
    catalog = Catalog(args.catalog)
    args.state.mkdir(parents=True, exist_ok=True)
    store = Store(args.state / "store")
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "manifest_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
              "scope": "All coreml_protobuf and coreml_package groups (not compiled/opaque models)",
              "input_semantics": "Synthetic numeric zeros/ones in declared firmware feature spaces; no app preprocessing reconstructed",
              "apple_runtime_parity_verified": False, "models": []}
    for model in catalog.models.values():
        if model.declaration["format"] not in {"coreml_protobuf", "coreml_package"}: continue
        row = model.summary() | {"demos": []}
        report["models"].append(row)
        try:
            imported = store.import_model(model)
            integrity = store.verify(model)
            bundle = store.bundle(model)
            paths = [bundle / f["path"] for f in model.files if f["path"].endswith(".mlmodel")]
            if len(paths) != 1: raise ValueError("Ambiguous protobuf entrypoint")
            spec = Model_pb2.Model(); spec.ParseFromString(paths[0].read_bytes())
            row["model_type"] = spec.WhichOneof("Type")
            row["integrity"] = integrity
            for fill in (0, 1):
                inputs = {}; recipe = {}
                for f in spec.description.input:
                    kind = f.type.WhichOneof("Type")
                    if kind == "doubleType": inputs[f.name] = float(fill); recipe[f.name] = float(fill)
                    elif kind == "multiArrayType":
                        shape = list(f.type.multiArrayType.shape)
                        if not shape or math.prod(shape) > 10_000_000: raise ValueError("Unsupported demo input shape")
                        inputs[f.name] = {"shape": shape, "data": [fill] * math.prod(shape)}
                        recipe[f.name] = {"shape": shape, "fill": fill}
                    else: raise ValueError(f"Demo cannot build semantic input of type {kind}")
                path = args.state / f"{model.id}-{'zero' if fill == 0 else 'one'}.json"
                raw = json.dumps(inputs, allow_nan=False, separators=(",", ":")) + "\n"
                path.write_text(raw)
                result = protobuf_cpu(model, bundle, inputs)
                row["demos"].append({"input_recipe": recipe, "input_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                                     "input_file": str(path), "result": result})
            row["status"] = "executed"
        except (ValueError, RuntimeFailure, OSError) as exc:
            row["status"] = "partial" if row["demos"] else "unsupported"
            row["error"] = str(exc)
    report["counts"] = {s: sum(r["status"] == s for r in report["models"]) for s in ("executed", "partial", "unsupported")}
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps(report["counts"]))


if __name__ == "__main__": main()
