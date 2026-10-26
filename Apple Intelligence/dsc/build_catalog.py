#!/usr/bin/env python3
import json, pathlib, hashlib, re, collections
P=pathlib.Path(__file__).parent
rs=[json.loads(l) for l in (P/'long_candidates.jsonl').open()]
selected=set(range(0,41))|set(range(44,67))|{89,98}|set(range(101,116))|set(range(145,148))|set(range(187,190))|{193}|set(range(194,230))|set(range(234,238))|set(range(239,252))|set(range(253,283))|{284,285}|set(range(287,289))|set(range(290,311))|{312,346}|set(range(347,354))|{357}
# Static literals can be assembled dynamically; these obvious partials are not standalone prompts.
fragments=set([0,*range(22,34),46,47,52,54,101,102,*range(109,116),187,188,*range(194,207),208,209,210,211,212,213,218,219,220,221,222,223,224,228,239,240,241,242,243,244,245,250,260,261,262,263,264,265,266,267,268,269,270,271,272,273,274,275,276,277,278,279,280,281,282,287,288,291,292,294,295,296,297,299,300,303,309,310,349,353])
tooldesc={89,214,217,235,236,237,242,285,296,297,298,302,303,308,309,310,347,348,349,353}
sha=json.loads((P/'source_sha256.json').read_text())
def capability(name):
 if name.startswith('TextComposer'):return 'Mail et Writing Tools'
 if name=='FoundationModels':return 'Foundation Models — refus et outils'
 if name.startswith('Photos'):return 'Photos — Memories et recherche'
 if name=='FitnessIntelligence':return 'Fitness — coaching entraînement'
 if name=='AssistantActionSuggestionCore':return 'Siri — suggestions et résumés de conversations'
 if name=='IntelligenceFlowRuntime':return 'Siri — conversations et titres'
 if name=='_CoreSpotlight_FoundationModels':return 'Spotlight — recherche multi-agents'
 if name=='GenerativeAgents':return 'Agents — transfert de contrôle'
 if name=='GenerativeAgentsEvaluation':return 'Agents — évaluation et simulation'
 if name=='GenerativeAssistantActions':return 'Siri — assistant externe et outils'
 if name=='ImagePlaygroundInternal':return 'Image Playground — apparence et styles'
 if name=='SummarizationKit':return 'Safari — résumé de titres'
 if name=='CallIntelligenceRuntime':return 'Appels — attente et position dans la file'
 return 'Vision — cadre multimodal'
records=[];keys=set()
def add(r,cls):
 key=(r['source_cache_path'],r['source_cache_offset'],r['text'])
 if key in keys:return
 keys.add(key);name=r['image_path'].split('/')[-1];ident='DSC-%04d'%(len(records)+1);data=r['text'].encode(r['encoding']);textsha=hashlib.sha256(data).hexdigest()
 f=P/'prompts'/f'{ident}.txt';f.parent.mkdir(exist_ok=True);f.write_bytes(data)
 rec={**r,'id':ident,'capability':capability(name),'classification':cls,'source_path':r['image_path'],'source_cryptex_path':'/System/Library/Caches/com.apple.dyld/'+pathlib.Path(r['source_cache_path']).name,'source_sha256':sha[r['source_cache_path']],'source_sha256_scope':'entire_source_cache_file','text_sha256':textsha,'text_path':str(f),'literal_completeness':'complete_NUL_delimited_static_literal' if r['nul_delimited'] else 'printable_run_fragment','runtime_composition_verified':False}
 records.append(rec)
for i in sorted(selected):
 cls='tool_description' if i in tooldesc else ('template_fragment' if i in fragments else 'complete_prompt')
 add(rs[i],cls)
# Include remaining exact small chat-template literals and concise instructional wrappers.
for line in (P/'strings_targeted.jsonl').open():
 r=json.loads(line);s=r['text']
 if len(s)>=40 and r['nul_delimited'] and ('{{ specialToken.' in s or s.startswith('system<n>')):add(r,'template_fragment')
with (P/'prompts.jsonl').open('w') as f:
 for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
with (P/'fragments.jsonl').open('w') as f:
 for r in records:
  if r['classification']=='template_fragment':f.write(json.dumps(r,ensure_ascii=False)+'\n')
# Model catalog instruction IDs and asset keys are evidence of routing, not prompt contents.
references=[];keys=set()
rr=re.compile(r'com\.apple\.MobileAsset\.UAF\.FM|com\.apple\.gm\.|com\.apple\.modelcatalog|prompt(?:Content)?Templates|promptCatalog|instructionCatalog|\.(?:json|grammar|template)$',re.I)
for line in (P/'strings_targeted.jsonl').open():
 r=json.loads(line)
 if rr.search(r['text']) and len(r['text'])<600:
  k=(r['image_path'],r['source_cache_offset'])
  if k in keys:continue
  keys.add(k);r['source_sha256']=sha[r['source_cache_path']];r['source_cryptex_path']='/System/Library/Caches/com.apple.dyld/'+pathlib.Path(r['source_cache_path']).name;r['classification']='code_reference';references.append(r)
with (P/'asset_and_instruction_references.jsonl').open('w') as f:
 for r in references:f.write(json.dumps(r,ensure_ascii=False)+'\n')
summary={'prompt_literal_count':len(records),'classifications':dict(collections.Counter(r['classification'] for r in records)),'capabilities':dict(collections.Counter(r['capability'] for r in records)),'instruction_asset_reference_count':len(references),'text_bytes':sum(r['length_bytes'] for r in records),'static_literal_warning':'Complete NUL-delimited strings do not prove the complete runtime system prompt; no dynamic concatenation reconstructed.'}
(P/'catalog_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
