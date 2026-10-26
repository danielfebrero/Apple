#!/usr/bin/env python3
"""Bounded reader for the observed AA01 + YOP E + PBZX MobileAsset subset.

Rejects symlinks, traversal, unsupported encodings and overwrites. Does not
decrypt DSME, validate YEC trailers, or claim full Apple Archive compatibility.
"""
import argparse
import hashlib
import json
import lzma
from pathlib import Path, PurePosixPath
import struct

MAX = 4 * 1024**3


def entries(data):
    pos = 0
    while pos < len(data):
        start = pos
        if data[pos:pos+4] not in (b"AA01", b"YAA1") or pos + 6 > len(data):
            raise ValueError(f"Invalid AA magic at {pos}")
        length = int.from_bytes(data[pos+4:pos+6], "little")
        end = pos + length
        if length < 6 or end > len(data): raise ValueError("Truncated header")
        pos += 6; fields = {}; blobs = []
        while pos < end:
            if pos + 4 > end: raise ValueError("Truncated field")
            key = bytes(data[pos:pos+3]).decode("ascii"); sub = chr(data[pos+3]); pos += 4
            if key in fields: raise ValueError("Duplicate field")
            if sub == "*": value = True; size = 0
            elif sub in "1248":
                size = int(sub); value = int.from_bytes(data[pos:pos+size], "little")
            elif sub == "P":
                if pos + 2 > end: raise ValueError("Truncated string length")
                size = int.from_bytes(data[pos:pos+2], "little"); pos += 2
                value = bytes(data[pos:pos+size]).decode("utf-8")
            elif sub in "FGHIJST":
                size = {"F":4,"G":20,"H":32,"I":48,"J":64,"S":8,"T":12}[sub]
                value = bytes(data[pos:pos+size]).hex()
            elif sub in "ABC":
                size = {"A":2,"B":4,"C":8}[sub]; value = int.from_bytes(data[pos:pos+size], "little")
                blobs.append((key, value))
            else: raise ValueError(f"Unsupported field subtype {sub}")
            if pos + size > end: raise ValueError("Truncated field value")
            fields[key] = value; pos += size
        payloads = {}
        for key, size in blobs:
            if size > MAX or pos + size > len(data): raise ValueError("Truncated/oversize blob")
            payloads[key] = memoryview(data)[pos:pos+size]; pos += size
        yield start, fields, payloads


def pbzx(data):
    if data[:4] != b"pbzx" or len(data) < 12: raise ValueError("Expected PBZX")
    block = struct.unpack(">Q", data[4:12])[0]
    if not 0 < block <= 64 * 1024**2: raise ValueError("PBZX block bound")
    pos = 12; result = bytearray()
    while pos < len(data):
        if pos + 16 > len(data): raise ValueError("Truncated PBZX header")
        plain, packed = struct.unpack(">QQ", data[pos:pos+16]); pos += 16
        if plain > block or packed > block * 2 or pos + packed > len(data): raise ValueError("PBZX chunk bound")
        chunk = bytes(data[pos:pos+packed]); pos += packed
        if plain != packed:
            decoder = lzma.LZMADecompressor(memlimit=256*1024**2)
            chunk = decoder.decompress(chunk, max_length=plain+1)
            if not decoder.eof or decoder.unused_data:
                raise ValueError("PBZX compressed chunk length mismatch")
        if len(chunk) != plain: raise ValueError("PBZX length mismatch")
        if len(result) + len(chunk) > MAX: raise ValueError("PBZX output bound")
        result.extend(chunk)
    return result


def unpack(data, output, records, depth=0):
    if depth > 4: raise ValueError("Nested archive bound")
    for offset, fields, blobs in entries(data):
        typ = chr(fields["TYP"])
        if typ == "M":
            operation = chr(fields.get("YOP", 0))
            if operation == "E":
                unpack(pbzx(blobs["DAT"]), output, records, depth+1)
            elif operation == "O":
                for _, trailer, _ in entries(pbzx(blobs["DAT"])):
                    if "SH2" not in trailer: continue
                    path = trailer.get("PAT", "")
                    matched = [r for r in records if r["path"] == path]
                    if len(matched) != 1 or matched[0]["sha256"] != trailer["SH2"]:
                        raise ValueError("AA trailer SHA-256 mismatch")
                    matched[0]["archive_sha256_verified"] = True
            elif operation != "M":
                raise ValueError("Unsupported AA metadata operation")
            continue
        path = fields.get("PAT", "")
        rel = PurePosixPath(path)
        if not path or rel.is_absolute() or ".." in rel.parts or "\x00" in path or "\\" in path:
            raise ValueError("Unsafe archive path")
        dest = output.joinpath(*rel.parts)
        if any(p.is_symlink() for p in [dest, *dest.parents]): raise ValueError("Symlink destination")
        if typ == "D": dest.mkdir(parents=True, exist_ok=True)
        elif typ == "F":
            dest.parent.mkdir(parents=True, exist_ok=True)
            blob = blobs.get("DAT", b"")
            digest = hashlib.sha256(blob).hexdigest()
            if "SH2" in fields and fields["SH2"] != digest: raise ValueError("AA SHA-256 mismatch")
            with dest.open("xb") as f: f.write(blob)
            records.append({"path": str(rel), "size": len(blob), "sha256": digest,
                            "archive_sha256_verified": "SH2" in fields,
                            "yec_verified": False, "depth": depth})
        else: raise ValueError(f"Unsupported entry type {typ}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path); p.add_argument("output", type=Path)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists() or a.report.exists(): raise ValueError("Output already exists")
    a.output.mkdir(parents=True)
    if a.source.stat().st_size > MAX: raise ValueError("Source archive bound")
    raw = a.source.read_bytes(); records = []
    unpack(raw, a.output, records)
    report = {"source": str(a.source.resolve()), "source_sha256": hashlib.sha256(raw).hexdigest(),
              "files": records, "plaintext_weights_verified": False, "image_inference_performed": False}
    a.report.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"files": len(records), "bytes": sum(x["size"] for x in records)}))


if __name__ == "__main__": main()
