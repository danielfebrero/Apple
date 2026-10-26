#!/usr/bin/env python3
"""Decode extracted Apple resources without modifying evidence; retain provenance."""
import argparse
import base64
import hashlib
import json
import pathlib
import plistlib
import re

SIGNALS = re.compile(r"\{\{[^\n]{1,200}?\}\}|you are\b|your (?:task|role|goal)\b|(?:system|instruction|prompt|template|grammar|guardrail|safety|summari[sz]|rewrite)", re.I)
NATURAL = re.compile(r"you are\b|your (?:task|role|goal)\b|\{\{[^\n]{1,200}?\}\}|(?:summarize|rewrite|generate|do not|don't|respond|return|translate|extract)\b", re.I)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def safe_json(obj):
    if isinstance(obj, bytes):
        try:
            return {"$bytes_utf8": obj.decode("utf-8")}
        except UnicodeDecodeError:
            return {"$bytes_base64": base64.b64encode(obj).decode()}
    if isinstance(obj, dict):
        return {str(k): safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [safe_json(v) for v in obj]
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)

def leaves(obj, location="$"):
    if isinstance(obj, dict):
        for key, val in obj.items():
            yield from leaves(val, location + "[" + json.dumps(str(key), ensure_ascii=False) + "]")
    elif isinstance(obj, list):
        for idx, val in enumerate(obj):
            yield from leaves(val, location + "[" + str(idx) + "]")
    elif isinstance(obj, str):
        yield location, obj

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=pathlib.Path)
    args = ap.parse_args()
    root = args.root.resolve()
    extracted = root / "extracted"
    decoded = root / "decoded"
    decoded.mkdir(exist_ok=True)
    entries, candidates, errors = [], [], []
    for path in sorted(extracted.rglob("*")):
        if not path.is_file():
            continue
        volume_rel = path.relative_to(extracted)
        volume = volume_rel.parts[0]
        rel = pathlib.Path(*volume_rel.parts[1:])
        data = path.read_bytes()
        if data[:4] in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf"):
            continue
        evidence = {"source_volume": volume, "source_path": "/" + rel.as_posix(), "source_sha256": digest(data),
                    "local_path": str(path.relative_to(root)), "size": len(data)}
        obj = None
        kind = "binary"
        if data.startswith(b"bplist") or b"<plist" in data[:512]:
            try:
                obj = safe_json(plistlib.loads(data))
                kind = "plist"
            except Exception as ex:
                errors.append({**evidence, "error": "plist: " + str(ex)})
        if obj is None:
            try:
                text = data.decode("utf-8-sig")
                if "\x00" in text:
                    raise UnicodeDecodeError("utf8", data, 0, 1, "NUL in text")
                kind = "text"
                try:
                    obj = json.loads(text)
                    kind = "json"
                except (ValueError, TypeError):
                    obj = text
            except UnicodeError:
                pass
        if obj is not None:
            target = decoded / volume / (rel.as_posix() + ".json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
            evidence["decoded_path"] = str(target.relative_to(root))
            for locator, value in leaves(obj):
                path_hint = re.search(r"(?:prompt|instruction|grammar)", str(rel), re.I)
                if len(value) < 8 or not (SIGNALS.search(value) or SIGNALS.search(locator) or (path_hint and len(value) >= 40)):
                    continue
                label = "instruction_candidate" if len(value) >= 40 and NATURAL.search(value) else "reference_or_configuration"
                candidates.append({**evidence, "locator": locator, "kind": label,
                                   "text_sha256": digest(value.encode("utf-8")), "text": value})
        entries.append({**evidence, "format": kind})
    (root / "resource-index.json").write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
    with (root / "resource-candidates.jsonl").open("w") as out:
        for row in candidates:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    (root / "decode-errors.json").write_text(json.dumps(errors, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"resources":len(entries), "candidates":len(candidates), "instruction_candidates":sum(c["kind"]=="instruction_candidate" for c in candidates), "errors":len(errors)}))

if __name__ == "__main__":
    main()
