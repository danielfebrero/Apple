import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "models/download_asset.py"
spec = importlib.util.spec_from_file_location("download_asset", SCRIPT)
download_asset = importlib.util.module_from_spec(spec); spec.loader.exec_module(download_asset)


class DownloadTests(unittest.TestCase):
    def test_verified_bytes_published_only_after_complete_digest(self):
        raw = b"test-payload"
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "asset.zip"
            with patch.object(download_asset, "open_url", return_value=io.BytesIO(raw)):
                r = download_asset.download("https://mesu.apple.com/test", hashlib.sha256(raw).hexdigest(), len(raw), dest)
            self.assertEqual(dest.read_bytes(), raw)
            self.assertEqual(r["status"], "downloaded_verified")
            self.assertFalse(r["apple_signature_verified"])
            self.assertEqual(list(Path(d).iterdir()), [dest])

    def test_wrong_hash_or_size_leaves_no_destination_or_partial(self):
        for raw, size, expected in ((b"abc", 4, hashlib.sha256(b"abc").hexdigest()),
                                    (b"abc", 2, hashlib.sha256(b"abc").hexdigest()),
                                    (b"abc", 3, "0" * 64)):
            with self.subTest(size=size, expected=expected), tempfile.TemporaryDirectory() as d:
                with patch.object(download_asset, "open_url", return_value=io.BytesIO(raw)):
                    with self.assertRaises(ValueError):
                        download_asset.download("https://mesu.apple.com/test", expected, size, Path(d) / "payload")
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_existing_artifact_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "payload"; dest.write_bytes(b"existing")
            with patch.object(download_asset, "open_url") as transport:
                with self.assertRaises(ValueError): download_asset.download("https://mesu.apple.com/test", "0" * 64, 10, dest)
                transport.assert_not_called()
            self.assertEqual(dest.read_bytes(), b"existing")

    def test_https_apple_domain_and_redacted_query(self):
        for url in ("http://mesu.apple.com/test", "https://apple.com.attacker.test/a",
                    "https://apple.com@attacker.test/a", "https://u:p@mesu.apple.com/a"):
            with self.assertRaises(ValueError): download_asset.apple_url(url)
        self.assertEqual(download_asset.public_url("https://updates.cdn-apple.com/a?signature=sensitive"),
                         "https://updates.cdn-apple.com/a")
        self.assertEqual(download_asset.apple_url("https://updates.cdn-apple.com/a"), "https://updates.cdn-apple.com/a")
