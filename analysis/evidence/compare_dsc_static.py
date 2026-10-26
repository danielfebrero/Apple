import pathlib,struct,json,hashlib,collections
BASE=pathlib.Path('/workspace/recherche/apple-sec')
DIRS={'beta':BASE/'ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/dsc','rc':BASE/'ios272rc/_ipsw/dsc-24B115'}
TARGETS={f'/System/Library/PrivateFrameworks/{s}.framework/{s}' for s in ['ModelCatalog','ModelCatalogRuntime','UnifiedAssetFramework','ModelManagerServices']}
def read_at(p,off,n):
 if off<0 or n<0 or n>32*1024*1024 or off+n>p.stat().st_size:raise ValueError('invalid read bounds')
 with p.open('rb') as f:f.seek(off); b=f.read(n)
 if len(b)!=n:raise ValueError('short read')
 return b
def parse(root):
 maps=[]
 for p in sorted(root.glob('dyld_shared_cache_arm64e*')):
  if p.suffix in ['.symbols','.atlas']:continue
  b=read_at(p,0,min(0x240,p.stat().st_size))
  if not b.startswith(b'dyld_v1'):continue
  off,n=struct.unpack_from('<II',b,0x10)
  if n>1000:raise ValueError('map count')
  data=read_at(p,off,n*32)
  for pos in range(0,len(data),32):
   va,size,fo,prot,init=struct.unpack_from('<QQQII',data,pos);maps.append((va,va+size,fo,p))
 def data(va,size):
  ms=[v for v in maps if v[0]<=va and va+size<=v[1]]
  ms.sort(key=lambda v:('.dyldlinkedit' in v[3].name,str(v[3])))
  if not ms:raise ValueError('unmapped '+hex(va))
  lo,hi,off,p=ms[0];return read_at(p,va-lo+off,size),p,va-lo+off
 p=root/'dyld_shared_cache_arm64e';b=read_at(p,0,p.stat().st_size);io,n=struct.unpack_from('<II',b,0x1c0)
 imgs={}
 for pos in range(io,io+32*n,32):
  va,mt,ino,pathoff,_=struct.unpack_from('<QQQII',b,pos);stop=b.find(b'\0',pathoff);path=b[pathoff:stop].decode('utf-8');imgs[path]=va
 results=[];errors=[];sections=[]
 for path in sorted(TARGETS):
  try:
   va=imgs[path];h,_,_=data(va,32);magic,cpu,sub,ft,ncmd,sizeofcmds,flags,res=struct.unpack('<8I',h)
   if magic!=0xfeedfacf:raise ValueError('invalid MachO magic '+hex(magic))
   cmds,_,_=data(va+32,sizeofcmds);pos=0
   for i in range(ncmd):
    cmd,size=struct.unpack_from('<II',cmds,pos)
    if size<8 or pos+size>len(cmds):raise ValueError('invalid command size')
    if cmd==0x19:
     nsects=struct.unpack_from('<I',cmds,pos+64)[0]
     for j in range(nsects):
      s=pos+72+j*80;sect=cmds[s:s+16].split(b'\0',1)[0].decode();seg=cmds[s+16:s+32].split(b'\0',1)[0].decode();addr,nbytes=struct.unpack_from('<QQ',cmds,s+32)
      if sect not in ('__cstring','__oslogstring') or not nbytes:continue
      raw,source,offset=data(addr,nbytes);cursor=0;sections.append({'image_path':path,'section':seg+','+sect,'source_cache_path':str(source),'source_cache_offset':hex(offset),'virtual_address':hex(addr),'size':len(raw),'sha256_section_bytes':hashlib.sha256(raw).hexdigest()})
      for part in raw.split(b'\0'):
       if len(part)>=4:
        try:
         value=part.decode('utf-8')
         if all(c.isprintable() or c in '\n\r\t' for c in value):results.append({'image_path':path,'section':seg+','+sect,'source_cache_path':str(source),'source_cache_offset':hex(offset+cursor),'virtual_address':hex(addr+cursor),'length_bytes':len(part),'text':value})
        except UnicodeDecodeError:pass
       cursor+=len(part)+1
    pos+=size
  except Exception as e:errors.append({'image_path':path,'error':str(e)})
 return {'image_count':len(imgs),'records':results,'sections':sections,'errors':errors}
res={k:parse(v) for k,v in DIRS.items()}
for k,r in res.items():print(k,'images',r['image_count'],'strings',len(r['records']),'errors',r['errors'])
hashes={}
for source in sorted({s['source_cache_path'] for build in res.values() for s in build['sections']}):
 h=hashlib.sha256()
 with open(source,'rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 hashes[source]=h.hexdigest()
for build in res.values():
 for row in build['sections']+build['records']:row['sha256']=hashes[row['source_cache_path']]
p=pathlib.Path('/tmp/apple-beta-dsc-bounded.json');p.write_text(json.dumps(res,ensure_ascii=False,indent=2))
comparison={'method':'read-only dyld mapping and Mach-O section parsing; NUL-delimited UTF-8 printable literals of length >=4; exact text set comparison limited to __cstring and __oslogstring of four identical framework paths','section_comparison':[], 'source_hashes':hashes,'image_counts':{k:v['image_count'] for k,v in res.items()},'parse_errors':{k:v['errors'] for k,v in res.items()}}
for path in sorted(TARGETS):
 beta={r['text'] for r in res['beta']['records'] if r['image_path']==path};rc={r['text'] for r in res['rc']['records'] if r['image_path']==path}
 comparison['section_comparison'].append({'firmware_path':path,'distinct_literals_beta':len(beta),'distinct_literals_rc':len(rc),'common':len(beta&rc),'added':[v for v in res['rc']['records'] if v['image_path']==path and v['text'] in rc-beta],'removed':[v for v in res['beta']['records'] if v['image_path']==path and v['text'] in beta-rc],'sections':{k:[v for v in res[k]['sections'] if v['image_path']==path] for k in res}})
pathlib.Path('/tmp/apple-beta-comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2))
for path in sorted(TARGETS):
 b={r['text'] for r in res['beta']['records'] if r['image_path']==path};r={r['text'] for r in res['rc']['records'] if r['image_path']==path}
 print(path,'beta',len(b),'rc',len(r),'common',len(b&r),'removed',len(b-r),'added',len(r-b))
 for s in sorted(r-b):
  if any(k in s.lower() for k in ['analytics','telemetry','private','sideload','purpose','prompt','consent','usage','catalog','override','policy','safety','server','cloud','identifier','log']):print('ADDED',repr(s)[:500])
 for s in sorted(b-r):
  if any(k in s.lower() for k in ['analytics','telemetry','private','sideload','purpose','prompt','consent','usage','catalog','override','policy','safety','server','cloud','identifier','log']):print('REMOVED',repr(s)[:500])
