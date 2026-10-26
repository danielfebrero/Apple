# Reproduire l'acquisition Visual

Depuis la racine du dépôt Apple. Python 3.11 standard, OpenSSL 3 et
`ipsw 3.1.704` (`/workspace/tools/bin/ipsw`) ont été utilisés. Les binaires et
JWT bruts restent dans `Apple Intelligence/models/cache/mobileasset-visual/`,
ignoré par Git. Les racines Apple publiques et leurs provenances sont jointes.

## Vérifications sans réseau, à partir des octets acquis

```sh
python3 'Apple Intelligence/analysis/visual-20261026/verify_catalogue_signature.py' --at-time 1793046504
python3 'Apple Intelligence/analysis/visual-20261026/process_acquired.py'
python3 'Apple Intelligence/analysis/visual-20261026/audit_sources.py'
python3 -m unittest discover -s 'Apple Intelligence/runtime/tests' -p 'test_mobileasset_visual.py' -v
python3 -m unittest discover -s 'Apple Intelligence/runtime/tests' -p 'test_download_asset.py' -v
```

Le premier script vérifie les signatures à l'heure historique du rapport ; ce
n'est pas une garantie de fraîcheur aujourd'hui. Le second revalide la signature
du catalogue Rave, les 24 archives et les 217 fichiers avant de réutiliser les
sorties existantes. Une sortie absente est déchiffrée AEA et extraite, mais DSME
reste protégé. Il ne remplace pas une sortie existante qui diffère. Le troisième
relit la définition UAF et vérifie les offsets/littéraux et hashes des caches
firmware `.30`/`.42` déjà déposés.

Les snapshots bruts ont ces SHA-256 :

- Luck : `d0e4de3141bf3fc0fc5d20771421c4a4e3f665d7c3f8643b59965b6e52a3d2f5`.
- Rave : `d0506afaf3b8ef90eb99d0357075f7e5207388e37c9510bdbba99cb62d1ea936`.

Les autres réponses sont identifiées dans `catalogue-signatures.json`.

## Nouvelle requête publique

Créer un répertoire de preuves distinct ; le client refuse d'écraser les noms
déjà utilisés. Conserver le raw dans un cache ignoré, car il contient les clés
d'archive publiées par Pallas.

```sh
mkdir -p 'Apple Intelligence/models/cache/mobileasset-visual/requery'
python3 'Apple Intelligence/models/pallas_catalog.py' \
  --request 'Apple Intelligence/analysis/visual-20261026/visual-rave-request.json' \
  --name fresh-rave \
  --output 'Apple Intelligence/models/cache/mobileasset-visual/requery' \
  --raw-output 'Apple Intelligence/models/cache/mobileasset-visual/requery' \
  --root-ca 'Apple Intelligence/analysis/visual-20261026/AppleIncRootCertificate.cer'
```

Une nouvelle réponse peut changer d'ordre, de nonce, de versions ou de
contenu. **Ne pas reprendre aveuglément les indices** de `selection.json` avec
une autre réponse. Vérifier sa signature puis sélectionner par
`AssetSpecifier`, `AssetVersion`, taille et mesure. Les rapports expurgés ne
sont pas eux-mêmes des JWT vérifiables ; leur lien avec le raw est son SHA-256.

Pour le snapshot Rave exact ci-dessus, l'acquéreur réutilise et rehache une
archive déjà présente ; la destination du rapport doit être nouvelle :

```sh
python3 'Apple Intelligence/models/acquire_mobileasset.py' \
  --catalogue 'Apple Intelligence/models/cache/mobileasset-visual/catalogues/visual-rave.response' \
  --index 0 --index 4 --index 13 \
  --output 'Apple Intelligence/models/cache/mobileasset-visual/archives' \
  --report 'Apple Intelligence/models/cache/mobileasset-visual/requery/reused.json'
```

Le raw est décodé pour les coordonnées ; ce script ne remplace pas le
vérificateur de signature. Les SHA-1 du catalogue et SHA-256 locaux sont
distingués dans chaque reçu. `models/download_asset.py` reste inchangé et sert
toujours aux payloads dont un SHA-256 attendu est établi.

`process_acquired.py` transmet les clés d'archive en mémoire à `ipsw fw aea` et
n'enregistre pas leurs valeurs dans les commandes de preuve. Le processus
d'extraction AA ne supporte que le sous-ensemble observé. Il valide SH2 quand
présent, pas YEC ; il ne déchiffre ni DSME ni le cryptex protégé.

## Portée du cache et preuve des acquis antérieurs

`acquisition-audit.json` est l'inventaire courant. Les journaux `download-rave-*`
et `initial-downloads.json` gardent les premières acquisitions. Les deux
passages de traitement gardent un journal séparé. Les plists UAF 27.2 sont
compatibles par borne OS seulement ; aucune sélection hardware n'est établie.

```sh
python3 'Apple Intelligence/models/verify_delivery.py' \
  --report 'Apple Intelligence/models/cache/mobileasset-visual/requery/previous-delivery.json'
```

`previous-delivery-verification.json` prouve que les 4 751 fichiers de firmware
précédents restent conformes. Aucun poids Visual chiffré n'a été ajouté au
catalogue de modèles exécutables, aucune inférence image n'a été réalisée.
