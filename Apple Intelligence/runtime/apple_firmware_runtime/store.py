"""Content-addressed local import with verification before every backend invocation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from .catalog import Model, RuntimeFailure


def digest_file(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            h.update(block)
    return size, h.hexdigest()


def require_regular(root: Path, relative: str) -> Path:
    """Refuse symlinks, including symlink parents, rather than following outside the bundle."""
    if root.is_symlink():
        raise RuntimeFailure("unsafe_file", f"Bundle root is a symlink: {root}")
    current = root
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            raise RuntimeFailure("unsafe_file", f"Symlink in asset path: {current}")
    if not current.is_file():
        raise RuntimeFailure("missing_file", f"Required asset is missing: {current}")
    return current


def verify_bundle(model: Model, root: Path, *, exact: bool = False) -> dict:
    expected = {f["path"] for f in model.files}
    total = 0
    for item in model.files:
        path = require_regular(root, item["path"])
        try:
            size, sha = digest_file(path)
        except OSError as exc:
            raise RuntimeFailure("asset_unreadable", f"Cannot read {path}: {exc}") from exc
        if size != item["size"] or sha != item["sha256"]:
            raise RuntimeFailure("integrity_mismatch", f"Asset differs from catalogue: {path}",
                                 expected_size=item["size"], actual_size=size,
                                 expected_sha256=item["sha256"], actual_sha256=sha)
        total += size
    if exact:
        actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if not p.is_dir()}
        if actual != expected:
            raise RuntimeFailure("unexpected_files", "Imported bundle contains undeclared files",
                                 unexpected=sorted(actual - expected), missing=sorted(expected - actual))
    return {"verified": True, "model_id": model.id, "files": len(expected), "size_bytes": total,
            "manifest_fingerprint": model.fingerprint, "root": str(root)}


class Store:
    def __init__(self, root: Path):
        self.root = root.expanduser().absolute()

    def bundle(self, model: Model) -> Path:
        return self.root / "bundles" / model.id / self.bundle_name(model)

    @staticmethod
    def bundle_name(model: Model) -> str:
        path = model.declaration.get("firmware_path", "")
        if model.declaration.get("format") == "coreai_asset":
            return "model.aimodel"
        if path.endswith(".mlmodelc") or model.declaration.get("format") == "coreml_compiled":
            return "model.mlmodelc"
        if path.endswith(".mlpackage") or model.declaration.get("format") == "coreml_package":
            return "model.mlpackage"
        return "model"

    def verify(self, model: Model) -> dict:
        receipt = self.root / "bundles" / model.id / "receipt.json"
        try:
            metadata = json.loads(require_regular(receipt.parent, receipt.name).read_text())
        except (OSError, ValueError) as exc:
            raise RuntimeFailure("not_imported", f"Run import for model {model.id}: {exc}") from exc
        if metadata.get("manifest_fingerprint") != model.fingerprint:
            raise RuntimeFailure("manifest_changed", "Catalogue declaration changed; re-import the model")
        return verify_bundle(model, self.bundle(model), exact=True)

    def import_model(self, model: Model) -> dict:
        # Verify all sources before making the selected bundle available.
        source_report = verify_bundle(model, model.source)
        destination = self.root / "bundles" / model.id
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{model.id}-", dir=destination.parent))
        try:
            bundle = temporary / self.bundle_name(model)
            bundle.mkdir()
            for item in model.files:
                blob = self.root / "blobs" / "sha256" / item["sha256"][:2] / item["sha256"]
                blob.parent.mkdir(parents=True, exist_ok=True)
                if blob.is_symlink():
                    raise RuntimeFailure("unsafe_file", f"CAS blob is a symlink: {blob}")
                if not blob.exists() or digest_file(blob) != (item["size"], item["sha256"]):
                    fd, temporary_name = tempfile.mkstemp(prefix=".import-", dir=blob.parent)
                    try:
                        with os.fdopen(fd, "wb") as output, require_regular(model.source, item["path"]).open("rb") as source:
                            shutil.copyfileobj(source, output)
                            output.flush()
                            os.fsync(output.fileno())
                        if digest_file(Path(temporary_name)) != (item["size"], item["sha256"]):
                            raise RuntimeFailure("source_changed", "Source changed during import")
                        os.replace(temporary_name, blob)
                    finally:
                        Path(temporary_name).unlink(missing_ok=True)
                target = bundle / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                # Separate inode: modifying a backend's working copy must not modify the CAS.
                shutil.copyfile(blob, target)
            verify_bundle(model, bundle, exact=True)
            receipt = {"model_id": model.id, "manifest_fingerprint": model.fingerprint,
                       "files": model.files, "source_verification": source_report}
            (temporary / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            # Old verified bundle is replaced only after the new one is complete.
            previous = destination.with_name(destination.name + ".previous")
            if previous.exists():
                shutil.rmtree(previous)
            if destination.exists():
                destination.rename(previous)
            try:
                temporary.rename(destination)
            except OSError:
                if previous.exists() and not destination.exists():
                    previous.rename(destination)
                raise
            if previous.exists():
                shutil.rmtree(previous)
            return self.verify(model)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
