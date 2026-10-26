#!/usr/bin/env python3
"""Offline processing/audit of the selected, downloaded Visual archives.

Uses raw catalogues only in the ignored cache. Archive keys are never written
in reports. Existing outputs are verified and retained. No DSME decryption or
image inference is performed. Run from anywhere; paths resolve from this file.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "models"))
from pallas_catalog import decode_response
from unpack_apple_archive import unpack
from verify_catalogue_signature import verify_one, APPLE_ROOT_SHA256


def digest(path):
    with path.open("rb") as f: return hashlib.file_digest(f, "sha256").hexdigest()


def main():
    cache = ROOT / "models/cache/mobileasset-visual"
    source = cache / "catalogues/visual-rave.response"
    root_der = (HERE/"AppleRootCA-G3.cer").read_bytes()
    if hashlib.sha256(root_der).hexdigest() != APPLE_ROOT_SHA256: raise ValueError("Wrong signing trust anchor")
    validation_time = json.loads((HERE/"catalogue-signatures.json").read_text())["verification_unix_time"]
    signature = verify_one(source, root_der, (HERE/"AppleIncRootCertificate.cer").read_bytes(), validation_time)
    if not signature["signature_verified"]: raise ValueError("Unverified source catalogue")
    assets = decode_response(source.read_bytes())["document"]["Assets"]
    indices = sorted(set(json.loads((HERE/"selection.json").read_text())["indices"] + [4, 63]))
    initial = {r["catalogue_index"]:r for r in json.loads((HERE/"initial-downloads.json").read_text())["assets"]}
    known = {4:"rave-base-81616", 0:"rave-conditioning", 13:"rave-emoji", 63:"rave-metadata-4501"}
    rows = []; decrypt_logs = []
    for i in indices:
        asset = assets[i]
        receipt = HERE / f"download-rave-{i}.json"
        row = json.loads(receipt.read_text()) if receipt.exists() else dict(initial[i])
        archive = Path(row["path"])
        assert archive.stat().st_size == asset["_DownloadSize"] == row["size"]
        assert digest(archive) == row["sha256"]
        with archive.open("rb") as f:
            assert hashlib.file_digest(f, "sha1").hexdigest() == row["catalogue_measurement_hex"]
        decoded = cache / "decrypted" / archive.stem
        if i == 63: decoded = cache / "decrypted-metadata" / archive.stem
        if not decoded.exists():
            result = subprocess.run(["/workspace/tools/bin/ipsw", "fw", "aea", "--key-val",
                                     asset["ArchiveDecryptionKey"], "--output", str(decoded.parent), str(archive)],
                                    capture_output=True, text=True)
            decrypt_logs.append({"index":i,"returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr,
                                 "command":"ipsw fw aea --key-val [from local catalogue] --output CACHE/decrypted ARCHIVE"})
            if result.returncode: raise ValueError(f"AEA decryption failed for index {i}")
        name = known.get(i, f"rave-asset-{i:03}")
        directory = cache / "extracted" / name
        inventory_path = HERE / (name + "-files.json")
        if directory.exists():
            inventory = json.loads(inventory_path.read_text())
            assert digest(decoded) == inventory["source_sha256"]
            for r in inventory["files"]:
                f = directory / r["path"]
                assert f.stat().st_size == r["size"] and digest(f) == r["sha256"]
        else:
            directory.mkdir(parents=True)
            raw = decoded.read_bytes(); records = []
            unpack(raw, directory, records)
            inventory = {"source":str(decoded),"source_sha256":hashlib.sha256(raw).hexdigest(),"files":records,
                         "plaintext_weights_verified":False,"image_inference_performed":False}
            inventory_path.write_text(json.dumps(inventory,indent=2)+"\n")
        protection = directory / "ContentProtection.plist"
        protected = plistlib.loads(protection.read_bytes()) if protection.exists() else {}
        for path, props in protected.items():
            if not (directory/path).is_file(): raise ValueError("Missing protected file")
            if not props.get("nonce") or not props.get("tag"): raise ValueError("Missing DSME metadata")
        row.update(catalogue_index=i, source_catalogue_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                   extracted_directory=str(directory), files=len(inventory["files"]),
                   extracted_bytes=sum(r["size"] for r in inventory["files"]),
                   aa_sha256_verified_files=sum(r["archive_sha256_verified"] for r in inventory["files"]),
                   protected_files=len(protected), protected_paths=sorted(protected),
                   aea_decrypted=True, plaintext_weights_verified=False)
        metadata = directory / "AssetData/metadata.plist"
        if metadata.exists(): row["readable_metadata"] = plistlib.loads(metadata.read_bytes())
        copied = []
        for relative in ("Info.plist", "ContentProtection.plist", "AssetData/metadata.plist"):
            original = directory / relative
            if not original.exists(): continue
            target = HERE / "manifests" / f"rave-{i:03}" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if digest(target) != digest(original): raise ValueError("Manifest evidence changed")
            else:
                with target.open("xb") as out: out.write(original.read_bytes())
            copied.append({"source_relative_path":relative,"evidence":str(target.relative_to(HERE)),"sha256":digest(target)})
        row["manifest_evidence"] = copied
        # Only try tiny JSON/MIL resources; failures are recorded as ciphertext
        # evidence, never interpreted as a loaded graph or executable model.
        checks = []
        for f in directory.rglob("*"):
            if f.is_file() and f.stat().st_size < 1024*1024 and f.suffix in {".json",".mil"}:
                try:
                    if f.suffix == ".json": json.loads(f.read_bytes())
                    else: f.read_text("utf-8")
                    checks.append({"path":str(f.relative_to(directory)),"readable":True})
                except (UnicodeError, ValueError):
                    checks.append({"path":str(f.relative_to(directory)),"readable":False})
        row["small_graph_metadata_parse_checks"] = checks
        rows.append(row)
        print(i, row["asset_specifier"], row["files"], "files; protected", len(protected), flush=True)
    if decrypt_logs or not (HERE/"aea-processing.json").exists():
        (HERE/"aea-processing.json").write_text(json.dumps(decrypt_logs,indent=2)+"\n")
    report = {"at":datetime.now(timezone.utc).isoformat(),"status":"encrypted_payloads_acquired_plaintext_bundle_blocked",
              "catalogue_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"assets":rows,
              "catalogue_signature_and_chain_verified":True,"certificate_validation_unix_time":validation_time,
              "archive_count":len(rows),"download_bytes":sum(r["size"] for r in rows),
              "extracted_files":sum(r["files"] for r in rows),"extracted_bytes":sum(r["extracted_bytes"] for r in rows),
              "protected_files":sum(r["protected_files"] for r in rows),"complete_plaintext_bundle":False,
              "hardware_variant_resolved":False,"image_inference_performed":False,"generated_images":0}
    (HERE/"acquisition-audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="assets"},indent=2))


if __name__ == "__main__": main()
