# Apple Intelligence — revue statique 24B115

**24 constats, observations comparatives et limites documentés. Aucun abus ni transfert clandestin de prompts démontré.**

- **Catalogues et diagnostics :** overrides de modèles/sécurité, alias locaux/serveur, métriques DifferentialPrivacy et mécanismes de diagnostic sensibles présents. Leur activation, les données réellement transmises et les valeurs de consentement restent inconnues.
- **Autorisations :** le fournisseur de sécurité déclare lecture des assets `purpose_auto` et `sideload`, et accès au flux Biome `SafetyOverrides`. Cela ne prouve ni chargement non signé ni permission effective sans autres contrôles.
- **Conception :** Photos Memories prévoit d’exclure récits religieux, politiques, tristes ou négatifs ; Spotlight contient des heuristiques familiales fondées sur le ton, les horaires et les adresses professionnelles. Ce sont des consignes et risques de conception, pas des effets mesurés.
- **Données personnelles :** des templates prévoient domicile/relations, historique, contexte écran et récupération de renseignements sensibles. Ils comportent aussi des limites de nécessité, des conditions et des règles de citation. Aucun accès indiscriminé n’est établi.
- **Bêta → RC :** ModelCatalog présente 13 nouveaux littéraux et un ancien non retrouvé dans les sections comparées. Les sections de chaînes de trois autres frameworks sont identiques. L’extraction rootfs bêta est presque entièrement vide : aucun changement de prompt ou de politique ne peut être déduit de ses stubs.

Les contrôles parentaux, PCC, certaines métadonnées techniques et les contributions volontaires à l’amélioration de Siri sont déjà décrits par Apple. Les détails internes sont comparés à huit références officielles ; « non documenté » ne signifie pas absence de toute documentation Apple.

Livrables : [UNDOCUMENTED.md](UNDOCUMENTED.md), [DESIGN-REVIEW.md](DESIGN-REVIEW.md), [findings.jsonl](findings.jsonl), méthode et preuves dans `analysis/` du [dépôt danielfebrero/Apple](https://github.com/danielfebrero/Apple/tree/master/analysis).

Chaque entrée distingue faits, inférences et non-établi, avec chemin source, SHA-256 et localisation. Les 9 103 ressources extraites (217 712 831 octets) concordent avec les manifestes et les copies originales. Analyse statique uniquement : aucun appareil, montage ou FUSE ; aucune instruction firmware exécutée.

Vérification finale : 141 ancres, 72 fichiers rehachés, 16 sections de cache comparées et 14 littéraux de delta relus ; aucun écart. Les niveaux C3/C2 qualifient séparément les faits statiques et leurs interprétations ; l’activation reste non établie.
