#!/usr/bin/env python3
"""Acquire explicit Pallas assets, checking the catalogue measurement and size.

The catalogue must have been obtained separately. SHA-1 measurements are
reported as such; an additional SHA-256 records the exact received bytes.
Neither an encrypted archive nor a verified digest proves usable model weights.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.parse

from download_asset import apple_url, open_url
from pallas_catalog import decode_response


def acquire(asset, destination):
    size = asset.get("_DownloadSize")
    algorithm = {"SHA-1": "sha1", "SHA-256": "sha256"}.get(asset.get("_MeasurementAlgorithm"))
    if not algorithm or not isinstance(size, int) or size <= 0:
        raise ValueError("Exact size and supported catalogue measurement required")
    expected = base64.b64decode(asset["_Measurement"], validate=True).hex()
    if len(expected) != hashlib.new(algorithm).digest_size * 2:
        raise ValueError("Invalid measurement length")
    url = apple_url(urllib.parse.urljoin(asset["__BaseURL"], asset["__RelativePath"]))
    if any(p.is_symlink() for p in [destination, *destination.parents]):
        raise ValueError("Destination directory symlink")
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / Path(urllib.parse.urlsplit(url).path).name
    if output.is_symlink():
        raise ValueError("Destination symlink")
    h = hashlib.new(algorithm); sha256 = hashlib.sha256(); count = 0
    status = "reused_verified" if output.exists() else "downloaded_verified"
    fd, tmp = tempfile.mkstemp(prefix=".mobileasset-", dir=destination)
    try:
        with os.fdopen(fd, "wb") as sink:
            source = output.open("rb") if status == "reused_verified" else open_url(url)
            with source:
                while chunk := source.read(1024 * 1024):
                    count += len(chunk)
                    if count > size:
                        raise ValueError("Payload larger than catalogue size")
                    h.update(chunk); sha256.update(chunk)
                    if status == "downloaded_verified": sink.write(chunk)
            sink.flush(); os.fsync(sink.fileno())
        if count != size or h.hexdigest() != expected:
            raise ValueError("Payload size/measurement mismatch")
        if status == "downloaded_verified": os.link(tmp, output)
        return {"at": datetime.now(timezone.utc).isoformat(), "status": status,
                "asset_specifier": asset.get("AssetSpecifier"), "asset_version": asset.get("AssetVersion"),
                "url": url, "path": str(output.resolve()), "size": count,
                "catalogue_measurement_algorithm": asset["_MeasurementAlgorithm"],
                "catalogue_measurement_hex": expected, "catalogue_measurement_verified": True,
                "sha256": sha256.hexdigest(), "asset_format": asset.get("AssetFormat"),
                "content_encryption": asset.get("_ContentEncryption"),
                "requires_personalization": asset.get("__RequiresPersonalization", False),
                "plaintext_weights_verified": False, "image_inference_performed": False}
    finally:
        Path(tmp).unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalogue", type=Path, required=True)
    p.add_argument("--index", type=int, action="append", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    if a.report.exists(): raise ValueError("Report already exists")
    raw = a.catalogue.read_bytes()
    d = json.loads(raw) if raw.lstrip().startswith(b"{") else decode_response(raw)
    assets = d.get("document", d)["Assets"]
    rows = []
    for i in a.index:
        if i < 0 or i >= len(assets): raise ValueError("Invalid asset index")
        row = acquire(assets[i], a.output); row["catalogue_index"] = i
        rows.append(row)
        print(json.dumps(row), flush=True)
        a.report.write_text(json.dumps({"catalogue_sha256": hashlib.sha256(a.catalogue.read_bytes()).hexdigest(),
                                       "assets": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
