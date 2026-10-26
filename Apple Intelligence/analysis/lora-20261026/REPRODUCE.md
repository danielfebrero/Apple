# Reproduire les essais LoRA sous Debian

Lire d'abord [le rapport et ses limites](../LORA-COREML.md).
Ces commandes partent de `Apple Intelligence/` dans un clone du dépôt.
Les modèles générés ici sont nos petits modèles contrôlés, pas AFM.

## Environnement de conversion

```sh
python3 -m venv /tmp/apple-lora-env
/tmp/apple-lora-env/bin/python -m pip install --upgrade pip
/tmp/apple-lora-env/bin/python -m pip install \
  --index-url https://download.pytorch.org/whl/cpu \
  --extra-index-url https://pypi.org/simple 'torch==2.7.0+cpu'
/tmp/apple-lora-env/bin/python -m pip install \
  -r analysis/lora-20261026/requirements-lock.txt
/tmp/apple-lora-env/bin/python -m pip check
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=1 \
  /tmp/apple-lora-env/bin/python analysis/lora-20261026/run_experiment.py \
  --output /tmp/apple-lora-proof
```

Le dossier de sortie doit être absent. Le lock reflète l'environnement du
26 octobre 2026 ; pip utilisé : 26.2.2. Les identités des distributions et hashes
des téléchargements sont dans `sources.json`. La sélection CPU explicite évite
un téléchargement CUDA inutile. L'ancienne tentative avec pip initial et le
seul index CPU a échoué sur les métadonnées `typing-extensions` puis `flit_core` ;
le journal original est conservé, les commandes corrigées sont celles ci-dessus.

La conversion est effectuée avec `skip_model_load=True`. L'essai négatif de
`MLModel.predict` vérifie que l'environnement Linux ne dispose pas de Core ML.
La validation MIL utilise l'interpréteur NumPy borné du dépôt.

## Exécution native Core AI, environnement séparé

```sh
python3 -m venv /tmp/apple-lora-coreai-env
/tmp/apple-lora-coreai-env/bin/python -m pip install --upgrade pip
/tmp/apple-lora-coreai-env/bin/python -m pip install \
  'coreai-core==1.0.0b3' 'numpy==2.4.6'
/tmp/apple-lora-coreai-env/bin/python -m pip install -e runtime
/tmp/apple-lora-coreai-env/bin/python analysis/lora-20261026/run_coreai.py \
  --results /tmp/apple-lora-proof --output /tmp/apple-lora-coreai-proof
```

Le wheel Linux Apple exige Python 3.11+ et glibc 2.34+ sur x86_64.
Le script écrit explicitement un AIProgram à partir des tableaux contrôlés.
Il n'utilise pas Core AI Torch ni un convertisseur Core ML. Ses A/B en entrée
ont les axes transposés par rapport au stockage PEFT, comme le décrit le code.

Depuis `runtime/`, exercer le chemin CLI déjà livré :

```sh
cd runtime
/tmp/apple-lora-coreai-env/bin/python -m apple_firmware_runtime \
  --catalog /tmp/apple-lora-coreai-proof/manifest.json \
  --source-root /tmp/apple-lora-coreai-proof --store /tmp/apple-lora-coreai-store \
  import controlled-dynamic-lora > /tmp/apple-lora-coreai-proof/cli-import.json
/tmp/apple-lora-coreai-env/bin/python -m apple_firmware_runtime \
  --catalog /tmp/apple-lora-coreai-proof/manifest.json \
  --source-root /tmp/apple-lora-coreai-proof --store /tmp/apple-lora-coreai-store \
  inspect controlled-dynamic-lora --load --backend coreai-cpu \
  > /tmp/apple-lora-coreai-proof/cli-inspect.json
/tmp/apple-lora-coreai-env/bin/python -m apple_firmware_runtime \
  --catalog /tmp/apple-lora-coreai-proof/manifest.json \
  --source-root /tmp/apple-lora-coreai-proof --store /tmp/apple-lora-coreai-store \
  predict controlled-dynamic-lora --backend coreai-cpu \
  --input /tmp/apple-lora-coreai-proof/input.json \
  > /tmp/apple-lora-coreai-proof/cli-predict.json
cd ..
/tmp/apple-lora-env/bin/python analysis/lora-20261026/verify_artifacts.py \
  --results /tmp/apple-lora-proof --coreai-results /tmp/apple-lora-coreai-proof \
  --output /tmp/apple-lora-independent-verification.json
```

Les journaux natifs peuvent aller sur stderr ; les trois fichiers CLI doivent
être du JSON strict. Le vérificateur exige une erreur absolue maximale < 3e-5.
Les erreurs mesurées dans la livraison sont de l'ordre de 1e-7. Les UUID de
manifestes de packages et les emplacements de code du bytecode peuvent varier ;
un hash identique entre deux nouvelles générations n'est pas promis.

## Confrontation au firmware, sans extraction

Si le cache déjà acquis est présent sous `models/cache/` :

```sh
/tmp/apple-lora-env/bin/python analysis/lora-20261026/inspect_firmware.py \
  --output /tmp/apple-lora-firmware-compatibility.json
```

Le clone public ne contient pas ce cache de poids Apple. Cette commande vérifie
les six fichiers de `md8-safari-adapter` et le protobuf de description lié à un
hash précis. Elle échoue si ces fichiers manquent ou diffèrent. Le rapport
livré conserve les résultats constatés sur le cache local.

## Fichiers livrés et sources conservées

- `results/` : huit packages Core ML contrôlés, deux checkpoints PEFT, base,
  adapters, vecteurs et sorties, métriques et SHA-256.
- `coreai-results/` : `.aimodel` contrôlé, catalogue séparé, entrées, sorties
  natives, métriques et preuves CLI.
- `independent-verification.json` : contrôles de la livraison sauvegardée.
- `firmware-compatibility.json` : vrai bundle Safari et références aux actifs.
- `sources.json` : URLs, timestamps, commits, hashes source et distributions.
- `logs/`, `provenance.json`, `environment.json` : journaux lisibles, liens vers
  les originaux locaux et paquets des deux environnements.
- `DELIVERY-SHA256.json` : empreintes de l'ensemble de ce sous-dossier, hors
  ce manifeste lui-même.

Originaux et clones :
`/workspace/recherche/apple-sec/apple-developer-tools-20261026/research/lora/`.
Les pages Apple et sources ont été conservées sous `sources/`, le clone officiel
dans `coremltools-main/`. Aucune licence/session Apple Developer n'a été acquise.
Les captures originales restent sous `/workspace/incoming/c4ad2990/` et ne sont
pas recopiées dans Git. Aucun poids binaire Apple n'est ajouté à ce lot.
