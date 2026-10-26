# Modèles et ressources réellement présents — iOS 27.2 RC / 24B115

Ce dossier inventorie les **octets présents dans les deux volumes locaux**, et
sépare les références UAF des fichiers de modèles. Les 1 267 groupes du catalogue
sont des unités de stockage : **724 modèles ou programmes candidats, 148 ressources
de poids et 395 ressources auxiliaires**, pas 1 267 réseaux indépendants validés.
L'inventaire ne démontre ni leur activation, ni leur emploi par une fonctionnalité
Apple Intelligence.

Les poids du modèle de langage principal AFM, ses adaptateurs téléchargés et les
modèles serveur PCC ne sont pas présents dans les volumes observés. Les noms
`com.apple.fm.*` et `com.apple.gm.*` du catalogue sont conservés comme **références
seules**. Les vrais modèles de batterie, caméra, reconnaissance, audio ou classement
du firmware ne deviennent pas des modèles Apple Intelligence parce qu'ils sont
inventoriés ici.

## Résultat vérifiable

| Volume | Entrées APFS parcourues | Fichiers retenus et extraits | Octets décompressés |
| --- | ---: | ---: | ---: |
| `RaveB24B115.V57OS` | 523 859 | 3 912 | 2 738 846 783 |
| `RaveB24B115.V57SystemCryptex` | 3 150 | 11 | 1 071 004 |
| **Total** | **527 009** | **3 923** | **2 739 917 787** |

Les 3 923 fichiers ont un chemin local réel, une taille conforme à l'inventaire
APFS et un SHA-256 calculé sur leurs octets extraits. Aucune erreur d'extraction.
Les poids restent dans `models/cache/`, ignoré par git. Les manifestes contiennent
les empreintes et localisations, pas les tenseurs.

Le catalogue regroupe notamment 391 bundles Core ML compilés, 2 bundles Sound
Analysis compilés, 251 ensembles Espresso et 25 sources `.mlmodel` (20 fichiers
autonomes et 5 paquets Core ML). Les autres entrées comprennent des programmes
HWX/BNNS, du MIL, des poids opaques, des tableaux NumPy, des tokenizers, des
vocabulaires et des sommes de contrôle. Les totaux exacts par format figurent dans
[`summary.json`](summary.json).

La catégorie `apple_intelligence` ne contient ici que deux **ressources** : le
tokenizer mmap nommé `spiece_mmap.model` du planificateur et un vocabulaire de VisualGeneration.
Le format mmap Apple du premier reste opaque ; sa compatibilité avec un chargeur
SentencePiece protobuf standard n'est pas établie.
`intelligence_adjacent` contient 80 groupes dont le contexte de chemin est pertinent
(EmbeddingCore, CoreSceneUnderstanding, IntelligencePlatformCore, etc.). Les 1 185
autres groupes sont classés `firmware_ml`. Cette classification décrit le chemin,
pas une preuve de rattachement fonctionnel en fonctionnement.

## Fichiers et contrat du catalogue

- [`manifest.json`](manifest.json) : `schema_version: 1`, build, appareil et
  `models[]`. Chaque groupe a un identifiant stable `m-<20 hex>`, `format`, `scope`,
  `inventory_kind`, `firmware_path`, `source_layout`, `source_path` et `files[]`.
  `source_path` est un **dossier relatif à la racine `Apple Intelligence/`** ;
  `files[].path` est relatif à ce dossier. Pour une source `.mlmodel` autonome, le
  dossier parent est la racine et le nom du fichier est conservé dans `files`.
- [`assets.jsonl`](assets.jsonl) : une ligne par fichier réel ; `id`, `model_id`,
  `firmware_path`, `bundle_relative_path`, `local_path` absolu, `size_bytes`, `sha256`,
  `format`, `role`, `scope`, `availability` et provenance APFS (image, volume, inode,
  private_id, taille attendue et drapeaux BSD). `magic_hex` décrit les 16 premiers
  octets, sans constituer une validation de format complète.
- [`resources.jsonl`](resources.jsonl) : les 1 850 plists UAF servant de preuves de
  référence, avec taille et SHA-256 des plists **binaires originales**.
- [`references.jsonl`](references.jsonl) : 650 identifiants uniques, 118 611
  localisations structurées. Chaque localisation contient le `resource_id`, un
  pointeur JSON de la plist décodée et `location: key|value`. Chaque entrée porte
  `availability: reference_only` et `weights_proven: false`. Format, taille et
  SHA-256 du payload restent non établis (`not_established` ou `null`) ; fonction,
  architecture, nombre de paramètres et interface restent inconnus. Un nom
  contenant `3b` ne confirme pas un nombre de paramètres. Les références de
  diffusion, tokenizers, configuration de sécurité et overrides sont distinguées.
