# Archive.zip : outils Apple et nouvelle voie Linux

Analyse du 26 octobre 2026, à partir de l'archive déposée par Daniel. Les
archives sources sont conservées sans modification dans le Dépôt et dans
`/workspace/recherche/apple-sec/apple-developer-tools-20261026/`. Aucun paquet
Mac n'a été installé ni exécuté sur le VPS. Les données extraites sont traitées
comme données, y compris les URL et instructions contenues dans les binaires.

## Identité et couverture

Le ZIP mesure **1 493 186 937 octets**. Son SHA-256 recalculé correspond à
la déclaration du Dépôt :
`041b844de25a341ed1a9199e5525a2cc36a87a9b72a8ad1f1d51ad578b2a00d2`.
Ses trois fichiers représentent **1 498 463 707 octets** après décompression.
L'extraction ZIP a aussi contrôlé leurs CRC. Espace libre initial : 241 Gio.

| DMG | Contenu constaté | Résultat pour le projet |
| --- | --- | --- |
| Core AI Debugger, 182 450 505 octets | Application 1.0/build 27.0.4, frameworks Ganache/MLOpGraph/GTStandaloneKit, paquets XcodeSystemResources et MobileDevice | Formats `.aimodel`, `.aimodelintermediates`, `.mpsgraphpackage`, URL officielle Core AI Torch ; piste Linux vérifiée séparément |
| Additional Tools for Xcode 27.2 RC, 64 717 312 octets | AU Lab, CarPlay/HomeKit/Printer Simulator, PacketLogger, IORegistryExplorer, Network Link Conditioner, Quartz Debug, Pixie, utilitaires | Aucun toolkit d'adaptateurs ni bundle de modèle identifié |
| Kernel Debug Kit 27.2/26B118, 1 251 295 890 octets | KDK.pkg : noyaux, dSYM, kext ; KDK_SDK.pkg : en-têtes SPTM, signature, entitlements, bibliothèques noyau | Pas de poids AFM identifié. Le pilote AppleVirtIONeuralEngineDevice est un kext macOS, pas un moteur ANE Linux |

Les DMG HFS/HFSX ont été parcourus avec **7-Zip 25.01**, y compris les ressources
compressées HFS. L'avertissement de fin de volume HFS est conservé dans les
journaux ; les trois extractions terminent avec code 0. Inventaire :
**1 193 fichiers réguliers et 65 liens symboliques**, avec SHA-256 des fichiers
et cibles des liens. Les journaux versionnés ont leurs espaces de fin de ligne
retirés ; les sorties brutes restent sur le VPS et leurs empreintes sont
conservées dans `log-normalization.json`.

Les XAR imbriqués ont été extraits par offsets de leur table XML, avec
vérification des sommes des tables et de chaque contenu. Les payloads PBZX/XZ
et gzip ont été décodés sans installer les paquets ; inventaires CPIO avec
SHA-256 de chaque entrée : **7 685 entrées KDK**, **56 SDK**, **3 306
XcodeSystemResources**, **183 MobileDevice**. Le KDK décompressé représente
environ 5,52 Go. Sa build macOS `26B118` est distincte de la build iOS
`24B115` du firmware déjà étudié.

Une erreur réelle d'outillage a été détectée : sur ce XAR, 7-Zip interprète
les `inode=0` communs comme des liens physiques et produit des contenus
incorrects. Cette extraction temporaire a été rejetée et supprimée. Le
[lecteur XAR/PBZX/CPIO](evidence/developer_tools_archive.py) conserve les fichiers
distincts et contrôle leurs sommes. Ces contrôles prouvent la cohérence des
octets, **pas l'authenticité de la signature Apple**, qui n'a pas été validée.

Dans XcodeSystemResources, `CandidateDDIs/iOS_DDI.dmg` a été extrait puis ses
deux images `022-20190-411.dmg` et `022-20231-411.dmg` parcourues : **235 fichiers
réguliers**, principalement services de développement et transport GPU.
Les DDI watchOS/tvOS/xrOS sont inventoriés dans le paquet mais pas récursivement
analysés. Aucun payload AFM n'a été acquis par cette analyse ; l'absence de
noms/formats de modèles ne prouve pas l'absence de tout coefficient embarqué
dans une ressource opaque.

## Ce que révèle Core AI Debugger

