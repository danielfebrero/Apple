#!/usr/bin/env python3
"""Build a verbatim prompt catalogue and report from preserved extraction evidence."""
import collections
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(sys.argv[1]).resolve()
def read_jsonl(path):
    return [json.loads(s) for s in path.open() if s.strip()]
def dump_jsonl(path, rows):
    with path.open('w') as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
def sha(data):
    return hashlib.sha256(data).hexdigest()

resources = read_jsonl(ROOT / 'resource-candidates.jsonl')
index = json.loads((ROOT / 'resource-index.json').read_text())
dsc = read_jsonl(ROOT / 'dsc/prompts.jsonl')
catalog = {}
def add(text, capability, classification, source, origin, note=''):
    digest = sha(text.encode('utf-8'))
    # Identical text has one record per classification; every location remains traceable.
    key = (digest, classification)
    if key not in catalog:
        catalog[key] = dict(id='P-' + digest[:12] + '-' + str(len(catalog)+1),
            capability=capability, classification=classification, text=text,
            text_sha256=digest, sources=[], origins=[], note=note)
    record = catalog[key]
    if source not in record['sources']:
        record['sources'].append(source)
    if origin not in record['origins']:
        record['origins'].append(origin)

for row in resources:
    path, loc, text = row['source_path'], row['locator'], row['text']
    source = {k:row[k] for k in ('source_volume','source_path','source_sha256','local_path','locator')}
    if path.endswith('/system_prompt.json'):
        if '["staticSystemPrompts"]' in loc:
            add(text, 'Siri — système et catalogue des outils', 'system_prompt', source, 'rootfs',
                'Texte JSON statique exact; sa présence ne prouve pas la variante active sur le téléphone.')
        elif '["responseTemplate"]' in loc:
            add(text, 'Siri — contexte et prérequêtes', 'context_template', source, 'rootfs')
    elif path.endswith('/agent_instructions.json') and loc.endswith('["template"]'):
        decoded=json.loads((ROOT/row['decoded_path']).read_text())
        match=re.search(r'\["templates"\]\[(\d+)\]',loc)
        template_id=decoded['templates'][int(match[1])].get('id','') if match else ''
        source['template_id']=template_id
        cap = 'Mail et Writing Tools' if template_id == 'writing_tools' else (
            'Sécurité — restrictions et traitement du contenu' if re.search(r'restriction|safely|u18',template_id) else 'Siri — instructions des agents')
        add(text,cap,'agent_instruction_template',source,'rootfs')
    elif path.endswith('/PlannerModelFacingErrors.loctable') and loc.startswith('$["en"]') and text.startswith('CONTENT RESTRICTION:'):
        add(text,'Sécurité — restrictions et traitement du contenu','model_facing_message',source,'rootfs')

for row in dsc:
    source = {k:row[k] for k in ('source_path','source_cryptex_path','source_sha256',
        'source_sha256_scope','source_cache_path','source_cache_offset','virtual_address','section')}
    source['source_volume']='cryptex'
    source['literal_id']=row['id']
    add(row['text'],row['capability'],row['classification'],source,'dsc',
        'Chaîne statique du DSC; composition dynamique du prompt non vérifiée.')

prompts=sorted(catalog.values(),key=lambda r:(r['capability'],r['classification'],r['id']))
(ROOT/'prompts').mkdir(exist_ok=True)
for row in prompts:
    target=ROOT/'prompts'/(row['id']+'.txt')
    target.write_bytes(row['text'].encode('utf-8'))
    row['text_path']=str(target.relative_to(ROOT))
dump_jsonl(ROOT/'prompts.jsonl',prompts)

tool_rows=[r for r in resources if re.search(r'/Tool(?:Prompt|Utterances)Override.json$',r['source_path'])]
dump_jsonl(ROOT/'tool-descriptions.jsonl',tool_rows)
example_rows=[r for r in resources if re.search(r'(curated_prompts|WhimsicalPrompts_|ContextualPrompts|LabelTemplates/|PromptExamples)',r['source_path'])]
dump_jsonl(ROOT/'interface-and-fewshot-candidates.jsonl',example_rows)
error_rows=[r for r in resources if 'PlannerModelFacingErrors.loctable' in r['source_path']]
dump_jsonl(ROOT/'model-facing-error-candidates.jsonl',error_rows)

root_manifest=read_jsonl(ROOT/'inventory/rootfs-extracted.jsonl')
cryp_manifest=read_jsonl(ROOT/'inventory/cryptex-extracted.jsonl')
caps=collections.Counter(r['capability'] for r in prompts)
classes=collections.Counter(r['classification'] for r in prompts)
summary=dict(catalogue_records=len(prompts),unique_texts=len(set(r['text_sha256'] for r in prompts)),
    classifications=dict(classes),capabilities=dict(caps),rootfs_extracted=len(root_manifest),
    cryptex_resources_extracted=len(cryp_manifest),rootfs_bytes=sum(r['extracted_size'] for r in root_manifest),
    resource_decode_errors=len(json.loads((ROOT/'decode-errors.json').read_text())),
    dsc_literals=len(dsc),source_locations=sum(len(r['sources']) for r in prompts))