- [`summary.json`](summary.json) : comptes, couverture, empreintes des inventaires
  et images source, règles et limites.

`function` est une description déclarée dans les métadonnées lorsqu'elle existe,
sinon un nom de chemin explicitement étiqueté comme tel. `architecture` recopie le
type de modèle, les précisions et histogrammes d'opérateurs déclarés ; elle ne
reconstruit pas une architecture absente. `interface` conserve les schémas
d'entrée/sortie/état et leur `evidence_asset_id`. Une interface non retrouvée reste
`not_available_from_selected_metadata`. `blockers` décrit les dépendances de
chargement et les limites de l'inventaire ; les résultats d'inférence du runtime
doivent être établis séparément.

## Exemples concrets

Tous les chemins ci-dessous sont des chemins du volume OS, dont les octets locaux
se trouvent sous `models/cache/rootfs/` avec la même arborescence.

| Identifiant | Chemin firmware | Format / octets du groupe |
| --- | --- | --- |
| `m-39ce2e705a2d140eee12` | `/System/Library/PrivateFrameworks/IntelligencePlatformCore.framework/EntitySimilarityLinearModel.mlmodelc` | Core ML compilé ; 8 fichiers, 3 749 octets |
| `m-55c02bca148033c1af01` | `/System/Library/PrivateFrameworks/EmbeddingCore.framework/SystemSearch/v8.0.0/md8-text-encoder.mlmodelc` | Core ML compilé ; 75 112 806 octets |
| `m-9609f876e0f519054b2e` | `/System/Library/PrivateFrameworks/EmbeddingCore.framework/SystemSearch/v8.0.0/md8-token-encoder.mlmodelc` | Core ML compilé ; 51 254 314 octets |
| `m-aaf7462e8a414c653e80` | `/System/Library/PrivateFrameworks/EmbeddingCore.framework/cross_encoder_v140_ane_8bit_combined.mlmodelc` | Core ML compilé ; 54 188 848 octets |
| `m-d188c66acc73610da7b4` | `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/spiece_mmap.model` | Tokenizer ; 9 454 928 octets ; aucun poids AFM |
| `m-9bc8b23e34984326c50b` | `/System/Library/PrivateFrameworks/FinHealthCore.framework/ModelResources/assets_WPC_ANALYTICS_OFFLINE_LAB/ghent_classifier/ghent_classifier.mlpackage` | Paquet Core ML source ; 31 417 octets |
| `m-d48a0d552af61b6bdab9` | `/System/Library/Frameworks/MediaToolbox.framework/Trial/assets_311/HLSMLBandwidthPredictor.mlmodel` | Core ML protobuf source ; 1 283 octets |

Exemple de poids réels : `EntitySimilarityLinearModel.mlmodelc/model.espresso.weights`,
440 octets, SHA-256
`a2cde4443ca52b95feb4895c7352d390d59abdd0d55b58081d16c25c0266a0c7`.
Ses métadonnées déclarent une entrée `x` Float32 `[1, 62]`, un produit linéaire et
une activation sigmoïde ; cette déclaration n'est pas à elle seule une mesure
comportementale du modèle dans le système.

## Sources locales et régénération

Images effectivement lues, toujours sans montage :

- OS : `/workspace/recherche/apple-sec/ios272rc/_ipsw/rootfs-dec/141-08876-212.dmg`,
  10 565 451 776 octets, SHA-256
  `3aece1d45bba734e8dfa90c5e1d320b8fa2348a3b023075e7c48df5142839e1d`.
- Cryptex : `/workspace/recherche/apple-sec/ios272rc/_ipsw/cryptex-dec/141-09724-222.dmg`,
  6 325 010 432 octets, SHA-256
  `7bb6bf2d5c568790ed7f08f364683e8889615800bf6da7aa6df1437472788ce7`.

L'inventaire OS complet est resté sur le VPS :
`/workspace/recherche/apple-sec/ios272rc/artifacts/apple-intelligence/inventory/rootfs-all.jsonl`,
SHA-256 `a46baed2752cbdf2a40a84dbb61f9ca34b5e6554d3b155b216a6ba29ae4af523`.
L'inventaire Cryptex versionné a le SHA-256
`4d728bd467f8dd609e0cf980b4ccdcb0dd89a945fa0f078dada6411390b8e2b7`.

