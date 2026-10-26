#!/usr/bin/env python3
"""Account for every DMG in a local IPSW, reusing the two acquired OS images.

Only AEA decryption uses the network (the existing ipsw tool's Apple FCS path).
No key material or decrypter output is included in the published report.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import zipfile


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ipsw', required=True, type=Path)
    p.add_argument('--work', required=True, type=Path)
    p.add_argument('--reader', required=True, type=Path)
    p.add_argument('--ipsw-tool', required=True, type=Path)
    p.add_argument('--report', required=True, type=Path)
    a = p.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    report = {'schema_version': 1, 'ipsw': str(a.ipsw), 'ipsw_size': a.ipsw.stat().st_size,
              'ipsw_sha256': sha(a.ipsw), 'images': [], 'signature_chain_verified': False,
              'note': 'ZIP CRC and SHA-256 establish local identity, not Apple signature validation.'}
    extra = []
    known = {'141-08876-212.dmg.aea': 'rootfs-dec/141-08876-212.dmg',
             '141-09724-222.dmg.aea': 'cryptex-dec/141-09724-222.dmg'}
    with zipfile.ZipFile(a.ipsw) as z:
        manifest_bytes = z.read('BuildManifest.plist')
        manifest = plistlib.loads(manifest_bytes)
        report['build_manifest_sha256'] = hashlib.sha256(manifest_bytes).hexdigest()
        report['build'] = manifest['ProductBuildVersion']
        report['product_version'] = manifest['ProductVersion']
        report['zip_member_count'] = len(z.infolist())
        components = collections.defaultdict(set)
        for identity in manifest['BuildIdentities']:
            for name, entry in identity['Manifest'].items():
                components[entry.get('Info', {}).get('Path', '')].add(name)
        for info in z.infolist():
            if not info.filename.endswith(('.dmg', '.dmg.aea')):
                continue
            row = {'member': info.filename, 'zip_size': info.file_size,
                   'zip_crc32': f'{info.CRC:08x}', 'components': sorted(components[info.filename])}
            report['images'].append(row)
            if info.filename in known:
                image = a.ipsw.parent / known[info.filename]
                row.update(status='previously_acquired', image_path=str(image),
                           image_size=image.stat().st_size, image_sha256=sha(image))
                continue
            if Path(info.filename).name != info.filename:
                raise ValueError('Unexpected nested DMG member')
            source = a.work / info.filename
            # Always compare the ZIP stream's hash; zipfile also checks its CRC.
            h = hashlib.sha256()
            with z.open(info) as f:
                for block in iter(lambda: f.read(8 << 20), b''):
                    h.update(block)
            row['member_sha256'] = h.hexdigest()
            if not source.is_file() or source.stat().st_size != info.file_size or sha(source) != h.hexdigest():
                temporary = source.with_suffix(source.suffix + '.partial')
                with z.open(info) as f, temporary.open('wb') as out:
                    shutil.copyfileobj(f, out, 8 << 20)
                if sha(temporary) != h.hexdigest():
                    raise ValueError('ZIP copy hash mismatch')
                temporary.replace(source)
            row['source_path'] = str(source)
            image = source
            if source.suffix == '.aea':
                folder = a.work / (source.name.removesuffix('.dmg.aea') + '-dec')
                folder.mkdir(exist_ok=True)
                image = folder / source.name.removesuffix('.aea')
                if not image.is_file():
                    try:
                        r = subprocess.run([str(a.ipsw_tool), 'fw', 'aea', '-o', str(folder), str(source)],
                                           capture_output=True, timeout=300)
                        row['decryption_exit_code'] = r.returncode
                    except subprocess.TimeoutExpired:
                        row.update(status='decryption_timeout')
                        continue
                    if r.returncode or not image.is_file():
                        row.update(status='decryption_failed', diagnostic='ipsw AEA failed; key material omitted')
                        continue
            with image.open('rb') as f:
                prefix = f.read(32)
            if b'IM4P' in prefix:
                folder = a.work / (source.stem + '-im4p')
                folder.mkdir(exist_ok=True)
                image = folder / source.name
                if not image.is_file():
                    r = subprocess.run([str(a.ipsw_tool), 'img4', 'im4p', 'extract',
                                        '--output', str(image), str(source)], capture_output=True, timeout=180)
                    row['im4p_exit_code'] = r.returncode
                    if r.returncode or not image.is_file():
                        row.update(status='im4p_extraction_failed')
                        continue
                row['container'] = 'IM4P; unencrypted APFS payload extracted by ipsw'
                with image.open('rb') as f:
                    prefix = f.read(32)
            row.update(image_path=str(image), image_size=image.stat().st_size,
                       image_sha256=sha(image), magic_hex=prefix.hex())
            inventory = a.work / (image.name + '-inventory.jsonl')
            with inventory.open('w') as out:
                try:
                    r = subprocess.run([str(a.reader), 'inventory', str(image)], stdout=out,
                                       stderr=subprocess.PIPE, text=True, timeout=180)
                except subprocess.TimeoutExpired:
                    row.update(status='inventory_timeout')
                    continue
            diagnostic = a.work / (image.name + '-inventory.stderr')
            diagnostic.write_text(r.stderr)
            row.update(inventory_exit_code=r.returncode, inventory_path=str(inventory),
                       inventory_sha256=sha(inventory), diagnostic=r.stderr[-2000:])
            match = re.search(r'volume=(.*?) sealed=', r.stderr)
            if r.returncode or not match or 'failed' in r.stderr.lower():
                row.update(status='inventory_failed')
                continue
            rows = [json.loads(line) for line in inventory.open() if line.strip()]
            row.update(status='inventoried', volume=match[1], entries=len(rows),
                       regular_files=sum(x['kind'] == 8 for x in rows))
            extra.append({'id': 'ipsw_' + image.name.split('.')[0].replace('-', '_'),
                          'volume': match[1], 'inventory_path': str(inventory), 'image_path': str(image)})
            print(info.filename, row['status'], row.get('entries'), flush=True)
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    (a.work / 'extra-volumes.json').write_text(json.dumps(extra, indent=2) + '\n')
    print(json.dumps({x['member']: x['status'] for x in report['images']}, indent=2))


if __name__ == '__main__':
    main()
