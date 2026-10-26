#!/usr/bin/env python3
"""Execute Apple's x+x tutorial through the verified catalogue/store CLI path."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import numpy as np
from coreai.authoring import AIProgram, Module, TensorSpec
from coreai._compiler.dialects import coreai as ops
from coreai._compiler.ir import Value

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apple_firmware_runtime.catalog import Catalog
from apple_firmware_runtime.cli import parser, run

SOURCE = "https://github.com/apple/coreai-torch/blob/main/docs/coreai-core/tutorials/run-an-aimodel.ipynb"


def create_tutorial_asset(path: Path) -> None:
    module = Module.create()
    with module:

        @ops.graph
        def main(
            x: Annotated[Value, TensorSpec(shape=[2, 3], dtype=np.float32)],
        ) -> Annotated[Value, TensorSpec(shape=[2, 3], dtype=np.float32, name="y")]:
            return ops.add(x, x)

    AIProgram(module).save_asset(path)


def main():
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("--state", type=Path, required=True, help="Dedicated demonstration output directory")
    arguments.add_argument("--output", type=Path, required=True, help="JSON execution evidence")
    args = arguments.parse_args()
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    asset = state / "apple-tutorial.aimodel"
    create_tutorial_asset(asset)
    files = []
    for path in sorted(asset.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            files.append({"path": path.relative_to(asset).as_posix(), "size": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()})
    declaration = {"id": "apple-coreai-tutorial-add", "label": "Apple tutorial: x+x (demonstration graph)",
                   "source_path": asset.name, "format": "coreai_asset", "entrypoint": "main",
                   "scope": "demonstration", "availability": "generated from official Apple tutorial",
                   "files": files, "evidence": {"source_url": SOURCE},
                   "limitations": "Not trained firmware weights, AFM, or a generative language model"}
    catalog = state / "manifest.json"
    catalog.write_text(json.dumps({"schema_version": 1, "models": [declaration]}, indent=2) + "\n")
    values = [[1.5, -2, 0], [0.25, 100, -0.125]]
    inputs = state / "input.json"
    inputs.write_text(json.dumps({"x": values}, allow_nan=False) + "\n")
    base = ["--catalog", str(catalog), "--source-root", str(state), "--store", str(state / "store")]
    imported = run(parser().parse_args(base + ["import", declaration["id"]]))
    inspected = run(parser().parse_args(base + ["inspect", declaration["id"], "--load", "--backend", "coreai-cpu"]))
    predicted = run(parser().parse_args(base + ["predict", declaration["id"], "--input", str(inputs), "--backend", "coreai-cpu"]))
    expected = np.asarray(values, dtype=np.float32) * 2
    actual = np.asarray(predicted["outputs"]["y"]["data"], dtype=np.float32)
    np.testing.assert_array_equal(actual, expected)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "source_url": SOURCE, "artifact_kind": "demonstration graph; no trained weights or AFM",
              "input": {"x": values}, "input_sha256": hashlib.sha256(inputs.read_bytes()).hexdigest(),
              "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
              "asset_files": files, "import": imported, "inspection": inspected, "prediction": predicted,
              "exact_equal_numpy": True, "output_array_sha256": hashlib.sha256(actual.tobytes()).hexdigest()}
    # The same model declaration was used for import, inspection and prediction.
    assert Catalog(catalog, state).get(declaration["id"]).fingerprint == predicted["manifest_fingerprint"]
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"executed": True, "backend": "coreai-cpu", "scope": "demonstration",
                      "output": predicted["outputs"], "evidence": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
