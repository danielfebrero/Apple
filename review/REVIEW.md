# Vérification indépendante — Apple Intelligence / 24B115

État final de cette revue, 2026-10-26 UTC. Analyse hors ligne, aucun montage et aucun réseau.

## Identité du corpus

Lecture de `BuildManifest.plist` directement dans l’archive ZIP IPSW : `ProductVersion=27.2`, `ProductBuildVersion=24B115`, `SupportedProductTypes=[iPhone18,3]`, `DeviceClass=v57ap`. Les cinq identités correspondent à cette carte (`ApBoardID=0x08`, `ApChipID=0x8150`). Cela confirme version/build/machine/carte ; l’étiquette commerciale « RC » et le nom commercial « iPhone 17 » ne sont pas établis par ces champs seuls.

SHA-256 de `BuildManifest.plist` extrait : `abba3b0916614585b2213b723cd4e1a34c9939ed3ba839f3fd3fe155179ddc96`.

Preuves : `build-identity.json`, `BuildManifest.plist`, `version-plists.json` et plists de version bruts.

## Frontières des volumes

L’archive comporte 168 entrées ZIP. Aucun chemin direct ne correspond aux termes Apple Intelligence/FoundationModels/Generative/Genmoji/ImagePlayground/WritingTools/MobileAsset/ModelCatalog/JSON/Prompt/Grammar/Override ; il s’agit principalement de conteneurs et de firmware. Cette recherche de noms ne sonde pas le contenu des DMG.

Le manifeste sépare :

| Composant | Fichier ZIP | Taille ZIP décompressée |
| --- | --- | ---: |
| OS racine | `141-08876-212.dmg.aea` | 9 126 805 504 |
| Cryptex SystemOS | `141-09724-222.dmg.aea` | 2 415 919 104 |
| Cryptex AppOS | `141-08824-240.dmg` | 16 777 216 |
| ExclaveOS | `141-08904-234.dmg.aea` | 536 870 912 |
| OS recovery | `141-09644-236.dmg.aea` | 260 046 848 |

Preuves : `ipsw-entries.json`, `ipsw-ai-name-candidates.json`, `build-identity.json`. Les deux fichiers `.mtree` sont des IM4P de type `msys` à payload compressé `pbze`; ils ne sont pas interprétés comme listes de chemins. Ils ne fondent aucune conclusion d’absence.

## Audit de l’inventaire SystemCryptex

L’inventaire `../inventory/cryptex-all.jsonl` contient 3 150 chemins : 2 253 fichiers réguliers, 895 répertoires, deux liens symboliques (`/usr/lib/libstdc++.6.dylib`, `/usr/lib/libstdc++.dylib`). Aucun inode en échec, aucun chemin dupliqué. Le journal ne contient aucune erreur de récursion et identifie `RaveB24B115.V57SystemCryptex`, scellé, `req_xid=1000000`.

SHA-256 de l’inventaire : `4d728bd467f8dd609e0cf980b4ccdcb0dd89a945fa0f078dada6411390b8e2b7`.

Aucun chemin AssetsV2/ModelCatalog/FoundationModels/GenerativeModels/GenerativeFunctions/ModelManager/WritingTools/Genmoji/ImagePlayground dans **cet inventaire SystemCryptex**. La requête plus large prompt/instruction/grammar/safety/override/Siri/Intelligence relève cinq chemins, tous liés à Safari/WebKit ou SiriWave. Les HTML « Prompt » sont des demandes de permission d’extensions et ne constituent pas des prompts de modèle.

Cela ne permet aucune conclusion d’absence dans l’OS racine, dans les assets téléchargés, ni à l’intérieur des images Mach-O du DSC. Preuve calculée : `cryptex-coverage-checks.json`.

## Contrôle de couverture DSC

La première sélection de 219 images sur 4 770 était fondée sur `foundationmodel|generativ|modelmanager|modelcatalog|siri|writingtool|playground|genmoji|emoji|summari`. Elle couvre les noms explicitement demandés mais omet des noms plausiblement utiles, dont `TextComposer`, `TextComposerRuntime`, `TextGeneration`, `TextGenerationInference`, `TokenGenerationInference`, `IntelligenceFlowConversationRuntime`, `PromptKit`, `PrivateMLClientInferenceProvider`, `PhotosIntelligence{,Core}` et `PersonalIntelligenceCore`.

Une liste large de 163 candidats supplémentaires a été transmise à l’agent DSC ; beaucoup sont des faux positifs (safety santé, assistant configuration, etc.). Ce nombre n’est pas un nombre de bibliothèques de prompts. Preuve : `dsc-extra-candidates.json`.

