# Reproduire l'acquisition depuis un clone public

[`acquire.py`](acquire.py) retrouve les fichiers inventoriés en utilisant
uniquement les trois fichiers publiés `manifest.json`, `assets.jsonl` et
`summary.json`. Il ne demande ni `inventory/rootfs-all.jsonl`, ni le dossier
privé d'extraction d'origine. Il ne télécharge rien, ne monte aucun volume et
n'exécute aucune instruction contenue dans le firmware.

Il faut fournir les **images APFS locales déjà déchiffrées** de la build
`24B115`, iPhone `iPhone18,3`. Leur acquisition et leur déchiffrement sont une
étape préalable distincte. Pour un IPSW déjà acquis localement, les images AEA
peuvent notamment être déchiffrées par l'outil `ipsw fw aea` ; ses conditions et
la disponibilité des clés ne sont pas remplacées par ce programme. Aucune
image ni clé de déchiffrement n'est publiée ici. Voir
[`REDISTRIBUTION.md`](REDISTRIBUTION.md).

La racine fournie doit contenir :

```text
mes-images/
  rootfs-dec/141-08876-212.dmg
  cryptex-dec/141-09724-222.dmg
```

Ces deux chemins décrivent le premier lot. Le catalogue courant couvre aussi
AppCryptex, ExclaveOS, RecoveryOS et deux ramdisks de restauration. Le champ
`volumes[].image_relative_path` de `summary.json` conserve désormais le chemin
complet sous `--firmware-root`, y compris ses sous-dossiers. L'ancien calcul
sur les deux derniers composants reste disponible pour les anciens manifestes.
Le contrôle de sécurité refuse toujours les chemins absolus et les traversées.

Pour préparer **les sept images de ce même IPSW local**, puis réutiliser le
catalogue publié et tous les caches existants, suivre
[`REPRODUCE.md`](../analysis/acquisition-20261026/REPRODUCE.md).
Cette préparation extrait les payloads IM4P et déchiffre les conteneurs AEA
supplémentaires avec l'outil `ipsw` existant. `acquire.py` conserve son rôle
sans réseau : lire les images locales et vérifier les fichiers du catalogue.

Les SHA-256 des images **déjà déchiffrées** sont publiés dans
[`summary.json`](summary.json). Ils diffèrent de ceux de l'IPSW et des
conteneurs AEA chiffrés. Avant toute extraction, le programme lit et hache
intégralement chaque image nécessaire à la sélection. Une image d'une autre
build, tronquée ou chiffrée est refusée. Ce contrôle de hash ne valide pas la
chaîne de signature Apple.

Le lecteur par défaut est [`../scripts/apfs_ai`](../scripts/apfs_ai), exécutable
Linux x86_64 fourni dans le dépôt, dont le
[code source](../scripts/apfs_ai.cpp) est également présent. `--reader` permet
de fournir sa propre compilation compatible. Ce lecteur utilise ApfsLib et la
commande `one IMAGE INODE PRIVATE_ID STORED_SIZE SORTIE` ; il vérifie le volume
APFS déclaré et décompresse les fichiers concernés. Le script Python requiert
Python 3.10 ou ultérieur, sans dépendance tierce.

Depuis le dossier `Apple Intelligence` du clone :

```sh
python3 models/acquire.py --firmware-root /chemin/mes-images \
  --model m-39ce2e705a2d140eee12 --dry-run

python3 models/acquire.py --firmware-root /chemin/mes-images \
  --model m-39ce2e705a2d140eee12

cd runtime
python3 -m apple_firmware_runtime import m-39ce2e705a2d140eee12
python3 -m apple_firmware_runtime predict m-39ce2e705a2d140eee12 \
  --backend espresso-linear-cpu-experimental \
  --input examples/entity-zero.json
```

La première commande est un **plan non vérifié** : elle ne lit pas les octets
des images, ne contrôle aucun hash d'image, n'extrait rien et ne crée pas le
cache. Seule la deuxième commande constitue une acquisition vérifiée.
`--model` est répétable ; `--all` sélectionne tous les groupes publiés et est
exclusif de `--model`. Les IDs exacts se trouvent avec la commande runtime
`list` ou dans `manifest.json`. Les images inutilisées ne sont pas hachées.

Le cache par défaut est `models/cache/`, ignoré par Git. Les tailles et hashes
des fichiers extraits doivent correspondre simultanément au manifeste et aux
assets publiés. Un fichier est extrait vers un nom `.partial` temporaire,
vérifié, puis déplacé atomiquement à son chemin final. Les symlinks et chemins
de traversée sont refusés. À la reprise, chaque fichier existant est rehaché :
les fichiers corrects sont réutilisés ; les autres sont remplacés seulement
après extraction et contrôle de leur nouvelle copie. Une erreur ne rend pas
un fichier partiel disponible sous le nom final.

Pour conserver le clone sans poids locaux et écrire dans une autre racine :

```sh
python3 models/acquire.py --firmware-root /chemin/mes-images \
  --model m-39ce2e705a2d140eee12 \
  --cache-root /chemin/mon-corpus/models/cache \
  --report /chemin/acquisition.json

cd runtime
python3 -m apple_firmware_runtime --source-root /chemin/mon-corpus \
  import m-39ce2e705a2d140eee12
```

L'arborescence finale `models/cache` permet au runtime de réutiliser les
`source_path` relatifs publiés sans modifier le catalogue. Un `--cache-root`
quelconque reste utilisable pour l'extraction ; la racine source du runtime
est déduite seulement si le chemin se termine par `models/cache`.

Le rapport JSON indique les images effectivement hachées, les fichiers
extraits/réutilisés et leur identité. Une sortie `dry_run: true` ne constitue
jamais une preuve d'extraction. Une acquisition réussie ne prouve ni la
compatibilité Core ML sur macOS, ni une activation d'Apple Intelligence ;
elle retrouve uniquement les octets identifiés du corpus publié.