Depuis la racine du dépôt :

```sh
python3 'Apple Intelligence/models/scan_models.py' --extract --hash-images
```

`--reextract` force une relecture APFS de chaque fichier, même lorsqu'un cache de
la bonne taille existe. Cette variante a aussi été comparée aux cinq manifestes :
les sorties sont identiques octet pour octet (voir
[`evidence/reproducibility.json`](evidence/reproducibility.json)). Pour vérifier
indépendamment les hashes locaux, les assemblages du catalogue et chaque pointeur
UAF : `python3 'Apple Intelligence/models/verify_inventory.py'` ; résultat conservé
dans [`evidence/inventory-verification.json`](evidence/inventory-verification.json).

`--artifact`, `--firmware-root` et `--reader` permettent de fournir d'autres
emplacements de ces mêmes sources. `--out` doit rester sous la racine
`Apple Intelligence/` pour garder des chemins compatibles avec le runtime ; le
script y ignore automatiquement `cache/`. Sans `--extract`, il inventorie les
fichiers déjà disponibles et marque explicitement les autres `apfs_only` avec
taille/hash locaux nuls. `--hash-images` recalcule les hashes des DMG complets ;
sans cette option, ces champs sont nuls et ne prétendent pas avoir été vérifiés.

Le lecteur APFS `scripts/apfs_ai` et sa source sont déjà dans ce dépôt. Il accepte
`inventory <dmg>` pour régénérer un inventaire complet et `one` pour extraire un
fichier identifié par inode/private_id. La méthode, le checkpoint et le traitement
Decmpfs sont décrits dans [`../inventory/APFS_METHOD.md`](../inventory/APFS_METHOD.md).
Un processus APFS neuf est lancé pour chaque extraction ; seules les tailles
conformes sont acceptées. Le scanner n'utilise pas le `fs_root` Blacksmith dont
certains fichiers sont des stubs de zéro octet.

## Couverture et limites

Les règles parcourent la totalité des **deux inventaires APFS** et retiennent les
bundles Core ML/SoundAnalysis et les paquets spécialisés identifiés, leurs enfants
complets, les fichiers Core ML source, Espresso, HWX, MIL, BNNS, NNET, LSTM, les poids
explicitement nommés, NumPy, tokenizers, vocabulaires et ressources des répertoires explicites `Models`,
`MLModels`, `ModelResources`, `Networks` et `NeuralNetworks`. Le code versionné est la
définition exacte de cette sélection. Les noms `.bin` et `.dat` génériques ne sont
pas classés automatiquement comme des poids : firmware radio, ressources de
l'application et bases de données ont aussi ces suffixes.

Il s'agit d'une couverture complète **des règles explicites**, pas d'une preuve
que chaque blob opaque de l'OS a été classé. Un ensemble Espresso peut avoir des
variantes matérielles ; un paquet peut contenir plusieurs programmes ; un fragment
MIL ou un poids isolé peut dépendre de ressources séparées. La présence d'un
checksum n'est pas celle de son modèle.

`/System/Library/AssetsV2/` est absent des deux inventaires. Les téléchargements de
la partition de données, l'état effectif d'un appareil, les sélections Trial/UAF
actives, l'exécution des moteurs Apple et PCC ne sont pas couverts. La signature
cryptographique Apple des images n'est pas validée ici. Les restrictions de
redistribution et l'absence d'autorisation déduite du firmware sont traitées dans
[`REDISTRIBUTION.md`](REDISTRIBUTION.md).

Quatre URL candidates de catalogues publics MobileAsset ont également été sondées
sur `mesu.apple.com` : les réponses étaient HTTP 403 avec un corps « not found ».
Ces URL étaient déduites de conventions de catalogue, pas observées comme URL de
payload dans le firmware. **Aucun payload n'a été acquis par ces quatre sondes** ;
cela n'établit ni chiffrement, ni authentification nécessaire, ni absence d'autres
canaux. Preuve : [`evidence/public-catalog-probes.json`](evidence/public-catalog-probes.json).

Le chemin public normal pour l'usage du modèle système passe par un appareil et
un OS compatibles, l'activation d'Apple Intelligence et la vérification de l'état
de disponibilité exposé par Foundation Models. L'OS gère l'acquisition des
ressources ; l'API ne constitue pas un export de poids. Les sources officielles
consultées sont conservées dans [`public-sources.json`](public-sources.json).
Voir les [instructions Apple pour activer Apple Intelligence](https://support.apple.com/en-mide/121115).
