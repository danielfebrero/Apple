# Modèles et ressources inventoriés

État courant : **2 016 groupes / 4 751 fichiers / 3 754 333 107 octets**,
sur les sept images de l'IPSW. Le [rapport complet](../analysis/ACQUISITION-GENERATION.md)
conserve le delta par rapport au premier inventaire et la preuve de génération
du petit UniLM du firmware. Les groupes restent des unités de stockage et de
ressources, pas un décompte de réseaux entraînés indépendants.

- [`inventory.md`](inventory.md) : portée, catégories, identifiants, provenance,
  schéma des manifestes et limites.
- [`ACQUIRE.md`](ACQUIRE.md) : reconstruire le cache depuis les images locales
  identifiées, sans dépendre des inventaires privés du VPS.
- [`REDISTRIBUTION.md`](REDISTRIBUTION.md) : conditions vérifiées ; aucun nouveau
  poids binaire publié, cache local exclu de Git.
- [`manifest.json`](manifest.json), [`assets.jsonl`](assets.jsonl) et
  [`references.jsonl`](references.jsonl) : groupes, fichiers et références seules.
- [`../runtime/README.md`](../runtime/README.md) : installation, CLI, interfaces,
  moteurs, exemples d'inférence réelle et procédures compatibles Apple.
- [`../analysis/model-format-audit.md`](../analysis/model-format-audit.md) : revue
  indépendante des formats, du modèle CPU et des dépendances absentes.
- [`evidence/`](evidence/README.md) : preuves de validation de cette livraison.

Les unités de catalogue incluent des modèles, des programmes compilés, des poids
isolés et des ressources auxiliaires. Leur total n'est pas un nombre de modèles
Apple Intelligence exécutables. Les champs `scope` et `inventory_kind` permettent
de les distinguer ; la présence de tous les octets ne prouve pas une prise en
charge du moteur ou une compréhension du pipeline applicatif.

Les poids conservés ici peuvent être contrôlés ensemble, avec le véritable
graphe CPU disponible :

```sh
cd 'Apple Intelligence'
python3 models/verify_delivery.py --run-cpu \
  --report runtime/.state/new-delivery-verification.json
```

Ce contrôle échoue si des fichiers manquent ou diffèrent. Il réalise une
inférence seulement sur le sous-ensemble explicitement accepté par le moteur
CPU ; son rapport ne transforme pas les autres vérifications en prédictions.
