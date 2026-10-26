# Runtime CPU indépendant sur Debian

## Complément après analyse d'Archive.zip

**16 modèles auxiliaires du firmware ont désormais été exécutés** : les 13
déjà démontrés, plus un LSTM et deux CNN à coefficients uint8. Les trois
nouveaux modèles produisent **six inférences** avec leurs vrais poids ; les
entrées restent des tenseurs synthétiques à zéro/un, sans reconstitution du
prétraitement applicatif. Les preuves historiques ci-dessous sont conservées.

| Modèle et ID | Entrée exacte à zéro | Sortie mesurée |
| --- | --- | --- |
| TTE_Model, `m-42c503b700dcb5d958aa` | `temporal_features` Float32 `[1,19,5]`, `static_features` Float32 `[1,10]` | `var_80` Float32 `[1,19,1]`, débute par `[-1.5703125,-1.9677734375,-2.009765625]` |
| mainModel_USEN, `m-6c123b9c8ab2f00ccad0` | `inp` Float32 `[1,512,1,256]` | `linear_0 = [-0.06349118798971176,-0.1297999620437622,0.19893214106559753]` |
| subClassModel_USEN, `m-ddd4e3cc19480fcb7ac3` | `inp` Float32 `[1,512,1,256]` | `linear_0 = [0.09083940088748932,-0.2461158037185669,-0.03678146004676819,0.09946630150079727]` |

Les types du tableau sont ceux des interfaces déclarées, vérifiés par le
backend. Les deux CNN calculent des **scores bruts à partir d'embeddings** :
ni pixels, ni chaîne de texte, ni noms de classes ou probabilités supposés.
TTE_Model fournit un tenseur numérique ; ces entrées artificielles ne
constituent pas une prédiction de batterie calibrée sur un appareil.

```sh
# Depuis runtime/, avec le cache firmware déjà acquis
python3 -m venv .venv-cpu
.venv-cpu/bin/pip install -e '.[cpu]'
.venv-cpu/bin/python examples/demo_tte_runtime.py \
  --output .state/tte-runtime-demo.json
OPENBLAS_NUM_THREADS=1 .venv-cpu/bin/python examples/demo_cnn_runtime.py \
  --output .state/cnn-runtime-demo.json
```

Le LSTM accepté est **forward Float32**, ordre de gates I/F/O/Z, sigmoid/tanh,
sans peepholes, clipping ou direction inverse. Le vrai graphe convertit ses
entrées et sorties intermédiaires selon ses types. `expand_dims` et `tile`
sont désormais pris en charge. Les CNN ajoutent déquantification affine uint8
par canal, convolution NCHW/OIHW **VALID sans padding**, sans groupes ni
dilatation, maxpool VALID, `expandDims` et `reshapeStatic`. Les variantes
absentes de ce sous-ensemble sont refusées. Les allocations et le travail
numérique sont bornés, les arités et axes invalides contrôlés.

La [preuve LSTM](../models/evidence/tte-runtime-demo.json) compare **5 376
valeurs** de la séquence et des états du vrai graphe à une lecture séparée des
blobs et un calcul scalaire Float64 avec `math.fsum` : erreur maximale
**4,925 × 10⁻⁷**. La [preuve CNN](../models/evidence/cnn-runtime-demo.json)
compare toutes les sorties finales à une référence scalaire indépendante :
erreur absolue maximale **0,00010014**, dans les tolérances publiées
`atol=2e-5, rtol=2e-5`. Les tests complémentaires utilisent des entrées non
uniformes pour vérifier ordre spatial, canaux, lots et strides. Cela valide
ces calculs CPU ; **la parité Core ML/ANE n'a pas été mesurée**.

Un **nouveau backend officiel Apple sous Linux**, [`coreai-cpu`](COREAI.md),
exécute aussi le format `.aimodel`, découvert par les liens/imports du
[Core AI Debugger](../analysis/DEVELOPER-TOOLS.md). Son tutoriel `x+x` et une
constante embarquée sont réellement exécutés, séparément des modèles firmware
entraînés. Le runtime `coreai-core 1.0.0b3` a été acquis publiquement ; il ne
fournit pas les poids AFM ou diffusion et ne transforme pas les `.mlmodelc`
du firmware en `.aimodel`.

