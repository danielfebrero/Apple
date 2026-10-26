#!/usr/bin/env python3
"""Reacquire published, hash-identified firmware assets from local decrypted DMGs.

No private APFS inventory, network, mounts, or replacement model is involved.
The existing apfs_ai reader extracts the exact published inode/private_id pairs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import time

BASE = Path(__file__).resolve().parent.parent
MAX_UINT64 = 2 ** 64 - 1


class AcquisitionError(Exception):
    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code, self.details = code, details

    def as_dict(self):
        return {"error": self.code, "message": str(self), **self.details}


def relative_path(value, context):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise AcquisitionError("invalid_metadata", f"Invalid path: {context}")
    if PurePosixPath(value).is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise AcquisitionError("unsafe_path", f"Unsafe relative path: {context}")
    return value


def firmware_relative(value, context):
    if not isinstance(value, str) or not value.startswith("/"):
        raise AcquisitionError("invalid_metadata", f"Expected absolute firmware path: {context}")
    return relative_path(value[1:], context)


def unsigned(value, context):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_UINT64:
        raise AcquisitionError("invalid_metadata", f"Invalid uint64: {context}")
    return value


def sha256(value, context):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AcquisitionError("invalid_metadata", f"Invalid SHA-256: {context}")
    return value


def no_symlinks(path):
    path = Path(os.path.abspath(path))
    for parent in reversed((path, *path.parents)):
        if parent.is_symlink():
            raise AcquisitionError("unsafe_path", f"Symlink is not accepted: {parent}")
    return path


def secure_mkdir(path):
    path = no_symlinks(path)
    # Construct one component at a time, checking each existing component.
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise AcquisitionError("unsafe_path", f"Symlink is not accepted: {current}")
        try:
            current.mkdir(exist_ok=True)
        except OSError as exc:
            raise AcquisitionError("cache_unwritable", f"Cannot create directory {current}: {exc}") from exc
        if not current.is_dir():
            raise AcquisitionError("unsafe_path", f"Cache parent is not a directory: {current}")


def load_json(path):
    path = no_symlinks(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AcquisitionError("metadata_unreadable", f"Cannot read {path}: {exc}") from exc


def identity(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


def hash_file(path):
    path = no_symlinks(path)
    if not path.is_file():
        raise AcquisitionError("missing_file", f"Required regular file is missing: {path}")
    before = identity(path)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    if identity(path) != before:
        raise AcquisitionError("source_changed", f"File changed while hashing: {path}")
    return size, digest.hexdigest(), before


def load_plan(manifest_path, assets_path, summary_path, selected, all_models, firmware_root, cache_root):
    manifest = load_json(manifest_path)
    summary = load_json(summary_path)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or not isinstance(manifest.get("models"), list):
        raise AcquisitionError("invalid_metadata", "Expected manifest schema_version 1 and models list")
    if not isinstance(summary, dict) or summary.get("schema_version") != 1 or not isinstance(summary.get("volumes"), list):
        raise AcquisitionError("invalid_metadata", "Expected summary schema_version 1 and volumes list")
    by_model = {}
    for model in manifest["models"]:
        mid = model.get("id") if isinstance(model, dict) else None
        if not isinstance(mid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", mid) or mid in by_model:
            raise AcquisitionError("invalid_metadata", "Invalid or duplicate model ID")
        by_model[mid] = model
    ids = list(by_model) if all_models else list(dict.fromkeys(selected))
    unknown = [mid for mid in ids if mid not in by_model]
    if unknown:
        raise AcquisitionError("unknown_model", "Model IDs absent from published manifest", model_ids=unknown)
    assets = {}
    try:
        with no_symlinks(assets_path).open(encoding="utf-8") as stream:
            for lineno, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                asset = json.loads(line)
                aid = asset.get("id") if isinstance(asset, dict) else None
                if not isinstance(aid, str) or aid in assets:
                    raise AcquisitionError("invalid_metadata", f"Invalid/duplicate asset at line {lineno}")
                assets[aid] = asset
    except (OSError, ValueError) as exc:
        raise AcquisitionError("metadata_unreadable", f"Cannot read assets JSONL: {exc}") from exc
    volumes = {}
    for volume in summary["volumes"]:
        vid = volume.get("volume_id")
        if not isinstance(vid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", vid) or vid in volumes:
            raise AcquisitionError("invalid_metadata", "Invalid or duplicate volume ID")
        # New manifests preserve arbitrary nesting relative to firmware_root.
        # The historical two-volume manifests used the final directory/name.
        old = PurePosixPath(volume.get("image_path", ""))
        local_image = relative_path(volume.get("image_relative_path", f"{old.parent.name}/{old.name}"),
                                    f"{vid}.image_relative_path")
        if PurePosixPath(local_image).name != old.name:
            raise AcquisitionError("invalid_metadata", f"{vid}: relative image basename differs from provenance")
        expected_size = unsigned(volume.get("image_size_bytes"), f"{vid}.image_size_bytes")
        expected_hash = sha256(volume.get("image_sha256"), f"{vid}.image_sha256")
        volumes[vid] = {"volume_id": vid, "volume": volume.get("volume"), "relative_path": local_image,
                        "path": firmware_root / local_image, "expected_size": expected_size, "sha256": expected_hash}
    jobs, seen = [], set()
    for mid in ids:
        model = by_model[mid]
        source_path = relative_path(model.get("source_path"), f"{mid}.source_path")
        source_parts = PurePosixPath(source_path).parts
        if len(source_parts) < 3 or source_parts[:2] != ("models", "cache"):
            raise AcquisitionError("invalid_metadata", f"{mid}: source_path must be relative to models/cache")
        model_files = model.get("files")
        if not isinstance(model_files, list) or not model_files:
            raise AcquisitionError("invalid_metadata", f"{mid}: empty files list")
        file_paths = set()
        for item in model_files:
            rel = relative_path(item.get("path"), f"{mid}.file.path")
            if rel in file_paths:
                raise AcquisitionError("invalid_metadata", f"{mid}: duplicate file path {rel}")
            file_paths.add(rel)
            aid = item.get("asset_id")
            asset = assets.get(aid)
            if not asset or asset.get("model_id") != mid:
                raise AcquisitionError("invalid_metadata", f"{mid}/{rel}: missing/mismatched asset provenance")
            source = asset.get("source")
            if not isinstance(source, dict):
                raise AcquisitionError("invalid_metadata", f"{aid}: source must be an object")
            vid = source.get("volume_id")
            if vid not in volumes or vid != model.get("volume_id"):
                raise AcquisitionError("invalid_metadata", f"{aid}: unknown/mismatched volume")
            if source.get("volume") != volumes[vid]["volume"]:
                raise AcquisitionError("invalid_metadata", f"{aid}: APFS volume name differs from summary")
            if PurePosixPath(source.get("image_path", "")).name != PurePosixPath(volumes[vid]["relative_path"]).name:
                raise AcquisitionError("invalid_metadata", f"{aid}: source image differs from summary")
            fwrel = firmware_relative(asset.get("firmware_path"), f"{aid}.firmware_path")
            destination_rel = "/".join((*source_parts[2:], rel))
            expected_rel = f"{vid}/{fwrel}"
            if destination_rel != expected_rel or asset.get("bundle_relative_path") != rel:
                raise AcquisitionError("invalid_metadata", f"{aid}: manifest destination and firmware provenance disagree")
            size = unsigned(item.get("size"), f"{aid}.size")
            digest = sha256(item.get("sha256"), f"{aid}.sha256")
            if asset.get("size_bytes") != size or source.get("expected_size") != size or asset.get("sha256") != digest:
                raise AcquisitionError("invalid_metadata", f"{aid}: published size/hash disagree")
            inode = unsigned(source.get("inode"), f"{aid}.inode")
            private_id = unsigned(source.get("private_id"), f"{aid}.private_id")
            stored_size = unsigned(source.get("stored_size"), f"{aid}.stored_size")
            if destination_rel in seen:
                raise AcquisitionError("invalid_metadata", f"Duplicate extraction destination: {destination_rel}")
            seen.add(destination_rel)
            jobs.append({"asset_id": aid, "model_id": mid, "volume_id": vid, "firmware_path": "/" + fwrel,
                         "destination": cache_root / destination_rel, "relative_cache_path": destination_rel,
                         "size_bytes": size, "sha256": digest, "inode": inode, "private_id": private_id,
                         "stored_size": stored_size})
    return ids, jobs, {vid: volumes[vid] for vid in sorted({job["volume_id"] for job in jobs})}


def extract_one(job, volume, reader, timeout):
    target = no_symlinks(job["destination"])
    previous = None
    if target.exists():
        size, digest, _ = hash_file(target)
        if (size, digest) == (job["size_bytes"], job["sha256"]):
            return {"asset_id": job["asset_id"], "path": str(target), "status": "reused_verified",
                    "size_bytes": size, "sha256": digest}
        previous = {"size_bytes": size, "sha256": digest}
    if identity(no_symlinks(volume["path"])) != volume["verified_identity"]:
        raise AcquisitionError("source_changed", "Verified DMG changed before extraction", image=str(volume["path"]))
    secure_mkdir(target.parent)
    fd, temporary_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".partial", dir=target.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        command = [str(reader), "one", str(volume["path"]), str(job["inode"]), str(job["private_id"]),
                   str(job["stored_size"]), str(temporary)]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise AcquisitionError("reader_timeout", f"APFS reader timed out for {job['firmware_path']}") from exc
        if process.returncode:
            raise AcquisitionError("reader_failed", f"APFS reader failed for {job['firmware_path']}",
                                   exit_code=process.returncode, stderr=process.stderr[-4000:])
        if volume["volume"] and f"volume={volume['volume']} " not in process.stderr:
            raise AcquisitionError("wrong_apfs_volume", "Reader did not report the expected APFS volume", stderr=process.stderr[-4000:])
        size, digest, _ = hash_file(temporary)
        if (size, digest) != (job["size_bytes"], job["sha256"]):
            raise AcquisitionError("integrity_mismatch", f"Extracted file differs from published identity: {job['firmware_path']}",
                                   expected_size=job["size_bytes"], actual_size=size,
                                   expected_sha256=job["sha256"], actual_sha256=digest)
        if identity(volume["path"]) != volume["verified_identity"]:
            raise AcquisitionError("source_changed", "Verified DMG changed during extraction")
        no_symlinks(target)
        os.replace(temporary, target)
        return {"asset_id": job["asset_id"], "path": str(target), "status": "repaired_verified" if previous else "extracted_verified",
                "size_bytes": size, "sha256": digest, **({"replaced_mismatch": previous} if previous else {})}
    finally:
        temporary.unlink(missing_ok=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--firmware-root", required=True, type=Path,
                   help="Local decrypted-image root containing rootfs-dec/ and cryptex-dec/; never downloaded")
    selection = p.add_mutually_exclusive_group(required=True)
    selection.add_argument("--model", action="append", default=[], help="Exact model ID; repeat to select several")
    selection.add_argument("--all", action="store_true", help="All published model/resource groups")
    p.add_argument("--manifest", type=Path, default=BASE / "models/manifest.json")
    p.add_argument("--assets", type=Path, default=BASE / "models/assets.jsonl")
    p.add_argument("--summary", type=Path, default=BASE / "models/summary.json")
    p.add_argument("--reader", type=Path, default=BASE / "scripts/apfs_ai")
    p.add_argument("--cache-root", type=Path, default=BASE / "models/cache",
                   help="Asset output root; use .../models/cache for runtime --source-root compatibility")
    p.add_argument("--timeout", type=float, default=180, help="Seconds per reader process")
    p.add_argument("--dry-run", action="store_true", help="Plan only: no image hashes verified, no extraction, no cache writes")
    p.add_argument("--report", type=Path, help="Write the exact JSON result to this local file")
    return p


def acquire(args):
    started = time.monotonic()
    firmware_root, cache_root = no_symlinks(args.firmware_root), no_symlinks(args.cache_root)
    ids, jobs, volumes = load_plan(args.manifest, args.assets, args.summary, args.model, args.all, firmware_root, cache_root)
    runtime_root = str(cache_root.parent.parent) if cache_root.parts[-2:] == ("models", "cache") else None
    result = {"schema_version": 1, "dry_run": args.dry_run, "network_requests": False,
              "private_inventory_used": False, "model_ids": ids, "file_count": len(jobs),
              "size_bytes": sum(job["size_bytes"] for job in jobs), "cache_root": str(cache_root),
              "runtime_source_root": runtime_root, "images": [], "files": [],
              "extraction_performed": False, "integrity_verified": False}
    if args.dry_run:
        result["message"] = "Plan only. No image hash or asset bytes were verified; no extraction or cache write occurred."
        result["images"] = [{"volume_id": v["volume_id"], "path": str(v["path"]),
                             "expected_size_bytes": v["expected_size"], "expected_sha256": v["sha256"],
                             "integrity_verified": False} for v in volumes.values()]
        result["files"] = [{"asset_id": j["asset_id"], "path": str(j["destination"]), "status": "planned_unverified"} for j in jobs]
        return result
    if not args.timeout > 0:
        raise AcquisitionError("invalid_argument", "--timeout must be positive")
    reader = no_symlinks(args.reader)
    if not reader.is_file() or not os.access(reader, os.X_OK):
        raise AcquisitionError("reader_unavailable", f"Executable APFS reader is missing: {reader}")
    for volume in volumes.values():
        print(f"Hashing {volume['volume_id']} image before extraction: {volume['path']}", file=sys.stderr, flush=True)
        size, digest, snapshot = hash_file(volume["path"])
        if (size, digest) != (volume["expected_size"], volume["sha256"]):
            raise AcquisitionError("image_integrity_mismatch", "Decrypted DMG differs from published image identity",
                                   image=str(volume["path"]), expected_size=volume["expected_size"], actual_size=size,
                                   expected_sha256=volume["sha256"], actual_sha256=digest)
        volume["verified_identity"] = snapshot
        result["images"].append({"volume_id": volume["volume_id"], "path": str(volume["path"]),
                                 "size_bytes": size, "sha256": digest, "integrity_verified": True})
    for job in jobs:
        result["files"].append(extract_one(job, volumes[job["volume_id"]], reader, args.timeout))
    result["extraction_performed"] = any(row["status"] != "reused_verified" for row in result["files"])
    result["integrity_verified"] = True
    result["elapsed_seconds"] = time.monotonic() - started
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = acquire(args)
        encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            report = no_symlinks(args.report)
            if report.is_relative_to(no_symlinks(args.cache_root)):
                raise AcquisitionError("invalid_argument", "--report must be outside the cache root")
            report.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0
    except AcquisitionError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"error": "acquisition_failed", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