La revue de chaînes a identifié des références littérales `com.apple.MobileAsset.UAF.FM.Overrides`, `.CodeLM`, `.Visual`, `.Overrides.root`, `promptTemplates`, `fallbackPromptTemplateCatalog`, `pgPromptTier1.grammar`, `pgPromptResponseTier1.grammar`. Une référence dans une dylib prouve un identifiant attendu par le code, pas la présence du téléchargement ni son contenu. Preuve avec image/section/offset : `dsc-resource-path-references.json`.

## Audit OS racine et extraction finale

L’OS racine `141-08876-212.dmg`, volume `RaveB24B115.V57OS`, a ensuite été inventorié : **523 859 chemins**, soit 260 824 fichiers réguliers, 260 279 répertoires et 2 756 liens symboliques. Aucun inode raté, aucun doublon de chemin ; journal de parcours sans erreur. Preuve : `rootfs-coverage-final.json` et `../logs/rootfs-inventory.log`.

L’extraction finale contient **9 100 fichiers / 217 709 111 octets**. J’ai relu et recalculé indépendamment **tous** leurs SHA-256 et tailles : aucun écart par rapport à `../inventory/rootfs-extracted.jsonl`, aucun code d’extraction en erreur. 9 088 fichiers portent le flag APFS de compression ; le résultat contrôlé est leur contenu logique décompressé. Preuve : `extraction-integrity-final.json`.

La comparaison avec mes sélections indépendantes a d’abord fait ressortir des fichiers `Metadata.generativefunctions` à noms opaques, et le binaire standalone `GenerativeExperiencesSafetyInferenceProvider`. Ils ont été ajoutés. Les **60** fichiers `Metadata.generativefunctions` contiennent exactement un objet JSON `{"syntaxTree":""}` : aucune instruction textuelle. Le triage des chaînes du binaire safety relève des noms techniques/modèles, aucun texte « You are », placeholder `{{...}}`, prompt ou instruction dans les runs ASCII recherchés. Cela ne prouve pas l’absence de données encodées ni de règles calculées dans le binaire. Preuves : `extraction-integrity-final.json`, `safety-provider-strings-review.json`.

Les autres différences brutes de sélection sont majoritairement des médias d’interface, bibliothèques exécutables, signatures, overrides opérateurs mobiles, tables de vocabulaire emoji, dialogues Siri compilés et modèles statistiques ne constituant pas, par leur nom seul, des templates génératifs. Elles restent documentées dans `extraction-integrity-review.json` ; cette liste d’écarts ne doit pas être présentée comme une liste de prompts manqués.

## Sémantique et déduplication Siri

Les JSON d’`IntelligenceFlowPlannerSupport.framework/asset_root` constituent des preuves directes : clés `staticSystemPrompts`, `staticSystemPromptsToPrefixIDs`, `prerequestMessageTemplates`, `templates[].template`, métadonnées de locale. Les textes sont des données extraites et n’ont jamais été adoptés comme instructions de cet audit.

| Élément | Fichiers | Entrées nommées | Textes uniques |
| --- | ---: | ---: | ---: |
| Systèmes CATALOG/PCC/ODM | 108 | 324 | **3** |
| Instructions d’agent CATALOG/PCC | 72 | 504 | **10 textes non vides** |

Les 108 fichiers système représentent **36 locales × 3 familles**. CATALOG et PCC déclarent chacun quatre noms de variante (`default`, `text_display_direct`, `voice_display`, `voice_voice`) ; ODM seulement `default`. Les textes sont strictement identiques d’une locale à l’autre et entre noms de variante au sein d’une même famille. Ce ne sont donc pas 324 textes système distincts ni 36 traductions.

- CATALOG : **94 244 caractères / 94 709 octets UTF-8**, 1 texte unique.
- PCC : **182 caractères/octets**, 1 texte unique.
- ODM : **244 caractères/octets**, 1 texte unique.

**324/324 identifiants préfixes intégrés correspondent au SHA-256 exact du texte UTF-8.** La longueur CATALOG déclarée `length=94244` est la longueur en caractères et non la taille du fichier ni du texte UTF-8 en octets. Cette cohérence interne renforce la validation de l’extraction ; elle ne démontre pas que chaque famille est active sur le téléphone au moment de l’analyse.

Pour les instructions d’agent : CATALOG contient deux entrées par locale, PCC douze. Sur 504 entrées, **432 portent un texte** et **72 n’ont pas de clé `template`** (`default`, `writing_personalization` dans PCC). Ne pas transformer ces IDs sans texte en prompts récupérés. `platform_base` et `span_match` sont communs aux deux familles, d’où dix textes uniques.

Les templates `platform_base` et `span_match` contiennent des expressions conditionnelles `{%- ... %}` et des substitutions `{{ ... }}`. Les IDs PCC comprennent `knowledge_restriction`, `math_restriction`, `process_content_safely`, les trois `u18_model_guidelines_*`, `writing_restriction`, `writing_tools` et les deux templates communs. Preuves exhaustives : `siri-schema-review.json`, `siri-agent-template-ids.json`.

