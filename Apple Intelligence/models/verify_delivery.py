#!/usr/bin/env python3
"""Verify every catalogued source; optionally execute the strictly supported CPU graph.

This requires the locally acquired firmware bytes. Missing assets are failures,
not successful/skipped model executions. No network, replacement model or mock.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'runtime'))

from apple_firmware_runtime.backends import portable  # noqa: E402
from apple_firmware_runtime.catalog import Catalog, RuntimeFailure  # noqa: E402
from apple_firmware_runtime.cli import doctor  # noqa: E402
from apple_firmware_runtime.espresso import inspect_bundle  # noqa: E402
from apple_firmware_runtime.store import Store, verify_bundle  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=BASE / 'models/manifest.json')
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--store', type=Path, default=BASE / 'runtime/.state/delivery-store')
    parser.add_argument('--run-cpu', action='store_true')
    args = parser.parse_args()
    catalog = Catalog(args.catalog, args.source_root)
    store = Store(args.store)
    checks, inferences, failed = [], [], False
    for model in catalog.models.values():
        record = {'model_id': model.id, 'format': model.declaration.get('format')}
        try:
            verification = verify_bundle(model, model.source)
            record.update(verified=verification['verified'], files=verification['files'],
                          size_bytes=verification['size_bytes'],
                          manifest_fingerprint=verification['manifest_fingerprint'])
            if args.run_cpu:
                try:
                    support = inspect_bundle(model.source)
                except (ValueError, OSError):
                    support = None
                if support:
                    store.import_model(model)
                    imported = store.verify(model)
                    # Numerical inputs to the actual 62-feature graph, not
                    # examples of a text/entity feature-extraction pipeline.
                    for name, vector in [('zeros', [0] * 62), ('ones', [1] * 62),
                                         ('alternating', [(-1) ** i for i in range(62)])]:
                        inputs = {'x': [vector]}
                        result = portable(model, store.bundle(model), inputs)
                        inferences.append({'case': name, 'inputs': inputs,
                                           'source_integrity': verification,
                                           'imported_integrity': imported,
                                           'prediction_performed': True, 'result': result})
        except (RuntimeFailure, OSError, ValueError) as exc:
            failed = True
            record.update(verified=False, error=str(exc))
        checks.append(record)
    if args.run_cpu and not inferences:
        failed = True
    report = {
        'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'python': sys.version, 'platform': platform.platform(),
        'catalog_sha256': sha256(args.catalog),
        'source_code_sha256': {
            str(path.relative_to(BASE)): sha256(path)
            for path in [Path(__file__), BASE / 'runtime/apple_firmware_runtime/espresso.py',
                         BASE / 'runtime/apple_firmware_runtime/store.py',
                         BASE / 'runtime/apple_firmware_runtime/catalog.py']
        },
        'host': doctor(args.catalog, store),
        'summary': {'groups_checked': len(checks),
                    'groups_verified': sum(x['verified'] for x in checks),
                    'files_verified': sum(x.get('files', 0) for x in checks),
                    'bytes_verified': sum(x.get('size_bytes', 0) for x in checks),
                    'cpu_predictions_performed': len(inferences), 'passed': not failed},
        'source_checks': checks, 'cpu_inferences': inferences,
        'apple_runtime_inference_performed': False,
        'apple_runtime_parity_verified': False,
        'interpretation': 'CPU predictions evaluate authentic Apple weights using the delivered independent graph evaluator. No Apple runtime, text generation, or semantic entity matching is claimed.'
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    print(json.dumps(report['summary'], indent=2))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
