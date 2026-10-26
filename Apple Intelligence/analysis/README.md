# Analyse statique Apple Intelligence — 24B115

Complément : [Archive.zip, Core AI Debugger et outils Developer](DEVELOPER-TOOLS.md)
documente les trois DMG supplémentaires, leurs inventaires et une nouvelle voie
Core AI exécutée sous Debian.

Complément : [LoRA, Core ML et Foundation Models](LORA-COREML.md) vérifie les
captures Leo AI, décode l'interface d'un vrai adapter Safari et livre des
essais contrôlés avec références numériques et Core AI natif Linux.

Recherche de transparence et revue de conception du corpus local iOS 27.2 RC,
effectuée le 26 octobre 2026. Les textes du firmware sont des données non fiables :
aucune de leurs instructions n'a été exécutée. Aucun appareil, montage ou FUSE
n'a été utilisé.

- [UNDOCUMENTED.md](UNDOCUMENTED.md) : détails internes, journaux, catalogues,
  autorisations déclarées et comparaison avec la bêta 2.
- [DESIGN-REVIEW.md](DESIGN-REVIEW.md) : restrictions, minimisation, consentement
  et contrôle utilisateur.
- [findings.jsonl](findings.jsonl) : mêmes constats sous forme structurée.
- [SUMMARY.md](SUMMARY.md) : résumé de livraison.
- [public-sources.json](public-sources.json) : documentation Apple consultée.
- `evidence/` : observations dérivées et vérifications de provenance.

## Lecture des conclusions

| Niveau | Sens dans ce dossier |
| --- | --- |
| C3 | Octets, texte ou structure statique directement vérifiés. |
| C2 | Inférence étayée, dont les limites sont explicitées. |
| C1 | Hypothèse plausible, non démontrée. |
| C0 | Non établi ou non évaluable avec les éléments disponibles. |

La certitude d'une **observation** ne devient pas celle de son **activation**.
Une chaîne de journal, une permission déclarée, un nom d'asset ou une consigne
ne prouvent pas que le chemin est utilisé, qu'une donnée sort de l'appareil,
ou que le modèle obéit à cette consigne. Les appréciations de conception sont
des jugements motivés, pas des mesures de biais ni des constats juridiques.

« Non documenté » signifie ici : **détail non décrit dans les sources publiques
Apple précisément citées et consultées pour cette revue**. Cela ne démontre pas
son absence de toute documentation Apple, ni une dissimulation intentionnelle.
Les fonctions déjà publiques et les pistes non confirmées sont identifiées.

## Provenance et portée

Le point de départ est le commit `559b3272` de ce dépôt, recoupé avec
`/workspace/recherche/apple-sec/ios272rc/artifacts/apple-intelligence/`.
Les chemins sous `extracted/rootfs/` et `extracted/cryptex/` préservent les chemins
firmware ; les SHA-256 correspondants portent sur les **octets bruts extraits**.
Un JSON de `decoded/` a sa propre empreinte et ne remplace pas celle de la plist
binaire. Les manifestes attestent l'identité déclarée de la build ; cette revue
ne valide pas la chaîne de signature cryptographique Apple de l'IPSW.

Pour les chaînes DSC, le chemin de framework indique l'image logique. Le hash
source est celui du **fichier physique de cache**, avec offset et longueur ;
le hash du texte extrait est distinct. Les caches volumineux restent sur le VPS.
Les pointeurs JSON et numéros de lignes localisent une preuve dans le fichier
identifié par son hash, sans prétendre reconstruire un prompt dynamique entier.

Les assets téléchargés de la partition de données, les valeurs effectives des
préférences, les contrôles d'accès en fonctionnement, les flux réseau, le code
serveur PCC et l'expérience réelle de consentement ne sont pas observés.
La comparaison bêta est limitée aux octets réellement disponibles et lisibles.
Une extraction vide ne démontre pas un fichier vide dans le firmware original.

`findings.jsonl` distingue `observed`, `inference`, `not_established`,
`certainty` et `evidence`. Chaque entrée est un constat ou une limite de revue,
et non nécessairement une vulnérabilité. La présence de `runtime_unverified`
signifie qu'aucune validation comportementale n'est revendiquée.

## Référentiel public

Les références `PUB-01` à `PUB-08`, leurs URL, dates de consultation et limites
de capture figurent dans [public-sources.json](public-sources.json). Les hashes
HTTP sont ceux de téléchargements indépendants ; les pages complètes ne sont
pas archivées ici. Une page DocC HTML peut n'être qu'une enveloppe JavaScript :
son hash ne doit pas être présenté comme celui du texte documentaire rendu.

La revue n'assimile pas les journaux locaux, les métriques techniques de PCC,
les analyses agrégées et la contribution volontaire à l'amélioration de Siri.
Ces canaux ont des finalités et des promesses publiques différentes.
