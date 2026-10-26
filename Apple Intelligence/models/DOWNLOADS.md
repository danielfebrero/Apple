# Acquisition des poids téléchargés séparément

État du 26 octobre 2026 : les 3 923 fichiers du cache local proviennent des
volumes firmware. Aucun nouveau poids principal AFM ni modèle de diffusion
n'a été téléchargé pendant ce complément. Le [runtime Debian](../runtime/DEBIAN.md)
progresse avec les poids déjà présents. L'autorisation explicite de Daniel
couvre téléchargement et implémentation du runtime Linux ; aucun nouveau GO
n'est nécessaire pour ces travaux.

## Trois sources distinctes

1. **IPSW local** : [`acquire.py`](ACQUIRE.md) couvre tous les groupes publiés
   avec `--all`, en vérifiant images et fichiers. Cette voie fonctionne déjà
   pour le corpus `24B115` et ne peut pas inventer la partition Data d'un appareil.
2. **Toolkit Foundation Models officiel** : la [page Apple](https://developer.apple.com/apple-intelligence/foundation-models-adapter)
   annonce les poids du modèle système et de son draft, un workflow Python et
   `examples/generate.py`, sur Mac Apple silicon ou machine Linux GPU. Accès
   Apple Developer Program et acceptation des conditions sont requis. La
   dernière version 26.0.0 ne couvre **pas les OS 27 et suivants**. Apple limite
   l'usage de ces assets à l'entraînement d'adaptateurs : ce n'est donc pas un
   remplacement attesté des modèles iOS 27.2 ni une source pour toute la
   génération d'images. Livrable nécessaire : l'archive officielle, avec sa
   version. Le numéro de licence/certificat Developer ne contient pas les poids.
3. **Assets d'un appareil Apple Intelligence activé** : le firmware référence
   `/private/var/MobileAsset/AssetsV2/com_apple_MobileAsset_UAF_FM_GenerativeModels/purpose_auto/`
   et les chemins PreinstalledAssetsV2. Pour un Mac, relever les dossiers
   effectivement présents sous `/System/Library/AssetsV2`,
   `/Library/Apple/System/Library/AssetsV2` et
   `/private/var/db/MobileAsset/AssetsV2` ; la disposition/permission doit être
   confirmée sur la machine, elle n'a pas été observée ici. Conserver bundles,
   manifestes et poids ensemble, puis relever les SHA-256 et la build d'OS.
   Une fois ces octets acquis, leur format réel déterminera le portage, sans
   supposer qu'ils sont équivalents au toolkit 26.

Aucun secret Apple Developer n'est nécessaire dans Telegram. La page publique
consultée ne fournit aucun lien direct d'archive utilisable sans session.
Le compte Developer annoncé par Daniel n'est pas encore accessible sur ce VPS.

## Catalogues MobileAsset : échecs bornés

[`mobileasset-probes.json`](evidence/mobileasset-probes.json) contient cinq
requêtes GET candidates vers `mesu.apple.com/assets/...` et `assets/macos/...`,
familles GenerativeModels/Visual/Overrides : toutes renvoient HTTP 403, avec
le même corps de 19 octets `<h1>not found</h1>\n\n`.
Les suffixes testés sont des **hypothèses de catalogue**, pas des URL de payload
extraites et attestées. Ces échecs ne prouvent ni authentification obligatoire,
ni absence des modèles sur les CDN, ni chiffrement.

[`download_asset.py`](download_asset.py) permet désormais :

```sh
# Sonde bornée, aucune inférence d'authentification à partir du statut HTTP.
python3 models/download_asset.py probe --url URL_CATALOGUE_APPLE \
  --report /tmp/catalogue-probe.json

# Lit un catalogue plist/JSON acquis ou exporté, expose BaseURL+RelativePath.
python3 models/download_asset.py catalogue /chemin/catalogue.plist

# URL de payload réelle + taille et SHA-256 attendus à fournir.
python3 models/download_asset.py fetch --url URL_PAYLOAD_APPLE \
  --size TAILLE_EN_OCTETS --sha256 SHA256_ATTENDU \
  --output /chemin/existant/asset.zip
```

Les placeholders ne sont pas des coordonnées établies. Le téléchargement
refuse les hôtes hors domaines Apple, les redirections non HTTPS, un fichier
final existant et les erreurs de taille/hash. Un temporaire est supprimé après
échec ; seul un fichier vérifié reçoit le nom final. Le contrôle vérifie
l'identité fournie, **pas une chaîne de signature Apple**. L'archive n'est pas
décompressée ou exécutée automatiquement. Les requêtes d'authentification ne
sont pas implémentées ; un lien public complet ou une archive acquise est requis.

Le journal de sondes est une preuve réseau réelle. Les tests de téléchargement
utilisent un transport en mémoire ; ils ne constituent pas une acquisition
réussie des poids AFM.
