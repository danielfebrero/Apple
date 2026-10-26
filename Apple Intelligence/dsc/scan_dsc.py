#!/usr/bin/env python3
"""Read cache image table + VM maps without altering sources; collect literal strings."""
import pathlib, struct, mmap, re, json, hashlib, collections, time
ROOT=pathlib.Path('/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115')
OUT=pathlib.Path(__file__).parent
BASE=ROOT/'dyld_shared_cache_arm64e'
handles=[]; maps=[]; caches=[]
for p in sorted(ROOT.glob('dyld_shared_cache_arm64e*')):
    if p.suffix in ['.symbols','.atlas']: continue
    f=p.open('rb'); handles.append(f); m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
    if not m[:16].startswith(b'dyld_v1'): continue
    o,n=struct.unpack_from('<II',m,0x10)
    for i in range(n):
        va,size,off,prot,init=struct.unpack_from('<QQQII',m,o+32*i)
        maps.append((va,va+size,off,p,m))
    caches.append({'file':str(p),'size':len(m),'uuid_hex':m[0x58:0x68].hex(),'mappings':n})
maps.sort(key=lambda x:x[0])
def locate(va,size=1):
    candidates=[q for q in maps if q[0]<=va and va+size<=q[1]]
    if not candidates: raise ValueError('unmapped '+hex(va)+' size '+hex(size))
    # invalid linkedit header duplicates readonly map; keep genuine readonly first
    for q in candidates:
        if '.81.dyldlinkedit' not in q[3].name: return q
    return candidates[0]
def data(va,size):
    q=locate(va,size); off=va-q[0]+q[2]; return bytes(q[4][off:off+size]),q,off
b=BASE.read_bytes();o,n=struct.unpack_from('<II',b,0x1c0)
images=[]
for i in range(n):
    va,mt,ino,po,pad=struct.unpack_from('<QQQII',b,o+32*i)
    name=b[po:b.find(b'\0',po)].decode()
    images.append({'image_path':name,'image_address':hex(va)})
(OUT/'images_all.json').write_text(json.dumps(images,indent=2))
rx=re.compile(r'foundationmodel|generativ|modelmanager|modelcatalog|siri|writingtool|playground|genmoji|emoji|summari',re.I)
extra=json.loads((OUT.parent/'review/dsc-extra-candidates.json').read_text())
extra_names={r['image_path'] for r in extra}
targets=[r for r in images if rx.search(r['image_path']) or r['image_path'] in extra_names]
(OUT/'images_targeted.json').write_text(json.dumps(targets,indent=2))
# ASCII runs retain exact offsets and embedded newlines. UTF8 pass complements them.
pattern=re.compile(rb'[\x09\x0a\x0d\x20-\x7e]{4,}')
sections=[];errors=[];touched=set();count=0
with (OUT/'strings_targeted.jsonl').open('w') as out:
    for image in targets:
        va=int(image['image_address'],16)
        try:
            hdr,_,_=data(va,32); magic,cpu,sub,filetype,ncmd,sz,flags,res=struct.unpack('<8I',hdr)
            if magic!=0xfeedfacf: raise ValueError('MachO magic '+hex(magic))
            cmds,_,_=data(va+32,sz); cur=0
            for k in range(ncmd):
                cmd,csize=struct.unpack_from('<II',cmds,cur)
                if cmd==0x19:
                    segname=cmds[cur+8:cur+24].split(b'\0')[0].decode();ns=struct.unpack_from('<I',cmds,cur+64)[0]
                    for si in range(ns):
                        x=cur+72+si*80; sect=cmds[x:x+16].split(b'\0')[0].decode();seg=cmds[x+16:x+32].split(b'\0')[0].decode(); addr,size=struct.unpack_from('<QQ',cmds,x+32)
                        if sect not in ['__cstring','__const','__oslogstring','__swift5_reflstr','__objc_methname','__objc_classname']: continue
                        if size==0:continue
                        raw,q,off=data(addr,size); touched.add(q[3]);sec={'image_path':image['image_path'],'segment':seg,'section':sect,'vm_address':hex(addr),'size':size,'source_cache_path':str(q[3]),'source_cache_offset':hex(off)};sections.append(sec)
                        seen=set()
                        def emit(rel,blob,encoding):
                            global count
                            if (rel,encoding) in seen:return
                            seen.add((rel,encoding));s=blob.decode(encoding)
                            rec={**sec,'source_cache_offset':hex(off+rel),'virtual_address':hex(addr+rel),'length_bytes':len(blob),'encoding':encoding,'nul_delimited':(rel == 0 or raw[rel-1] == 0) and (rel+len(blob)==len(raw) or raw[rel+len(blob)]==0),'text':s}
                            out.write(json.dumps(rec,ensure_ascii=False)+'\n');count+=1
                        for hit in pattern.finditer(raw):emit(hit.start(),hit.group(),'ascii')
                        # Full UTF8 literals where non-ASCII exists; do not claim random binary runs.
                        start=0
                        for part in raw.split(b'\0'):
                            if len(part)>=4 and any(x>=128 for x in part):
                                try:
                                    s=part.decode('utf-8')
                                    if sum(c.isprintable() or c in '\n\r\t' for c in s)/len(s)>.98 and sum(c.isalpha() for c in s)>2:emit(start,part,'utf-8')
                                except UnicodeDecodeError:pass
                            start+=len(part)+1
                cur+=csize
        except Exception as e:errors.append({'image_path':image['image_path'],'error':str(e)})
        print('scanned',image['image_path'],flush=True)
sha={}
for p in sorted(touched):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    sha[str(p)]=h.hexdigest()
(OUT/'source_sha256.json').write_text(json.dumps(sha,indent=2))
(OUT/'sections_targeted.json').write_text(json.dumps(sections,indent=2))
(OUT/'scan_summary.json').write_text(json.dumps({'all_image_count':len(images),'targeted_image_count':len(targets),'section_count':len(sections),'string_count':count,'errors':errors,'source_cache_files_hashed':len(sha),'caches':caches},indent=2))
print('DONE',len(targets),len(sections),count,'errors',errors,flush=True)
