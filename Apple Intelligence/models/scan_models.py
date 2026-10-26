#!/usr/bin/env python3
"""Inventory real firmware ML bytes and distinguish UAF references. No mounts.

The default sources are the complete APFS inventories kept on the extraction VPS.
--extract uses the existing read-only APFS reader, one fresh process per file.
Weights stay under ignored models/cache; only manifests belong in git.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import hashlib
import json
import pathlib
import plistlib
import re
import shutil
import subprocess
import sys

BASE = pathlib.Path(__file__).resolve().parents[1]
LAB = pathlib.Path('/workspace/recherche/apple-sec/ios272rc')
ARTIFACT = LAB / 'artifacts/apple-intelligence'
BUNDLE = re.compile(r'(?i)(?:\.mlmodelc(?:\.bundle)?|\.mlpackage|\.espresso\.bundle|\.snmodelc|\.slidernetmodel|\.gecmodel|\.suggestionsmodelassets|\.vimodels|\.mdl|\.model|\.mpsgraphpackage|\.aimodelx?)(?=/|$)')
ESPRESSO = re.compile(r'(?i)\.espresso\.(?:net(?:-e)?|bin|shape|weights|hwx|precompilation_info|md5)(?:\.config)?$')
STANDALONE = re.compile(r'(?i)(?:\.mlmodel|\.model|\.lstm|\.mlmodelc|\.mlmodelc\.zip|\.espresso\.(?:net(?:-e)?|shape|weights|hwx|precompilation_info|md5)(?:\.config)?|\.hwx|\.e5|\.mil(?:\.weights)?|\.bnnsir|\.npy|\.npz|\.onnx|\.gguf|\.safetensors|\.tflite|\.nnet(?:\.bin)?|\.weight\.bin)$')
REFERENCE = re.compile(r'(?:com\.apple\.(?:fm|gm|safety(?:_nsfw)?)\.[A-Za-z0-9_.-]+(?:\?variant=[A-Za-z0-9_.-]+)?|com\.apple\.if\.planner\.nlrouter\.tokenizer(?:\.[A-Za-z0-9_.-]+)?|com\.apple\.mediaanalysis\.aem\.md[0-9]+\.tokenizer(?:\.[A-Za-z0-9_.-]+)?|request-resources-key-apple-diffusion-models)')


def digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def write_json(path: pathlib.Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def write_jsonl(path: pathlib.Path, rows) -> None:
    with path.open('w') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')


def scope(path: str) -> str:
    if re.search(r'(?i)(?:FoundationModels|GenerativeModels|ModelCatalog|VisualGeneration|IntelligenceFlowPlannerSupport|WritingTools)\.framework/|com_apple_MobileAsset_UAF_FM', path):
        return 'apple_intelligence'
    if re.search(r'(?i)(?:EmbeddingCore|CoreSceneUnderstanding|IntelligencePlatform(?:Core)?|IntelligenceFlowRuntime|DocumentUnderstanding|VisualLookUp|TextComposer)\.framework/', path):
        return 'intelligence_adjacent'
    return 'firmware_ml'


def select(rows: list[dict]) -> list[tuple[dict, str]]:
    """Select complete recognized bundles, packages and explicit ML resources.

    .bin/.dat in general are deliberately not treated as ML. Explicit neural
    weight/model names and recognized model-directory children are included.
    """
    bundle_roots = set()
    for row in rows:
        p = row['path']
        m = BUNDLE.search(p)
        if m and row['kind'] == 4:
            bundle_roots.add(p[:m.end()])
        if row['kind'] == 8 and '/Data/com.apple.CoreML/' in p:
            bundle_roots.add(p.split('/Data/com.apple.CoreML/')[0])
    roots = sorted(bundle_roots, key=len, reverse=True)
    extra_roots = [root for root in roots if not BUNDLE.search(root)]
    selected = []
    for row in rows:
        if row['kind'] != 8:
            continue
        p = row['path']
        m = BUNDLE.search(p)
        recognized_root = p[:m.end()] if m and p[:m.end()] in bundle_roots else None
        if recognized_root is None and '/Data/com.apple.CoreML/' in p:
            recognized_root = p.split('/Data/com.apple.CoreML/')[0]
        if recognized_root is None:
            recognized_root = next((root for root in extra_roots if p.startswith(root + '/')), None)
        if recognized_root:
            selected.append((row, recognized_root))
        elif STANDALONE.search(p):
            selected.append((row, ''))
        elif re.search(r'(?i)\.(?:weights|nlembedding|maxent|rcmodel|mpsgraph|espresso\.bin)$|(?:weights?\.bin|weights?description\.json)$', p):
            selected.append((row, ''))
        elif re.search(r'(?i)/(?:[^/]+\.(?:lm|rnnlm|cpml))/|/weights/[^/]+\.bin$|/LinguisticData/[^/]+/AssetData/embedding\.dat$', p):
            # Keep existing IDs/layouts for the already published standalone
            # neural models; add every sidecar instead of regrouping them.
            selected.append((row, ''))
        elif re.search(r'/CoreHandwriting\.framework/diffusion_[^/]+\.(?:json|codemap)$', p):
            selected.append((row, ''))
        elif '/AWD/Metadata/' not in p and re.search(r'(?i)/(?:[^/]*(?:model|classifier|embedding|neural|prediction)[^/]*\.(?:bin|dat|adb|pb)|default_factors_[^/]*\.(?:bin|pb))$', p):
            # Named opaque candidates are retained without claiming a neural
            # architecture. AWD event schemas are explicitly not ML payloads.
            selected.append((row, ''))
        elif re.search(r'(?i)/weights/(?:weight|weights)[.]bin$|/RawSFD/[^/]*weight[.]bin$|/(?:th[.]rnnlm|Japanese[.]lm)/model[.]bin$', p):
            selected.append((row, ''))
        elif re.search(r'(?i)/(?:usr/share/(?:morphun/)?tokenizer/|[^/]*[.]rnnlm/sp[.]model$)|(?:tokenizer[^/]*|[^/]*tokenizer-vocab)[.](?:txt|json|model|index|dat)$', p):
            selected.append((row, ''))
        elif re.search(r'(?i)(?:spiece|sentencepiece)[^/]*[.](?:model|vocab|json)$|/[^/]*vocab[^/]*[.](?:txt|json|trie|bplist|dat)$', p):
            selected.append((row, ''))
        elif re.search(r'(?i)/(?:EmbeddingCore|CoreSceneUnderstanding|IntelligenceFlowPlannerSupport|IntelligenceFlowRuntime|VisualGeneration|DocumentUnderstanding)[.]framework/[^/]*(?:config|vocab|tokeniz)[^/]*[.](?:json|plist|txt|yaml|yml)$', p):
            selected.append((row, ''))
        elif re.search(r'/(?:MLModels|ModelResources|NeuralNetworks|Networks|Models)/', p):
            selected.append((row, ''))
    return selected


def classify(path: str) -> tuple[str, str]:
    p = path.lower()
    name = pathlib.PurePosixPath(p).name
    if p.endswith('.mlmodel'):
        return 'coreml_protobuf', 'model'
    if p.endswith('.mlmodelc'):
        return 'opaque_coreml_compiled_file', 'model'
    if p.endswith('.mlmodelc.zip'):
        return 'zip_coreml_compiled', 'archive'
    if p.endswith('.weights') or p.endswith('.weight.bin') or '/weights/' in p and p.endswith('.bin') or '/rawsfd/' in p and 'weight.bin' in p:
        return 'espresso_weights' if '.espresso.' in p else 'opaque_weights', 'weights'
    if re.search(r'(?i)weights?\.bin$|\.espresso\.bin$', p):
        return 'espresso_weights' if '.espresso.' in p else 'opaque_weights', 'weights'
    if p.endswith(('.nlembedding', '.maxent', '.rcmodel')):
        return 'opaque_model_resource', 'model'
    if p.endswith('.mpsgraph'):
        return 'apple_mpsgraph', 'graph'
    if p.endswith('.hwx'):
        return 'apple_ane_hwx', 'compiled_program'
    if p.endswith('.bnnsir'):
        return 'apple_bnns_ir', 'compiled_program'
    if p.endswith('.e5'):
        return 'apple_e5_metadata', 'metadata'
    if p.endswith('.net') or p.endswith('.net-e'):
        return 'espresso_graph', 'graph'
    if p.endswith('.shape'):
        return 'espresso_shapes', 'shapes'
    if p.endswith('.mil'):
        return 'coreml_mil', 'graph'
    if p.endswith('.npy'):
        return 'numpy_npy', 'weights'
    if any(s in p for s in ('tokenizer', 'spiece', 'sentencepiece')) or name == 'sp.model' or name.startswith('spm_') and name.endswith('.model'):
        return 'tokenizer_resource', 'tokenizer'
    if 'vocab' in name:
        return 'vocabulary_resource', 'vocabulary'
    if p.endswith('.md5'):
        return 'checksum_text', 'checksum'
    if p.endswith('.nnet') or p.endswith('.nnet.bin') or p.endswith('/model.bin') or p.endswith('.lstm'):
        return 'opaque_neural_network', 'model'
    if p.endswith('.model'):
        return 'opaque_model_resource', 'model'
    if name == 'coremldata.bin':
        return 'coreml_runtime_data', 'runtime_data'
    if name.endswith('.dat') and '.mlmodelc' in p or name == 'weight.bin':
        return 'opaque_coreml_data', 'weights'
    if name.endswith('.dat'):
        return 'opaque_model_data', 'resource'
    if name in ('metadata.json', 'manifest.json') or p.endswith(('.json', '.plist', '.config', '.precompilation_info')):
        return 'json_or_plist_metadata', 'metadata'
    return 'opaque_resource', 'resource'


def group_key(row: dict, bundle: str) -> tuple[str, str, str]:
    p = row['path']
    if bundle:
        return bundle, bundle, 'directory'
    m = ESPRESSO.search(p)
    if m:
        stem = re.sub(r'(?i)(?:\.H[0-9A-Z]+|\.E[0-9]+)+$', '', p[:m.start()])
        return 'espresso:' + stem, str(pathlib.PurePosixPath(p).parent), 'sidecars'
    return p, str(pathlib.PurePosixPath(p).parent), 'file'


def model_format(files: list[dict], firmware_path: str, kind: str) -> str:
    formats = {r['format'] for r in files}
    if kind == 'directory' and '.mlmodelc' in firmware_path.lower():
        return 'coreml_compiled'
    if kind == 'directory' and firmware_path.endswith('.snmodelc'):
        return 'soundanalysis_compiled'
    if kind == 'directory' and firmware_path.endswith('.mpsgraphpackage'):
        return 'apple_mpsgraph_package'
    if kind == 'directory' and firmware_path.endswith('.aimodel'):
        return 'coreai_asset'
    if kind == 'directory' and firmware_path.endswith('.aimodelx'):
        return 'coreai_specialized_asset'
    if kind == 'directory' and any(r['format'] == 'coreml_protobuf' for r in files):
        return 'coreml_package'
    if 'coreml_protobuf' in formats:
        return 'coreml_protobuf'
    if 'espresso_graph' in formats:
        return 'espresso'
    if 'apple_ane_hwx' in formats:
        return 'apple_ane_hwx'
    if len(formats) == 1:
        return next(iter(formats))
    return 'mixed_ml_resources'


def declared_model_details(files: list[dict], fmt: str, label: str) -> dict:
    """Copy declared schemas; never infer tensor meaning from a shape alone."""
    architecture = {'status': 'not_established', 'container_format': fmt}
    interface = {'status': 'not_available_from_selected_metadata'}
    function = {'label': label, 'basis': 'path_name_only', 'activation': 'unverified'}
    metadata = next((r for r in files if r['bundle_relative_path'] == 'metadata.json' and r['local_path']), None)
    if metadata:
        try:
            data = json.loads(pathlib.Path(metadata['local_path']).read_text())
            entries = data if isinstance(data, list) else [data]
            entries = [x for x in entries if isinstance(x, dict)]
            if entries:
                architecture = {'status': 'firmware_metadata_declared', 'evidence_asset_id': metadata['id'], 'entries': [{k: x[k] for k in ('modelType', 'specificationVersion', 'storagePrecision', 'computePrecision', 'neuralNetworkLayerTypeHistogram', 'mlProgramOperationTypeHistogram', 'generatedClassName') if k in x} for x in entries]}
                interface = {'status': 'firmware_metadata_declared', 'evidence_asset_id': metadata['id'], 'entries': [{k: x[k] for k in ('inputSchema', 'outputSchema', 'stateSchema', 'method', 'availability') if k in x} for x in entries]}
                description = next((x['shortDescription'] for x in entries if x.get('shortDescription')), None)
                if description:
                    function = {'label': description, 'basis': 'firmware_metadata_description', 'evidence_asset_id': metadata['id'], 'activation': 'unverified'}
        except (OSError, ValueError, TypeError):
            pass
    blockers = []
    if fmt in ('coreml_compiled', 'soundanalysis_compiled'):
        blockers.append('Apple runtime and compatible OS/hardware required for general execution; iOS compiled bundles are not assumed portable to macOS.')
    elif fmt in ('coreml_protobuf', 'coreml_package'):
        blockers.append('Requires a compatible Core ML runtime or a separately verified conversion; inventory does not validate inference.')
    elif fmt == 'espresso':
        blockers.append('Private Espresso operators and weight layout need explicit backend support; a graph/weight pair alone does not validate execution.')
    elif fmt in ('apple_ane_hwx', 'apple_bnns_ir'):
        blockers.append('Compiled Apple-specific program; no portable CPU execution or supported decompilation established.')
    elif fmt in ('tokenizer_resource', 'vocabulary_resource', 'checksum_text', 'espresso_shapes'):
        blockers.append('Auxiliary resource alone; not a complete neural model.')
    else:
        blockers.append('Container or opaque resource requires a separately verified loader and complete dependencies.')
    blockers.append('Activation and end-to-end application behavior are unobserved by this static inventory.')
    return {'function': function, 'architecture': architecture, 'interface': interface, 'blockers': blockers}


def extract_asset(row: dict, volume: dict, bundle: str, args) -> dict:
    firmware_path = row['path']
    cache = args.out / 'cache' / volume['id'] / firmware_path.lstrip('/')
    expected = row['uncompressed_size'] if row['bsd_flags'] & 32 else row['size']
    candidates = [cache, BASE / 'extracted' / volume['id'] / firmware_path.lstrip('/'), args.artifact / 'extracted' / volume['id'] / firmware_path.lstrip('/')]
    local = next((p for p in candidates if p.is_file() and p.stat().st_size == expected), None)
    if args.reextract:
        local = None
    error = None
    if local is not None and args.extract and local != cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, cache)
        local = cache
    if local is None and args.extract:
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_name(cache.name + '.partial')
        try:
            proc = subprocess.run([str(args.reader), 'one', str(volume['image_path']), str(row['inode']), str(row['private_id']), str(row['size']), str(tmp)], capture_output=True, text=True, timeout=180)
            if proc.returncode or not tmp.is_file() or tmp.stat().st_size != expected:
                error = {'returncode': proc.returncode, 'stderr': proc.stderr[-2000:], 'actual_size': tmp.stat().st_size if tmp.is_file() else None}
                tmp.unlink(missing_ok=True)
            else:
                tmp.replace(cache)
                local = cache
        except (OSError, subprocess.TimeoutExpired) as e:
            error = {'error': str(e)}
            tmp.unlink(missing_ok=True)
    fmt, role = classify(firmware_path)
    key, source_root, kind = group_key(row, bundle)
    model_id = 'm-' + identity(volume['id'] + ':' + key)
    relative = str(pathlib.PurePosixPath(firmware_path).relative_to(source_root)) if kind != 'file' or source_root != firmware_path else pathlib.PurePosixPath(firmware_path).name
    result = {
        'id': 'a-' + identity(volume['id'] + ':' + firmware_path), 'model_id': model_id,
        'firmware_path': firmware_path, 'bundle_relative_path': relative,
        'local_path': str(local.resolve()) if local else None,
        'size_bytes': local.stat().st_size if local else None,
        'sha256': digest(local) if local else None,
        'format': fmt, 'role': role, 'scope': scope(firmware_path),
        'availability': 'local_extracted' if local else 'apfs_only',
        'source': {'volume_id': volume['id'], 'volume': volume['volume'], 'image_path': str(volume['image_path']), 'inode': row['inode'], 'private_id': row['private_id'], 'expected_size': expected, 'stored_size': row['size'], 'bsd_flags': row['bsd_flags']},
        'group': {'key': key, 'source_root': source_root, 'kind': kind},
    }
    if local:
        with local.open('rb') as f:
            result['magic_hex'] = f.read(16).hex()
    if error:
        result['extraction_error'] = error
    return result


def references(args) -> tuple[list[dict], list[dict]]:
    sources, refs = [], collections.defaultdict(list)
    root = BASE / 'extracted/rootfs/System/Library/UnifiedAssetFramework'
    for path in sorted(root.rglob('*.plist')):
        try:
            raw = path.read_bytes()
            data = plistlib.loads(raw)
        except (ValueError, OSError, plistlib.InvalidFileException):
            continue
        hits = []

        def walk(value, pointer=''):
            if isinstance(value, dict):
                for key, child in sorted(value.items()):
                    escaped = str(key).replace('~', '~0').replace('/', '~1')
                    child_pointer = pointer + '/' + escaped
                    for match in REFERENCE.finditer(str(key)):
                        hits.append((match.group(), child_pointer, 'key'))
                    walk(child, child_pointer)
            elif isinstance(value, list):
                for i, child in enumerate(value):
                    walk(child, pointer + '/' + str(i))
            elif isinstance(value, str):
                for match in REFERENCE.finditer(value):
                    hits.append((match.group(), pointer, 'value'))

        walk(data)
        if not hits:
            continue
        source_id = 'r-' + identity(str(path.relative_to(BASE)))
        sources.append({'id': source_id, 'local_path': str(path.resolve()), 'firmware_path': '/' + str(path.relative_to(BASE / 'extracted/rootfs')), 'size_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'format': 'apple_plist', 'role': 'reference_only'})
        for name, pointer, location in sorted(set(hits)):
            refs[name].append({'resource_id': source_id, 'json_pointer': pointer, 'location': location})
    records = []
    for name, evidence in sorted(refs.items()):
        kind = 'usage_alias' if name.startswith('request-resources-') else 'configuration' if name.startswith(('com.apple.safety.', 'com.apple.safety_nsfw.')) else 'override' if any(s in name for s in ('.overrides.', '.safety_deny.')) else 'tokenizer' if 'tokenizer' in name else 'adapter_metadata' if 'adapter_metadata' in name else 'model_or_asset_reference'
        records.append({'id': 'ref-' + identity(name), 'identifier': name, 'reference_kind': kind, 'availability': 'reference_only', 'weights_proven': False, 'format': 'not_established', 'size_bytes': None, 'sha256': None, 'function': {'status': 'not_established', 'name_hint': name, 'basis': 'reference_identifier_only'}, 'architecture': {'status': 'not_established', 'parameter_count': None}, 'interface': {'status': 'not_established'}, 'blockers': ['No association between this identifier and an acquired payload has been established.', 'An identifier does not establish neural weights, architecture, parameter count or an executable runtime.'], 'evidence': evidence})
    return sources, records


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact', type=pathlib.Path, default=ARTIFACT)
    p.add_argument('--firmware-root', type=pathlib.Path, default=LAB / '_ipsw')
    p.add_argument('--reader', type=pathlib.Path)
    p.add_argument('--out', type=pathlib.Path, default=BASE / 'models')
    p.add_argument('--extract', action='store_true', help='extract missing files into ignored cache')
    p.add_argument('--reextract', action='store_true', help='force fresh APFS extraction for every selected file, implies --extract')
    p.add_argument('--hash-images', action='store_true', help='hash full source DMGs (additional I/O)')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--extra-volumes', type=pathlib.Path,
                   help='JSON list of additional local APFS volumes: id, volume, inventory_path, image_path')
    args = p.parse_args()
    args.extract = args.extract or args.reextract
    args.out = args.out.resolve()
    if not args.out.is_relative_to(BASE):
        p.error('--out must stay under the Apple Intelligence root; manifest source_path is relative to that root')
    args.reader = args.reader or args.artifact / 'scripts/apfs_ai'
    if args.extract and not args.reader.is_file():
        p.error('--reader must name the existing APFS extraction executable')
    if not 1 <= args.workers <= 16:
        p.error('--workers must be between 1 and 16')
    args.out.mkdir(parents=True, exist_ok=True)
    ignore = args.out / '.gitignore'
    ignore_text = ignore.read_text() if ignore.exists() else ''
    if '/cache/' not in ignore_text.splitlines():
        ignore.write_text(ignore_text.rstrip('\n') + '\n/cache/\n')
    volumes = [
        {'id': 'rootfs', 'volume': 'RaveB24B115.V57OS', 'inventory_path': args.artifact / 'inventory/rootfs-all.jsonl', 'image_path': args.firmware_root / 'rootfs-dec/141-08876-212.dmg'},
        {'id': 'cryptex', 'volume': 'RaveB24B115.V57SystemCryptex', 'inventory_path': BASE / 'inventory/cryptex-all.jsonl', 'image_path': args.firmware_root / 'cryptex-dec/141-09724-222.dmg'},
    ]
    if args.extra_volumes:
        extra = json.loads(args.extra_volumes.read_text())
        if not isinstance(extra, list):
            p.error('--extra-volumes must contain a JSON list')
        seen = {v['id'] for v in volumes}
        for v in extra:
            if not isinstance(v, dict) or not isinstance(v.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]+', v['id']) or v['id'] in seen:
                p.error('invalid or duplicate extra volume ID')
            if not isinstance(v.get('volume'), str) or not v['volume']:
                p.error('extra volume requires the observed APFS volume name')
            for key in ('inventory_path', 'image_path'):
                if not isinstance(v.get(key), str) or not pathlib.Path(v[key]).is_file():
                    p.error(f'extra volume requires a local {key}')
                v[key] = pathlib.Path(v[key])
            seen.add(v['id'])
            volumes.append(v)
    assets, coverage = [], []
    for volume in volumes:
        inv = volume['inventory_path']
        if not inv.is_file():
            p.error(f'complete inventory required: {inv}; partial AI inventories are not a substitute')
        rows = [json.loads(line) for line in inv.open() if line.strip()]
        selected = select(rows)
        total = sum(row['uncompressed_size'] if row['bsd_flags'] & 32 else row['size'] for row, _ in selected)
        print(f"{volume['id']}: {len(rows)} entries, {len(selected)} ML files, {total} expected bytes", file=sys.stderr, flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(lambda pair: extract_asset(pair[0], volume, pair[1], args), selected))
        assets.extend(results)
        coverage.append({'volume_id': volume['id'], 'volume': volume['volume'], 'inventory_path': str(inv.resolve()), 'inventory_sha256': digest(inv), 'inventory_entries': len(rows), 'regular_files': sum(r['kind'] == 8 for r in rows), 'selected_files': len(selected), 'selected_expected_bytes': total, 'local_files': sum(r['availability'] == 'local_extracted' for r in results), 'extraction_errors': sum('extraction_error' in r for r in results), 'image_path': str(volume['image_path'].resolve()), 'image_size_bytes': volume['image_path'].stat().st_size if volume['image_path'].is_file() else None, 'image_sha256': digest(volume['image_path']) if args.hash_images and volume['image_path'].is_file() else None, 'assets_v2_entries': sum('/System/Library/AssetsV2/' in r['path'] for r in rows)})
    assets.sort(key=lambda r: (r['source']['volume_id'], r['firmware_path']))
    for v, item in zip(volumes, coverage):
        try:
            item['image_relative_path'] = str(v['image_path'].resolve().relative_to(args.firmware_root.resolve()))
        except ValueError:
            p.error('all image paths must be under --firmware-root for portable reacquisition')
    grouped = collections.defaultdict(list)
    for row in assets:
        grouped[row['model_id']].append(row)
    models = []
    for mid, files in sorted(grouped.items()):
        group = files[0]['group']
        volume = files[0]['source']['volume_id']
        source_root = group['source_root']
        firmware_path = source_root if group['kind'] == 'directory' else files[0]['firmware_path']
        cache_root = args.out / 'cache' / volume / source_root.lstrip('/')
        all_local = all(r['availability'] == 'local_extracted' for r in files)
        models.append({'id': mid, 'label': pathlib.PurePosixPath(group['key'].removeprefix('espresso:')).name, 'format': model_format(files, firmware_path, group['kind']), 'scope': scope(firmware_path), 'firmware_path': firmware_path, 'volume_id': volume, 'source_path': str(cache_root.relative_to(BASE)) if cache_root.is_relative_to(BASE) else str(cache_root), 'source_layout': group['kind'], 'availability': 'local_extracted' if all_local else 'incomplete', 'file_count': len(files), 'total_size_bytes': sum(r['source']['expected_size'] for r in files), 'asset_ids': [r['id'] for r in files], 'files': [{'asset_id': r['id'], 'path': r['bundle_relative_path'], 'sha256': r['sha256'], 'size': r['size_bytes'], 'format': r['format'], 'role': r['role'], 'local_path': r['local_path']} for r in files]})
        models[-1].update(declared_model_details(files, models[-1]['format'], models[-1]['label']))
        roles = {r['role'] for r in files}
        models[-1]['inventory_kind'] = 'model_or_program' if roles & {'model', 'graph', 'compiled_program'} else 'weight_resource' if 'weights' in roles else 'auxiliary_resource'
    for row in assets:
        row.pop('group')
    resources, refs = references(args)
    write_jsonl(args.out / 'assets.jsonl', assets)
    write_jsonl(args.out / 'resources.jsonl', resources)
    write_jsonl(args.out / 'references.jsonl', refs)
    manifest = {'schema_version': 1, 'build': '24B115', 'device': 'iPhone18,3', 'models': models}
    write_json(args.out / 'manifest.json', manifest)
    summary = {'schema_version': 1, 'build': '24B115', 'device': 'iPhone18,3', 'volumes': coverage, 'asset_count': len(assets), 'local_asset_count': sum(r['availability'] == 'local_extracted' for r in assets), 'local_bytes': sum(r['size_bytes'] or 0 for r in assets), 'model_groups': len(models), 'inventory_kinds': dict(sorted(collections.Counter(r['inventory_kind'] for r in models).items())), 'formats': dict(sorted(collections.Counter(r['format'] for r in models).items())), 'scopes': dict(sorted(collections.Counter(r['scope'] for r in models).items())), 'reference_resources': len(resources), 'unique_reference_identifiers': len(refs), 'reference_occurrences': sum(len(r['evidence']) for r in refs), 'selection_rule_version': 4, 'weights_in_git': False, 'limitations': ['Selection is exhaustive for the explicit rules in scan_models.py, not a proof that every opaque firmware blob is or is not ML.', 'Complete model bundles include resources and runtime data; group counts are packaging units, not independently validated trained networks.', 'intelligence_adjacent is path-based context, not evidence of Apple Intelligence activation.', 'UAF names are references only; no matching downloaded AFM base weights were observed.', 'Only the listed local APFS inventories are covered; data partition downloads and PCC server models are absent.', 'No on-device execution or Apple signature-chain validation.']}
    write_json(args.out / 'summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('asset_count', 'local_asset_count', 'local_bytes', 'model_groups', 'formats', 'unique_reference_identifiers')}, indent=2))
    return int(any(r.get('extraction_errors') for r in coverage))


if __name__ == '__main__':
    raise SystemExit(main())
