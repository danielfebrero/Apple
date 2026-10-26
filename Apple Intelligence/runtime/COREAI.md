# Core AI sur Debian

Le backend optionnel `coreai-cpu` exécute de vrais assets `.aimodel` avec le
runtime Linux officiel d’Apple, `coreai-core==1.0.0b3`. Il est vérifié sur Debian
12, x86_64, Python 3.11 et glibc 2.36. Les wheels Apple Linux sont marquées
`manylinux_2_34_x86_64`, Python 3.11 à 3.14.

Ce format est distinct de Core ML (`.mlmodel`, `.mlmodelc`, `.mlpackage`). Le
backend n’importe pas ces derniers comme s’ils étaient des assets Core AI. Il
ne fournit aucun poids AFM ni modèle Apple Intelligence entraîné.

## Complément : réseau pondéré avec corrections LoRA

Les [essais LoRA](../analysis/LORA-COREML.md) exécutent désormais une base
contrôlée `64→48→16` avec quatre matrices LoRA fournies comme entrées à chaque
appel. Le graphe Core AI est écrit explicitement à partir des tableaux de test ;
aucun convertisseur Core ML, asset `.fmadapter` ou poids AFM n'intervient.
Les 36 inférences natives et l'exécution du même asset par le catalogue/store/CLI
sont comparées à une référence NumPy Float64. Les [commandes](../analysis/lora-20261026/REPRODUCE.md)
et [preuves](../analysis/lora-20261026/coreai-results/report.json) sont livrées.
Le transport actuel couvre déjà ces tenseurs : pas de nouvelle compatibilité
avec les formats de modèles compilés du firmware revendiquée.

## Installation et démonstration

Depuis `runtime/`, dans un environnement Python 3.11+ dédié :

```sh
python3 -m venv /tmp/apple-coreai-env
/tmp/apple-coreai-env/bin/pip install '.[coreai]'
/tmp/apple-coreai-env/bin/python examples/demo_coreai.py \
  --state /tmp/apple-coreai-demo --output /tmp/apple-coreai-proof.json
```

La démonstration reprend le [tutoriel Apple officiel](https://github.com/apple/coreai-torch/blob/main/docs/coreai-core/tutorials/run-an-aimodel.ipynb)
`y = x + x`. Elle crée le graphe, son catalogue avec tailles et SHA-256, importe
ses octets dans le store, inspecte sa signature réelle puis exécute le même
modèle via le chemin CLI normal. Une égalité exacte avec NumPy est exigée :

```text
[[1.5, -2, 0], [0.25, 100, -0.125]]
→ [[3, -4, 0], [0.5, 200, -0.25]]
```

C’est un graphe de démonstration sans poids entraînés. Le catalogue firmware
principal n’est pas modifié et le résultat porte `scope: demonstration`.

## Utiliser un asset acquis

Déclarer dans un catalogue séparé `format: coreai_asset`, `source_path` vers
le dossier `.aimodel` complet, `files` avec le chemin relatif, la taille et le
SHA-256 de **chaque fichier**, et éventuellement `entrypoint` (défaut `main`).
Le store conserve l’extension sous `model.aimodel`.

```sh
apple-firmware --catalog /tmp/apple-coreai-demo/manifest.json \
  --source-root /tmp/apple-coreai-demo --store /tmp/apple-coreai-demo/store \
  inspect apple-coreai-tutorial-add --load --backend coreai-cpu

apple-firmware --catalog /tmp/apple-coreai-demo/manifest.json \
  --source-root /tmp/apple-coreai-demo --store /tmp/apple-coreai-demo/store \
  predict apple-coreai-tutorial-add --backend coreai-cpu \
  --input /tmp/apple-coreai-demo/input.json
```

Les entrées sont des tableaux numériques imbriqués ou des objets
`{"shape": [2, 3], "data": [1, 2, 3, 4, 5, 6], "dtype": "float32"}`.
Le champ `dtype` est optionnel mais doit correspondre à la signature si fourni.
Les sorties contiennent `dtype`, `shape` et `data` sous chaque nom de sortie.
Les données sont copiées avant libération du modèle natif.

Les noms, dimensions statiques, types numériques, valeurs finies et tailles
bornées sont vérifiés. Les entrées entières avec fraction ou dépassement sont
refusées ; les booléens ne sont pas acceptés comme nombres. Les fonctions avec
état, formes flexibles et images ne sont pas intégrées. `--compute` doit rester
`cpu`. L’intégrité du store est vérifiée avant chaque invocation CLI.

## Format et portée constatés

Le tutoriel sauvegarde `main.mlirb` (bytecode MLIR), `main.hash` (32 octets de
SHA-256 du bytecode) et `metadata.json` (`assetVersion: 2.0`). La version OS de
compatibilité du graphe est 27.0 ; son exécution ici utilise le runtime local
Linux. La bibliothèque Python d’Apple abaisse le programme vers un asset
temporaire `.aimodelx` contenant du format ODIX, puis l’exécute. Ce détour est
implémenté par Apple, sans émulation macOS.

Un autre test exécute un graphe avec une constante de 2 048 float32, conservée
dans les ressources du bytecode après sauvegarde et import. Cela vérifie la
conservation de ces constantes ; aucun poids AFM externe n’a été acquis ni
validé par ce test. Le format ODIX observé peut contenir ses poids ; on ne
suppose pas un fichier de poids séparé pour chaque asset.

Sources : [coreai-torch Apple](https://github.com/apple/coreai-torch),
[paquet coreai-core](https://pypi.org/project/coreai-core/1.0.0b3/),
[docs de débogage](https://apple.github.io/coreai-torch/main/api/debugging.html).
Les preuves réseau, hashes du wheel et entrée/sortie Linux sont conservés sous
`/workspace/recherche/apple-sec/apple-developer-tools-20261026/research/coreai/`.

## Vérification

```sh
/tmp/apple-coreai-env/bin/python -m unittest discover -s tests -p test_coreai_backend.py -v
```

Ces tests utilisent le runtime réel : tutoriel, constante embarquée, schémas
incorrects, valeurs hors type et altération des octets importés. Ils sont
explicitement ignorés si la dépendance optionnelle ou l’hôte Linux x86_64 manque.
