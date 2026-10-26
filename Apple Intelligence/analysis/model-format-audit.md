# Audit indépendant des formats et de l'exécution des modèles

Audit local du 26 octobre 2026, build `24B115`, sans appareil et sans exécution
d'instructions extraites. Sources : inventaire APFS complet de l'OS, inventaire
SystemOS Cryptex, octets extraits par le lecteur APFS existant, puis catalogue
`models/`. Les anciens fichiers `artifacts/ios-firmware/.../fs_root` ne suffisent
pas comme preuve : plusieurs bundles batterie y contenaient des fichiers de
**zéro octet**, alors que l'inventaire APFS indique de vrais graphes et poids.

## Résultat démontré

Une inférence numérique réelle fonctionne sous Linux pour le modèle auxiliaire
`IntelligencePlatformCore.framework/EntitySimilarityLinearModel.mlmodelc`, avec
ses coefficients extraits du firmware. Le backend Python expérimental exécute
strictement sa couche linéaire 62→1 et sa sigmoïde. Six tests d'intégration ont
réussi sur le véritable bundle local : cinq vecteurs numériques de référence,
contrat d'entrée, valeurs extrêmes et refus des corruptions/opérateurs non pris
en charge. Les références numériques ont été recalculées séparément avec une
précision Decimal de 70 chiffres.

Cela ne démontre pas l'exécution d'Apple Foundation Models, de Genmoji ou d'Image
Playground. Le pipeline qui construit les 62 caractéristiques n'est pas
reproduit. La parité avec le runtime Apple n'a pas été mesurée.

## Périmètre des fichiers réellement présents

Le catalogue issu de `models/scan_models.py`, règle de sélection **version 3**,
contient lors de cette revue **3 923 fichiers**, **2 739 917 787 octets**, tous
extraits localement, regroupés en **1 267 unités** : **724 modèles ou programmes
candidats**, **148 ressources de poids** et **395 ressources auxiliaires**.
Ces comptes ont été recalculés à partir du manifeste et des assets, puis
recoupés avec le responsable de l'inventaire final. Les unités incluent des
ressources, vocabulaires, poids et checksums ; leur nombre n'est pas un nombre
de réseaux entraînés indépendants. Les 391 groupes Core ML compilés, 2 groupes
Sound Analysis et 251 ensembles Espresso, ainsi que les modèles spécialisés
audio, vision, batterie, SMS ou classement, sont distincts des poids Foundation
Models téléchargés.

Les fichiers sont décrits individuellement par taille, SHA-256, image, volume,
inode et chemin dans `models/assets.jsonl`. Les poids restent dans le cache
local ignoré par git. Ce catalogue couvre les règles explicites de sélection ;
il ne prétend pas classifier tous les fichiers opaques d'un firmware.

Les deux groupes classés `apple_intelligence` sont des ressources auxiliaires :
le tokenizer mmap du planificateur et un vocabulaire VisualGeneration. Les
80 groupes `intelligence_adjacent` et les 1 185 groupes `firmware_ml` sont
classés selon leurs chemins, sans preuve d'activation. Les 25 sources
`.mlmodel` sont réparties en 20 fichiers autonomes et 5 packages.

