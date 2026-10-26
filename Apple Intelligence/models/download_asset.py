#!/usr/bin/env python3
"""Explicit Apple HTTPS catalogue probes and hash-verified payload downloads.

This tool does not derive private URLs from UAF identifiers, authenticate to
Developer, or treat an HTTP error as proof that a model requires authentication.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request


def apple_url(url):
    p = urllib.parse.urlsplit(url)
    host = (p.hostname or "").lower()
    if p.scheme != "https" or p.username or p.password or p.port not in (None, 443):
        raise ValueError("Expected an explicit HTTPS URL without embedded credentials")
    if not (host == "apple.com" or host.endswith(".apple.com") or host.endswith(".cdn-apple.com")):
        raise ValueError("Expected an Apple-controlled host")
    return url


class AppleRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        apple_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url):
    return urllib.request.build_opener(AppleRedirect()).open(apple_url(url), timeout=30)


def public_url(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def probe(url):
    row = {"url": public_url(url), "url_status": "operator_supplied_or_candidate_not_firmware_attested",
           "at": datetime.now(timezone.utc).isoformat(), "payload_acquired": False}
    try:
        with open_url(url) as r:
            raw = r.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024: raise ValueError("Catalogue exceeds 8 MiB limit")
            row.update(http_status=r.status, response_sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            doc = plistlib.loads(raw)
            row.update(status="catalogue_received", assets=len(doc.get("Assets", [])),
                       note="Metadata only; signatures and model payloads have not been verified")
    except urllib.error.HTTPError as exc:
        raw = exc.read(4096)
        row.update(status="http_error", http_status=exc.code, response_prefix_sha256=hashlib.sha256(raw).hexdigest(),
                   response_prefix_bytes=len(raw), content_type=exc.headers.get("Content-Type"),
                   note="Failure of this URL from this host only; not proof of authentication or model availability")
    except (ValueError, OSError, plistlib.InvalidFileException) as exc:
        row.update(status="error", error=type(exc).__name__)
    return row


def catalogue_rows(path):
    raw = path.read_bytes()
    if len(raw) > 8 * 1024 * 1024: raise ValueError("Catalogue exceeds limit")
    doc = json.loads(raw) if raw.lstrip().startswith(b"{") else plistlib.loads(raw)
    rows = []
    for i, asset in enumerate(doc.get("Assets", [])):
        base, relative = asset.get("__BaseURL"), asset.get("__RelativePath")
        url = urllib.parse.urljoin(base, relative) if isinstance(base, str) and isinstance(relative, str) else None
        if url: apple_url(url)
        rows.append({"index": i, "asset_id": asset.get("AssetId", asset.get("_AssetId")),
                     "asset_type": asset.get("AssetType"), "download_bytes": asset.get("_DownloadSize"),
                     "url": public_url(url) if url else None, "sha256_established": False})
    return {"catalogue_sha256": hashlib.sha256(raw).hexdigest(), "assets": rows,
            "note": "URLs from operator-supplied catalogue; no payload, Apple signature or build compatibility verified"}


def download(url, expected, size, output):
    if not re.fullmatch(r"[a-f0-9]{64}", expected): raise ValueError("Expected lowercase SHA-256")
    if size <= 0: raise ValueError("Expected positive exact payload size")
    # Refuse an existing destination; a partial/error cannot replace a prior artifact.
    if output.exists() or output.is_symlink(): raise ValueError("Destination already exists")
    if not output.parent.is_dir(): raise ValueError("Destination parent must already exist")
    fd, tmp = tempfile.mkstemp(prefix=".apple-download-", dir=output.parent)
    tmp = Path(tmp)
    try:
        h = hashlib.sha256(); count = 0
        with os.fdopen(fd, "wb") as f, open_url(url) as r:
            while data := r.read(1024 * 1024):
                count += len(data)
                if count > size: raise ValueError("Payload larger than expected")
                h.update(data); f.write(data)
            f.flush(); os.fsync(f.fileno())
        if count != size or h.hexdigest() != expected: raise ValueError("Payload size/SHA-256 mismatch")
        # Link fails atomically if a destination appeared during the download.
        os.link(tmp, output)
        return {"status": "downloaded_verified", "url": public_url(url), "path": str(output.resolve()),
                "size": count, "sha256": expected, "apple_signature_verified": False,
                "note": "Matches supplied digest/size; no claim of AFM identity, model support or Apple signature verification"}
    finally:
        tmp.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    op = sub.add_parser("probe"); op.add_argument("--url", action="append", required=True); op.add_argument("--report", type=Path)
    op = sub.add_parser("catalogue"); op.add_argument("path", type=Path)
    op = sub.add_parser("fetch"); op.add_argument("--url", required=True); op.add_argument("--sha256", required=True)
    op.add_argument("--size", type=int, required=True); op.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.command == "probe": result = {"probes": [probe(url) for url in a.url]}
        elif a.command == "catalogue": result = catalogue_rows(a.path)
        else: result = download(a.url, a.sha256, a.size, a.output)
        text = json.dumps(result, indent=2) + "\n"
        if a.command == "probe" and a.report: a.report.write_text(text)
        print(text, end="")
        return 0 if a.command != "probe" or all(x["status"] == "catalogue_received" for x in result["probes"]) else 2
    except (ValueError, OSError) as exc:
        # Avoid dumping signed query strings in exceptions.
        print(json.dumps({"error": type(exc).__name__, "message": str(exc) if isinstance(exc, ValueError) else "I/O or network error"}))
        return 2


if __name__ == "__main__": raise SystemExit(main())
