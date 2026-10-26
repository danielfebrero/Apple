#!/usr/bin/env python3
"""Cross-check baseline preservation, all image inventories and payload locators."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess

BASE=Path(__file__).resolve().parents[2]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=BASE)
    p.add_argument('--baseline',default='fb0cabba')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    repo=a.root.parent
    old_raw=subprocess.check_output(['git','-c','safe.directory='+str(repo),'-C',str(repo),
                                      'show',a.baseline+':Apple Intelligence/models/assets.jsonl'])
    old={r['id']:r for r in map(json.loads,old_raw.splitlines())}
    new={r['id']:r for r in map(json.loads,(a.root/'models/assets.jsonl').open())}
    summary=json.loads((a.root/'models/summary.json').read_text())
    report=json.loads((a.output.parent/'acquire-all-expanded.json').read_text())
    missing=sorted(set(old)-set(new))
    changed=[key for key in old.keys() & new.keys()
             if (old[key]['size_bytes'],old[key]['sha256'],old[key]['model_id']) !=
                (new[key]['size_bytes'],new[key]['sha256'],new[key]['model_id'])]
    assert not missing and not changed
    assert len(report['files'])==len(new)==summary['asset_count']
    assert report['integrity_verified'] and not report['dry_run']
    assert {r['asset_id'] for r in report['files']}==set(new)
    inputs={name:sha(a.root/'models'/name) for name in
            ['manifest.json','assets.jsonl','summary.json','resources.jsonl','references.jsonl']}
    volumes=[]
    used={(r['source']['volume_id'],r['firmware_path']) for r in new.values()}
    for v in summary['volumes']:
        inv=Path(v['inventory_path'])
        assert sha(inv)==v['inventory_sha256']
        rows=[json.loads(line) for line in inv.open() if line.strip()]
        volumes.append({'volume_id':v['volume_id'],'volume':v['volume'],
                        'entries':len(rows),'failed_inodes':sum(not r['inode_ok'] for r in rows),
                        'selected_files':v['selected_files'],'bytes':v['selected_expected_bytes'],
                        'extraction_errors':v['extraction_errors'],
                        'image_sha256':v['image_sha256'],'image_relative_path':v['image_relative_path'],
                        'downloaded_fm_asset_paths':[r['path'] for r in rows
                         if '/AssetsV2/' in r['path'] and ('UAF_FM' in r['path'] or 'GenerativeModels' in r['path'])]})
    resources=list(map(json.loads,(a.root/'models/resources.jsonl').open()))
    coords,urls,families=[],[],set()
    def walk(x,loc):
        if isinstance(x,dict):
            for key,value in x.items():
                if any(s in key.lower() for s in ['baseurl','relativepath','downloadurl','payloadurl']):
                    coords.append({'key':key,'location':loc,'value':str(value)[:300]})
                if 'com.apple.MobileAsset.UAF.FM.' in key:
                    families.add(key)
                walk(value,loc+'/'+key)
        elif isinstance(x,list):
            for i,value in enumerate(x):
                walk(value,loc+'/'+str(i))
        elif isinstance(x,str) and x.startswith(('http://','https://')):
            urls.append({'location':loc,'url':x})
    for r in resources:
        path=Path(r['local_path'])
        assert sha(path)==r['sha256']
        walk(plistlib.loads(path.read_bytes()),r['firmware_path'])
    coordinates={'resources_scanned':len(resources),'payload_coordinate_fields':coords,
                 'url_strings':urls,'observed_asset_families':sorted(families),
                 'note':'UAF resources only; no inference of authentication or global CDN absence.'}
    (a.output.parent/'uaf-payload-coordinates.json').write_text(json.dumps(coordinates,indent=2)+'\n')
    result={'status':'passed','baseline_commit':a.baseline,'baseline_assets':len(old),
            'baseline_model_groups':1267,'baseline_assets_missing':missing,'baseline_assets_changed':changed,
            'new_files':len(new)-len(old),'new_bytes':summary['local_bytes']-sum(x['size_bytes'] for x in old.values()),
            'final_files':len(new),'final_groups':summary['model_groups'],'final_bytes':summary['local_bytes'],
            'inventory_kinds':summary['inventory_kinds'],'image_count':len(volumes),
            'inventory_entries':sum(v['entries'] for v in volumes),'volumes':volumes,
            'acquire_statuses':dict(collections.Counter(f['status'] for f in report['files'])),
            'metadata_sha256':inputs,'uaf_payload_coordinates_found':len(coords),'uaf_urls_found':len(urls),
            'all_images_hashed_by_scanner':all(v['image_sha256'] for v in volumes),
            'limitations':['Exhaustive for published selectors, not a universal classifier of every opaque firmware blob.',
                           'Catalogue groups include metadata, weights, programs and classical statistical resources; not a count of trained networks.',
                           'Image SHA-256/ZIP CRC do not establish Apple signature-chain validation.',
                           'No device Data partition or PCC models were acquired.']}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['volumes','metadata_sha256','limitations']},indent=2))


if __name__=='__main__':
    main()