Preuves consultables : [synthèse finale](../models/summary.json),
[manifeste](../models/manifest.json),
[vérification de l'inventaire et des pointeurs UAF](../models/evidence/inventory-verification.json)
et [vérification des fichiers et des calculs CPU](../models/evidence/delivery-verification.json).
Chaque rapport décrit son périmètre ; le rapport de livraison publie le
SHA-256 du manifeste contrôlé et doit correspondre au manifeste de la livraison.

| Objet observé | Ce que prouvent les octets | Exécution établie |
| --- | --- | --- |
| `.mlmodel` | Sérialisation Core ML ; des descriptions et des paramètres peuvent être présents. | Lecture du format possible ; conversion/inférence portable générale non validée ici. |
| `.mlpackage` | Modèle et fichiers de poids séparés, avec manifeste. Cinq groupes présents. | Backend Core ML macOS préparé ; aucune exécution macOS dans cette revue Linux. |
| `.mlmodelc` | Bundle compilé : métadonnées, données runtime et, selon le modèle, Espresso ou MIL/poids. | Chargement Apple dépend de la compatibilité de la plateforme ; un sous-ensemble Espresso démontré en CPU indépendant. |
| `.espresso.net` | Certains sont du JSON ; d'autres commencent par `pbze` ou `pbzx`. | Un parseur JSON seul ne couvre pas tous les graphes. |
| `.espresso.weights` | Coefficients/sections binaires réels quand présents. | La table du modèle EntitySimilarity est décodée et validée ; le reste n'est pas automatiquement pris en charge. |
| `model.mil` + `weights/weight.bin` | Programme MIL et paramètres externes ; graphes inspectables. | Aucun interpréteur général MIL Linux ni conversion complète validée. |
| `.hwx` | Programmes compilés pour matériel Apple ; en-tête constaté `cefaefbe`. | Aucun backend ANE sous Linux établi. |
| `metadata.json`, plists UAF, prompts, lexiques | Descriptions de modèles, références d'assets et ressources auxiliaires. | Leur présence seule ne fournit pas un réseau génératif exécutable. |

Une vérification des en-têtes des fichiers du catalogue trouve notamment des
graphes Espresso JSON, 81 graphes marqués `pbze` et 15 marqués `pbzx`. Ces derniers
ne doivent pas être présentés comme du JSON corrompu. Les extensions sont des
indices de conteneur ; l'inventaire conserve aussi les octets magiques.

Une piste examinée, `ghent_classifier.mlpackage`, contient un `.mlmodel` de
25 711 octets et un `weight.bin` de 3 974 octets. Son protobuf annonce la version
de spécification 8 et un ML Program avec opset `CoreML7` ; il n'est donc pas un
simple réseau historique dont la seule extension suffirait à garantir la
conversion. `TTE_Model` est aussi un vrai package avec `Manifest.json`, malgré
l'absence de suffixe `.mlpackage` dans son chemin firmware.

Apple distingue la [représentation ML Program des réseaux historiques](https://apple.github.io/coremltools/docs-guides/source/comparing-ml-programs-and-neural-networks.html)
et sérialise leurs poids séparément. Les [formats pris en charge](https://apple.github.io/coremltools/docs-guides/source/convert-to-ml-program.html)
doivent être respectés au chargement. Installer `coremltools` sous Linux ne
fournit pas le runtime Core ML : son [API de prédiction exige macOS](https://apple.github.io/coremltools/docs-guides/source/model-prediction.html).

## Preuve précise du modèle CPU

Identifiant catalogue : `m-39ce2e705a2d140eee12`.

Chemin APFS :
`/System/Library/PrivateFrameworks/IntelligencePlatformCore.framework/EntitySimilarityLinearModel.mlmodelc/`.

| Fichier | Octets | SHA-256 |
| --- | ---: | --- |
| `model.espresso.weights` | 440 | `a2cde4443ca52b95feb4895c7352d390d59abdd0d55b58081d16c25c0266a0c7` |
| `model.espresso.shape` | 323 | `b3af0c00f15b60e9b416d4d387f424da289ada6987439c8e99ee9bdc802bccf9` |
| `metadata.json` | 1 397 | `66bcf63f6250c74e0ad35712e81383a7851b3c174b5c1926555d048f57601639` |

Le graphe JSON de 777 octets décrit `inner_product`, entrée `x`, `nB=62`,
`nC=1`, `blob_weights=3`, `blob_biases=1`, puis `activation`, `mode=3`, sortie
`var_9`. La correspondance avec la sigmoïde ne repose pas sur une supposition
sur ce numéro privé : les métadonnées déclarent explicitement
`ActivationSigmoid:1` et `InnerProduct:1`. Elles donnent entrée Float32
`[1,62]`, sortie scalaire et stockage Float32.

Le fichier de poids commence par un entier little-endian 64 bits, `4`, suivi de
quatre paires 64 bits `(identifiant, longueur)` : `(0,56), (1,16), (2,48),
`(3,248)`. Les données commencent à l'octet 72. La section 1 fournit le biais
Float32 à l'octet 128, `-0.005316493567079306`. La section 3, à l'octet 192,
fournit exactement 62 coefficients Float32. Les autres zones sont du padding
nul, vérifié par le chargeur.

L'opération calculée est `sigmoid(b + somme(w[i] * x[i]))` : entrée et sortie
arrondies Float32, calcul intermédiaire Float64. Entrée nulle :
`0.49867087602615356`. Entrée composée de 62 uns : `0.6698617339134216`.
La sigmoïde utilise une branche stable qui n'entraîne pas de débordement
exponentiel pour les entrées Float32 finies.

Limite de précision : les métadonnées firmware déclarent
`computePrecision:Float16`. Le résultat du backend indépendant n'est donc pas
présenté comme identique bit à bit à un calcul Apple. Le backend s'appelle
`espresso-linear-cpu-experimental` et expose cette limite dans son résultat.
Il refuse les autres graphes et les poids quantifiés, plutôt que de leur
attribuer une sortie.

Voir [l'implémentation](../runtime/apple_firmware_runtime/espresso.py),
[les tests](../runtime/tests/test_espresso.py) et [le contrat](../runtime/ESPRESSO.md).

## Foundation Models et diffusion : références présentes, poids non établis

`UnifiedAssetFramework/AssetSets/com.apple.modelcatalog.plist` contient
366 noms d'assets distincts, dont 239 sous `com.apple.fm.language.instruct_3b`
et 35 sous `com.apple.fm.language.instruct_300m`. Il référence notamment les
bases `generic`, `generic_sparse`, les modèles de brouillon, tokenizers,
adaptations et préprocesseurs. Il s'agit d'identifiants de souscription et de
résolution d'assets, pas de poids tensoriels.

Empreinte de ce plist extrait :
`fbd703cfc378263a215199c0491868fc6859cddab74b10b93e70f25486b8ef92`.

`UnifiedAssetFramework/AssetSets/com.apple.MobileAsset.UAF.FM.Visual.plist`
référence 18 assets, dont `image_diffusion_v1.base`, `emoji`,
`personalized_emoji`, `messages_backgrounds`, `style_scribble`,
`understanding.conditioning` et `imagescaler.upscaler`. L'alias
`request-resources-key-apple-diffusion-models.plist` relie ces identifiants à
`com.apple.MobileAsset.UAF.FM.Visual`. Ces fichiers prouvent l'existence des
références et de la sélection ; ils ne contiennent pas ces modèles.

Empreinte du plist Visual extrait :
`3f22c9feaae28c8b2dd8d1de87f0f6adbbca2a6b30aa966ed129740302d29a87`.

L'inventaire complet de l'OS ne contient aucun chemin de payload `UAF_FM`.
Les occurrences `UAF.FM` y sont les trois plists de configuration
Overrides/Visual/CodeLM. Les deux volumes inspectés ne comportent aucun
`/System/Library/AssetsV2/`. L'extension SafetyInferenceProvider référence,
dans ses droits d'accès, des emplacements de téléchargement tels que
`/private/var/MobileAsset/AssetsV2/com_apple_MobileAsset_UAF_FM_GenerativeModels/purpose_auto/`
et les variantes `PreinstalledAssetsV2/InstallWithOs`. Ces emplacements sont
des dépendances attendues par le logiciel, pas des données d'appareil extraites
ici. La partition de données téléchargée et les modèles PCC sont hors corpus.

La ressource `IntelligenceFlowPlannerSupport.framework/spiece_mmap.model`
est présente, de 9 454 928 octets, SHA-256
`b2d198014e40d75f2d1e826959f1d2a90b2b32438768ec8984af8561df02fe89`.
Son en-tête `0000000038894d001c1c3f00e89f0300` n'est pas celui d'un
protobuf SentencePiece standard : le tag initial zéro serait invalide.
Son nom et son emplacement suggèrent une ressource tokenizer en mémoire
mappée ; son décodage complet n'a pas été établi. Même un tokenizer complet
ne fournirait pas les matrices de poids du modèle de langage.

L'absence constatée est bornée par ces images et ces chemins : elle n'exclut
pas un modèle sous nom opaque ni un téléchargement ultérieur. Aucun format
des poids AFM ou diffusion effectivement téléchargés n'est inféré à partir
des seuls noms de catalogue.

## Revue des nouveaux chargeurs

Le runtime sépare une inspection statique, un chargeur Core ML macOS et le
petit évaluateur CPU. Le catalogue et le store vérifient taille et SHA-256
des fichiers avant l'appel du backend ; les sorties d'inférence restent
distinctes des déclarations d'architecture et d'interface.

Points signalés à l'auteur du backend pendant cette revue : conserver les
graphes Espresso binaires comme ressources opaques lors de l'inspection,
charger les packages sans suffixe comme des `.mlpackage` complets et utiliser
un `CFMutableData` pour l'encodeur PNG Swift. Ces trois corrections sont
présentes dans les sources revues. Les API Core ML d'image, de
contraintes de forme et de validation des valeurs ont été recoupées avec la
documentation Apple. La compilation et l'exécution du backend Apple ne
peuvent pas être attestées sur cet hôte Linux.

## Acquisition publique et dernière revue

[`models/acquire.py`](../models/acquire.py) reconstruit les chemins de sortie
depuis les trois documents publiés `manifest.json`, `assets.jsonl` et
`summary.json`. La revue a validé un plan complet de 3 923 destinations uniques
et 2 739 917 787 octets, en fournissant une racine d'images fictive : aucun
inventaire privé ni ancien chemin hôte n'est nécessaire pour construire ce
plan. Ce test `--dry-run` ne vérifie aucun octet d'image et n'est pas une preuve
d'extraction.

Pour l'acquisition réelle, le code hache d'abord chaque DMG nécessaire, exige
le hash et la taille publiés, contrôle le volume déclaré par le lecteur APFS,
puis confronte taille et hash de chaque fichier aux métadonnées publiques.
Les sorties utilisent des fichiers temporaires distincts ; seuls les fichiers
vérifiés sont déplacés vers leur destination. Les chemins de traversée et
symlinks sont refusés. Les coordonnées APFS, le mapping des destinations et
les identités des assets sont recoupés entre les trois documents.

Le lecteur Linux x86_64 [`apfs_ai`](../scripts/apfs_ai) est suivi dans git en
mode exécutable `100755`, accompagné de son [source](../scripts/apfs_ai.cpp).
Il dépend des bibliothèques système zlib, bzip2, libstdc++, libgcc, libc et
libm, présentes sur l'hôte de revue. Le clone ne fournit pas les DMG déchiffrés ;
cette condition préalable et la distinction avec les conteneurs AEA sont
expliquées dans [ACQUIRE.md](../models/ACQUIRE.md). Le script n'ajoute aucun
téléchargement de modèle de remplacement.

Le client [FoundationModels système](../runtime/foundationmodels/README.md)
vérifie la disponibilité du modèle géré par l'OS, puis n'annonce un résultat
qu'après succès de `respond(to:)`. Sa documentation distingue les poids gérés
par le Mac des poids identifiés de la RC. Le code et les appels de session
ont été revus à partir de la [documentation Apple](https://developer.apple.com/documentation/foundationmodels/languagemodelsession).
Aucune compilation ni inférence de ce client Apple n'a été réalisée sous
Linux. Aucune nouvelle lacune bloquante de format ou substitution de modèle
n'a été établie lors de cette dernière revue ; les preuves de livraison doivent
être régénérées après toute modification finale du manifeste.
