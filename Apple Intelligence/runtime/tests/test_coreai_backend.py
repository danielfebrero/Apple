"""Optional integration tests execute the genuine Apple Linux Core AI runtime."""

import hashlib
import importlib.util
import json
import platform
import tempfile
import unittest
from pathlib import Path
from typing import Annotated

from apple_firmware_runtime.backends import coreai_cpu
from apple_firmware_runtime.catalog import Catalog, RuntimeFailure
from apple_firmware_runtime.cli import parser, run
from apple_firmware_runtime.store import Store

AVAILABLE = (platform.system() == "Linux" and platform.machine().lower() in {"x86_64", "amd64"}
             and all(importlib.util.find_spec(name) for name in ("numpy", "coreai")))


@unittest.skipUnless(AVAILABLE, "Install optional Apple Linux dependencies: pip install '.[coreai]'")
class CoreAIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "tutorial.aimodel"
        self.create_graph(self.source)
        self.catalog_path = self.root / "manifest.json"
        self.model = self.catalogue(self.source)
        self.store = Store(self.root / "store")
        self.store.import_model(self.model)

    @staticmethod
    def create_graph(path, *, dtype="float32", shape=(2, 3), weights=None):
        import numpy as np
        from coreai.authoring import AIProgram, Module, TensorSpec
        from coreai._compiler.dialects import coreai as ops
        from coreai._compiler.ir import Value

        element_type = np.dtype(dtype)
        module = Module.create()
        with module:

            @ops.graph
            def main(
                x: Annotated[Value, TensorSpec(shape=list(shape), dtype=element_type)],
            ) -> Annotated[Value, TensorSpec(shape=list(shape), dtype=element_type, name="y")]:
                return ops.add(x, x if weights is None else weights)

        AIProgram(module).save_asset(path)

    def catalogue(self, source):
        files = []
        for path in sorted(source.rglob("*")):
            if path.is_file():
                raw = path.read_bytes()
                files.append({"path": path.relative_to(source).as_posix(), "size": len(raw),
                              "sha256": hashlib.sha256(raw).hexdigest()})
        declaration = {"id": "tutorial", "format": "coreai_asset", "source_path": source.name,
                       "scope": "demonstration", "files": files}
        self.catalog_path.write_text(json.dumps({"schema_version": 1, "models": [declaration]}))
        return Catalog(self.catalog_path, self.root).get("tutorial")

    def arguments(self, *extra):
        return parser().parse_args(["--catalog", str(self.catalog_path), "--source-root", str(self.root),
                                    "--store", str(self.store.root), *extra])

    def predict(self, values):
        inputs = self.root / "input.json"
        inputs.write_text(json.dumps(values))
        return run(self.arguments("predict", "tutorial", "--backend", "coreai-cpu", "--input", str(inputs)))

    def test_tutorial_executes_through_cli_store_and_actual_descriptors(self):
        self.assertEqual(self.store.bundle(self.model).suffix, ".aimodel")
        inspected = run(self.arguments("inspect", "tutorial", "--load", "--backend", "coreai-cpu"))
        self.assertFalse(inspected["prediction_performed"])
        self.assertEqual(inspected["input_schema"]["x"], {"dtype": "float32", "shape": [2, 3]})
        result = self.predict({"x": [[1.5, -2, 0], [0.25, 100, -0.125]]})
        self.assertTrue(result["prediction_performed"])
        self.assertTrue(result["integrity"]["verified"])
        self.assertEqual(result["artifact_identity"], "selected catalogue asset")
        self.assertEqual(result["outputs"]["y"], {"dtype": "float32", "shape": [2, 3],
                                                   "data": [[3.0, -4.0, 0.0], [0.5, 200.0, -0.25]]})
        # Compilation writes its derived ODIX into a temporary directory, leaving verified bytes intact.
        self.assertTrue(self.store.verify(self.model)["verified"])

    def test_flat_typed_tensor_is_checked_and_executed(self):
        result = self.predict({"x": {"dtype": "float32", "shape": [2, 3], "data": [1, 2, 3, 4, 5, 6]}})
        self.assertEqual(result["outputs"]["y"]["data"], [[2, 4, 6], [8, 10, 12]])

    def test_invalid_names_shapes_and_types_are_rejected(self):
        for values in ({"wrong": [[0] * 3] * 2}, {"x": [[0] * 6]},
                       {"x": [["1"] * 3] * 2}, {"x": [[True, 2, 3], [4, 5, 6]]},
                       {"x": [[float("nan"), 1, 2], [3, 4, 5]]},
                       {"x": {"shape": [2, 3], "dtype": "float64", "data": [0] * 6}},
                       {"x": {"shape": [True, 3], "data": [0] * 6}}):
            with self.subTest(values=values):
                with self.assertRaises(RuntimeFailure) as caught:
                    self.predict(values)
                self.assertEqual(caught.exception.code, "invalid_inputs")

    def test_corrupted_or_extra_imported_bytes_stop_prediction(self):
        target = self.store.bundle(self.model) / "main.mlirb"
        data = target.read_bytes()
        target.write_bytes(bytes([data[0] ^ 1]) + data[1:])
        with self.assertRaises(RuntimeFailure) as caught:
            self.predict({"x": [[0] * 3] * 2})
        self.assertEqual(caught.exception.code, "integrity_mismatch")
        self.store.import_model(self.model)
        (target.parent / "undeclared.weights").write_bytes(b"extra")
        with self.assertRaises(RuntimeFailure) as caught:
            self.predict({"x": [[0] * 3] * 2})
        self.assertEqual(caught.exception.code, "unexpected_files")

    def test_constant_resource_survives_save_import_and_runtime_compilation(self):
        import numpy as np
        weights = np.arange(2048, dtype=np.float32).reshape(1, 2048) / 32
        self.create_graph(self.source, shape=(1, 2048), weights=weights)
        self.model = self.catalogue(self.source)
        self.store.import_model(self.model)
        self.assertGreater((self.source / "main.mlirb").stat().st_size, weights.nbytes)
        result = self.predict({"x": np.full((1, 2048), 0.5).tolist()})
        np.testing.assert_array_equal(np.asarray(result["outputs"]["y"]["data"], dtype=np.float32), weights + 0.5)
        self.assertTrue(self.store.verify(self.model)["verified"])

    def test_integer_signature_does_not_silently_truncate_or_overflow(self):
        self.create_graph(self.source, dtype="int32")
        self.model = self.catalogue(self.source)
        self.store.import_model(self.model)
        for invalid in (0.5, 2**31):
            with self.assertRaises(RuntimeFailure) as caught:
                self.predict({"x": [[invalid] * 3] * 2})
            self.assertEqual(caught.exception.code, "invalid_inputs")
        result = self.predict({"x": [[-2, 0, 1], [2, 3, 4]]})
        self.assertEqual(result["outputs"]["y"]["dtype"], "int32")
        self.assertEqual(result["outputs"]["y"]["data"], [[-4, 0, 2], [4, 6, 8]])

    def test_non_cpu_compute_is_not_ignored(self):
        with self.assertRaises(RuntimeFailure) as caught:
            coreai_cpu(self.model, self.store.bundle(self.model), compute="all")
        self.assertEqual(caught.exception.code, "unsupported_compute")


if __name__ == "__main__":
    unittest.main()
