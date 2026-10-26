#!/usr/bin/env python3
"""Independently verify all local inventory hashes, layouts and UAF locators."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import plistlib
import subprocess


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument('--hash-images', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    folder = root / 'models'
    manifest = json.loads((folder / 'manifest.json').read_text())
    summary = json.loads((folder / 'summary.json').read_text())
    assets = {r['id']: r for r in map(json.loads, (folder / 'assets.jsonl').open())}
    resources = {r['id']: r for r in map(json.loads, (folder / 'resources.jsonl').open())}
    references = list(map(json.loads, (folder / 'references.jsonl').open()))
    checked, checked_bytes, used, metadata_declarations = {}, 0, set(), 0

    def verify_file(path, size, sha):
        nonlocal checked_bytes
        path = path.resolve()
        if path not in checked:
            actual_size, actual_sha = path.stat().st_size, digest(path)
            checked[path] = (actual_size, actual_sha)
            checked_bytes += actual_size
        assert checked[path] == (size, sha), f'wrong bytes: {path}'

    for asset in assets.values():
        assert asset['availability'] == 'local_extracted', f'missing bytes: {asset["id"]}'
        assert asset['size_bytes'] == asset['source']['expected_size'], asset['id']
        verify_file(pathlib.Path(asset['local_path']), asset['size_bytes'], asset['sha256'])
    mids = set()
    for model in manifest['models']:
        assert model['id'] not in mids, model['id']
        mids.add(model['id'])
        source_path = (root / model['source_path']).resolve()
        assert source_path.is_relative_to(root), model['source_path']
        assert model['file_count'] == len(model['files']) == len(model['asset_ids']), model['id']
        assert model['total_size_bytes'] == sum(f['size'] for f in model['files']), model['id']
        for file in model['files']:
            path = (source_path / file['path']).resolve()
            assert path.is_relative_to(source_path), file['path']
            asset = assets[file['asset_id']]
            assert asset['model_id'] == model['id'], asset['id']
            assert asset['bundle_relative_path'] == file['path'], asset['id']
            assert (asset['size_bytes'], asset['sha256']) == (file['size'], file['sha256']), asset['id']
            verify_file(path, file['size'], file['sha256'])
            assert file['asset_id'] not in used, file['asset_id']
            used.add(file['asset_id'])
        for field in ('architecture', 'interface', 'function'):
            source = model[field].get('evidence_asset_id')
            if source:
                assert source in model['asset_ids'], source
                metadata_declarations += 1
    assert used == set(assets)

    decoded = {}
    for resource in resources.values():
        path = pathlib.Path(resource['local_path'])
        verify_file(path, resource['size_bytes'], resource['sha256'])
        decoded[resource['id']] = plistlib.loads(path.read_bytes())
    locators = 0
    for ref in references:
        assert ref['availability'] == 'reference_only' and ref['weights_proven'] is False, ref['id']
        for evidence in ref['evidence']:
            value = decoded[evidence['resource_id']]
            parts = [p.replace('~1', '/').replace('~0', '~') for p in evidence['json_pointer'].split('/')[1:]]
            for part in parts:
                value = value[int(part)] if isinstance(value, list) else value[part]
            observed = parts[-1] if evidence['location'] == 'key' else value
            assert isinstance(observed, str) and ref['identifier'] in observed, evidence
            locators += 1
    assert summary['asset_count'] == summary['local_asset_count'] == len(assets)
    assert summary['model_groups'] == len(manifest['models'])
    assert summary['local_bytes'] == sum(a['size_bytes'] for a in assets.values())
    assert summary['reference_resources'] == len(resources)
    assert summary['unique_reference_identifiers'] == len(references)
    assert summary['reference_occurrences'] == locators
    source_checks = []
    for volume in summary['volumes']:
        inv = pathlib.Path(volume['inventory_path'])
        assert digest(inv) == volume['inventory_sha256'], str(inv)
        if args.hash_images:
            assert digest(pathlib.Path(volume['image_path'])) == volume['image_sha256'], volume['image_path']
        source_checks.append({'volume_id': volume['volume_id'], 'inventory_sha256_verified': True, 'image_sha256_verified': args.hash_images})
    tracked = subprocess.run(['git', '-c', 'safe.directory=' + str(root.parent), '-C', str(root.parent), 'ls-files', '--', root.name + '/models/cache'], capture_output=True, text=True, check=True)
    assert not tracked.stdout.strip(), 'weight cache has tracked files'
    print(json.dumps({'status': 'passed', 'asset_files_verified': len(assets), 'inventory_groups_verified': len(manifest['models']), 'reference_resources_verified': len(resources), 'reference_locators_verified': locators, 'metadata_evidence_links_verified': metadata_declarations, 'bytes_hashed_including_uaf': checked_bytes, 'cache_tracked_files': 0, 'source_checks': source_checks}, indent=2))


if __name__ == '__main__':
    main()
