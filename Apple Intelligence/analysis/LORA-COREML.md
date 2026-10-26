# LoRA, Core ML et Foundation Models : vérification des captures Leo AI

Recherche et essais du **26 octobre 2026**, poursuivant le commit `630d212b`.
Corpus publié : `Apple Intelligence/` dans `danielfebrero/Apple`. Les dossiers
`/workspace/recherche/apple-sec/ios272rc` et
`/workspace/recherche/apple-sec/apple-developer-tools-20261026` restent les
sources locales. **Aucune archive n'a été réextraite.**

**Verdict : la recette générique PyTorch → PEFT → Core ML fonctionne sur un
modèle accessible. Elle ne fournit ni les poids AFM manquants, ni un chargeur
universel des adapters Apple extraits. L'affirmation selon laquelle aucun
toolkit Foundation Models Adapter séparé n'existe est fausse.**

Les captures ont été lues visuellement. Elles montrent une commande
`pip install -U coremltools peft torch` et le lien Apple sur les modèles
multifonctions. Le code Python situé sous le pli de la première capture n'est
pas lisible : aucun contenu supplémentaire ne lui est attribué. Les empreintes
des deux images figurent dans [le registre des sources](lora-20261026/sources.json).

## 1. Les mécanismes à distinguer

| Mécanisme | Fonction réelle | Prérequis et versions | Ce qu'il ne donne pas |
| --- | --- | --- | --- |
| LoRA avec PEFT/PyTorch | Entraîne de petites matrices ajoutées aux couches d'un réseau. PEFT peut sélectionner ou désactiver des adapters nommés. | Modèle de base, architecture exacte, noms et formes des couches, paramètres LoRA compatibles. Test : PEFT 0.17.1 et Torch 2.7.0+cpu. | Les poids de base absents ; un loader automatique d'assets privés Apple. |
| Fusion LoRA | `merge_and_unload` calcule des matrices effectives et restitue un modèle PyTorch ordinaire. | Base et matrices LoRA connues ; convention de scaling/dtype respectée. La formule simple testée ne couvre pas toutes les variantes PEFT. | Le partage des matrices de base modifiées entre plusieurs variantes fusionnées. |
| Conversion Core ML | `ct.convert` traduit un graphe TorchScript ou ExportedProgram pris en charge vers Core ML. Les opérations LoRA deviennent des opérations de graphe ordinaires. | Graphe et paramètres disponibles ; couverture des opérateurs. TorchScript testé ici. La conversion `torch.export`, ajoutée dans Core ML Tools 8, n'a pas été testée ici. | Téléchargement AFM, reconstruction d'un réseau à partir de son nom ou conversion inverse générale d'un `.mlmodelc`. |
| Core ML multifonction | Assemble des fonctions déjà définies, avec déduplication des constantes communes. La fonction est choisie au chargement. | Core ML Tools 8.0+, ML Program, iOS 18/macOS 15 minimum. Test : Tools 9.0, spécification 9. | L'ajout à la volée d'un nouvel adapter PEFT arbitraire dans un modèle système. |
| Adapter fourni comme tenseurs d'entrée | Un graphe explicitement construit peut recevoir les matrices A/B à chaque appel. | Architecture de graphe prévue pour ces entrées et formes connues. Démontré ici avec Core AI Linux. | Un protocole `.fmadapter` ou un mécanisme standard de chargement dynamique AFM. |
| Foundation Models Adapter Toolkit | Workflow spécialisé Apple avec actifs correspondant à une version du modèle système ; export `.fmadapter`. | Téléchargement Developer distinct ; version et OS assortis. | Une extension intégrée de `coremltools`, ni les actifs iOS 27.2 de ce dossier. |

