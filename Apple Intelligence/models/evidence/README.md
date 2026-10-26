# Preuves de la livraison du 26 octobre 2026

Ces fichiers distinguent les contrôles d'octets, les calculs utilisant de vrais
poids et les étapes Apple non réalisées. Aucun résultat d'inférence Apple n'est
déduit d'une inspection statique ou d'un test utilisant des données artificielles.

| Preuve | Ce qui a réellement été vérifié |
| --- | --- |
| [`reproducibility.json`](reproducibility.json) | Relecture APFS forcée des 3 923 fichiers depuis les DMG ; cinq manifestes régénérés identiques octet pour octet. |
| [`inventory-verification.json`](inventory-verification.json) | Tailles/SHA-256, assemblages de catalogue et résolution des 118 611 pointeurs UAF dans les plists originales. |
| [`delivery-verification.json`](delivery-verification.json) | 1 267 groupes, 3 923 fichiers et 2 739 917 787 octets contrôlés ; trois calculs du graphe CPU sur les poids extraits. |
| [`installed-cli.json`](installed-cli.json) | CLI installée par roue, appelée depuis `/tmp` : catalogue, import, vérification, inspection et prédiction CPU ; refus explicite du backend Core ML sur Linux. |
| [`acquisition-entity-verification.json`](acquisition-entity-verification.json) | Nouvelle extraction des huit fichiers EntitySimilarity dans une racine distincte ; image OS intégralement hachée avant extraction ; aucun inventaire APFS privé utilisé. |
| [`acquisition-entity-resume-verification.json`](acquisition-entity-resume-verification.json) | Reprise : huit fichiers réutilisés après contrôle, sans fausse revendication d'une nouvelle extraction. |
| [`acquired-entity-prediction.json`](acquired-entity-prediction.json) | Inférence CPU réelle après import depuis ce cache distinct. |
| [`unittest.json`](unittest.json) | 26 tests : 25 réussis, 1 saut explicite nécessitant le SDK macOS. Les six tests du modèle CPU ont utilisé les vrais octets firmware locaux. |
| [`public-catalog-probes.json`](public-catalog-probes.json) | Quatre URL publiques candidates de catalogue MobileAsset renvoient HTTP 403 ; un diagnostic contient `not found`. Aucun poids acquis par cette méthode. |

Les nombres de groupes incluent les ressources auxiliaires : ils ne représentent
pas des modèles Apple Intelligence indépendants. L'identité du manifeste contrôlé
et les empreintes de code apparaissent dans les rapports. Les sorties CPU sont
celles du moteur indépendant livré (`espresso-linear-cpu-experimental`), avec
entrées/poids Float32 et calcul intermédiaire Float64. L'exécution du runtime
Apple et sa précision Float16 n'ont pas été comparées.

Pour régénérer les contrôles avec le corpus local disponible :

`verify_inventory.py` contrôle aussi les inventaires APFS d'origine conservés
sur le VPS. Dans un clone public avec seulement le cache réacquis, utiliser
`verify_delivery.py` ; cette seconde commande ne dépend pas de ces inventaires.

```sh
cd 'Apple Intelligence'
python3 models/verify_inventory.py
python3 models/verify_delivery.py --run-cpu \
  --report runtime/.state/delivery-recheck.json
cd runtime
python3 -m unittest discover -s tests -v
```

Les procédures d'acquisition sont dans [`../ACQUIRE.md`](../ACQUIRE.md) ; les
commandes installées et les interfaces sont dans
[`../../runtime/README.md`](../../runtime/README.md).

Limites : aucune génération AFM/diffusion, aucun accès PCC, aucune exécution
on-device, aucune compilation du backend Swift ni inférence Core ML sur Mac
réalisés dans cette livraison. Le client Foundation Models système est également
fourni sans preuve de compilation/exécution Apple. Les quatre sondes HTTP ne
démontrent ni l'inexistence d'autres points de livraison, ni un chiffrement ou
une obligation d'authentification. La voie documentée reste le téléchargement
géré par Apple Intelligence sur une plateforme compatible.