Validation finale avec les deux dépendances optionnelles : **60 tests runtime,
59 réussis et un saut macOS**, plus **six tests d'archives réussis**. Les trois
nouveaux modèles et le tutoriel ont également été exécutés depuis des exemples
et la CLI installée, appelée hors du dépôt. Voir
[`developer-tools-runtime-validation.json`](../models/evidence/developer-tools-runtime-validation.json)
et [`developer-tools-installed-cli.json`](../models/evidence/developer-tools-installed-cli.json).

**L'objectif complet reste ouvert** : aucune génération AFM de texte, d'image,
de son ou de vidéo n'est démontrée. Les principaux poids et assets de Data
manquent ; les formats opaques/compilés et opérateurs non portés restent hors
du sous-ensemble CPU. Les archives supplémentaires ne contiennent aucun bundle
AFM identifié. La [note d'acquisition](../models/DOWNLOADS.md) décrit les
artefacts encore nécessaires, sans demander d'identifiants en clair.

## Premier lot protobuf : état historique

Le 26 octobre 2026, **12 modèles supplémentaires** du firmware `24B115` ont
produit des sorties sur Debian x86_64, avec deux entrées numériques chacun.
Avec EntitySimilarity déjà pris en charge par le backend Espresso, cela porte
le sous-ensemble démontré à **13 modèles auxiliaires**. Ce nombre ne représente
ni tous les modèles du firmware, ni les générateurs AFM/diffusion.

Le nouveau backend `coreml-protobuf-cpu-experimental` lit les graphes protobuf
et leurs véritables coefficients. Core ML Tools fournit uniquement les
définitions de format ; le calcul utilise NumPy. Aucun moteur Apple n'est
chargé. Les avertissements `Failed to load _MLModelProxy` de Core ML Tools sur
Linux sont attendus : ce proxy n'est pas appelé.

## Installation et démonstrations

Depuis `Apple Intelligence/runtime` :

```sh
python3 -m venv .venv-cpu
.venv-cpu/bin/pip install -e '.[cpu]'
.venv-cpu/bin/python -m apple_firmware_runtime doctor
.venv-cpu/bin/python examples/demo_cpu_catalog.py \
  --output .state/cpu-protobuf-demos.json
```

Environnement effectivement utilisé : Python 3.11, NumPy 2.4.6, Core ML Tools
9.0. Les poids doivent avoir été acquis avec `models/acquire.py` ; les
dépendances ne téléchargent aucun poids AFM. Le venv de validation sur ce VPS
est `/tmp/apple-portable-env` et n'est pas une dépendance durable du dépôt.

Le démonstrateur sélectionne les **25 groupes protobuf/package non compilés**,
importe chaque bundle avec contrôle de taille/SHA-256, puis tente deux entrées :
tous les nombres à zéro, puis à un, avec les formes déclarées. Il écrit les
fichiers d'entrée JSON dans `.state/cpu-demos`, ainsi que leur recette et leur
SHA-256 dans le rapport. Chaque modèle non pris en charge conserve son erreur.
Résultat : **12 exécutés, 13 refusés, aucune réussite partielle**.

Le rapport livré est
[`cpu-protobuf-demos.json`](../models/evidence/cpu-protobuf-demos.json).
Chaque sortie est une inférence numérique réelle, mais les entrées sont
synthétiques : elles ne reconstituent pas des transactions, SMS ou comportements
utilisateur réels et n'évaluent pas la qualité de la tâche métier.

| Exemple | Entrée zéro exacte | Sortie mesurée |
| --- | --- | --- |
| `_PSRuleImportancePredictor` | `bothMatched`, Float32, forme `[44]` | classe `0`, score classe 1 `0.12007111568098154` |
| `gbdt` | 19 scalaires `0`…`18`, tous à `0.0` | `predictedValue = -0.04956429392099382` |
| `item_model…` | `features`, Float32, forme `[500,471]` | 500 scores à `0.44035521149635315` |
| `ghent_classifier` | `input_`, Float16, forme `[1,25]` | `target=[2]`, scores `[0.03955078125,0.96044921875]` |
| `BlackPearlSender` | `x`, Float32, forme `[1,2002]` | `Identity=[[0.9870795607566833]]` |
| `trialDurationModel` | 26 scalaires nuls, noms dans le rapport | `duration_pred=5.555012254971856` |

Pour relancer une entrée par l'interface normale, après le démonstrateur :

```sh
.venv-cpu/bin/python -m apple_firmware_runtime \
  --store .state/cpu-demos/store predict m-c0787c3ed9e447b6892c \
  --backend coreml-protobuf-cpu-experimental \
  --input .state/cpu-demos/m-c0787c3ed9e447b6892c-zero.json
```

Les noms de sorties sont ceux du graphe ; `target` de ghent est construit par
ses opérateurs, sans réétiquetage supposé. Les scores d'arbres sans transformée
sont conservés tels que spécifiés, sans calibration ajoutée.

## Formats portés et limites

* Arbres : six comparaisons, accumulation des feuilles et biais, transformées
  softmax/logistique ; régression et classification. Les pipelines observés
  ajoutent un `featureVectorizer` avec ordre explicite des colonnes.
* Réseau dense : constantes, soustraction et multiplication diffusées, couche
  dense de rang 2, squeeze, sigmoid/ReLU ; uniquement exact-shape sans
  prétraitement image. Les CNN/LSTM ne sont pas implémentés.
* MIL : constantes immédiates ou `BlobStorage` v2, FP16/FP32 et entiers pris
  en charge, casts, split/gather, reshape/transpose, linéaire, relu/sigmoid,
  softmax, concat, opérations arithmétiques, sélection et réductions.
  Les sous-blocs, listes, boucles, LSTM, quantifications et opérations absentes
  de la liste explicite sont refusés.

Les tenseurs d'entrée sont validés contre les types/formes fixes du protobuf.
Les bundles restent vérifiés par le store avant chaque inférence. Les chemins,
sentinelles, alignements, types et tailles des poids MIL sont contrôlés.
Les casts/intermédiaires suivent les types déclarés ; les produits matriciels
FP16 utilisent une accumulation Float32 puis arrondi au type de sortie.
**La parité avec Core ML/ANE n'a pas été mesurée.** NumPy/BLAS et le matériel
peuvent différer du runtime Apple, en particulier en précision réduite.

Les 13 refus couvrent notamment les classifieurs texte opaques, les réseaux
convolutifs, les états optionnels et les programmes MIL avec boucles/LSTM.
Les modèles compilés, ANE/HWX, formats Espresso non portés et ressources
opaques ne font pas partie de ces 25 tentatives. Aucun texte, image, son ou
vidéo n'a été généré avec AFM, Genmoji ou Image Playground.

## Vérification

```sh
.venv-cpu/bin/python -m unittest discover -s tests -v
```

Les tests nouveaux contrôlent les seuils d'arbres avec égalité, la logistique,
les cycles et chemins de poids invalides, la troncature des blobs et les entrées
non numériques. Deux références indépendantes utilisent le vrai firmware :
somme manuelle des trois feuilles GBDT et produit scalaire du scoreur normalisé
en double précision. Les deux programmes MIL ont des démonstrations réelles ;
ces démonstrations ne sont pas une référence indépendante de parité Apple.

Validation finale : **38 tests, 37 réussis, 1 saut macOS**, et CLI installée
appelée depuis `/tmp`. Les versions, empreintes du code et sorties de cette
commande sont dans [`cpu-validation.json`](../models/evidence/cpu-validation.json)
et [`cpu-installed-cli.json`](../models/evidence/cpu-installed-cli.json).

Formats de référence Apple : [arbres](https://apple.github.io/coremltools/mlmodel/Format/TreeEnsemble.html),
[réseaux](https://apple.github.io/coremltools/mlmodel/Format/NeuralNetwork.html),
[BlobStorage](https://github.com/apple/coremltools/blob/main/mlmodel/src/MILBlob/Blob/StorageFormat.hpp)
et [types de blobs](https://github.com/apple/coremltools/blob/main/mlmodel/src/MILBlob/Blob/BlobDataType.hpp).

Les [chemins d'acquisition des poids absents](../models/DOWNLOADS.md) sont séparés
des résultats d'exécution : une référence UAF ou un compte Developer ne fournit
pas à lui seul les octets du modèle.
