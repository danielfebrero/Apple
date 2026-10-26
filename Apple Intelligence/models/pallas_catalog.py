#!/usr/bin/env python3
"""Record bounded, unauthenticated Apple Pallas catalogue queries.

TLS verification stays enabled. An optional official Apple root extends the
system trust store. Decoding a JWT is explicitly not signature verification.
No device identity, account cookie, bearer token or credential is fabricated.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.request

LIMIT = 32 * 1024 * 1024
ENDPOINTS = {"https://gdmf.apple.com/v2/assets", "https://gdmf-ados.apple.com/v2/assets"}


def validate_assets(document):
    if "Assets" in document and (not isinstance(document["Assets"], list)
                                 or any(not isinstance(a, dict) for a in document["Assets"])):
        raise ValueError("Expected Assets array of objects")


def decode_response(raw):
    """Return metadata, preserving its unverified status, or reject bad input."""
    if len(raw) > LIMIT: raise ValueError("Catalogue bound")
    stripped = raw.strip()
    if stripped.startswith(b"{"):
        document = json.loads(stripped)
        if not isinstance(document, dict): raise ValueError("Expected JSON object")
        validate_assets(document)
        return {"encoding": "json", "document": document,
                "signature_verified": False}
    pieces = stripped.split(b".")
    if len(pieces) != 3:
        raise ValueError("Expected a JSON object or compact JWT")
    def decode(part):
        return json.loads(base64.b64decode(part + b"=" * (-len(part) % 4), altchars=b"-_", validate=True))
    header, document = decode(pieces[0]), decode(pieces[1])
    if not isinstance(header, dict) or not isinstance(document, dict):
        raise ValueError("Expected JWT header and payload objects")
    validate_assets(document)
    return {"encoding": "jwt", "header": header, "document": document,
            "signature_verified": False}


def redact_keys(value):
    if isinstance(value, dict):
        return {k: ("[kept only in local raw catalogue]" if k == "ArchiveDecryptionKey" else redact_keys(v))
                for k, v in value.items()}
    if isinstance(value, list): return [redact_keys(v) for v in value]
    return value


def query(request, output, name, endpoint="https://gdmf.apple.com/v2/assets", root_ca=None, raw_output=None):
    if endpoint not in ENDPOINTS:
        raise ValueError("Unrecognized Pallas endpoint")
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
        raise ValueError("Invalid evidence name")
    if not output.is_dir():
        raise ValueError("Output directory must exist")
    report_path = output / (name + ".json")
    raw_path = raw_output / (name + ".response") if raw_output else None
    if report_path.exists() or (raw_path and raw_path.exists()):
        raise ValueError("Evidence destination exists")
    context = ssl.create_default_context()
    report = {"at": datetime.now(timezone.utc).isoformat(), "endpoint": endpoint,
              "request": request, "authentication": "none", "tls_verification_enabled": True, "tls_verified": False,
              "payload_acquired": False, "root_ca": None}
    if root_ca:
        cert = root_ca.read_bytes()
        if not cert.startswith(b"-----BEGIN"):
            cert = ssl.DER_cert_to_PEM_cert(cert).encode()
        context.load_verify_locations(cadata=cert.decode("ascii"))
        report["root_ca"] = {"file": root_ca.name,
                             "sha256": hashlib.sha256(root_ca.read_bytes()).hexdigest()}
    req = urllib.request.Request(endpoint, data=json.dumps(request, sort_keys=True).encode(),
                                 headers={"Content-Type": "application/json", "Accept": "application/json",
                                          "User-Agent": "Apple-Visual-acquisition-audit/1.0"})
    try:
        try:
            response = urllib.request.urlopen(req, context=context, timeout=45)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ValueError("Response exceeds catalogue bound")
            report.update(http_status=response.code, bytes=len(raw), tls_verified=True,
                          response_sha256=hashlib.sha256(raw).hexdigest(),
                          headers={k: v for k, v in response.headers.items()
                                   if k.lower() in {"content-type", "content-length", "date", "server", "via", "x-cache", "etag"}})
        if raw_path:
            with raw_path.open("xb") as f:
                f.write(raw)
            report["response_file"] = str(raw_path.resolve())
        try:
            decoded = decode_response(raw)
            report.update(redact_keys(decoded))
            doc = decoded["document"]
            report["assets_count"] = len(doc.get("Assets", []))
            report["status"] = "catalogue_received" if report["http_status"] == 200 else "http_error"
        except (ValueError, UnicodeError):
            report["status"] = "non_catalogue_response"
    except (OSError, ValueError) as exc:
        report.update(status="transport_error", error=type(exc).__name__, diagnostic=str(exc))
    with report_path.open("x") as f:
        f.write(json.dumps(report, indent=2) + "\n")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--endpoint", choices=sorted(ENDPOINTS), default="https://gdmf.apple.com/v2/assets")
    p.add_argument("--root-ca", type=Path)
    p.add_argument("--raw-output", type=Path, help="Existing local cache directory; raw JWT contains archive keys")
    a = p.parse_args()
    result = query(json.loads(a.request.read_text()), a.output, a.name, a.endpoint, a.root_ca, a.raw_output)
    print(json.dumps({k: v for k, v in result.items() if k not in {"document", "header"}}, indent=2))
    return 0 if result["status"] == "catalogue_received" else 2


if __name__ == "__main__":
    raise SystemExit(main())
