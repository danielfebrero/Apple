import pathlib,json,hashlib,plistlib,collections
BETA=pathlib.Path('/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g')
RC=pathlib.Path(__file__).resolve().parents[2]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=sorted(p for p in (BETA/'fs_root').rglob('*') if p.is_file())
rows=[]
for p in sorted((RC/'extracted/rootfs').rglob('*')):
 if not p.is_file():continue
 rel=p.relative_to(RC/'extracted/rootfs');q=BETA/'fs_root'/rel
 if not q.is_file():continue
 rows.append({'firmware_path':'/'+str(rel),'beta_path':str(q),'rc_path':str(p.relative_to(RC)),'beta_size':q.stat().st_size,'rc_size':p.stat().st_size,'beta_sha256':digest(q),'rc_sha256':digest(p)})
builds={}
for name,root in [('beta',BETA/'metadata'),('rc',RC/'review')]:
 builds[name]=[]
 for fn in ['BuildManifest.plist','Restore.plist','SystemVersion.plist']:
  p=root/fn;v=plistlib.loads(p.read_bytes());builds[name].append({'path':str(p),'sha256':digest(p),'identity':{k:v[k] for k in ['ProductVersion','ProductBuildVersion','ProductName','SupportedProductTypes'] if k in v}})
x={'counts':{'beta_files':len(files),'beta_empty':sum(p.stat().st_size==0 for p in files),'beta_nonempty':sum(p.stat().st_size>0 for p in files),'rc_extracted_rootfs_files':sum(p.is_file() for p in (RC/'extracted/rootfs').rglob('*')),'intersection_paths':len(rows),'intersection_beta_nonempty':sum(v['beta_size']>0 for v in rows)},'builds':builds,'common_paths':rows,'beta_nonempty_files':[{'path':str(p),'size':p.stat().st_size,'sha256':digest(p)} for p in files if p.stat().st_size>0]}
pathlib.Path('/tmp/apple-beta-fs-comparison.json').write_text(json.dumps(x,ensure_ascii=False,indent=2));print(json.dumps(x['counts']))