Sources primaires : [guide multifonction Apple](https://apple.github.io/coremltools/docs-guides/source/multifunction-models.html),
[release Core ML Tools 8.0](https://github.com/apple/coremltools/releases/tag/8.0),
[workflow PyTorch Apple](https://apple.github.io/coremltools/docs-guides/source/convert-pytorch-workflow.html),
[export PyTorch Apple](https://apple.github.io/coremltools/docs-guides/source/model-exporting.html),
[implémentation PEFT 0.17.1](https://github.com/huggingface/peft/blob/v0.17.1/src/peft/tuners/lora/layer.py).

Apple décrit aussi des adapters spécialisés intégrés, sélectionnés par cas
d'usage dans le framework, par exemple le content tagging
([WWDC25, à partir de 18:22](https://developer.apple.com/videos/play/wwdc2025/286/?time=1102)).
Ce choix d'un modèle système préconfiguré est distinct du chargement de poids
PEFT externes. Aucun de ces appels système n'a été exécuté sur ce VPS.

Pour une couche linéaire, la convention testée est :

```text
W : [sortie, entrée] ; A : [rang, entrée] ; B : [sortie, rang]
y = x Wᵀ + biais + (alpha/rang) (x Aᵀ) Bᵀ
W_fusionné = W + (alpha/rang) B A
```

La correction `BA` ne détermine pas `W`. Même avec les bonnes dimensions,
changer la base produit un autre modèle. Le contrôle négatif de ce lot mesure
un écart maximal de **1,44744** en remplaçant la base tout en gardant le même
adapter. Les rangs, clés, quantifications, conventions et versions doivent
donc être établis sur les vrais actifs, avant toute tentative de fusion.

### Ce que dit le code actuel de coremltools

Le dépôt Apple a été cloné et conservé localement, au commit
`a207b1a3452eafe02f2d870f486287834af2c82d` du 30 septembre 2026.
La dernière distribution stable observée sur PyPI est **9.0**. Le code main
et la distribution testée sont identifiés séparément ; les essais ne sont
pas présentés comme un build de main.

- [`MultiFunctionDescriptor` et `save_multifunction`](https://github.com/apple/coremltools/blob/a207b1a3452eafe02f2d870f486287834af2c82d/coremltools/models/utils.py#L1412)
  lisent les modèles et leurs dossiers de poids existants, assemblent leurs
  fonctions et appliquent la déduplication des constantes. Ils ne téléchargent
  aucun modèle et ne résolvent aucun identifiant MobileAsset.
- [La passe de déduplication](https://github.com/apple/coremltools/blob/a207b1a3452eafe02f2d870f486287834af2c82d/coremltools/converters/mil/mil/passes/defs/cleanup/const_deduplication.py#L79)
  recherche des valeurs communes. Si les matrices ont été fusionnées avec des
  corrections différentes, ces matrices ne sont plus communes.
- [Le test LoRA multifonction Apple](https://github.com/apple/coremltools/blob/a207b1a3452eafe02f2d870f486287834af2c82d/coremltools/converters/mil/frontend/torch/test/test_torch_conversion_api.py#L686)
  importe PEFT et trace le réseau. Il est encore marqué `xfail(run=False)`
  avec un problème de chargement MLModel signalé ; un commentaire distingue
  aussi l'exécution Intel/arm64. Cela interdit de déduire la parité matérielle
  d'une simple conversion ; cela ne démontre pas que tous les modèles échouent.
- La recherche dans les modules de conversion et de modèles n'a identifié
  aucun chargeur AFM/`.fmadapter`. La prise en charge illustrée passe par les
  opérations PyTorch, avec PEFT comme dépendance externe.

La commande `pip install -U ...` installe des outils, pas des modèles. Elle
n'épingle pas une combinaison validée : PyPI indiquait ici PEFT **0.21.2** et
Torch **2.14.1**, alors que la distribution Core ML Tools testée annonce une
couverture Torch jusqu'à 2.7 et le code main jusqu'à 2.8. Cela ne prouve pas un
échec des versions ultérieures ; elles n'ont simplement pas été validées dans
ce lot. Les versions et hashes des téléchargements utilisés sont enregistrés.

## 2. Toolkit et acquisition officielle

La [page officielle Foundation Models Adapter](https://developer.apple.com/apple-intelligence/foundation-models-adapter/)
décrit un téléchargement séparé contenant code Python, actifs de base/draft et
exporteur `.fmadapter`. Elle exige une adhésion Apple Developer Program et
l'acceptation des conditions. Le droit de déploiement en application est une
étape distincte du test local. La version **26.0.0 est terminale et incompatible
avec les OS 27+** ; chaque adapter correspond à une version précise de base.
Apple prévoit Python 3.11+, un Mac Apple silicon de 32 Go ou une machine Linux
GPU. Les actifs du toolkit sont réservés à l'entraînement d'adapters ; son
exemple de génération sert à valider ce workflow.

La requête publique vers le [catalogue Developer](https://developer.apple.com/download/all/?q=Foundation%20Models)
a redirigé vers la connexion Apple. **Aucune session, licence ou archive toolkit
n'était disponible pour ce tour.** Aucun téléchargement authentifié n'a été
simulé. Les échecs 404 des anciennes pages DocC liées sont conservés comme
limites de consultation, et non comme preuve d'absence du toolkit.

Le [papier Apple sur les modèles 2025](https://machinelearning.apple.com/research/apple-foundation-models-2025-updates)
décrit notamment le toolkit d'adapters de rang 32 pour son modèle d'environ
3 milliards de paramètres. Cette description ne fournit ni les formes internes
des actifs iOS 27.2 ni une preuve d'équivalence avec ceux du toolkit 26.

Les deux voies restent donc celles documentées dans [DOWNLOADS.md](../models/DOWNLOADS.md) :
archive officielle versionnée acquise via Developer, ou actifs complets d'un
appareil autorisé avec build, manifestes et hashes. Un certificat Developer,
un prompt, un tokenizer ou un nom d'asset ne remplace pas ces octets. Le
toolkit texte ne fournit pas non plus les poids Image Playground/Genmoji.

## 3. Confrontation aux fichiers réellement extraits

[L'inspection reproductible](lora-20261026/inspect_firmware.py) lit les
**3 923 entrées** du manifeste existant, soit **2 739 917 787 octets** déclarés.
Elle ne réextrait rien et ne rehache pas l'ensemble de ces 2,7 Go : les six
fichiers de l'adapter étudié sont, eux, tous revérifiés contre leur SHA-256.

| Objet réel | Observation | Compatibilité avec la recette des captures |
| --- | --- | --- |
| 25 fichiers protobuf Core ML, packages, graphes MIL/Espresso et bundles compilés | Modèles auxiliaires hétérogènes ; certains disposent déjà d'un interpréteur CPU borné. | Leur suffixe ne leur donne pas une architecture PyTorch/PEFT ni une base AFM. |
| Catalogues UAF | 366 identifiants langage, dont 239 `instruct_3b` et 35 `instruct_300m` ; 18 références visuelles. | Sélection/références, sans matrices AFM ou diffusion. Les formes et rangs des adapters référencés restent inconnus. |
| Fichiers PEFT ou `.fmadapter` nommés | Aucun `adapter_config.json`, `adapter_model.*`, `.safetensors` ou `.fmadapter` dans l'inventaire. | Absence bornée aux fichiers inventoriés ; les payloads opaques ne sont pas tous décodés. |
| `md8-safari-adapter.mlmodelc`, ID `m-7b9fdc2970fc78c9d2ff` | Six fichiers, 11 181 502 octets : runtime data, E5, HWX et deux BNNSIR. | Vrai bundle compilé portant le nom adapter, mais aucune paire A/B PEFT établie. Le nom ne prouve pas LoRA ou AFM. |

**Nouveau décodage du véritable adapter Safari.** Dans le `coremldata.bin` de
339 octets, SHA-256
`47e011e35309791ef958ac5d378d154cc3a4026106b9fd340a66039d3bcc9f56`,
un `ModelDescription` protobuf public de 224 octets commence à l'offset 83.
Son champ de longueur est à l'offset 75. La lecture est liée à ce hash précis,
sans présenter cet offset comme un parseur universel.

| Fonction | Entrées | Sortie |
| --- | --- | --- |
| `main_ctx_77` | `spatial` Float32 `[1,77,768]` ; `eos_pos` Int32 `[1]` | `output` Float16 `[1,512]` |
| `main_ctx_512`, défaut | `spatial` Float32 `[1,512,768]` ; `eos_pos` Int32 `[1]` | `output` Float16 `[1,512]` |

Ces interfaces décrivent des tenseurs, pas des textes ou des tokens à générer.
Le chemin EmbeddingCore et la sortie 512 étayent l'interprétation d'une
transformation d'embeddings ; le modèle amont, sa sémantique exacte et les
matrices internes ne sont pas établis. E5 conserve la trace d'une compilation
de `model.mil`, mais ce source est absent du bundle inventorié. Le HWX et les
BNNSIR ne sont ni des checkpoints PyTorch ni des packages Core ML source.
L'essai `ct.convert(..., source="pytorch")` rejette effectivement ce bundle.
Son inférence Linux n'est pas revendiquée.

Les détails, formes, hashes et erreurs sont dans
[firmware-compatibility.json](lora-20261026/firmware-compatibility.json).

## 4. Essais Debian et vérification indépendante

Un venv neuf utilise Python **3.11.2**, Torch **2.7.0+cpu**, PEFT **0.17.1**,
Core ML Tools **9.0**, NumPy **2.2.6** et Transformers **4.55.4**.
Le réseau contrôlé comporte deux couches `64→48→16`, ReLU, une base de
3 904 paramètres et deux adapters de rang 4, chacun de 704 paramètres.
Les poids sont générés localement, avec graine fixe ; aucun modèle de hub
n'est téléchargé. Les adapters sont effectivement entraînés sur des cibles
contrôlées, pendant 180 étapes chacun. Douze vecteurs distincts des données
d'entraînement, dont un nul, servent aux comparaisons.

| Essai réalisé | Résultat observé |
| --- | --- |
| Initialisation PEFT | B nul, sortie exactement égale à la base : attacher un LoRA sans apprentissage ne spécialise pas le modèle. |
| Entraînement, base gelée | MSE `0,00947108 → 0,00000481214` et `0,00661295 → 0,00000278252` ; base vérifiée inchangée. |
| PyTorch adapté/fusionné et référence NumPy Float64 | Écart absolu maximal inférieur à `2,1e-7` sur les vecteurs du lot. |
| Conversion et relecture des octets sauvegardés | Base, deux adapters, deux variantes fusionnées et deux packages multifonctions produits. Les graphes sont évalués par l'interpréteur NumPy borné existant. |
| Cible plus ancienne | Une variante fusionnée convertie pour iOS 15, spécification 6, donne également le bon résultat numérique. iOS 18 est le seuil multifonction, pas celui de toute arithmétique LoRA. |
| Partage physique des poids | Les deux fonctions non fusionnées pointent vers les mêmes offsets de blob pour les matrices et biais de base. Les A/B restent distincts. |
| Sélection dynamique PEFT | Changement d'adapter et désactivation valides. Une trace faite avant le changement conserve l'adapter initial ; elle n'exporte pas le sélecteur Python. |
| Prédiction Apple Core ML sous Linux | Rejet explicite : macOS requis. La conversion n'est pas une inférence Core ML Linux. |

Tailles des packages effectivement produits, somme de leurs fichiers :

| Variante | Chaque package individuel | Package multifonction des deux |
| --- | ---: | ---: |
| LoRA séparés de la base | 24 571 octets | **31 313 octets** |
| Poids fusionnés | 18 065 octets | **34 172 octets** |

Les blobs de poids non fusionnés passent de deux fois 19 392 à **22 464 octets**.
Les variantes fusionnées passent de deux fois 15 936 à **31 424 octets** : les
biais peuvent rester communs, les matrices modifiées ne le sont plus. Les tailles
incluent les différences de graphes, protobuf, alignements et manifestes ; elles
ne constituent pas une extrapolation de performance mémoire AFM.

### Core AI natif : un progrès distinct sur le runtime Linux

Dans l'environnement Core AI déjà isolé, `coreai-core==1.0.0b3` et
NumPy **2.4.6**, un graphe `.aimodel` est **écrit explicitement** avec les mêmes
poids contrôlés. La base est embarquée ; A1/B1/A2/B2 sont des entrées Float32
ordinaires, changées à chaque appel. Ce n'est pas un convertisseur `.mlpackage`
ou un lecteur d'adapter Apple. Le chemin dérive de
[l'API d'authoring et du tutoriel officiels Apple](https://github.com/apple/coreai-torch/blob/main/docs/coreai-core/tutorials/run-an-aimodel.ipynb).

**36 inférences natives réussissent** : 12 entrées × base/adapter 1/adapter 2.
Écart maximal contre la référence Float64 : **1,52634e-7**. Le même asset est
importé, inspecté et exécuté par le catalogue/store/CLI existant, avec contrôle
des fichiers. Le runtime sait déjà transporter ces entrées ; aucune extension
des formats du catalogue firmware n'est nécessaire.

Deux premiers graphes ont été rejetés par la réécriture Core AI pour des formes
de biais/scaling non identiques à la sortie. Les constantes ont été explicitement
dimensionnées `[1,sortie]` ; les journaux d'échec sont conservés. L'ordre d'import
du tutoriel (`coreai.authoring` avant les dialectes) est également nécessaire
avec cette distribution, sinon un import circulaire apparaît. Ces limites
locales ne sont pas généralisées à toutes les API Apple.

Le [vérificateur indépendant](lora-20261026/verify_artifacts.py) recharge les
NPZ, les vrais `.safetensors` et les protobuf sauvegardés. Il reconstruit la
référence en **fusionnant les matrices en Float64**, contrairement au calcul
en deux branches du script d'expérience. Il compare ensuite les sorties
PyTorch sauvegardées, les graphes MIL, les sorties Core AI natives et la CLI.
Il contrôle aussi les hashes et les offsets partagés.
Voir [le résultat final](lora-20261026/independent-verification.json).
Les **19 comparaisons numériques** passent, avec une erreur maximale de
**2,00077e-7**, sous le seuil fixé à `3e-5`.
L'interpréteur MIL reste celui du dépôt ; cette référence distincte ne vaut
pas validation du moteur Apple Core ML sur Mac.

## 5. Gain réel et limites

- **Contenu/prompts :** les 231 entrées du corpus restent celles déjà livrées.
  Ce lot ajoute une interface tensorielle réelle décodée, pas de nouveaux
  prompts ni une preuve d'activation du modèle Safari.
- **Acquisition :** zéro nouveau poids AFM ou diffusion. Le toolkit séparé est
  confirmé, mais sa version 26 ne résout pas la dépendance aux actifs iOS 27.2.
- **Linux :** adaptation, fusion, conversion et vérification numérique sont
  reproductibles. Le runtime natif Core AI passe maintenant un réseau pondéré
  avec corrections LoRA dynamiques contrôlées, au-delà du précédent `x+x`.
- **Portage Apple :** aucun chargement de `.fmadapter`, de BNNSIR/HWX Safari ou
  de base AFM n'est démontré. Les **16 modèles auxiliaires Apple** déjà exécutés
  restent 16 ; les démonstrations synthétiques de ce lot ne s'y ajoutent pas.

Conclusion opérationnelle **C3 pour les faits observés**, **C0 pour l'exécution
AFM Linux** : poursuivre l'acquisition des vrais actifs versionnés et de leur
architecture. Installer ces trois paquets ou combiner des fonctions n'enlève
aucun de ces prérequis. Les sources originales, captures, clones et journaux
bruts sont conservés sur le VPS ; les commandes, artefacts contrôlés et preuves
publiables sont livrés dans [lora-20261026/](lora-20261026/REPRODUCE.md).