## Classification par capacité et limites

**Siri / composition de texte.** L’instruction PCC `writing_tools` est bien présente (9 762 caractères), avec des règles de composition pour documents, courriels, messages, notes et insertion de texte, des rubriques Mail/Messages, une personnalisation et des règles de révision. C’est une instruction réelle de composition de Siri ; elle ne suffit pas à identifier le template propre à chaque fonctionnalité du produit Writing Tools. Le template `writing_restriction` (2 375 caractères) et les règles `process_content_safely` sont également récupérés.

**Résumé mail / notifications.** Les configurations de namespaces, les alias UAF et le code DSC attestent de capacités de résumé. Dans l’inventaire rootfs, mes recherches par noms mail/notif/summar/prompt/model ne révèlent pas de fichier de template autonome clairement attribuable au résumé génératif mail/notifications. Beaucoup de « PromptForSender » sont des dialogues vocaux Siri compilés. L’absence de template portant un nom explicite ne permet pas de conclure que cette capacité n’utilise aucun prompt, notamment dans les téléchargements MobileAsset ou le texte construit à l’exécution.

**Image Playground.** Les 55 plists `curated_prompts.plist` contiennent **3 190 entrées de suggestions au total** (58 par fichier), avec catégories, IDs, emoji et noms localisables. Ce sont des choix/suggestions de création, et non des prompts système. Les annotations du fichier montrent des paramètres de personnalisation ; ne pas les confondre avec les instructions internes du modèle.

**Genmoji / visual generation.** Les aliases et asset sets UAF décrivent des ressources visuelles, des filtres et des adaptateurs pour emoji/Genmoji. Les index de `CoreEmoji` constituent principalement du vocabulaire/recherche/localisation ; je n’en déduis aucun prompt système. La présente revue n’établit pas de template système complet propre à Genmoji.

**Photos / Memories.** `WhimsicalPrompts_*.json` représente **23 fichiers / 554 entrées**, `ContextualPrompts.json` **160 entrées**. Schéma : libellé `prompt`, clé de localisation, propriétés musicales/traits ou déclencheur contextuel. Ce sont des suggestions de scénario, pas des identités/règles système. Preuve : `example-classification-review.json`.

**Descriptions d’outils.** `ToolPromptOverride.json` contient **394 IDs d’intents**, chacun avec une `description`. Ce sont des descriptions pour outils/intentions, à conserver comme telle, sans les compter comme 394 prompts système.

**Grammaires.** Les recherches de noms `.grammar`, `.gbnf`, `.bnf`, `.ebnf` ou `grammar*.json/txt/plist` dans le rootfs ne trouvent que `CoreHandwriting.framework/latex_grammar.txt`. Les chaînes DSC citent `pgPromptTier1.grammar` et `pgPromptResponseTier1.grammar`, sans fichier de ce nom découvert dans les deux inventaires. Une grammaire embarquée en section binaire, générée ou téléchargée ne serait pas exclue par ces requêtes.

## Ressources embarquées et téléchargements

Le rootfs contient les **déclarations** UAF `AssetSetConfiguration` pour `com.apple.MobileAsset.UAF.FM.Overrides`, `.FM.Visual` et `.FM.CodeLM` (ce dernier dans `Deprecated`), ainsi que `com.apple.modelcatalog`, `com.apple.summarizationkit` et leurs usages. Le schéma `Assets[].AssetName`, `AutoAssetSpecifierTemplate`, `RequiredUsageTypes`, `MetadataAsset` est une description des ressources et de leur résolution, pas leurs octets.

La recherche de chemins dans les deux inventaires ne trouve aucun `/System/Library/AssetsV2` ni de payload préinstallé dont le chemin contient `UAF.FM`/`UAF_FM`/`GenerativeModels`/`FoundationModels`. Le rootfs utilise notamment `/System/Library/PreinstalledAssetsV2/RequiredByOs` et `/private/var/MobileAsset/PreinstalledAssetsV2/InstallWithOs` pour d’autres familles. Cela borne précisément ce qui est absent **sous ces noms dans ces images** ; cela n’exclut pas une ressource sous nom opaque ou un téléchargement ultérieur.

Les catalogues font apparaître des ressources `safety_deny`, des guardrails et des overrides. Si leur texte n’est pas présent, on peut livrer leurs identifiants et leur raccordement aux capacités, mais pas reconstruire ni inventer leurs filtres ou prompts. Preuves : `rootfs-coverage-final.json`, `ai-capability-content-review.json`, ressources brutes et manifestes d’extraction.

Aucune recherche sandbox→noyau menée. Un croisement éventuel relève de « hors direction ».
