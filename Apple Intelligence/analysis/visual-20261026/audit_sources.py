#!/usr/bin/env python3
"""Reproduce catalogue coverage and exact local firmware evidence, read-only."""
import hashlib
import json
import mmap
from pathlib import Path
import plistlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def digest(path):
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()


def main():
    uaf = ROOT/"extracted/rootfs/System/Library/UnifiedAssetFramework/AssetSets/com.apple.MobileAsset.UAF.FM.Visual.plist"
    config = plistlib.loads(uaf.read_bytes())
    acquired = json.loads((HERE/"acquisition-audit.json").read_text())
    catalogue = json.loads((HERE/"visual-rave.json").read_text())
    all_assets = catalogue["document"]["Assets"]
    rows = []
    identifiers = set()
    for asset in config["Assets"]:
        templates = [x["AutoAssetSpecifierTemplate"] for x in asset.get("Expansions",[])]
        for name in [asset["AssetName"],*templates]:
            if name.startswith("com.apple.fm.visual.image_diffusion_v1."): identifiers.add(name)
        hits = [i for i,a in enumerate(all_assets) if a.get("AssetSpecifier") in templates]
        got = [a["catalogue_index"] for a in acquired["assets"] if a["catalogue_index"] in hits]
        rows.append({"logical_asset":asset["AssetName"],"templates":templates,"catalogue_indices":hits,
                     "acquired_indices":got,"resolution":"template_present" if hits else "not_returned_by_this_query",
                     "plaintext_component_verified":False})
    build_path = ROOT/"review/BuildManifest.plist"
    manifest = plistlib.loads(build_path.read_bytes()); identity = manifest["BuildIdentities"][0]
    mapping = json.loads((ROOT/"dsc/source_sha256.json").read_text())
    needles = {
        ".42":["https://gdmf.apple.com/v2/assets","https://gdmf-auth.apple.com/v2/assets",
               "https://gdmf-ados.apple.com/v2/assets","0c88076f-c292-4dad-95e7-304db9d29d34",
               "IOService:/IOResources/AppleKeyStore","aks_get_dsme_key","DSME_COMPRESSED",
               "ContentProtection.plist","failed to verify GCM tag","Successfully fetched dsme key",
               "Fetching of dsme key not supported here","Successfully decrypted all files under %@"],
        ".30":["noise_predictorChunk1","noise_predictorChunk2","noise_predictor","clip_encoder",
               "decoder_alpha_emoji","local_conditioning_producer.mlmodelc","face_encoder.mlmodelc",
               "dpmSolverMultistepScheduler","lcmScheduler","flowScheduler"],
    }
    literals = []
    for suffix, strings in needles.items():
        file = Path(next(k for k in mapping if k.endswith(suffix)))
        measured = digest(file)
        assert measured == mapping[str(file)]
        with file.open("rb") as f, mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
            for needle in strings:
                offset = data.find(needle.encode()+b"\0")
                if offset < 0: offset = data.find(needle.encode())
                if offset < 0: raise ValueError("Literal absent: "+needle)
                literals.append({"cache":str(file),"cache_sha256":measured,"file_offset":hex(offset),"literal":needle})
    report = {"uaf_file":str(uaf),"uaf_sha256":digest(uaf),"logical_assets":len(config["Assets"]),
              "usage_types":len(config["UsageTypes"]),"distinct_diffusion_names_and_templates":sorted(identifiers),
              "diffusion_logical_assets":sum(a["AssetName"].startswith("com.apple.fm.visual.image_diffusion_v1.") for a in config["Assets"]),
              "coverage":rows,"unreturned_templates_are_not_proven_nonexistent":True,
              "hardware":{"source":str(build_path),"source_sha256":digest(build_path),
                          "product_types":manifest.get("SupportedProductTypes"),"chip_id":identity["ApChipID"],
                          "board_id":identity["ApBoardID"],"device_class":identity["Info"]["DeviceClass"],
                          "build_train":identity["Info"]["BuildTrain"],"build":identity["Info"]["BuildNumber"],
                          "catalogue_hardware_mapping_established":False},
              "firmware_literals":literals,
              "scope_note":"Exact strings and offsets establish firmware evidence, not a reconstructed call graph, extracted DSME key, or successful inference."}
    (HERE/"source-and-coverage-audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"logical_assets":len(rows),"diffusion_names":len(identifiers),"templates_returned":sum(bool(r["catalogue_indices"]) for r in rows),
                      "templates_acquired":sum(bool(r["acquired_indices"]) for r in rows),"literals_verified":len(literals)},indent=2))


if __name__ == "__main__": main()
