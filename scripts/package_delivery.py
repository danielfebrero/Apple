#!/usr/bin/env python3
"""Package extracted evidence, excluding large reproducible caches and duplicates."""
import hashlib
import json
import pathlib
import sys
import zipfile

root=pathlib.Path(sys.argv[1]).resolve()
exclude_names={'strings_targeted.jsonl','cache_info.json','rootfs-prompt-name-review.json',
    'resource-candidates.jsonl','interface-and-fewshot-candidates.jsonl'}
paths=[]
for p in sorted(root.rglob('*')):
    rel=p.relative_to(root)
    if p.is_symlink() or not p.is_file():
        continue
    if rel.parts[0]=='decoded' or any(x in ('corrected','cache-shadow','__pycache__') for x in rel.parts):
        continue
    if p.suffix in ('.zip','.mtree') or p.name in exclude_names or p.name in ('SHA256SUMS','DELIVERY-SHA256.txt','package-summary.json'):
        continue
    paths.append((p,rel.as_posix()))
sumfile=root/'SHA256SUMS'
with sumfile.open('w') as out:
    for p,rel in paths:
        out.write(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+rel+'\n')
paths.append((sumfile,'SHA256SUMS'))
target=root/'apple-intelligence-24B115.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p,rel in paths:
        z.write(p,rel)
with zipfile.ZipFile(target) as z:
    bad=z.testzip()
if bad:
    raise RuntimeError('ZIP CRC mismatch: '+bad)
digest=hashlib.sha256(target.read_bytes()).hexdigest()
(root/'DELIVERY-SHA256.txt').write_text(digest+'  '+target.name+'\n')
summary={'archive':target.name,'files':len(paths),'bytes':target.stat().st_size,'sha256':digest,'crc_verified':True}
(root/'package-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
