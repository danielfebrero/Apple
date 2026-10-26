"""Offline checks for MobileAsset acquisition and the observed AA/PBZX subset.

Synthetic data tests parser and integrity handling; it is never evidence of
Apple model ownership, archive authenticity, completeness, or image inference.
"""
import base64
import hashlib
import importlib.util
import io
import json
import lzma
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch


MODELS = Path(__file__).resolve().parents[2] / "models"


def load(name):
    spec = importlib.util.spec_from_file_location(name, MODELS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Register the sibling modules without changing sys.path for other test suites.
download = load("download_asset")
pallas = load("pallas_catalog")
acquire = load("acquire_mobileasset")
archive = load("unpack_apple_archive")


def jwt(document, header=None):
    def b64(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=")
    return b".".join((b64(header if header is not None else {"alg": "ES256"}),
                       b64(document), b"unverified-signature"))


class Response(io.BytesIO):
    code = 200
    headers = {"Content-Type": "application/jose", "Set-Cookie": "never-publish"}


def field(key, subtype, value):
    prefix = key.encode("ascii") + subtype.encode("ascii")
    if subtype == "P":
        raw = value.encode("utf-8")
        return prefix + struct.pack("<H", len(raw)) + raw
    if subtype in "1248ABC":
        size = {"A": 2, "B": 4, "C": 8}.get(subtype, int(subtype) if subtype.isdigit() else 0)
        return prefix + value.to_bytes(size, "little")
    if subtype == "H":
        return prefix + value
    raise AssertionError(subtype)


def entry(typ="F", path="nested/file.bin", data=b"payload", digest=None, extra=b""):
    fields = field("TYP", "1", ord(typ))
    if path is not None:
        fields += field("PAT", "P", path)
    if digest is not None:
        fields += field("SH2", "H", digest)
    fields += extra
    payload = b""
    if data is not None:
        fields += field("DAT", "B", len(data))
        payload = data
    return b"AA01" + struct.pack("<H", 6 + len(fields)) + fields + payload


def pbzx(raw, compressed=False, block=None):
    packed = lzma.compress(raw) if compressed else raw
    return b"pbzx" + struct.pack(">QQQ", block or max(len(raw), 1), len(raw), len(packed)) + packed


class CatalogueTests(unittest.TestCase):
    def test_json_and_jwt_decode_are_explicitly_unverified(self):
        document = {"Assets": [{"AssetSpecifier": "test"}]}
        for raw, encoding in ((json.dumps(document).encode(), "json"), (jwt(document), "jwt")):
            with self.subTest(encoding=encoding):
                result = pallas.decode_response(raw)
                self.assertEqual(result["document"], document)
                self.assertEqual(result["encoding"], encoding)
                self.assertFalse(result["signature_verified"])

    def test_invalid_catalogues_rejected(self):
        bad = (b"", b"[]", b"{} trailing", b"a.b", b"not-json.payload.signature", b"e30!.e30.signature",
               jwt([]), jwt({}, header=[]))
        for raw in bad:
            with self.subTest(raw=raw):
                with self.assertRaises((ValueError, UnicodeError)):
                    pallas.decode_response(raw)

    def test_decode_bound_applies_outside_network_query(self):
        with patch.object(pallas, "LIMIT", 4), self.assertRaises(ValueError):
            pallas.decode_response(b'{"Assets": []}')

    def test_assets_must_be_an_array_of_objects_when_present(self):
        for assets in (None, 1, "invalid", {}, [None], ["invalid"]):
            for encode in (lambda doc: json.dumps(doc).encode(), jwt):
                with self.subTest(assets=assets, encode=encode), self.assertRaises(ValueError):
                    pallas.decode_response(encode({"Assets": assets}))

    def test_query_records_hash_redacts_keys_and_does_not_publish_cookie(self):
        raw = jwt({"Assets": [{"ArchiveDecryptionKey": "secret",
                               "nested": [{"ArchiveDecryptionKey": "also-secret"}]}]})
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(pallas.urllib.request, "urlopen", return_value=Response(raw)) as transport:
                report = pallas.query({"AssetType": "test"}, root, "catalogue", raw_output=root)
            self.assertEqual(report["status"], "catalogue_received")
            self.assertEqual(report["response_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(report["assets_count"], 1)
            self.assertEqual((root / "catalogue.response").read_bytes(), raw)
            self.assertNotIn("secret", (root / "catalogue.json").read_text())
            self.assertNotIn("Set-Cookie", report["headers"])
            self.assertFalse(report["signature_verified"])
            self.assertFalse(report["payload_acquired"])
            self.assertTrue(report["tls_verified"])
            self.assertIsNotNone(transport.call_args.kwargs["context"])

    def test_query_bound_and_existing_evidence_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(pallas, "LIMIT", 8), patch.object(
                    pallas.urllib.request, "urlopen", return_value=Response(b"x" * 9)):
                report = pallas.query({}, root, "oversize")
            self.assertEqual(report["status"], "transport_error")
            self.assertFalse(report["tls_verified"])
            self.assertTrue(report["tls_verification_enabled"])
            prior = (root / "oversize.json").read_bytes()
            with patch.object(pallas.urllib.request, "urlopen") as transport:
                with self.assertRaises(ValueError):
                    pallas.query({}, root, "oversize")
                transport.assert_not_called()
            self.assertEqual((root / "oversize.json").read_bytes(), prior)

    def test_invalid_evidence_names_and_endpoints_rejected_before_transport(self):
        with tempfile.TemporaryDirectory() as d, patch.object(pallas.urllib.request, "urlopen") as transport:
            for name in ("../escape", "/absolute", "", "name.json"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    pallas.query({}, Path(d), name)
            with self.assertRaises(ValueError):
                pallas.query({}, Path(d), "valid", endpoint="https://example.test/")
            transport.assert_not_called()


class AcquisitionTests(unittest.TestCase):
    def asset(self, raw=b"model-payload", algorithm="SHA-1"):
        h = hashlib.new({"SHA-1": "sha1", "SHA-256": "sha256"}[algorithm], raw).digest()
        return {"__BaseURL": "https://updates.cdn-apple.com/assets/", "__RelativePath": "test/payload.aea",
                "_DownloadSize": len(raw), "_MeasurementAlgorithm": algorithm,
                "_Measurement": base64.b64encode(h).decode(), "AssetSpecifier": "synthetic"}

    def test_sha1_and_sha256_measurements_verified_with_separate_sha256(self):
        raw = b"model-payload"
        for algorithm in ("SHA-1", "SHA-256"):
            with self.subTest(algorithm=algorithm), tempfile.TemporaryDirectory() as d:
                with patch.object(acquire, "open_url", return_value=io.BytesIO(raw)):
                    report = acquire.acquire(self.asset(raw, algorithm), Path(d))
                self.assertEqual((Path(d) / "payload.aea").read_bytes(), raw)
                self.assertEqual(report["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(report["catalogue_measurement_algorithm"], algorithm)
                self.assertTrue(report["catalogue_measurement_verified"])
                self.assertFalse(report["plaintext_weights_verified"])
                self.assertFalse(report["image_inference_performed"])
                self.assertEqual(report["status"], "downloaded_verified")

    def test_hash_or_size_mismatch_publishes_no_file_or_partial(self):
        original = b"model-payload"
        for raw in (b"different!!!", original[:-1], original + b"x"):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as d:
                with patch.object(acquire, "open_url", return_value=io.BytesIO(raw)):
                    with self.assertRaises(ValueError):
                        acquire.acquire(self.asset(original), Path(d))
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_invalid_measurements_and_external_hosts_rejected(self):
        changes = ({"_Measurement": "!invalid-base64!"}, {"_Measurement": "YQ=="},
                   {"_MeasurementAlgorithm": "MD5"}, {"_DownloadSize": 0},
                   {"_DownloadSize": -1}, {"_DownloadSize": "13"},
                   {"__RelativePath": "https://attacker.test/payload"})
        with tempfile.TemporaryDirectory() as d, patch.object(acquire, "open_url") as transport:
            for change in changes:
                with self.subTest(change=change), self.assertRaises(ValueError):
                    acquire.acquire(dict(self.asset(), **change), Path(d))
            transport.assert_not_called()

    def test_existing_good_file_rehashed_without_network_or_replacement(self):
        raw = b"model-payload"
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "payload.aea"
            dest.write_bytes(raw)
            prior_inode = dest.stat().st_ino
            with patch.object(acquire, "open_url") as transport:
                report = acquire.acquire(self.asset(raw), Path(d))
                transport.assert_not_called()
            self.assertEqual(report["status"], "reused_verified")
            self.assertEqual(dest.stat().st_ino, prior_inode)
            self.assertEqual(list(Path(d).iterdir()), [dest])

    def test_existing_wrong_file_preserved_and_no_network(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "payload.aea"
            dest.write_bytes(b"wrong")
            with patch.object(acquire, "open_url") as transport:
                with self.assertRaises(ValueError):
                    acquire.acquire(self.asset(), Path(d))
                transport.assert_not_called()
            self.assertEqual(dest.read_bytes(), b"wrong")
            self.assertEqual(list(Path(d).iterdir()), [dest])

    def test_destination_created_during_download_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            destination = root / "payload.aea"

            def transport(_):
                destination.write_bytes(b"concurrent-artifact")
                return io.BytesIO(b"model-payload")

            with patch.object(acquire, "open_url", side_effect=transport):
                with self.assertRaises(FileExistsError):
                    acquire.acquire(self.asset(), root)
            self.assertEqual(destination.read_bytes(), b"concurrent-artifact")
            self.assertEqual(list(root.iterdir()), [destination])

    def test_reused_destination_removed_concurrently_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            destination = root / "payload.aea"
            destination.write_bytes(b"model-payload")
            make_temp = acquire.tempfile.mkstemp

            def remove_prior(**kwargs):
                destination.unlink()
                return make_temp(**kwargs)

            with patch.object(acquire.tempfile, "mkstemp", side_effect=remove_prior), patch.object(
                    acquire, "open_url", return_value=io.BytesIO(b"model-payload")) as transport:
                with self.assertRaises(FileNotFoundError):
                    acquire.acquire(self.asset(), root)
                transport.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])

    def test_final_symlink_refused_without_reading_or_network(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            outside = root / "outside"
            outside.write_bytes(b"preserve")
            (root / "payload.aea").symlink_to(outside)
            with patch.object(acquire, "open_url") as transport:
                with self.assertRaises(ValueError):
                    acquire.acquire(self.asset(), root)
                transport.assert_not_called()
            self.assertEqual(outside.read_bytes(), b"preserve")

    def test_destination_symlink_and_symlink_ancestor_refused(self):
        for via_ancestor in (False, True):
            with self.subTest(via_ancestor=via_ancestor), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                outside = root / "outside"
                outside.mkdir()
                link = root / "linked"
                link.symlink_to(outside, target_is_directory=True)
                destination = link / "child" if via_ancestor else link
                with patch.object(acquire, "open_url", return_value=io.BytesIO(b"model-payload")) as transport:
                    with self.assertRaises(ValueError):
                        acquire.acquire(self.asset(), destination)
                    transport.assert_not_called()
                self.assertEqual(list(outside.iterdir()), [])


class AppleArchiveTests(unittest.TestCase):
    def unpack(self, raw, root):
        records = []
        archive.unpack(raw, root, records)
        return records

    def test_file_sha256_is_verified_and_false_inference_claims_avoided(self):
        raw = b"real-bytes-but-synthetic-test"
        with tempfile.TemporaryDirectory() as d:
            records = self.unpack(entry(data=raw, digest=hashlib.sha256(raw).digest()), Path(d))
            self.assertEqual((Path(d) / "nested/file.bin").read_bytes(), raw)
            self.assertEqual(records[0]["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertTrue(records[0]["archive_sha256_verified"])
            self.assertFalse(records[0]["yec_verified"])

    def test_file_without_sh2_is_hashed_but_not_archive_verified(self):
        with tempfile.TemporaryDirectory() as d:
            records = self.unpack(entry(), Path(d))
            self.assertFalse(records[0]["archive_sha256_verified"])
            self.assertEqual(records[0]["sha256"], hashlib.sha256(b"payload").hexdigest())

    def test_sha256_mismatch_prevents_file_creation(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                self.unpack(entry(digest=b"\0" * 32), Path(d))
            self.assertFalse((Path(d) / "nested/file.bin").exists())

    def test_nested_yop_e_pbzx_raw_and_xz(self):
        inner = entry(data=b"a" * 1024, digest=hashlib.sha256(b"a" * 1024).digest())
        for compressed in (False, True):
            raw = entry("M", path=None, data=pbzx(inner, compressed), extra=field("YOP", "1", ord("E")))
            with self.subTest(compressed=compressed), tempfile.TemporaryDirectory() as d:
                records = self.unpack(raw, Path(d))
                self.assertEqual(records[0]["depth"], 1)
                self.assertTrue(records[0]["archive_sha256_verified"])
                self.assertEqual((Path(d) / "nested/file.bin").read_bytes(), b"a" * 1024)

    def test_yop_o_pbzx_trailer_sha256_is_verified_but_yec_is_not(self):
        inner = entry(data=None, digest=hashlib.sha256(b"payload").digest())
        trailer = entry("M", path=None, data=pbzx(inner), extra=field("YOP", "1", ord("O")))
        with tempfile.TemporaryDirectory() as d:
            records = self.unpack(entry() + trailer, Path(d))
            self.assertTrue(records[0]["archive_sha256_verified"])
            self.assertFalse(records[0]["yec_verified"])

    def test_yop_o_bad_digest_or_unmatched_path_rejected(self):
        for path, digest in (("nested/file.bin", b"\0" * 32),
                             ("missing", hashlib.sha256(b"payload").digest())):
            inner = entry(path=path, data=None, digest=digest)
            trailer = entry("M", path=None, data=pbzx(inner), extra=field("YOP", "1", ord("O")))
            with self.subTest(path=path), tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(ValueError, "trailer SHA-256 mismatch"):
                    self.unpack(entry() + trailer, Path(d))

    def test_unknown_metadata_operation_rejected_and_m_metadata_allowed(self):
        for operation in ("X", "\0"):
            raw = entry("M", path=None, data=None, extra=field("YOP", "1", ord(operation)))
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(ValueError, "Unsupported AA metadata operation"):
                    self.unpack(raw, Path(d))
        metadata = entry("M", path=None, data=None, extra=field("YOP", "1", ord("M")))
        with tempfile.TemporaryDirectory() as d:
            records = self.unpack(metadata + entry(), Path(d))
            self.assertEqual(len(records), 1)
            self.assertEqual((Path(d) / "nested/file.bin").read_bytes(), b"payload")

    def test_traversal_absolute_and_backslash_paths_rejected(self):
        for path in ("../outside", "a/../../outside", "/absolute", "a\\escape", "a\0b"):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ValueError):
                    self.unpack(entry(path=path), Path(d))
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_existing_file_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "nested").mkdir()
            (root / "nested/file.bin").write_bytes(b"preserve")
            with self.assertRaises(FileExistsError):
                self.unpack(entry(), root)
            self.assertEqual((root / "nested/file.bin").read_bytes(), b"preserve")

    def test_symlink_destination_and_ancestors_refused(self):
        for symlink_name in ("nested", "nested/file.bin"):
            with self.subTest(symlink_name=symlink_name), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                outside = root / "outside"
                outside.mkdir()
                output = root / "output"
                output.mkdir()
                link = output / symlink_name
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(outside, target_is_directory=True)
                with self.assertRaises(ValueError):
                    self.unpack(entry(), output)
                self.assertEqual(list(outside.iterdir()), [])

    def test_truncated_duplicate_unsupported_and_oversize_fields_rejected(self):
        valid = entry()
        bad = (b"bad", valid[:5], valid[:7], valid[:-1],
               entry(extra=field("TYP", "1", ord("F"))),
               entry(extra=b"BADZ"),
               b"AA01" + struct.pack("<H", 10) + b"TYP8")
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)):
                list(archive.entries(raw))
        with patch.object(archive, "MAX", 2), self.assertRaises(ValueError):
            list(archive.entries(entry(data=b"123")))

    def test_pbzx_truncation_chunk_bounds_length_mismatch_and_output_bound(self):
        bad = (b"pbzx", b"wrong" + b"\0" * 20,
               b"pbzx" + struct.pack(">Q", 0),
               b"pbzx" + struct.pack(">Q", 65 * 1024**2),
               b"pbzx" + struct.pack(">Q", 8) + b"\0",
               b"pbzx" + struct.pack(">QQQ", 8, 9, 0),
               b"pbzx" + struct.pack(">QQQ", 8, 8, 17),
               pbzx(b"12345678")[:-1],
               b"pbzx" + struct.pack(">QQQ", 1024, 1, len(lzma.compress(b"longer"))) + lzma.compress(b"longer"))
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                archive.pbzx(raw)
        with patch.object(archive, "MAX", 4), self.assertRaisesRegex(ValueError, "output bound"):
            archive.pbzx(pbzx(b"12345"))

    def test_nesting_bound(self):
        raw = entry()
        for _ in range(6):
            raw = entry("M", path=None, data=pbzx(raw), extra=field("YOP", "1", ord("E")))
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(ValueError, "Nested archive bound"):
            self.unpack(raw, Path(d))


if __name__ == "__main__":
    unittest.main()
