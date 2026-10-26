# Acquisition APFS sans montage

Le [complément IPSW complet](../analysis/ACQUISITION-GENERATION.md) applique
ce même lecteur aux sept images et conserve leurs inventaires et hashes.
Les comptes ci-dessous décrivent l'extraction initiale des ressources AI.

Lecteur dérivé de `/workspace/opt/build/dscextract.cpp`, lié à l'archive existante `/workspace/opt/build/obj/libapfsall.a` (ApfsLib du projet apfs-fuse). Aucun montage ni appel FUSE. Ouvrir un conteneur avec `ApfsContainer::Init(1000000)` et le volume numéro 0; le checkpoint explicite évite l'incohérence « latest » déjà constatée dans cet environnement.

## Inventaires

`scripts/apfs_ai inventory <dmg>` parcourt la racine APFS et écrit une ligne JSON par entrée: chemin absolu, type APFS (`4=directory`, `8=regular`, `10=symlink`), inode, private_id, taille du dstream ou taille décompressée, taille décompressée inode, drapeaux BSD et résultat de récupération de l'inode. Les erreurs de parcours sont écrites sur stderr. Les journaux d'inventaire ne signalent aucune erreur.

- `cryptex-all.jsonl`: volume `RaveB24B115.V57SystemCryptex`, image `_ipsw/cryptex-dec/141-09724-222.dmg`, 3 150 entrées.
- `rootfs-all.jsonl`: volume `RaveB24B115.V57OS`, image `_ipsw/rootfs-dec/141-08876-212.dmg`, 523 859 entrées. Cette image OS a été extraite de l'IPSW existant puis déchiffrée avec `ipsw fw aea`; aucun montage.
- `rootfs-ai-paths.jsonl`: sous-ensemble de noms pertinents pour AI.
- `apfs-summary.json`: comptages et chemins témoins par capacité.

## Extraction des ressources

Chaque fichier est ouvert dans un processus APFS neuf pour éviter la pollution du cache B-tree observée dans l'extracteur antérieur. Les fichiers marqués `bsd_flags & 0x20` passent par l'attribut `com.apple.decmpfs` et `DecompressFile`; les autres passent par `ReadFile(private_id, offset, size)`.

Commande reproductible:

```sh
scripts/apfs_ai one <dmg> <inode> <private_id> <size> <output>
```

`scripts/extract_ai_resources.py` contient les règles de sélection et réalise l'extraction en quatre workers, chacun lançant un processus neuf par fichier. Il ne modifie pas les volumes source. Les ressources cryptex sont dans `extracted/cryptex/` et les ressources OS dans `extracted/rootfs/`, avec l'arborescence APFS conservée. Les manifests `*-extracted.jsonl` associent chemin source, image, volume, inode, fichier local, code de retour, taille attendue, taille extraite et SHA-256 des octets **décompressés**.

État final: 3 ressources cryptex et 9 100 ressources rootfs; aucune erreur ni discordance de taille. Les 9 100 fichiers rootfs totalisent 217 709 111 octets. Le journal `rootfs-extract.log` concerne les 9 049 fichiers initiaux; les 51 compléments de revue figurent dans le manifest final (métadonnées GenerativeFunctions et extension SafetyInferenceProvider).

Les fichiers opaques de `Metadata.generativefunctions` contiennent tous le même JSON de 23 octets: `{"syntaxTree":""}` avec espaces et retours à la ligne. Ils ne renferment pas de prompts.

## Correction de deux fichiers DSC déjà extraits

L'ancien extracteur traitait les fichiers compressés comme des extents bruts. Cela produisait pour `.81.dyldlinkedit` un en-tête UUID de `.80.dyldreadonly`, et un en-tête invalide pour `.symbols`. La décompression Decmpfs a restauré les UUID attendus:

- `dsc/corrected/dyld_shared_cache_arm64e.81.dyldlinkedit`: 698 679 296 octets, UUID `E422C513-5B8E-3FF2-B82C-21282F01D8D1`.
- `dsc/corrected/dyld_shared_cache_arm64e.symbols`: 1 252 147 200 octets, UUID `D7E18327-75F2-34D9-98A1-C57386CB26E3`.

Les fichiers DSC initiaux n'ont pas été modifiés. `dsc/corrected/dyld_shared_cache_arm64e.81.raw-wrong.dyldlinkedit` conserve temporairement la lecture incorrecte, pour diagnostic; il ne doit pas être utilisé comme source d'analyse.
