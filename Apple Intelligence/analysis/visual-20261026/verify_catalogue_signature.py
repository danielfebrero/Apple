#!/usr/bin/env python3
"""Verify cached Apple Pallas ES256 catalogues without publishing their payload.

Python standard library + OpenSSL 3 are sufficient. Trust is anchored exclusively
in the pinned official Apple Root CA - G3, not a certificate supplied by the JWT.
Raw catalogues can contain ArchiveDecryptionKey and must stay in the local cache.
This verifies signatures/certificate validity, not revocation, freshness, asset
archive integrity, or the acquisition of any model weights.
"""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import ssl
import subprocess
import tempfile
import urllib.request


APPLE_ROOT_SHA256 = "63343abfb89a6a03ebb57e9b3f5fa7be7c4f5c756f3017b3a8c488c3653e9179"
APPLE_ROOT_URL = "https://www.apple.com/certificateauthority/AppleRootCA-G3.cer"
EXPECTED_SIGNER = "C=US,O=Apple Inc.,CN=Pallas ECDH SIGN PROD"
SIGNER_PURPOSE_OID = "1.2.840.113635.100.6.53"
LIMIT = 32 * 1024 * 1024
P256_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def b64url_decode(raw):
    if not re.fullmatch(rb"[A-Za-z0-9_-]+", raw):
        raise ValueError("Noncanonical compact-JWT base64url")
    return base64.b64decode(raw + b"=" * (-len(raw) % 4), altchars=b"-_", validate=True)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def der_integer(number):
    raw = number.to_bytes(max(1, (number.bit_length() + 7) // 8), "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return b"\x02" + bytes([len(raw)]) + raw


def encode_ecdsa_der(r, s):
    values = der_integer(r) + der_integer(s)
    return b"\x30" + bytes([len(values)]) + values


def es256_signature(signature):
    # Standard JWS ES256 is 64-byte r || s. Actual Apple Pallas responses use
    # canonical ASN.1 DER ECDSA (70--72 bytes) despite the ES256 header. Accept
    # this explicit format only after validating its entire canonical structure.
    if len(signature) == 64:
        r, s = int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big")
        encoding = "JWS fixed-width r||s"
    elif 8 <= len(signature) <= 72 and signature[0] == 0x30 and signature[1] == len(signature) - 2:
        integers = []
        pos = 2
        while pos < len(signature):
            if pos + 2 > len(signature) or signature[pos] != 0x02:
                raise ValueError("Invalid DER ECDSA integer")
            size = signature[pos + 1]
            value = signature[pos + 2:pos + 2 + size]
            if not 1 <= size <= 33 or len(value) != size or value[0] & 0x80:
                raise ValueError("Invalid positive DER ECDSA integer")
            integers.append(int.from_bytes(value, "big"))
            pos += 2 + size
        if len(integers) != 2:
            raise ValueError("DER ECDSA must contain two integers")
        r, s = integers
        if encode_ecdsa_der(r, s) != signature:
            raise ValueError("Noncanonical DER ECDSA signature")
        encoding = "ASN.1 DER ECDSA (Apple Pallas deviation from standard JWS ES256 r||s)"
    else:
        raise ValueError("Unsupported ES256 signature encoding")
    if not 0 < r < P256_ORDER or not 0 < s < P256_ORDER:
        raise ValueError("ECDSA signature integer outside P-256 group order")
    return encode_ecdsa_der(r, s), encoding, r, s


class Commands:
    def __init__(self, work):
        self.work = work
        self.records = []

    def run(self, name, args, *, required=True):
        result = subprocess.run(args, capture_output=True, check=False)
        record = {
            "name": name,
            "argv": [str(x).replace(str(self.work), "$WORK") for x in args],
            "returncode": result.returncode,
            "stdout": result.stdout.decode("utf-8", "replace").replace(str(self.work), "$WORK").strip(),
            "stderr": result.stderr.decode("utf-8", "replace").replace(str(self.work), "$WORK").strip(),
        }
        self.records.append(record)
        if required and result.returncode:
            raise ValueError("OpenSSL command failed: " + name)
        return result


def certificate_info(der, name, work, commands):
    der_path = work / (name + ".der")
    pem_path = work / (name + ".pem")
    der_path.write_bytes(der)
    pem_path.write_text(ssl.DER_cert_to_PEM_cert(der), encoding="ascii")
    result = commands.run(name + "-metadata", [
        "openssl", "x509", "-in", str(pem_path), "-noout", "-subject", "-issuer",
        "-dates", "-serial", "-nameopt", "RFC2253", "-text",
    ])
    metadata = result.stdout.decode("ascii")
    fields = {}
    for key in ("subject", "issuer", "notBefore", "notAfter", "serial"):
        match = re.search(r"^" + key + r"=(.*)$", metadata, re.M)
        if not match:
            raise ValueError("Missing certificate metadata: " + key)
        fields[key] = match.group(1).strip()
    for key in ("notBefore", "notAfter"):
        value = datetime.strptime(fields[key], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        fields[key + "_utc"] = value.isoformat()
    fields.update({
        "der_sha256": sha256(der),
        "der_bytes": len(der),
        "signature_algorithm": re.search(r"Signature Algorithm: (.*)", metadata).group(1).strip(),
        "public_key_algorithm": re.search(r"Public Key Algorithm: (.*)", metadata).group(1).strip(),
        "curve": re.search(r"ASN1 OID: (.*)", metadata).group(1).strip(),
        "ca": "CA:TRUE" in metadata,
        "digital_signature_key_usage": "Digital Signature" in metadata,
        "has_pallas_signing_oid": SIGNER_PURPOSE_OID + ":" in metadata,
    })
    # Certificate/public-key text is public; it never contains the JWT payload.
    return fields, pem_path


def verify_one(path, root_der, tls_root_der, at_time):
    raw = path.read_bytes()
    if len(raw) > LIMIT:
        raise ValueError("Catalogue exceeds bounded size")
    parts = raw.strip().split(b".")
    if len(parts) != 3:
        raise ValueError("Expected one compact JWT")
    header = json.loads(b64url_decode(parts[0]), object_pairs_hook=unique_object)
    document = json.loads(b64url_decode(parts[1]), object_pairs_hook=unique_object)
    if not isinstance(header, dict) or not isinstance(document, dict):
        raise ValueError("Expected object header and payload")
    if header.get("alg") != "ES256":
        raise ValueError("Only explicitly selected ES256 is accepted")
    if "crit" in header:
        raise ValueError("Unsupported critical JWT extension")
    chain = header.get("x5c")
    if not isinstance(chain, list) or len(chain) != 2:
        raise ValueError("Expected Pallas leaf and one intermediate, without supplied trust anchor")
    certs = [base64.b64decode(cert, validate=True) for cert in chain]
    signature = b64url_decode(parts[2])
    with tempfile.TemporaryDirectory(prefix="pallas-signature-") as temp:
        work = Path(temp)
        commands = Commands(work)
        leaf, leaf_path = certificate_info(certs[0], "leaf", work, commands)
        intermediate, intermediate_path = certificate_info(certs[1], "intermediate", work, commands)
        root, root_path = certificate_info(root_der, "pinned-apple-root", work, commands)
        tls_root_path = work / "tls-apple-root.pem"
        tls_root_path.write_text(ssl.DER_cert_to_PEM_cert(tls_root_der), encoding="ascii")
        if leaf["subject"] != EXPECTED_SIGNER:
            raise ValueError("Unexpected Apple catalogue signing identity")
        if leaf["curve"] != "prime256v1" or leaf["ca"] or not leaf["digital_signature_key_usage"]:
            raise ValueError("Unexpected ES256 signer key/constraints")
        if not leaf["has_pallas_signing_oid"]:
            raise ValueError("Missing Apple Pallas-specific signing certificate OID")
        verify_base = ["openssl", "verify", "-no-CAfile", "-no-CApath", "-no-CAstore",
                       "-purpose", "any", "-x509_strict", "-auth_level", "2",
                       "-attime", str(at_time), "-check_ss_sig"]
        commands.run("pinned-root-self-signature", verify_base + [
            "-trusted", str(root_path), str(root_path)])
        commands.run("chain-to-exact-pinned-root", verify_base + [
            "-trusted", str(root_path), "-untrusted", str(intermediate_path), str(leaf_path)])
        wrong_anchor = commands.run("negative-chain-with-tls-root-only", verify_base + [
            "-trusted", str(tls_root_path), "-untrusted", str(intermediate_path), str(leaf_path)],
            required=False)
        if wrong_anchor.returncode == 0:
            raise ValueError("Negative trust-anchor test unexpectedly succeeded")
        # A header thumbprint is only a consistency check, never a trust anchor.
        thumbprint = header.get("x5t#S256")
        if not isinstance(thumbprint, str):
            raise ValueError("Missing leaf certificate thumbprint")
        thumb_raw = base64.b64decode(thumbprint + "=" * (-len(thumbprint) % 4), altchars=b"-_", validate=True)
        if thumb_raw != hashlib.sha256(certs[0]).digest():
            raise ValueError("Leaf certificate thumbprint mismatch")
        public_key = commands.run("leaf-public-key", [
            "openssl", "x509", "-in", str(leaf_path), "-noout", "-pubkey"])
        pub_path = work / "leaf-public-key.pem"
        pub_path.write_bytes(public_key.stdout)
        message_path = work / "signed-input.bin"
        signature_path = work / "signature.der"
        message_path.write_bytes(parts[0] + b"." + parts[1])
        signature_der, signature_encoding, r, s = es256_signature(signature)
        signature_path.write_bytes(signature_der)
        verify_jwt = ["openssl", "dgst", "-sha256", "-verify", str(pub_path),
                      "-signature", str(signature_path), str(message_path)]
        commands.run("jwt-es256-signature", verify_jwt)
        # Retain syntactically valid JSON but change its exact signed encoding.
        changed_payload = base64.urlsafe_b64encode(b64url_decode(parts[1]) + b" ").rstrip(b"=")
        message_path.write_bytes(parts[0] + b"." + changed_payload)
        payload_negative = commands.run("negative-modified-payload", verify_jwt, required=False)
        message_path.write_bytes(parts[0] + b"." + parts[1])
        # Change r while retaining canonical DER and a valid P-256 scalar.
        signature_path.write_bytes(encode_ecdsa_der((r % (P256_ORDER - 1)) + 1, s))
        signature_negative = commands.run("negative-modified-signature", verify_jwt, required=False)
        if payload_negative.returncode == 0 or signature_negative.returncode == 0:
            raise ValueError("Modified JWT unexpectedly verified")
        # Store no arbitrary payload fields, no archive key, and no compact JWT.
        report = {
            "response_file": path.name,
            "response_bytes": len(raw),
            "response_sha256": sha256(raw),
            "encoding": "compact-JWT",
            "algorithm": "ES256",
            "signature_encoding": signature_encoding,
            "signature_bytes": len(signature),
            "assets_count": len(document.get("Assets", [])),
            "posting_date": document.get("PostingDate"),
            "verified_at_utc": datetime.fromtimestamp(at_time, timezone.utc).isoformat(),
            "certificate_chain": [leaf, intermediate, root],
            "chain_verified": True,
            "signature_verified": True,
            "leaf_thumbprint_matches": True,
            "negative_tests": {"modified_payload_rejected": True,
                               "modified_signature_rejected": True,
                               "tls_root_as_signing_anchor_rejected": True},
            "jwt_registered_time_claims_present": [k for k in ("iat", "nbf", "exp") if k in document],
            "commands": commands.records,
        }
        return report


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogues", type=Path, default=here.parent.parent / "models/cache/mobileasset-visual/catalogues")
    parser.add_argument("--root", type=Path, default=here / "AppleRootCA-G3.cer")
    parser.add_argument("--tls-root", type=Path, default=here / "AppleIncRootCertificate.cer")
    parser.add_argument("--output", type=Path, default=here / "catalogue-signatures.json")
    parser.add_argument("--at-time", type=int, help="Unix time for reproducible certificate validity checks (default: current UTC)")
    parser.add_argument("--check-official-root", action="store_true", help="Compare pinned DER to a fresh HTTPS download from apple.com; keep only hash/size")
    args = parser.parse_args()
    at_time = args.at_time if args.at_time is not None else int(datetime.now(timezone.utc).timestamp())
    root_der = args.root.read_bytes()
    if sha256(root_der) != APPLE_ROOT_SHA256:
        raise ValueError("Root is not the exact pinned Apple Root CA - G3 DER")
    tls_root_der = args.tls_root.read_bytes()
    root_source = {"official_url": APPLE_ROOT_URL, "der_sha256": APPLE_ROOT_SHA256,
                   "der_bytes": len(root_der), "fresh_https_comparison": False}
    if args.check_official_root:
        with urllib.request.urlopen(APPLE_ROOT_URL, timeout=30) as response:
            official = response.read(128 * 1024 + 1)
            if response.status != 200 or official != root_der:
                raise ValueError("Fresh official root differs from exact pinned DER")
            root_source.update(fresh_https_comparison=True, http_status=response.status,
                               https_system_trust_verified=True)
    paths = sorted(args.catalogues.glob("*.response"))
    if not paths:
        raise ValueError("No cached responses found")
    report = {
        "format_version": 1,
        "tool": "verify_catalogue_signature.py",
        "tool_sha256": sha256(Path(__file__).read_bytes()),
        "openssl_version": subprocess.check_output(["openssl", "version"], text=True).strip(),
        "verification_unix_time": at_time,
        "verification_utc": datetime.fromtimestamp(at_time, timezone.utc).isoformat(),
        "signing_trust_anchor": root_source,
        "transport_tls_root": {"file": args.tls_root.name, "der_sha256": sha256(tls_root_der),
                               "used_as_signing_trust_anchor": False},
        "security_scope": {
            "signature_and_chain": True,
            "revocation_checked": False,
            "jwt_freshness_or_anti_replay_verified": False,
            "archive_integrity_or_decryption_verified": False,
            "model_weight_acquisition_proved": False,
            "note": "Apple's signed catalogue authenticates metadata only. No raw JWT, asset key, or payload is included. OpenSSL checks chain signatures, constraints, and certificate validity at the recorded time. No OCSP/CRL or replay claim is made.",
        },
        "reproduce": [
            "cd '/workspace/Apple/Apple Intelligence'",
            "python3 analysis/visual-20261026/verify_catalogue_signature.py --at-time " + str(at_time),
            "# Add --check-official-root for an HTTPS comparison to Apple's official root download.",
            "# Each command below uses $WORK for the temporary directory recreated by the script.",
        ],
        "responses": [],
    }
    failed = False
    for path in paths:
        try:
            entry = verify_one(path, root_der, tls_root_der, at_time)
        except (ValueError, OSError, TypeError, KeyError) as exc:
            # Exceptions are controlled diagnostics; never stringify parsed payloads.
            entry = {"response_file": path.name, "response_sha256": sha256(path.read_bytes()),
                     "signature_verified": False, "error": str(exc)}
            failed = True
        report["responses"].append(entry)
    report["all_signatures_and_chains_verified"] = not failed
    report["catalogues_checked"] = len(paths)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"catalogues_checked": len(paths),
                      "all_signatures_and_chains_verified": not failed,
                      "report": str(args.output)}, indent=2))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
