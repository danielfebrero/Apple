"""Acquisition preflight checks using the published real EntitySimilarity records."""

import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("firmware_acquire", BASE / "models/acquire.py")
acquire = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acquire)
MODEL_ID = "m-39ce2e705a2d140eee12"


class AcquirePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        manifest = json.loads((BASE / "models/manifest.json").read_text())
        self.model = next(m for m in manifest["models"] if m["id"] == MODEL_ID)
        self.assets = [json.loads(line) for line in (BASE / "models/assets.jsonl").read_text().splitlines()
                       if json.loads(line)["model_id"] == MODEL_ID]
        self.manifest_path = self.root / "manifest.json"
        self.assets_path = self.root / "assets.jsonl"
        self.write_metadata()
        self.args = acquire.parser().parse_args([
            "--firmware-root", str(self.root / "not-present-firmware"), "--model", MODEL_ID,
            "--manifest", str(self.manifest_path), "--assets", str(self.assets_path),
            "--summary", str(BASE / "models/summary.json"),
            "--cache-root", str(self.root / "out/models/cache"), "--dry-run",
        ])

    def write_metadata(self):
        self.manifest_path.write_text(json.dumps({"schema_version": 1, "models": [self.model]}))
        self.assets_path.write_text("\n".join(json.dumps(a) for a in self.assets) + "\n")

    def test_dry_run_neither_extracts_nor_claims_verification(self):
        result = acquire.acquire(self.args)
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["integrity_verified"])
        self.assertFalse(result["extraction_performed"])
        self.assertFalse(result["private_inventory_used"])
        self.assertEqual(result["file_count"], 8)
        self.assertEqual(result["runtime_source_root"], str(self.root / "out"))
        self.assertFalse(self.args.cache_root.exists())
        self.assertFalse(result["images"][0]["integrity_verified"])

    def test_path_traversal_in_manifest_rejected_before_writes(self):
        self.model["files"][0]["path"] = "../outside.bin"
        self.write_metadata()
        with self.assertRaises(acquire.AcquisitionError) as caught:
            acquire.acquire(self.args)
        self.assertEqual(caught.exception.code, "unsafe_path")
        self.assertFalse(self.args.cache_root.exists())

    def test_manifest_destination_must_match_asset_firmware_path(self):
        self.model["source_path"] = "models/cache/rootfs/some-other-bundle"
        self.write_metadata()
        with self.assertRaises(acquire.AcquisitionError) as caught:
            acquire.acquire(self.args)
        self.assertEqual(caught.exception.code, "invalid_metadata")

    def test_manifest_asset_hash_disagreement_rejected(self):
        self.model["files"][0]["sha256"] = "0" * 64
        self.write_metadata()
        with self.assertRaises(acquire.AcquisitionError) as caught:
            acquire.acquire(self.args)
        self.assertEqual(caught.exception.code, "invalid_metadata")

    def test_symlink_cache_ancestor_rejected(self):
        (self.root / "elsewhere").mkdir()
        (self.root / "out").symlink_to(self.root / "elsewhere", target_is_directory=True)
        with self.assertRaises(acquire.AcquisitionError) as caught:
            acquire.acquire(self.args)
        self.assertEqual(caught.exception.code, "unsafe_path")

    def test_zero_byte_stub_image_rejected_before_reader_and_cache_write(self):
        self.args.dry_run = False
        (self.args.firmware_root / "rootfs-dec").mkdir(parents=True)
        (self.args.firmware_root / "rootfs-dec/141-08876-212.dmg").write_bytes(b"")
        with self.assertRaises(acquire.AcquisitionError) as caught:
            acquire.acquire(self.args)
        self.assertEqual(caught.exception.code, "image_integrity_mismatch")
        self.assertFalse(self.args.cache_root.exists())


if __name__ == "__main__":
    unittest.main()
