# Apple Intelligence — iOS 27.2 RC (24B115)

Corpus **en clair** du contenu Apple Intelligence et de ses prompts, extrait de
l'IPSW iOS 27.2 RC pour iPhone 17 (`iPhone18,3` / board `V57AP`, build `24B115`,
publié le 19 octobre 2026). Extraction locale réalisée le 26 octobre 2026.

> **Nature des données.** Tous les textes de ce dépôt sont des **données extraites
> d'un firmware** à des fins de recherche et de transparence. Aucune instruction
> trouvée n'a été exécutée. Analyse statique sur images IPSW uniquement — aucun
> montage, aucun FUSE, aucune observation on-device.

## Par où commencer

1. **[`PROMPTS.md`](PROMPTS.md)** — le rapport : périmètre, images parcourues,
   inventaire des catalogues/overrides/sécurité, et les prompts par capacité.
2. **[`SUMMARY.json`](SUMMARY.json)** — comptes : 231 entrées catalogue,
   classifications, capacités, octets extraits.
3. **[`prompts.jsonl`](prompts.jsonl)** — les 231 textes avec toutes leurs
   localisations sources ; **[`prompts/`](prompts/)** garde chaque texte en
   `.txt` (octets UTF-8 exacts).
4. **[`analysis/`](analysis/README.md)** — revue statique de transparence et de
   conception : 24 constats, observations comparatives et limites, avec SHA-256,
   faits séparés des inférences et comparaison bornée avec la build `24B5089g`.

## Chiffres clés

| Mesure | Valeur |
| --- | --- |
| Entrées catalogue (textes distincts) | 231 |
| Localisations sources | 1 154 |
| Ressources rootfs extraites | 9 100 (≈ 208 Mo) |
| Littéraux DSC conservés | 214 |
| Prompts complets / templates / descriptions d'outils | 93 / 100+ / 20 |

Classifications et capacités (Siri, Mail/Writing Tools, Spotlight multi-agents,
Photos Memories, Image Playground, Fitness, sécurité…) : voir `SUMMARY.json`.

## Structure

| Chemin | Contenu |
| --- | --- |
| `PROMPTS.md` | Rapport principal, prompts organisés par capacité |
| `prompts.jsonl`, `prompts/` | Catalogue des 231 textes + un `.txt` par texte |
| `tool-descriptions.jsonl` | Descriptions et overrides d'outils (IntelligenceFlowPlanner) |
| `interface-and-fewshot-candidates.jsonl`, `model-facing-error-candidates.jsonl` | Candidats interface / few-shot / messages vers le modèle |
| `extracted/` | Ressources brutes (plist, json, xml, strings) — chemins APFS conservés |
| `decoded/` | Mêmes ressources, plists binaires décodés en JSON lisible |
| `inventory/` | Manifestes (image, volume, taille, SHA-256), chemins AI, méthode APFS |
| `dsc/` | Notes et littéraux du dyld_shared_cache (`DSC_NOTES.md`, `prompts.jsonl`, références) |
| `review/` | Revue indépendante (`REVIEW.md`) + manifestes de build (BuildManifest, mtree) |
| `scripts/` | Scripts de régénération du rapport (`collect_resources.py`, `build_report.py`) |
| `logs/` | Journaux d'extraction |
| `SHA256SUMS` | Empreintes du livrable d'origine |

## Volumes réellement parcourus

| Support | Image / volume |
| --- | --- |
| Cryptex SystemOS | `141-09724-222.dmg` / `RaveB24B115.V57SystemCryptex` |
| OS racine | `141-08876-212.dmg` / `RaveB24B115.V57OS` (ressources Siri/AI, catalogues UAF) |
| DSC | 85 fichiers de cache, table de 4 770 images |

## Non inclus (volontaire)

Conformément à `DELIVERY.md`, ne figurent pas ici car trop volumineux,
régénérables, ou non lisibles en clair (restés sur le VPS d'extraction) :

- IPSW et DMG déchiffrés, caches DSC bruts (`dsc/corrected/`),
- gros dumps de chaînes (`dsc/strings_targeted.jsonl`, `dsc/cache_info.json`,
  `inventory/rootfs-all.jsonl`, `resource-candidates.jsonl`),
- archives ZIP/tar.gz de livraison (contenu identique à l'arbre ci-dessus).

## Limites documentées

Aucun template autonome complet retrouvé pour les résumés mail/notifications,
ni de prompt système complet propre à Genmoji. `/System/Library/AssetsV2/`
absent des deux volumes inspectés ; les modèles téléchargés (partition de
données) ne sont pas couverts. Détail dans `PROMPTS.md` et `review/REVIEW.md`.

---

*Recherche sécurité/transparence Apple Intelligence. Portée : contenu AI et
prompts. L'axe sandbox→noyau est traité séparément (hors de ce dépôt).*