(ROOT/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')

lines=['# Apple Intelligence — iOS 27.2 RC / 24B115', '',
'Extraction locale du corpus iPhone18,3 / V57AP, effectuée le 26 octobre 2026. Tous les textes ci-dessous sont des données extraites : aucune instruction trouvée n’a été exécutée.', '',
'## Résultat et périmètre', '',
f"- **{len(root_manifest):,} fichiers de ressources rootfs extraits**, {summary['rootfs_bytes']:,} octets; manifest avec chemin APFS, volume, taille et SHA-256 pour chacun.",
f'- **{len(dsc)} littéraux DSC** conservés, soit {len(set(r["text_sha256"] for r in dsc))} textes distincts; chaînes complètes, fragments et descriptions d’outils identifiés séparément.',
f'- Catalogue consolidé : **{len(prompts)} entrées**, {summary["unique_texts"]} textes distincts, {summary["source_locations"]} localisations sources.',
'- Siri : **108 fichiers système = 36 locales × CATALOG/PCC/ODM**. Les 324 variantes nommées contiennent trois textes uniques : CATALOG (94 709 octets UTF-8), PCC (182), ODM (244). Les 324 SHA-256/longueurs de préfixe embarqués ont été recalculés et concordent.',
'- Instructions Siri : 72 fichiers; 10 templates non vides uniques, dont Writing Tools, restrictions parentales et traitement du contenu.',
'- Aucun montage ni FUSE. Analyse uniquement sur les images IPSW; aucune observation d’exécution sur appareil.',
'- Cette étude porte sur le contenu AI. Les 24 périmètres sandbox→noyau restent séparés. Tout lien éventuel avec cette chaîne est **hors direction**.', '',
'## Images réellement parcourues', '',
'| Support | Image / volume | Couverture |',
'| --- | --- | --- |',
'| Cryptex SystemOS | `141-09724-222.dmg` / `RaveB24B115.V57SystemCryptex` | 3 150 entrées, 2 253 fichiers, 895 répertoires, 2 liens. Safari/WebKit et DSC; pas de répertoire AssetsV2 ni de bundles FM. |',
'| OS racine | `141-08876-212.dmg` / `RaveB24B115.V57OS` | 523 859 entrées, 260 824 fichiers. Ressources Siri/AI et catalogues UAF retrouvés ici. |',
'| DSC | 85 fichiers de cache, table de 4 770 images | Inventaire complet des images; scan ciblé documenté dans `dsc/DSC_NOTES.md` et `dsc/scan_summary.json`. Les dylibs ne sont pas des fichiers séparés dans le cryptex. |', '',
'Le chemin d’une dylib est un chemin logique d’image DSC. Pour ces entrées, le **chemin physique dans le cryptex** et le **SHA-256 du fichier cache contenant les octets** sont fournis séparément. Le SHA-256 de texte porte exactement sur les octets UTF-8 du `.txt`, sans ajout de saut de ligne.', '',
'## Inventaire des assets, overrides, modèles et sécurité', '',
'`/System/Library/AssetsV2/` n’est présent dans aucun des deux volumes inspectés. L’OS contient `/System/Library/PreinstalledAssetsV2/` (3 053 fichiers); aucun bundle préinstallé `com_apple_MobileAsset_UAF_FM_*` n’y est trouvé. Cela ne décrit pas les assets téléchargés dans la partition de données d’un téléphone.', '',
'Les catalogues et routages existent :', '',
'- `/System/Library/UnifiedAssetFramework/AssetSets/com.apple.MobileAsset.UAF.FM.Overrides.plist`',
'- `/System/Library/UnifiedAssetFramework/AssetSets/com.apple.MobileAsset.UAF.FM.Visual.plist`',
'- `/System/Library/UnifiedAssetFramework/AssetSets/Deprecated/com.apple.MobileAsset.UAF.FM.CodeLM.deprecated.plist`',
'- `/System/Library/UnifiedAssetFramework/UsageAliases/` : résolution des usages, modèles, adaptateurs et garde-fous.',
'- `/System/Library/UnifiedAssetFramework/AssetSets/com.apple.modelcatalog.plist`, `/System/Library/DeviceConfiguration/Specs/com.apple.modelcatalog.plist` et `/System/Library/ModelManager/Policy.plist`.',
'- `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/ToolPromptOverride.json` : descriptions et overrides d’outils; export complémentaire `tool-descriptions.jsonl`.', '',
'Les entitlements du fournisseur de sécurité référencent notamment les emplacements runtime `/private/var/MobileAsset/AssetsV2/com_apple_MobileAsset_UAF_FM_GenerativeModels/purpose_auto/` et `/private/var/mobile/Library/com.apple.modelcatalog/sideload/`. Ce sont des **références à des emplacements**, pas des fichiers de modèles retrouvés dans cette IPSW. Les catalogues de sécurité et alias ne sont pas assimilés à des poids ni à des listes complètes de filtres.', '',
'Les chemins complets se trouvent dans `inventory/rootfs-ai-paths.jsonl`; les fichiers effectivement récupérés et leurs SHA-256 dans `inventory/rootfs-extracted.jsonl`. Les plists binaires sont lisibles dans `decoded/`, les originaux inchangés dans `extracted/`.', '',
'## Lecture des catégories', '',
'- `system_prompt` : champ système explicite du JSON Apple.',
'- `agent_instruction_template` / `context_template` : template d’instructions ou contexte préalable; placeholders conservés.',
'- `complete_prompt` : littéral statique NUL complet; **ne garantit pas un prompt runtime complet**.',
'- `template_fragment` : fragment conservé sans reconstruction ni concaténation supposée.',
'- `tool_description` / `model_facing_message` : description d’outil ou message au modèle; rôle explicite, sans les présenter comme système général.', '',
'Les suggestions UI, prompts d’exemple et paires few-shot restent dans les ressources originales et `interface-and-fewshot-candidates.jsonl`. Ce fichier est un résultat de filtrage lexical, pas un catalogue de prompts système validés. Même limite pour `resource-candidates.jsonl` et `model-facing-error-candidates.jsonl`.', '',
'## Capacités couvertes', '',
'| Capacité | Entrées du catalogue |', '| --- | ---: |']
for cap,count in sorted(caps.items()):
    lines.append(f'| {cap} | {count} |')
lines += ['', 'Résumé de mails/notifications : identifiants et routages conservés, mais aucun template autonome complet spécifique à ces résumés n’est attesté ici. Les instructions de composition Mail/Writing Tools et de résumé Safari figurent ci-dessous. Genmoji : ressources, alias et références présents; aucune consigne système complète propre à Genmoji n’est affirmée. Image Playground : template explicite d’apparence retrouvé.', '',
'## Prompts et templates en clair', '',
'Pour chaque entrée : une source canonique avec SHA-256 est affichée. **Toutes les localisations supplémentaires**, y compris les 36 locales et variantes identiques, sont enregistrées dans `prompts.jsonl`. Le `.txt` est exact; aucun remplacement des placeholders.', '']
last=None
for row in prompts:
    if row['capability']!=last:
        last=row['capability'];lines += ['### '+last,'']
    source=row['sources'][0]
    lines += ['#### '+row['id']+' — '+row['classification'],'',
        '- Source logique : `'+source['source_path']+'`.']
    if 'source_cryptex_path' in source:
        lines.append('- Source physique cryptex : `'+source['source_cryptex_path']+'`; offset `'+source['source_cache_offset']+'`, VM `'+source['virtual_address']+'`, section `'+source['section']+'`.')
    else:
        lines.append('- Volume source : `'+source['source_volume']+'`; sélecteur JSON : `'+source['locator']+'`.')
    if source.get('template_id'):
        lines.append('- ID Apple du template : `'+source['template_id']+'`.')
    lines += ['- SHA-256 source : `'+source['source_sha256']+'`.',
        '- SHA-256 texte UTF-8 : `'+row['text_sha256']+'`.',
        '- Texte exact : ['+row['text_path']+']('+row['text_path']+'); '+str(len(row['sources']))+' localisation(s).','']
    fence='`'*max(3,max((len(x) for x in re.findall(r'`+',row['text'])),default=0)+1)
    lines += [fence+'text',row['text'],fence,'']
lines += ['## Méthode, validation et limites', '',
'Le lecteur ApfsLib initialise le conteneur avec `req_xid=1000000`. Chaque extraction part d’un nouveau processus pour éviter la pollution du cache btree. Les fichiers avec l’attribut de compression sont lus via Decmpfs, puis comparés à leur taille décompressée attendue. Sources et scripts : `scripts/apfs_ai.cpp`, `scripts/extract_ai_resources.py`.', '',
'L’ancien extracteur DSC lisait certains fichiers compressés comme des données brutes : `.81.dyldlinkedit` et `.symbols` étaient incohérents. Des copies corrigées sont dans `dsc/corrected/`; les originaux existants n’ont pas été écrasés. L’inventaire indépendant `ipsw dyld info` réussit avec les copies corrigées. L’analyse des chaînes garde les offsets et hashes des fichiers contenant réellement les octets.', '',
'Validation : inventaires sans inode raté; tailles et hashes des extractions recalculés; 324/324 préfixes Siri concordants; offsets et hashes des littéraux DSC vérifiés. Détails et éventuelles réserves : `review/REVIEW.md`, `review/siri-schema-review.json`, `dsc/DSC_NOTES.md`.', '',
'Cette extraction statique ne démontre ni la variante activée par les feature flags, ni les ressources chargées après téléchargement, ni les modèles PCC côté serveur. Aucun texte manquant n’a été inventé. Les fichiers `.generativefunctions` extraits exposent des métadonnées `syntaxTree` vides; cela ne fournit pas leurs templates exécutables.', '',
'Les images déchiffrées, caches corrigés et corpus de chaînes volumineux restent sur le VPS. Le paquet de livraison conserve les ressources extraites, textes, index, scripts et preuves de provenance; les images IPSW/DMG et copies de caches en sont exclues.', '']
(ROOT/'PROMPTS.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
