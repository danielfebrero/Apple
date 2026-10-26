#!/usr/bin/env python3
"""Extract selected AI resources, no mount, one APFS process per file."""
import collections, concurrent.futures, hashlib, json, pathlib, re, subprocess, sys
BASE=pathlib.Path(__file__).resolve().parent.parent
IMG=pathlib.Path('/workspace/recherche/apple-sec/ios272rc/_ipsw/rootfs-dec/141-08876-212.dmg')
STRONG=re.compile(r'/System/Library/(?:UnifiedAssetFramework/|ModelManager/|ModelCatalog[^/]*(?:/|$)|PrivateFrameworks/(?:IntelligenceFlowPlannerSupport|FoundationModels|GenerativeModels(?:Foundation)?|GenerativeFunctions(?:Foundation|Instrumentation)?|ModelCatalog(?:Runtime)?|ModelManager[^/]*|TextComposer(?:Runtime)?|TextComposition[^/]*|SummarizationKit|ProactiveSummarization|VisualGeneration|ImageGenerationServices|GenerativeExperiences(?:Runtime)?|WritingTools)[.]framework/)|/usr/libexec/Moments[.]framework/LabelTemplates/', re.I)
CONTEXT=re.compile(r'FoundationModels|GenerativeModels|GenerativeFunctions|ModelCatalog|ModelManager|Genmoji|ImagePlayground|WritingTools|Intelligence(?:Flow|Platform)|VisualGeneration|TextComposer|Summari|Siri|Assistant',re.I)
KEYNAME=re.compile(r'prompt|instruction|grammar|override|safety|guardrail|(?:^|_)template',re.I)
TEXT_SUFFIX={'.json','.plist','.yaml','.yml','.txt','.xml','.config','.loctable','.strings','.stringsdict','.asciipb','.prompt','.template','.jinja','.jinja2','.j2'}
SKIP_SUFFIX={'.png','.jpg','.jpeg','.heic','.car','.metallib','.wav','.caf','.mov','.mp4','.vfx'}
def reason(row):
 p=row['path'];q=pathlib.PurePosixPath(p)
 if row['kind']!=8 or p.startswith('/System/Library/Templates/'):return None
 if '/_CodeSignature/' in p:return None
 if '/Metadata.generativefunctions/' in p or 'GenerativeExperiencesSafetyInferenceProvider.appex/' in p:return 'review_supplement_generativemetadata_or_safety'
 if STRONG.search(p) and q.suffix not in SKIP_SUFFIX:return 'ai_resource_root'
 if q.name=='metadata.json':return 'model_metadata'
 if KEYNAME.search(q.name) and (q.suffix in TEXT_SUFFIX or CONTEXT.search(p)):return 'instruction_filename'
 if CONTEXT.search(p) and q.suffix in TEXT_SUFFIX:return 'ai_context_text'
 if re.search(r'(?:AssetsV2|PreinstalledAssetsV2)/.*(?:UAF|FM[._]|Generative|Intelligence)',p,re.I):return 'ai_asset'
 return None
def extract(r):
 dst=BASE/'extracted/rootfs'/r['path'].lstrip('/');dst.parent.mkdir(parents=True,exist_ok=True)
 cmd=[str(BASE/'scripts/apfs_ai'),'one',str(IMG),str(r['inode']),str(r['private_id']),str(r['size']),str(dst)]
 try:
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
  raw=dst.read_bytes() if dst.exists() else b''
  expected=r['uncompressed_size'] if r['bsd_flags']&32 else r['size']
  r.update(image=IMG.name,volume='RaveB24B115.V57OS',local_path=str(dst.relative_to(BASE)),extraction_rc=p.returncode,extracted_size=len(raw),expected_size=expected,sha256=hashlib.sha256(raw).hexdigest(),size_ok=len(raw)==expected,stderr=p.stderr.strip())
 except Exception as e:r.update(extraction_rc=-1,error=str(e))
 return r
def main():
 rows=[]
 for line in open(BASE/'inventory/rootfs-all.jsonl'):
  r=json.loads(line);why=reason(r)
  if why:r['selection_reason']=why;rows.append(r)
 rows.sort(key=lambda r:(0 if re.search(r'system_prompt|agent_instructions|ToolPrompt|prompts[.]json',r['path']) else 1,r['path']))
 with open(BASE/'inventory/rootfs-selected.jsonl','w') as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 print('Selected',len(rows),'files',sum(r['size'] for r in rows),'bytes',flush=True)
 stats=collections.Counter()
 with open(BASE/'inventory/rootfs-extracted.jsonl','w') as f,concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for n,r in enumerate(pool.map(extract,rows),1):
   f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush()
   stats['ok' if r.get('extraction_rc')==0 and r.get('size_ok') else 'error']+=1
   if n%250==0 or r.get('extraction_rc')!=0 or not r.get('size_ok'):print(n,r['path'],dict(stats),flush=True)
 print('DONE',dict(stats),flush=True)
if __name__=='__main__':main()
