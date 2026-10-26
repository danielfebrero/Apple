"""Explicit backend dispatch; unavailable runtimes never produce synthetic output."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from .catalog import Model, RuntimeFailure


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise RuntimeFailure("invalid_json", f"Cannot read JSON {path}: {exc}") from exc


def static_inspection(model: Model, bundle: Path) -> dict:
    result = model.summary() | {"backend": "static", "prediction_performed": False, "resources": []}
    for field in ("function", "architecture", "interface", "interfaces", "blockers", "runtime", "evidence", "limitations"):
        if field in model.declaration:
            result[field] = model.declaration[field]
    # These are declared file descriptions, not a guessed input schema.
    for item in model.files:
        name = Path(item["path"]).name
        if name in ("metadata.json", "Manifest.json") or name.endswith((".espresso.net", ".espresso.shape")):
            resource = {"path": item["path"], "sha256": item["sha256"]}
            if item["size"] > 8 * 1024 * 1024:
                resource["not_decoded"] = "JSON resource exceeds inspection limit of 8 MiB"
            else:
                try:
                    resource["content"] = read_json(bundle / item["path"])
                except RuntimeFailure as exc:
                    resource["not_decoded"] = "Not valid UTF-8 JSON; kept as opaque verified resource"
                    resource["diagnostic"] = str(exc)
            result["resources"].append(resource)
    try:
        from .espresso import inspect_bundle
        result["portable_backend"] = inspect_bundle(bundle)
    except (ValueError, OSError, ImportError) as exc:
        result["portable_backend"] = {"supported": False, "reason": str(exc)}
    return result


def entrypoint(model: Model, bundle: Path) -> Path:
    if model.declaration.get("format") not in ("coreml_compiled", "coreml_package", "coreml_protobuf"):
        raise RuntimeFailure("unsupported_format", "This resource is not a complete public Core ML model/package",
                             format=model.declaration.get("format"))
    firmware_path = model.declaration.get("firmware_path", "")
    if firmware_path.endswith((".mlmodelc", ".mlpackage")) or model.declaration.get("format") == "coreml_package":
        return bundle
    sources = [f["path"] for f in model.files if f["path"].endswith(".mlmodel")]
    if len(sources) == 1:
        return bundle / sources[0]
    if model.declaration.get("format") == "coreml_compiled":
        return bundle
    raise RuntimeFailure("unsupported_format", "Asset is not a complete Core ML model/package", format=model.declaration.get("format"))


def require_coreml_host() -> None:
    if platform.system() != "Darwin":
        raise RuntimeFailure("backend_unavailable", "Core ML inference requires macOS; this host is " +
                             platform.system() + " " + platform.machine(),
                             required="macOS with CoreML and Xcode Command Line Tools",
                             note="iOS-compiled bundles may still be incompatible on macOS; no result is substituted")
    if shutil.which("xcrun") is None:
        raise RuntimeFailure("backend_unavailable", "Install Xcode Command Line Tools (xcode-select --install)")


def coreml_runner(cache: Path) -> Path:
    require_coreml_host()
    source = Path(__file__).with_name("CoreMLRunner.swift")
    if not source.is_file():
        raise RuntimeFailure("backend_unavailable", f"Missing packaged Swift backend: {source}")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()[:20]
    target = cache / "backends" / ("coreml-" + source_hash)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".coreml-build-", dir=target.parent)
    os.close(fd)
    temporary = Path(temp_name)
    try:
        environment = os.environ.copy()
        environment.setdefault("MACOSX_DEPLOYMENT_TARGET", "13.0")
        completed = subprocess.run(["xcrun", "swiftc", "-O", str(source), "-o", str(temporary)],
                                   text=True, capture_output=True, env=environment)
        if completed.returncode:
            raise RuntimeFailure("backend_build_failed", "Swift backend did not compile", stderr=completed.stderr)
        temporary.chmod(0o700)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def coreml(model: Model, bundle: Path, cache: Path, *, inputs: dict | None = None,
           compute: str = "cpu") -> dict:
    require_coreml_host()
    model_path = entrypoint(model, bundle)
    if model.declaration.get("format") == "coreml_package" and model_path.suffix != ".mlpackage":
        raise RuntimeFailure("package_path_requires_import", "Import this package first to give its working directory the .mlpackage extension")
    runner = coreml_runner(cache)
    request = {"action": "inspect" if inputs is None else "predict", "model_path": str(model_path),
               "compute": compute, "inputs": inputs}
    completed = subprocess.run([str(runner)], input=json.dumps(request, allow_nan=False),
                               text=True, capture_output=True)
    try:
        response = json.loads(completed.stdout)
    except ValueError as exc:
        raise RuntimeFailure("backend_protocol_error", "Swift backend did not return JSON", stderr=completed.stderr,
                             exit_code=completed.returncode) from exc
    if completed.returncode or "error" in response:
        raise RuntimeFailure(response.get("error", "coreml_failed"), response.get("message", "Core ML load/prediction failed"),
                             backend="coreml", diagnostics=completed.stderr)
    return response | {"model_id": model.id, "manifest_fingerprint": model.fingerprint,
                       "backend": "coreml", "artifact_identity": "selected firmware asset",
                       "compatibility": "load accepted by this host; no claim about other macOS or hardware"}


def portable(model: Model, bundle: Path, inputs: dict) -> dict:
    from .espresso import predict_bundle
    try:
        response = predict_bundle(bundle, inputs)
    except (ValueError, OSError) as exc:
        raise RuntimeFailure("portable_backend_rejected", str(exc)) from exc
    return response | {"model_id": model.id, "manifest_fingerprint": model.fingerprint,
                       "artifact_identity": "selected firmware asset"}


def protobuf_cpu(model: Model, bundle: Path, inputs: dict) -> dict:
    try:
        from .protobuf_cpu import predict_file
    except ImportError as exc:
        raise RuntimeFailure("backend_unavailable", "Install optional CPU dependencies: pip install '.[cpu]'", diagnostic=str(exc)) from exc
    if model.declaration.get("format") not in ("coreml_protobuf", "coreml_package"):
        raise RuntimeFailure("unsupported_format", "CPU protobuf backend needs an uncompiled .mlmodel or .mlpackage")
    files = [bundle / f["path"] for f in model.files if f["path"].endswith(".mlmodel")]
    if len(files) != 1:
        raise RuntimeFailure("unsupported_format", "Expected exactly one protobuf entrypoint")
    try:
        response = predict_file(files[0], inputs)
    except (ValueError, OSError, KeyError, IndexError, TypeError, ArithmeticError) as exc:
        raise RuntimeFailure("portable_backend_rejected", str(exc)) from exc
    return response | {"model_id": model.id, "manifest_fingerprint": model.fingerprint,
                       "artifact_identity": "selected firmware asset"}