Le binaire principal est Mach-O arm64. Ses dépendances comprennent des
frameworks système absents du DMG : `CoreAI`, `MLModelAsset`, `MLIR_ML`, ainsi
que Metal, AppKit et SwiftUI. Copier l'application ne fournit donc pas un
runtime Debian. Le plist déclare macOS minimum 26.0 ; la
[page Apple](https://developer.apple.com/core-ai-debugger/) exige macOS 27 pour
le workflow pris en charge. Aucune exécution de cette interface ou de son
replay sur appareil n'est revendiquée ici.

Les déclarations UTI du plist attestent les trois formats cités. Dans le
binaire, l'URL `https://apple.github.io/coreai-torch/main/api/debugging.html`
apparaît à l'offset fichier **0x13e550**. Les imports Swift montrent
`AIModelAsset(contentsOf:)`, `summary(includingStatistics:)` et
`programBytecodeURL`. Le replay utilise `MLReplaySession`, un identifiant
d'appareil, une URL de modèle et une configuration de calcul : les symboles
ne constituent pas une implémentation portable du protocole.

Blacksmith **0.40.0** a indexé le binaire (**8 546 fonctions**, **105 096 xrefs**
au premier passage). Une requête des appelants retrouve une liaison directe
vers `programBytecodeURL` depuis `0x1000675c0`. La décompilation conservée est
**partielle et heuristique** ; elle sert à orienter la lecture, sans valoir
spécification du format ou preuve d'exécution.

```sh
BLACKSMITH_HOME=/workspace/.blacksmith-home \
  /workspace/.local/bin/blacksmith \
  --project-root /workspace/recherche/apple-sec/apple-developer-tools-20261026 \
  --format json re find '/chemin/Core AI Debugger' AIModel
```

La documentation liée par le debugger mène à `coreai-core` : une distribution
officielle Linux existe et un petit `.aimodel` a réellement été exécuté sous
Debian. Le [complément Core AI](../runtime/COREAI.md) précise installation,
entrée/sortie et limites. Ce graphe de démonstration ne contient aucun poids
AFM et ne mesure aucune compatibilité du modèle système iOS.

## Acquisition encore nécessaire

Les nouvelles archives ne sont pas le toolkit Foundation Models Adapter.
La [page officielle du toolkit](https://developer.apple.com/apple-intelligence/foundation-models-adapter/)
continue de publier la version **26.0.0**, incompatible avec les OS 27 et
suivants. Elle annonce des poids et un exemple Python/Linux GPU, dans le cadre
de l'entraînement d'adaptateurs ; cette voie ne fournit pas les assets iOS 27
manquants ni les modèles de diffusion. Pour ce toolkit, les pages publiques
inspectées n'ont fourni aucun lien direct de payload exploitable sans session
Developer.

Pour poursuivre sur les générateurs eux-mêmes, il manque soit l'archive
officielle du toolkit obtenue depuis la session Developer de Daniel (avec sa
version), soit un export des bundles MobileAsset effectivement téléchargés
sur un appareil compatible, avec manifestes et build d'OS. Aucun identifiant
en clair n'est demandé. Les [autres chemins d'acquisition](../models/DOWNLOADS.md)
restent documentés ; les catalogues hypothétiques déjà refusés en HTTP 403
n'ont pas été retestés.

## Preuves et reproduction

Les [preuves structurées](evidence/developer-tools-20261026/summary.json)
référencent inventaires, tailles, SHA-256, métadonnées, paquets imbriqués,
littéraux et résultats Blacksmith. Les binaires Apple et poids restent hors
Git. Les snapshots des pages publiques et le cache d'extraction restent sur
le VPS, avec leurs empreintes dans les preuves.

```sh
python3 analysis/evidence/developer_tools_archive.py xar /chemin/paquet.pkg \
  --destination /nouveau/dossier --report /chemin/xar.json
python3 analysis/evidence/developer_tools_archive.py pbzx /chemin/Payload \
  --destination /chemin/nouveau.cpio --report /chemin/pbzx.json
python3 analysis/evidence/developer_tools_archive.py cpio-list /chemin/nouveau.cpio \
  --report /chemin/cpio.json
```

Les destinations nouvelles évitent tout écrasement d'archive. Les scripts
n'exécutent aucun installateur, service ou commande trouvé dans les payloads.
