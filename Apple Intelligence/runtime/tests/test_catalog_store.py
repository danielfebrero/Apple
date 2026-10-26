"""Integrity and input-validation tests use tiny local byte fixtures, never mock inference."""

import hashlib
import json
from pathlib import Path
import platform
import shutil
import tempfile
import unittest

from apple_firmware_runtime.catalog import Catalog, RuntimeFailure
from apple_firmware_runtime.store import Store, verify_bundle
from apple_firmware_runtime.backends import coreml, coreml_runner, entrypoint, static_inspection
from apple_firmware_runtime.cli import main


class CatalogStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "weights.bin").write_bytes(b"exact asset bytes\x00\xff")
        (self.source / "metadata.json").write_text('{"input": "declared data only"}')
        files = []
        for path in sorted(self.source.iterdir()):
            raw = path.read_bytes()
            files.append({"path": path.name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        self.declaration = {"id": "m-fixture", "label": "Integrity fixture", "source_path": "source", "files": files,
                            "format": "opaque_weights", "firmware_path": "/fixture/weights.bin"}
        self.catalog_path = self.root / "manifest.json"
        self.write_catalog()
        self.catalog = Catalog(self.catalog_path, self.root)
        self.model = self.catalog.get("m-fixture")
        self.store = Store(self.root / "store")

    def write_catalog(self):
        self.catalog_path.write_text(json.dumps({"schema_version": 1, "models": [self.declaration]}))

    def test_import_and_verify_all_bytes_and_separate_cas_inode(self):
        report = self.store.import_model(self.model)
        self.assertTrue(report["verified"])
        self.assertEqual(report["files"], 2)
        path = self.store.bundle(self.model) / "weights.bin"
        file = next(f for f in self.model.files if f["path"] == "weights.bin")
        blob = self.store.root / "blobs/sha256" / file["sha256"][:2] / file["sha256"]
        self.assertEqual(path.read_bytes(), blob.read_bytes())
        self.assertNotEqual(path.stat().st_ino, blob.stat().st_ino)

    def test_truncated_source_is_rejected_before_bundle_is_exposed(self):
        (self.source / "weights.bin").write_bytes(b"")
        with self.assertRaises(RuntimeFailure) as caught:
            self.store.import_model(self.model)
        self.assertEqual(caught.exception.code, "integrity_mismatch")
        self.assertFalse(self.store.bundle(self.model).exists())

    def test_same_size_corruption_is_rejected_and_reimport_repairs_working_copy(self):
        self.store.import_model(self.model)
        target = self.store.bundle(self.model) / "weights.bin"
        original = target.read_bytes()
        target.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        with self.assertRaises(RuntimeFailure) as caught:
            self.store.verify(self.model)
        self.assertEqual(caught.exception.code, "integrity_mismatch")
        self.store.import_model(self.model)
        self.assertEqual(target.read_bytes(), original)

    def test_extra_imported_file_is_rejected(self):
        self.store.import_model(self.model)
        (self.store.bundle(self.model) / "undeclared.bin").write_bytes(b"unknown")
        with self.assertRaises(RuntimeFailure) as caught:
            self.store.verify(self.model)
        self.assertEqual(caught.exception.code, "unexpected_files")

    def test_symlink_source_rejected_even_if_content_hash_matches(self):
        target = self.root / "outside.bin"
        shutil.move(self.source / "weights.bin", target)
        (self.source / "weights.bin").symlink_to(target)
        with self.assertRaises(RuntimeFailure) as caught:
            verify_bundle(self.model, self.source)
        self.assertEqual(caught.exception.code, "unsafe_file")

    def test_changed_catalogue_requires_reimport(self):
        self.store.import_model(self.model)
        self.declaration["function"] = "Additional reviewed metadata"
        self.write_catalog()
        revised = Catalog(self.catalog_path, self.root).get(self.model.id)
        with self.assertRaises(RuntimeFailure) as caught:
            self.store.verify(revised)
        self.assertEqual(caught.exception.code, "manifest_changed")

    def test_invalid_paths_and_hashes_rejected_before_access(self):
        mutations = ["../escape", "/absolute", "a/../../escape", "a\\escape", "a//b", "./file"]
        for path in mutations:
            with self.subTest(path=path):
                self.declaration["files"][0]["path"] = path
                self.write_catalog()
                with self.assertRaises(RuntimeFailure):
                    Catalog(self.catalog_path, self.root)
        self.declaration["files"][0]["path"] = "safe"
        self.declaration["files"][0]["sha256"] = "0" * 63 + "G"
        self.write_catalog()
        with self.assertRaises(RuntimeFailure):
            Catalog(self.catalog_path, self.root)

    def test_boolean_file_size_is_not_accepted_as_integer(self):
        self.declaration["files"][0]["size"] = True
        self.write_catalog()
        with self.assertRaises(RuntimeFailure):
            Catalog(self.catalog_path, self.root)

    def test_duplicate_file_paths_and_ids_are_rejected(self):
        self.declaration["files"].append(self.declaration["files"][0].copy())
        self.write_catalog()
        with self.assertRaises(RuntimeFailure):
            Catalog(self.catalog_path, self.root)
        self.declaration["files"].pop()
        self.catalog_path.write_text(json.dumps({"schema_version": 1, "models": [self.declaration, self.declaration]}))
        with self.assertRaises(RuntimeFailure):
            Catalog(self.catalog_path, self.root)

    def test_resource_cannot_be_misrepresented_as_coreml_entrypoint(self):
        with self.assertRaises(RuntimeFailure) as caught:
            entrypoint(self.model, self.source)
        self.assertEqual(caught.exception.code, "unsupported_format")

    def test_package_without_filename_suffix_keeps_complete_package_entrypoint(self):
        # Real inventory includes packages named TTE_Model without a .mlpackage suffix.
        self.declaration["format"] = "coreml_package"
        self.declaration["firmware_path"] = "/fixture/TTE_Model"
        self.declaration["files"][0]["path"] = "Data/com.apple.CoreML/model.mlmodel"
        self.write_catalog()
        package = Catalog(self.catalog_path, self.root).get(self.model.id)
        bundle = self.store.bundle(package)
        self.assertEqual(bundle.suffix, ".mlpackage")
        self.assertEqual(entrypoint(package, bundle), bundle)

    def test_static_inspection_is_explicitly_not_prediction(self):
        result = static_inspection(self.model, self.source)
        self.assertFalse(result["prediction_performed"])
        self.assertEqual(result["resources"][0]["content"], {"input": "declared data only"})
        self.assertFalse(result["portable_backend"]["supported"])

    @unittest.skipIf(platform.system() == "Darwin", "Linux/unavailable-host assertion")
    def test_coreml_cannot_report_success_on_linux(self):
        with self.assertRaises(RuntimeFailure) as caught:
            coreml(self.model, self.source, self.store.root, inputs={})
        self.assertEqual(caught.exception.code, "backend_unavailable")
        self.assertIn(platform.system(), str(caught.exception))

    @unittest.skipUnless(platform.system() == "Darwin" and shutil.which("xcrun"), "Requires macOS Swift/CoreML SDK")
    def test_mac_backend_compiles_against_actual_public_sdk(self):
        runner = coreml_runner(self.store.root)
        self.assertTrue(runner.is_file())


if __name__ == "__main__":
    unittest.main()
