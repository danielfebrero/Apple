#!/usr/bin/env python3
"""Read existing extracted files and manifests. Never re-extract firmware."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import struct

import coremltools as ct
from coremltools.proto import Model_pb2
from google.protobuf.json_format import MessageToDict


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    assets = [json.loads(line) for line in (root / "models/assets.jsonl").read_text().splitlines()]
    manifest_path = root / "models/manifest.json"
    models = json.loads(manifest_path.read_text())["models"]
    adapter = next(m for m in models if m["id"] == "m-7b9fdc2970fc78c9d2ff")
    files = []
    for f in adapter["files"]:
        p = root / adapter["source_path"] / f["path"]
        assert p.stat().st_size == f["size"] and sha(p) == f["sha256"]
        files.append({"path": str(p.relative_to(root)), "size": p.stat().st_size,
                      "sha256": sha(p), "format": f["format"]})
    binary = root / adapter["source_path"] / "coremldata.bin"
    b = binary.read_bytes()
    # This offset is a finding for this one hash, not a universal compiled-model
    # parser. A little-endian length at byte 75 precedes a public ModelDescription.
    assert sha(binary) == "47e011e35309791ef958ac5d378d154cc3a4026106b9fd340a66039d3bcc9f56"
    length = struct.unpack_from("<Q", b, 75)[0]
    assert length == 224 and 83 + length <= len(b)
    description = Model_pb2.ModelDescription.FromString(b[83:83 + length])
    assert [f.name for f in description.functions] == ["main_ctx_77", "main_ctx_512"]
    assert description.defaultFunctionName == "main_ctx_512"
    sources = []
    names = {}
    for label, filename in (("language", "com.apple.modelcatalog.plist"),
                            ("visual", "com.apple.MobileAsset.UAF.FM.Visual.plist")):
        path = root / "extracted/rootfs/System/Library/UnifiedAssetFramework/AssetSets" / filename
        decoded = root / "decoded/rootfs/System/Library/UnifiedAssetFramework/AssetSets" / (filename + ".json")
        j = json.loads(decoded.read_text())
        names[label] = sorted({a["AssetName"] for a in j["Assets"]})
        sources.append({"path": str(path.relative_to(root)), "sha256": sha(path),
                        "decoded_path": str(decoded.relative_to(root)), "decoded_sha256": sha(decoded)})
    errors = {}
    for name, obj in (("compiled_safari_adapter", str(root / adapter["source_path"])),):
        try:
            ct.convert(obj, source="pytorch", skip_model_load=True)
        except Exception as exc:
            errors[name] = {"type": type(exc).__name__, "message": str(exc)}
        else:
            raise AssertionError("Compiled iOS bundle unexpectedly accepted as PyTorch source")
    local_formats = collections.Counter(a["format"] for a in assets)
    report = {"scope": "existing inventoried files only; names cannot classify all opaque payloads",
        "manifest_sha256": sha(manifest_path), "inventoried_files": len(assets),
        "inventoried_bytes": sum(a["size_bytes"] for a in assets), "formats": dict(local_formats),
        "named_adapter_files": [a["firmware_path"] for a in assets if any(
            s in a["firmware_path"].lower() for s in ("adapter", "lora", "fmadapter", "safetensors"))],
        "standard_peft_or_fmadapter_paths": [a["firmware_path"] for a in assets if any(
            s in a["firmware_path"].lower() for s in ("adapter_config.json", "adapter_model.", ".fmadapter", ".safetensors"))],
        "real_compiled_adapter": {"id": adapter["id"], "files_verified": files,
            "description_offset": 83, "description_length": length,
            "description": MessageToDict(description),
            "missing_from_inventoried_bundle": ["source model.mil", "source .mlmodel protobuf", "PEFT matrices/configuration"],
            "not_established": ["LoRA rank and tensor keys", "base model identity", "AFM compatibility", "Linux inference"]},
        "asset_catalogue_sources": sources,
        "asset_reference_counts": {k: len(v) for k, v in names.items()},
        "instruct_3b_reference_count": sum("com.apple.fm.language.instruct_3b." in n for n in names["language"]),
        "instruct_300m_reference_count": sum("com.apple.fm.language.instruct_300m." in n for n in names["language"]),
        "adapter_named_references": [n for n in names["language"] if "adapter" in n.lower()],
        "base_named_language_references": [n for n in names["language"] if ".base." in n],
        "visual_references": names["visual"], "conversion_rejections": errors,
        "AFM_base_or_adapter_payload_acquired": False,
        "inference": "coremltools cannot reconstruct unavailable source weights or a PEFT state_dict from these names"}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"files": len(assets), "adapter_files_verified": len(files),
                      "decoded_interface": MessageToDict(description), "conversion_rejections": errors}, indent=2))


if __name__ == "__main__":
    main()
