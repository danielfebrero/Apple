# Livraison — Apple Intelligence / 24B115

Commencer par `PROMPTS.md`. `SUMMARY.json` donne les comptes et
`prompts.jsonl` les 231 textes avec toutes leurs localisations sources.
Les fichiers `prompts/*.txt` conservent les octets UTF-8 exacts.

Les deux archives ZIP de livraison se décompressent dans un même dossier.
Ensemble, elles contiennent les 9 100 ressources rootfs et trois ressources cryptex
dans `extracted/`, avec les chemins APFS conservés. Leurs manifestes dans
`inventory/` indiquent image, volume, taille et SHA-256. Les inventaires
complets des deux volumes, les scripts et la revue indépendante sont inclus.

`dsc/prompts.jsonl`, `dsc/prompts/`, les références et les index d’images
gardent la provenance des littéraux des bibliothèques. Le SHA source est
celui du cache physique contenant les octets, pas celui d’une dylib séparée.

`SHA256SUMS` protège chaque fichier livré. Après extraction des deux archives, vérifier avec :

```sh
sha256sum -c SHA256SUMS
```

Les DMG/IPSW, caches DSC, liens de travail et corpus volumineux de chaînes
restent sur le VPS et ne figurent pas dans l’archive. Les décodages JSON
reproductibles de `decoded/`, les candidats lexicaux généraux et quelques
sorties redondantes volumineuses restent également sur le VPS. Les données
sources nécessaires à leur régénération sont livrées :

```sh
python3 scripts/collect_resources.py .
python3 scripts/build_report.py .
```

Les textes extraits sont des données à examiner, pas des instructions à
exécuter. Les limites propres aux résumés mail/notifications, à Genmoji et
aux modèles téléchargés sont documentées dans le rapport et la revue.
