"""CLI operations are local. Neither weights nor replacement models are downloaded."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path

from . import __version__
from .backends import coreai_cpu, coreml, portable, protobuf_cpu, read_json, static_inspection
from .catalog import Catalog, RuntimeFailure
from .store import Store, verify_bundle


def default_catalog() -> Path:
    return Path(os.environ.get("APPLE_FIRMWARE_CATALOG", Path(__file__).resolve().parents[2] / "models" / "manifest.json"))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Verified firmware models: catalogue, local import, inspection, explicit inference")
    p.add_argument("--catalog", type=Path, default=default_catalog(), help="models/manifest.json")
    p.add_argument("--source-root", type=Path, help="Directory relative to which source_path is resolved")
    p.add_argument("--store", type=Path, default=Path(os.environ.get("APPLE_FIRMWARE_RUNTIME_STORE", "~/.cache/apple-firmware-runtime")),
                   help="Local content-addressed store")
    p.add_argument("--version", action="version", version=__version__)
    subs = p.add_subparsers(dest="command", required=True)
    subs.add_parser("doctor", help="Report host/backend availability without loading a model")
    listing = subs.add_parser("list", help="List model IDs; exact ID is required for subsequent commands")
    listing.add_argument("--scope")
    listing.add_argument("--format")
    listing.add_argument("--search", default="")
    for name in ("import", "verify", "inspect", "predict"):
        op = subs.add_parser(name)
        op.add_argument("model", help="Exact model ID from list")
        if name in ("verify", "inspect"):
            op.add_argument("--source", action="store_true", help="Verify/use original extracted source instead of imported bundle")
        if name == "inspect":
            op.add_argument("--load", action="store_true", help="Load selected backend and return its actual model schema")
            op.add_argument("--backend", choices=("coreml", "coreai-cpu"), default="coreml")
        if name == "predict":
            op.add_argument("--input", required=True, type=Path, help="JSON object, feature names from inspect")
            op.add_argument("--backend", choices=("coreml", "espresso-linear-cpu-experimental", "coreml-protobuf-cpu-experimental", "coreai-cpu"), default="coreml")
            op.add_argument("--output", type=Path, help="Write JSON result to this local file")
        if name in ("inspect", "predict"):
            op.add_argument("--compute", choices=("cpu", "all", "cpu-and-gpu", "cpu-and-ne"), default="cpu")
    return p


def doctor(catalog_path: Path, store: Store) -> dict:
    darwin = platform.system() == "Darwin"
    return {"version": __version__, "platform": platform.platform(), "machine": platform.machine(),
            "catalog": str(catalog_path), "catalog_present": catalog_path.is_file(), "store": str(store.root),
            "coreml": {"available_to_attempt": darwin and shutil.which("xcrun") is not None,
                       "required": "macOS + CoreML framework + Xcode Command Line Tools",
                       "limitation": "An iOS compiled model may not load on macOS; runtime errors are preserved"},
            "espresso_linear_cpu_experimental": {"available": True,
                       "limitation": "Strict attested InnerProduct(62→1)+sigmoid subset; no Apple parity measurement"},
            "coreml_protobuf_cpu_experimental": {
                       "dependencies_present": all(importlib.util.find_spec(x) is not None for x in ("numpy", "coremltools")),
                       "required": "pip install '.[cpu]'",
                       "limitation": "Trees/pipelines and bounded MIL/dense operators; unsupported graphs fail explicitly; no Apple parity measurement"},
            "coreai_cpu": {
                       "dependencies_present": all(importlib.util.find_spec(x) is not None for x in ("numpy", "coreai")),
                       "host_supported": platform.system() == "Linux" and platform.machine().lower() in ("x86_64", "amd64"),
                       "required": "Python >=3.11, glibc >=2.34; pip install '.[coreai]'",
                       "limitation": "Apple .aimodel assets only; stateless static numeric tensors; no AFM weights included"},
            "apple_intelligence_generation": {"available_from_this_firmware_corpus": False,
                       "reason": "Prompts and asset references do not supply AFM generation weights/runtime"},
            "network_requests": False}


def run(args: argparse.Namespace) -> dict | list:
    store = Store(args.store)
    if args.command == "doctor":
        return doctor(args.catalog, store)
    catalog = Catalog(args.catalog, args.source_root)
    if args.command == "list":
        return [m.summary() for m in catalog.models.values()
                if (not args.scope or m.declaration.get("scope") == args.scope)
                and (not args.format or m.declaration.get("format") == args.format)
                and args.search.casefold() in json.dumps(m.summary(), ensure_ascii=False).casefold()]
    model = catalog.get(args.model)
    if args.command == "import":
        return store.import_model(model)
    if getattr(args, "source", False):
        verified = verify_bundle(model, model.source)
        bundle = model.source
    else:
        verified = store.verify(model)
        bundle = store.bundle(model)
    if args.command == "verify":
        return verified
    if args.command == "inspect":
        if args.load:
            result = (coreai_cpu(model, bundle, compute=args.compute) if args.backend == "coreai-cpu"
                      else coreml(model, bundle, store.root, compute=args.compute))
        else:
            result = static_inspection(model, bundle)
        return result | {"integrity": verified}
    inputs = read_json(args.input)
    if not isinstance(inputs, dict):
        raise RuntimeFailure("invalid_inputs", "Input JSON must be an object mapping actual feature names to values")
    if args.backend == "coreml":
        result = coreml(model, bundle, store.root, inputs=inputs, compute=args.compute)
    elif args.backend == "coreml-protobuf-cpu-experimental":
        result = protobuf_cpu(model, bundle, inputs)
    elif args.backend == "coreai-cpu":
        result = coreai_cpu(model, bundle, inputs, compute=args.compute)
    else:
        result = portable(model, bundle, inputs)
    result["integrity"] = verified
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        output = run(args)
        print(json.dumps(output, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except RuntimeFailure as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, allow_nan=False), file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": "operation_failed", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
