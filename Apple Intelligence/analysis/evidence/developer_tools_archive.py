#!/usr/bin/env python3
"""Read Apple developer XAR/PBZX archives on Linux without running installers.

XAR data entries are read by TOC offsets, never by inode. Some Apple packages
give unrelated files inode=0; 7-Zip 25.01 incorrectly hardlinks those entries.
Checksums establish archive consistency, not Apple signature authenticity.
"""
import argparse
import hashlib
import json
import lzma
from pathlib import Path, PurePosixPath
import struct
import xml.etree.ElementTree as ET
import zlib


def exact(stream, count):
    data = stream.read(count)
    if len(data) != count:
        raise ValueError("truncated archive")
    return data


def digest(data, algorithm):
    if algorithm not in {"sha1", "sha256", "sha512", "md5"}:
        raise ValueError(f"unsupported archive checksum: {algorithm}")
    return hashlib.new(algorithm, data).hexdigest()


def extract_xar(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    report = {"source": str(source), "files": [], "signature_verified": False}
    with source.open("rb") as stream:
        magic, header_size, version, toc_length, toc_size, algorithm = struct.unpack(
            ">4sHHQQI", exact(stream, 28))
        if magic != b"xar!" or version != 1 or header_size < 28:
            raise ValueError("unsupported XAR header")
        if toc_length > 64 * 1024 * 1024 or toc_size > 128 * 1024 * 1024:
            raise ValueError("TOC exceeds inspection bound")
        stream.seek(header_size)
        packed_toc = exact(stream, toc_length)
        toc = zlib.decompress(packed_toc)
        if len(toc) != toc_size:
            raise ValueError("TOC size mismatch")
        root = ET.fromstring(toc).find("toc")
        heap = header_size + toc_length
        checksum = root.find("checksum")
        if checksum is not None:
            stream.seek(heap + int(checksum.findtext("offset")))
            expected = exact(stream, int(checksum.findtext("size"))).hex()
            if digest(packed_toc, checksum.get("style")) != expected:
                raise ValueError("TOC checksum mismatch")
        (destination / "xar-toc.xml").write_bytes(toc)

        def walk(parent, relative=PurePosixPath()):
            for entry in parent.findall("file"):
                name = entry.findtext("name")
                if not name or name in {".", ".."} or "/" in name or "\\" in name:
                    raise ValueError("unsafe XAR path component")
                child = relative / name
                target = destination.joinpath(*child.parts)
                kind = entry.findtext("type")
                if kind == "directory":
                    target.mkdir(parents=True, exist_ok=True)
                    walk(entry, child)
                elif kind == "file":
                    data = entry.find("data")
                    if data is None:
                        raise ValueError(f"missing data for {child}")
                    offset, length, size = (int(data.findtext(k)) for k in
                                            ("offset", "length", "size"))
                    if min(offset, length, size) < 0 or size > 16 * 1024**3:
                        raise ValueError("invalid XAR bounds")
                    stream.seek(heap + offset)
                    packed = exact(stream, length)
                    archived = data.find("archived-checksum")
                    if archived is not None and digest(packed, archived.get("style")) != archived.text:
                        raise ValueError(f"archived checksum mismatch: {child}")
                    encoding = data.find("encoding").get("style")
                    if encoding == "application/octet-stream":
                        unpacked = packed
                    elif encoding == "application/x-gzip":
                        unpacked = zlib.decompress(packed)
                    else:
                        raise ValueError(f"unsupported XAR encoding: {encoding}")
                    if len(unpacked) != size:
                        raise ValueError(f"extracted size mismatch: {child}")
                    extracted = data.find("extracted-checksum")
                    if extracted is not None and digest(unpacked, extracted.get("style")) != extracted.text:
                        raise ValueError(f"extracted checksum mismatch: {child}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as output:
                        output.write(unpacked)
                    report["files"].append({"path": str(child), "size": size,
                        "sha256": hashlib.sha256(unpacked).hexdigest(),
                        "archive_checksums_verified": True, "encoding": encoding})
                else:
                    raise ValueError(f"unsupported XAR entry type: {kind}")
        walk(root)
    return report


def unpack_pbzx(source, destination):
    chunks = []
    with source.open("rb") as stream, destination.open("xb") as output:
        if exact(stream, 4) != b"pbzx":
            raise ValueError("not PBZX")
        flags = struct.unpack(">Q", exact(stream, 8))[0]
        while flags & 0x1000000:
            flags, length = struct.unpack(">QQ", exact(stream, 16))
            if length > 64 * 1024 * 1024:
                raise ValueError("PBZX chunk exceeds bound")
            packed = exact(stream, length)
            if packed.startswith(b"\xfd7zXZ\x00"):
                data = lzma.decompress(packed)
                encoding = "xz"
            else:
                data = packed
                encoding = "raw"
            if len(data) > 64 * 1024 * 1024:
                raise ValueError("PBZX decoded chunk exceeds bound")
            output.write(data)
            chunks.append({"packed": length, "unpacked": len(data), "encoding": encoding})
        if stream.read(1):
            raise ValueError("unconsumed PBZX data")
    with destination.open("rb") as stream:
        sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"source": str(source), "output": str(destination), "chunks": chunks,
            "size": destination.stat().st_size, "sha256": sha256}


def inventory_cpio(source):
    records = []
    with source.open("rb") as stream:
        while True:
            magic = exact(stream, 6)
            if magic in {b"070701", b"070702"}:
                header = magic + exact(stream, 104)
                values = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
                inode, mode, uid, gid, nlink, mtime, size, devmajor, devminor, rdevmajor, rdevminor, namesize, checksum = values
                aligned = True
            elif magic == b"070707":
                header = magic + exact(stream, 70)
                mode = int(header[18:24], 8)
                nlink = int(header[36:42], 8)
                namesize, size = int(header[59:65], 8), int(header[65:76], 8)
                aligned = False
            else:
                raise ValueError("only odc/newc/crc CPIO supported")
            if namesize < 1 or namesize > 1024 * 1024:
                raise ValueError("invalid CPIO name size")
            name = exact(stream, namesize)
            if not name.endswith(b"\x00"):
                raise ValueError("unterminated CPIO name")
            if aligned:
                stream.seek((-stream.tell()) % 4, 1)
            name = name[:-1].decode("utf-8")
            if name == "TRAILER!!!":
                break
            data_offset = stream.tell()
            digest_ = hashlib.sha256()
            remaining, sum_ = size, 0
            while remaining:
                part = exact(stream, min(remaining, 1024 * 1024))
                digest_.update(part)
                if magic == b"070702":
                    sum_ = (sum_ + sum(part)) & 0xffffffff
                remaining -= len(part)
            if magic == b"070702" and sum_ != checksum:
                raise ValueError("CPIO checksum mismatch")
            records.append({"path": name, "size": size, "mode": oct(mode), "data_offset": data_offset,
                            "nlink": nlink, "sha256": digest_.hexdigest()})
            if aligned:
                stream.seek((-stream.tell()) % 4, 1)
    return {"source": str(source), "entries": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["xar", "pbzx", "cpio-list"])
    parser.add_argument("source", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "cpio-list":
        result = inventory_cpio(args.source)
    else:
        if args.destination is None:
            parser.error("--destination required")
        result = {"xar": extract_xar, "pbzx": unpack_pbzx}[args.action](args.source, args.destination)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"action": args.action, "report": str(args.report),
                      "records": len(result.get("files", result.get("entries", [])))}))


if __name__ == "__main__":
    main()
