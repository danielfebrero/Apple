"""Small, strict manifest reader. Declared availability is never execution proof."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


class RuntimeFailure(Exception):
    def __init__(self, code: str, message: str, **details: Any):
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict:
        return {"error": self.code, "message": str(self), **self.details}


def safe_relative(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise RuntimeFailure("invalid_manifest", f"Invalid relative path: {context}")
    parts = value.split("/")
    if PurePosixPath(value).is_absolute() or any(p in ("", ".", "..") for p in parts):
        raise RuntimeFailure("invalid_manifest", f"Unsafe relative path: {context}")
    return value


@dataclass(frozen=True)
class Model:
    declaration: dict
    source: Path

    @property
    def id(self) -> str:
        return self.declaration["id"]

    @property
    def files(self) -> list[dict]:
        return self.declaration["files"]

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(self.declaration, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode()).hexdigest()

    def summary(self) -> dict:
        return {k: self.declaration.get(k) for k in
                ("id", "label", "format", "scope", "availability", "firmware_path")} | {
            "file_count": len(self.files), "size_bytes": sum(f["size"] for f in self.files),
            "manifest_fingerprint": self.fingerprint,
        }


class Catalog:
    def __init__(self, path: Path, source_root: Path | None = None):
        self.path = path.resolve()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeFailure("catalog_unreadable", f"Cannot read catalogue {path}: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("models"), list):
            raise RuntimeFailure("invalid_manifest", "Catalogue must have schema_version: 1 and models: []")
        # Manifest source_path is relative to Apple Intelligence/, two directories above models/manifest.json.
        self.root = (source_root or self.path.parent.parent).resolve()
        self.models: dict[str, Model] = {}
        for declaration in raw["models"]:
            if not isinstance(declaration, dict):
                raise RuntimeFailure("invalid_manifest", "Model declaration must be an object")
            model_id = declaration.get("id")
            if not isinstance(model_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", model_id):
                raise RuntimeFailure("invalid_manifest", "Model id must be a safe unique path component")
            if model_id in self.models:
                raise RuntimeFailure("invalid_manifest", f"Duplicate model id: {model_id}")
            source = safe_relative(declaration.get("source_path"), f"{model_id}.source_path")
            files = declaration.get("files")
            if not isinstance(files, list) or not files:
                raise RuntimeFailure("invalid_manifest", f"No declared files for {model_id}")
            seen = set()
            for item in files:
                if not isinstance(item, dict):
                    raise RuntimeFailure("invalid_manifest", f"Invalid file entry for {model_id}")
                rel = safe_relative(item.get("path"), f"{model_id}.files.path")
                if rel in seen:
                    raise RuntimeFailure("invalid_manifest", f"Duplicate file path: {model_id}/{rel}")
                seen.add(rel)
                if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]):
                    raise RuntimeFailure("invalid_manifest", f"Invalid SHA-256 for {model_id}/{rel}")
                size = item.get("size")
                if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                    raise RuntimeFailure("invalid_manifest", f"Invalid size for {model_id}/{rel}")
            self.models[model_id] = Model(declaration, self.root / source)

    def get(self, model_id: str) -> Model:
        try:
            return self.models[model_id]
        except KeyError as exc:
            raise RuntimeFailure("unknown_model", f"Unknown model: {model_id}; run list") from exc
