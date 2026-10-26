# Reproduire l'acquisition et les essais

Depuis la racine de `danielfebrero/Apple`, branche `master`. Les chemins cités
sont ceux du VPS ; remplacer les préfixes si nécessaire. Python 3.11, Linux
x86_64. Le cache de poids et l'IPSW restent locaux, hors Git.

## 1. Préparer toutes les images du même IPSW

Les deux images OS et SystemOS déchiffrées du premier lot sont déjà sous
`_ipsw/rootfs-dec` et `_ipsw/cryptex-dec`. Le script réutilise ces octets, extrait
les autres images du ZIP, déchiffre les conteneurs AEA avec l'outil existant et
retire l'enveloppe IM4P des ramdisks. Le déchiffrement AEA peut joindre le service
FCS Apple ; aucune clé ou sortie du déchiffreur n'entre dans les preuves Git.
Les sept images sont ensuite parcourues avec le lecteur APFS, sans montage.

```sh
python3 'Apple Intelligence/analysis/acquisition-20261026/inventory_ipsw.py' \
  --ipsw /workspace/recherche/apple-sec/ios272rc/_ipsw/iPhone18,3_27.2_24B115_Restore.ipsw \
  --work /workspace/recherche/apple-sec/ios272rc/_ipsw/model-audit \
  --reader '/workspace/Apple/Apple Intelligence/scripts/apfs_ai' \
  --ipsw-tool /workspace/opt/ipsw-3.1.730/ipsw \
  --report /tmp/ipsw-images.json
```

`model-audit/extra-volumes.json` décrit les cinq images supplémentaires avec
leurs noms de volume réellement observés. Les hashes attendus des images
décryptées sont dans `models/summary.json`. La version de l'outil local est
`ipsw 3.1.730`. Le lecteur APFS et sa source sont versionnés dans `scripts/`.

## 2. Reconstituer le cache publié

Cette commande utilise uniquement le manifeste public, les assets, le résumé
et les images locales ; elle ne télécharge rien. Elle revérifie les fichiers
déjà présents, et extrait ceux qui manquent. Une sortie dry-run n'est pas
une preuve d'acquisition.

```sh
python3 'Apple Intelligence/models/acquire.py' \
  --firmware-root /workspace/recherche/apple-sec/ios272rc/_ipsw \
  --all --report /tmp/acquire-all.json > /tmp/acquire-all.stdout.json
```

Les chemins relatifs des sept images sont publiés sous
`summary.json:volumes[].image_relative_path`. Les images sans fichier
sélectionné sont vérifiées par l'étape 1, pas rehachées par l'acquéreur.

Pour **régénérer la sélection** à partir des inventaires APFS complets du VPS :

```sh
python3 'Apple Intelligence/models/scan_models.py' --extract --hash-images \
  --reader 'Apple Intelligence/scripts/apfs_ai' \
  --extra-volumes /workspace/recherche/apple-sec/ios272rc/_ipsw/model-audit/extra-volumes.json

python3 'Apple Intelligence/models/verify_inventory.py'
```

Pour rejouer l'audit versionné avec son rapport d'acquisition voisin :

```sh
python3 'Apple Intelligence/models/acquire.py' \
  --firmware-root /workspace/recherche/apple-sec/ios272rc/_ipsw --all \
  --report 'Apple Intelligence/analysis/acquisition-20261026/acquire-all-expanded.json' \
  > /tmp/acquire-audit.stdout.json
python3 'Apple Intelligence/analysis/acquisition-20261026/audit_acquisition.py' \
  --output 'Apple Intelligence/analysis/acquisition-20261026/acquisition-audit.json'
```

Le dernier audit attend le rapport d'acquisition finale dans son dossier de
sortie (`acquire-all-expanded.json`). Il contrôle la conservation de chaque
fichier de `fb0cabba`, les métadonnées, les inventaires et les ressources UAF.
Il ne remplace pas le contrôle des hashes du cache par `acquire.py` et
`verify_inventory.py`.

## 3. Générer avec le véritable UniLM du firmware

Environnement déjà présent et utilisé :
`/workspace/recherche/apple-sec/apple-developer-tools-20261026/research/lora/venv`.
Versions de référence : `torch==2.7.0+cpu`, `numpy==2.2.6`.
Pour un environnement neuf :

```sh
python3 -m venv /tmp/apple-unilm-env
/tmp/apple-unilm-env/bin/pip install numpy==2.2.6
/tmp/apple-unilm-env/bin/pip install torch==2.7.0+cpu \
  --index-url https://download.pytorch.org/whl/cpu
```

```sh
/tmp/apple-unilm-env/bin/python \
  'Apple Intelligence/analysis/acquisition-20261026/unilm_linux.py' \
  --prompt 'the weather is ' --prompt 'I would like to ' \
  --prompt 'the capital of France is ' --steps 24 --output /tmp/unilm-generation.json

OPENBLAS_NUM_THREADS=2 /tmp/apple-unilm-env/bin/python \
  'Apple Intelligence/analysis/acquisition-20261026/validate_unilm.py' \
  --generation /tmp/unilm-generation.json --output /tmp/unilm-validation.json
```

Le programme vérifie cinq sources contre les SHA-256 du catalogue avant
l'inférence. Il ne crée aucun poids. Le rapport de génération garde les
tokens, les cinq meilleurs choix de chaque pas et le hash des logits.
Les sorties attendues et les limites sont dans le
[rapport](../ACQUISITION-GENERATION.md). Les hashes bit à bit sont rejoués dans
le même environnement CPU ; une autre pile BLAS/version n'a pas été validée.

## 4. Contrôler les pistes image et les régressions

Le runtime officiel `coreai-core==1.0.0b3` est déjà installé dans
`research/coreai/linux-env`. Ailleurs, installer cette version dans un venv
Linux x86_64 compatible glibc 2.34+. Les essais suivants utilisent une API
interne de lecture du bytecode, chacun dans un processus enfant isolé, sans
core dump. Ils n'exécutent aucun graphe image.

```sh
python3 'Apple Intelligence/analysis/acquisition-20261026/probe_image_paths.py' \
  --coreai-python /workspace/recherche/apple-sec/apple-developer-tools-20261026/research/coreai/linux-env/bin/python \
  --output /tmp/image-paths.json

python3 -m unittest discover -s 'Apple Intelligence/runtime/tests' -p test_acquire.py -v
python3 -m unittest discover -s 'Apple Intelligence/runtime/tests' -p test_scan_models.py -v
```

Résultats du lot : 8 tests d'acquisition et 5 de sélection passent ; 20 sondes
MPSGraph se terminent par SIGABRT avec diagnostic de dialecte non pris en charge.
Le rapport les conserve comme échecs de lecture, sans sortie générée.

Les comptes v3 des rapports historiques restent ceux de leur date. Les comptes
v4 courants sont dans `models/summary.json`. Le nouveau lot ne réécrit pas les
preuves antérieures pour leur attribuer les nouveaux résultats.
