# Exécuter les modèles réellement disponibles

**Complément Debian :** [16 modèles auxiliaires du firmware exécutés](DEBIAN.md),
dont trois nouveaux modèles LSTM/CNN à poids quantifiés après analyse
d'Archive.zip. Six nouvelles entrées/sorties complètent les 24 démonstrations
du premier lot protobuf. Le [backend officiel Core AI Linux](COREAI.md)
exécute aussi les `.aimodel`, avec démonstration distincte sans poids AFM.
Le backend Espresso décrit ci-dessous reste disponible.
Les [chemins d'acquisition AFM](../models/DOWNLOADS.md) distinguent le toolkit
Developer des assets iOS 27 absents.

Ce programme sélectionne les **octets du firmware inventorié**, vérifie leur
SHA-256, les importe dans un stockage local, inspecte leurs descriptions et
appelle un backend explicite. Il ne télécharge aucun modèle de remplacement.

Le premier backend CPU fonctionne sur **EntitySimilarityLinearModel**,
un petit réseau de similarité d'entités adjacent à Apple Intelligence :
62 nombres → couche linéaire → sigmoid. Ses poids proviennent du firmware.
Ce réseau n'est pas le modèle génératif Apple Foundation Models. Les poids
principaux AFM, les téléchargements de la partition de données et le runtime
privé de génération ne sont pas établis dans ce corpus : les prompts seuls
ne permettent pas de lancer Siri ou Writing Tools.

Le backend public Core ML pour macOS charge un `.mlmodelc`, ou compile un
`.mlmodel` / `.mlpackage`, expose `MLModel.modelDescription`, valide les
entrées avec `MLFeatureDescription.isAllowedValue`, puis appelle réellement
`MLModel.prediction(from:)`. **Il n'a pas été compilé ni exécuté sur ce VPS
Linux**, qui ne possède ni Swift ni CoreML. La compatibilité d'un bundle
compilé pour iOS avec macOS reste à tester modèle par modèle. Un échec de
chargement est une erreur explicite, jamais une sortie artificielle.

## Installation locale

Python 3.10 ou ultérieur suffit au catalogue, aux empreintes et au backend
Espresso initial, sans dépendance tierce. Le backend protobuf requiert
`pip install '.[cpu]'` ; Core AI nécessite Python 3.11+ et `.[coreai]`.

```sh
cd '/workspace/Apple/Apple Intelligence/runtime'
python3 -m apple_firmware_runtime doctor
python3 -m apple_firmware_runtime list --search EntitySimilarity
```

Pour installer la commande dans un environnement virtuel :

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/apple-firmware doctor
```

Le chemin du catalogue est déduit de cet arbre avec l'installation modifiable.
Une installation classique de roue requiert `--catalog /chemin/models/manifest.json`
ou `APPLE_FIRMWARE_CATALOG`. Les poids et le catalogue ne sont pas intégrés
à la distribution Python.

Sur macOS, installer les outils Xcode avec `xcode-select --install`.
La première commande Core ML compile le fichier Swift public fourni.
Le déploiement Swift cible macOS 13 par défaut, ou
`MACOSX_DEPLOYMENT_TARGET` lorsqu'il est déjà défini. Chaque modèle peut
requérir une version d'OS ou un matériel plus récent ; Core ML décide de sa
compatibilité réelle.

## Catalogue et import vérifié

Le catalogue est [`../models/manifest.json`](../models/manifest.json).
[`../models/README.md`](../models/README.md) décrit l'extraction reproductible
depuis les images locales et le périmètre d'inventaire. Le cache des poids est
ignoré par Git ; sa présence sur ce VPS ne vaut pas distribution publique.
Voir [`../models/REDISTRIBUTION.md`](../models/REDISTRIBUTION.md).
Depuis un clone public, [`../models/ACQUIRE.md`](../models/ACQUIRE.md) décrit
`acquire.py`, qui retrouve les octets connus depuis des DMG locaux vérifiés,
sans dépendre de l'inventaire APFS privé d'origine.

```sh
python3 -m apple_firmware_runtime list --scope intelligence_adjacent
python3 -m apple_firmware_runtime list --format coreml_protobuf
python3 -m apple_firmware_runtime verify m-39ce2e705a2d140eee12 --source
python3 -m apple_firmware_runtime import m-39ce2e705a2d140eee12
python3 -m apple_firmware_runtime verify m-39ce2e705a2d140eee12
python3 -m apple_firmware_runtime inspect m-39ce2e705a2d140eee12
```

Les IDs sont exacts, obtenus par `list`. `inspect` sans `--load` conserve les
schémas JSON et métadonnées du firmware, ainsi que les limites du catalogue ;
il ne lance aucune prédiction. Les `.espresso.net` opaques restent opaques.
Les ressources non JSON trop volumineuses restent vérifiées sans être décodées.

Le stockage par défaut est `~/.cache/apple-firmware-runtime` ; on peut choisir
`--store /chemin/local` avant la sous-commande, ou définir
`APPLE_FIRMWARE_RUNTIME_STORE`. Les blobs sont adressés par SHA-256 ; les bundles
assemblés utilisent des copies distinctes pour éviter de modifier les blobs.
Chaque lancement recontrôle **tous** les fichiers du modèle. Les fichiers
manquants, symlinks, changements de taille ou de hash et fichiers ajoutés au
bundle importé font échouer la commande. Toute modification du catalogue
requiert un nouvel `import` pour le modèle concerné.

`--source-root` remplace la racine à partir de laquelle sont résolus les
`source_path` relatifs du manifeste, par exemple après copie locale du corpus.
Il ne change pas les hashes attendus. Il n'existe aucun téléchargement implicite.

## Inférence CPU vérifiable sur Linux

```sh
python3 -m apple_firmware_runtime import m-39ce2e705a2d140eee12
python3 -m apple_firmware_runtime predict m-39ce2e705a2d140eee12 \
  --backend espresso-linear-cpu-experimental \
  --input examples/entity-zero.json --output /tmp/entity-result.json
```

Résultat mesuré sur ce VPS avec ce vecteur nul :
`outputs.var_9 = 0.49867087602615356` ; SHA-256 des poids
`a2cde4443ca52b95feb4895c7352d390d59abdd0d55b58081d16c25c0266a0c7`.
Le vecteur de démonstration est une entrée numérique choisie pour vérifier
le calcul, sans prétention de représenter des entités réelles.

Ce backend indépendant calcule les vrais poids décodés et refuse tout autre
graphe, format ou schéma. Son calcul Float64 avec entrées/sortie Float32 n'a
pas été comparé à l'exécution Apple Float16. L'extraction des 62 features
sémantiques n'est pas reconstituée. Détails et limites :
[`ESPRESSO.md`](ESPRESSO.md).

## Core ML sur macOS

Après sélection et import du modèle réel :

```sh
python3 -m apple_firmware_runtime inspect ID_DU_MODELE --load --compute cpu
python3 -m apple_firmware_runtime predict ID_DU_MODELE \
  --backend coreml --input /chemin/entrees.json --compute cpu \
  --output /chemin/resultat.json
```

`ID_DU_MODELE` est à remplacer par un ID retourné par `list`. Le chargement
donne les noms, types et contraintes d'entrée et de sortie de **ce modèle**.
Il n'infère ni prétraitement, ni normalisation, ni labels, ni tokenisation.
Une description d'entrées lisible ne démontre pas que leur sémantique soit connue.

Le fichier d'entrée est un objet JSON dont les clés sont les noms exacts :

- `Double` : nombre fini ; `Int64` : entier, ou chaîne décimale pour préserver
  toute la plage Int64 ; `String` : chaîne.
- `MultiArray` : `{"shape": [1, 62], "data": [0, 0, ...]}` avec données plates,
  le nombre exact d'éléments et la forme acceptée par le modèle. Le type
  numérique vient de la contrainte du modèle. Les booléens et débordements
  numériques sont refusés. Les dimensions doivent être positives ; le transport
  borne chaque tableau à 100 millions d'éléments.
- `Dictionary` : objet JSON avec valeurs numériques et clés chaîne ou
  décimales selon la contrainte. `Sequence` : liste de chaînes ou d'entiers.
- `Image` : `{"image_path": "/chemin/absolu/image.png"}` à la dimension
  par défaut attendue. Le transport ne redimensionne pas l'image ; il décode
  ses pixels avec ImageIO puis utilise la conversion de pixel Core ML.

Le backend refuse les clés supplémentaires, les features obligatoires absentes
et tout type non pris en charge par le transport JSON, notamment les états
persistants. Les tableaux de sortie sont plats avec forme/type ; les Int64
sont des chaînes décimales typées ; les images sont des PNG encodés en base64.
Le transport est synchrone, sans batch ni session de génération récurrente.

Sur Linux, `--backend coreml` renvoie `backend_unavailable` avec le système
et l'architecture réels. Des `.hwx`, poids seuls, graphes MIL bruts et ressources
de tokenisation ne constituent pas une entrée Core ML publique complète :
ils restent importables/vérifiables et ne sont pas proposés comme modèles
génératifs exécutables. Chaque famille conserve son blocage dans le catalogue.

Le [programme FoundationModels système](foundationmodels/README.md) est une
voie distincte, sur un Mac compatible où Apple Intelligence est activé. Il
utilise les actifs gérés par l'OS ; leur identité n'est pas celle des hashes RC.

## Validation et références

```sh
python3 -m unittest discover -s tests -v
```

Les tests vérifient le rejet des erreurs d'intégrité et chemins dangereux,
l'absence de substitution sur Linux et les calculs réels contre des valeurs
de référence calculées séparément à haute précision. Les tests du backend
CPU se sautent explicitement si le corpus réel est absent. Le test de
compilation Swift se saute sur Linux : il ne constitue pas une preuve macOS.

Les API publiques utilisées sont documentées par Apple :
[`MLModel.modelDescription`](https://developer.apple.com/documentation/coreml/mlmodel/modeldescription),
[`MLFeatureDescription`](https://developer.apple.com/documentation/coreml/mlfeaturedescription),
[`isAllowedValue`](https://developer.apple.com/documentation/coreml/mlfeaturedescription/isallowedvalue(_:)),
[`MLMultiArrayShapeConstraint`](https://developer.apple.com/documentation/coreml/mlmultiarrayshapeconstraint),
[`MLSequence`](https://developer.apple.com/documentation/coreml/mlsequence),
et les [limites de prédiction de Core ML Tools](https://apple.github.io/coremltools/docs-guides/source/model-prediction.html).
Sources vérifiées le 26 octobre 2026 ; une API documentée ne prouve pas la
compatibilité d'un asset iOS particulier.
