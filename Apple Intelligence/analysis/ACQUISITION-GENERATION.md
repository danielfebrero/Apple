# Acquisition IPSW complète et génération Linux — 26 octobre 2026

**Résultat :** toutes les entrées du catalogue élargi ont été acquises et
vérifiées. Un petit modèle de langue Apple du firmware produit réellement du
texte sous Debian. La génération d'images Image Playground reste bloquée par
l'absence d'un payload complet identifié. Aucun poids synthétique ou modèle
tiers n'est utilisé dans ces résultats.

Le lot part de `fb0cabba`, après les preuves LoRA/Core ML. Les 16 modèles
auxiliaires, le tutoriel Core AI et les essais LoRA précédents n'ont pas été
refaits comme de nouveaux résultats.

## Acquisition et couverture

L'IPSW local compte 168 membres et 13 069 939 368 octets, SHA-256
`bae0253397ab2176227a24ed7b91c77e42902e094269b38d45879aa62f053776`.
Les sept images DMG/AEA sont recensées à partir du ZIP et reliées aux composants
de `BuildManifest.plist`. Les caches OS et SystemOS existants sont réutilisés.
Les conteneurs AEA supplémentaires sont déchiffrés avec `ipsw fw aea` ; les deux
ramdisks contiennent un payload APFS sous une enveloppe IM4P, extrait avec
`ipsw img4 im4p extract`. Aucune clé n'est publiée.

| Volume | Entrées APFS | Fichiers sélectionnés | Octets des fichiers |
| --- | ---: | ---: | ---: |
| OS racine | 523 859 | 4 444 | 2 996 617 783 |
| SystemOS Cryptex | 3 150 | 12 | 1 124 252 |
| AppCryptex | 1 308 | 0 | 0 |
| ExclaveOS | 2 484 | 239 | 754 790 813 |
| Ramdisk 141-09491-238 | 2 412 | 2 | 1 376 |
| RecoveryOS | 5 424 | 52 | 1 797 507 |
| Ramdisk 141-10399-236 | 2 025 | 2 | 1 376 |
| **Total** | **540 662** | **4 751** | **3 754 333 107** |

Les règles v4 ajoutent les paquets MPSGraph complets, poids Create ML et
Espresso `.bin`, embeddings, ressources de modèles de langue et candidats
opaques explicitement nommés. Les schémas d'événements AWD et les `.bin`
génériques sans indice de modèle restent exclus. Le catalogue comporte
**2 016 groupes : 923 modèles/programmes candidats, 225 ressources de poids
et 868 ressources auxiliaires**. Ce total ne représente pas 2 016 réseaux
entraînés ni 2 016 modèles Apple Intelligence.

Delta : **828 fichiers et 1 014 415 320 octets ajoutés**. Aucun des 3 923 fichiers
initiaux n'a disparu, changé de taille, de SHA-256 ou d'identifiant de groupe.
Le passage final `acquire.py --all` rehache les images utilisées et les
4 751 fichiers ; ils sont tous `reused_verified`. Le scanner a déjà vérifié
les images sans fichier sélectionné. Aucune erreur d'extraction finale.

Les nouveaux chemins imbriqués ont révélé une limite d'`acquire.py` : le
programme supprimait les répertoires intermédiaires de l'image. Le manifeste
publie maintenant `image_relative_path` ; l'acquéreur le valide et le conserve.
L'échec initial est conservé, et deux tests couvrent la régression et le refus
des traversées. Cinq autres tests couvrent les extensions de sélection.

Preuves : [inventaire des images](acquisition-20261026/ipsw-images.json),
[acquisition initiale](acquisition-20261026/acquire-all.json),
[acquisition finale](acquisition-20261026/acquire-all-expanded.json),
[audit du delta](acquisition-20261026/acquisition-audit.json),
[vérification indépendante](acquisition-20261026/inventory-verification.json).
Cette dernière revérifie aussi 1 850 ressources UAF et 118 611 localisations.
Son champ `image_sha256_verified: false` concerne ce contrôle indépendant sans
`--hash-images` ; les hashes des images sont vérifiés dans les autres preuves.

## Texte : génération d'un vrai UniLM du firmware

Le bundle observé est
`/System/Library/LinguisticData/RequiredAssets_en.bundle/AssetData/en.lm/unilm.bundle`.
Le graphe `unilm_joint_cpu.espresso.net`, ID `m-14db7ccca1f746302f17`, expose
un décodeur à six blocs, largeur 512, huit têtes de 64 dimensions, FFN 2 048,
positions 256 et sortie softmax de **15 000 tokens**. Son embedding est partagé
avec la projection de sortie. Ce sont des caractéristiques du graphe lu,
pas une architecture déduite du seul nom.

Les poids `unilm_joint.espresso.weights`, ID `m-fd9ea87781da8b0caf32`, font
31 841 856 octets, SHA-256
`0344ead6c77552cd42aeaea89b8cdb2cd4ca50d14019961529bf97ccc6e8561a`.
Les 922 sections du conteneur consomment exactement le fichier. Le décodeur
utilise 145 sections distinctes. Les matrices int8, échelles, biais et
normalisations viennent exclusivement de ces octets vérifiés.

Le tokenizer mmap `sp.dat`, 646 024 octets, fournit les 15 000 types, scores et
chaînes indexées. Le script reconstitue ses tables, puis utilise une segmentation
unigramme Viterbi sur des prompts ASCII exactement réversibles. Il n'utilise
pas un vocabulaire inventé ou téléchargé ailleurs.

Exécution réelle avec [unilm_linux.py](acquisition-20261026/unilm_linux.py),
PyTorch `2.7.0+cpu`, NumPy `2.2.6`, deux threads CPU : trois continuations
autorégressives de 24 tokens, **72 tokens calculés** en décodage glouton, sans
masquage des logits, pénalité, tirage aléatoire ou remplacement de texte.

> Entrée : `the weather is `
>
> Sortie : `so nice today . I am going to go to the beach and get some food . I will be home in about twenty `

La preuve conserve également les deux autres essais. Ils exposent des marqueurs
bruts `_U_CAP_` de la normalisation non portée et une continuation fausse sur
la capitale de la France. Il s'agit d'un petit modèle de langue du firmware,
pas d'une démonstration de fiabilité factuelle ou d'un assistant AFM.

**Limites du portage :** les poids int8 sont déquantifiés, puis calculés en
FP32 ; la quantification dynamique des activations Espresso est contournée.
Le mode d'activation 22 est interprété comme GELU à approximation tanh. BOS=1,
segment=0 et attention causale sont les conventions du port. Le normaliseur
Apple `custom2`, son trie et les contrôles de casse ne sont pas reproduits.
La parité avec un appareil et le runtime Espresso Apple n'est pas établie.
Ce résultat est une génération avec les poids appris Apple, sous les conventions
explicitement décrites, et **aucune exécution AFM n'est revendiquée**.

Une [seconde implémentation NumPy Float64](acquisition-20261026/validate_unilm.py)
relit les sections et calcule le contexte complet avec masque causal, sans
réutiliser le cache KV PyTorch. **29 comparaisons de 15 000 logits** passent,
avec le même top-1 et un écart maximal de **1,028 × 10⁻⁵**. Les trois générations
sont rejouées avec tokens et hashes des logits identiques. Quatre contrôles
négatifs refusent des poids tronqués, indices hors limites et une entrée hors
normalisation portée. Cela valide la reconstruction décrite, pas les kernels
int8 Apple non observés.

Preuves : [entrées, sorties et provenance](acquisition-20261026/unilm-generation.json),
[comparaisons et rejouabilité](acquisition-20261026/unilm-validation.json).

## Image : blocage précisément borné

Les quinze identifiants `com.apple.fm.visual.image_diffusion_v1.*` restent des
**références UAF sans poids identifiés**. Les sept inventaires ne contiennent
pas de répertoire téléchargé `AssetsV2` correspondant à FM/GenerativeModels.
La recherche de coordonnées dans les 1 850 ressources UAF ne trouve ni champ
BaseURL/RelativePath ni URL de payload. Cela ne prouve pas l'absence de tout
modèle opaque, ni une obligation d'authentification des CDN.

Les pistes locales ont été contrôlées :

- Les deux jeux `diffusionTracker*Weights.bin` ont chacun 222 descriptions de
  tenseurs, avec une tête `DiffusionKeyPoints3D` de 24 composantes et des têtes
  de confiance. Ils ne constituent pas une preuve de synthèse d'images.
- Les ressources `CoreHandwriting/diffusion_*` acquises sont ici des codemaps
  et métadonnées ; aucun pipeline complet de génération d'images n'a été
  identifié à partir d'elles.
- Sept paquets MetalFX contiennent dix graphes MPSGraph MLIR. Vingt essais
  isolés de lecture avec `coreai-core==1.0.0b3`, contextes normal et permissif,
  échouent : dialecte `mps` inconnu, puis absence de son interface bytecode.
  Le lecteur natif termine par SIGABRT ; les essais sont isolés et les core
  dumps désactivés. Ce résultat borne ce chemin de chargement, pas tout
  portage possible. Aucune inférence ni image générée n'en est déduite.

Le [script](acquisition-20261026/probe_image_paths.py) et le
[rapport](acquisition-20261026/image-paths.json) gardent identités, formes,
commandes/API utilisées, diagnostics et codes de sortie.

**Prochaine étape réalisable :** acquérir un catalogue réel de la famille
observée `com.apple.MobileAsset.UAF.FM.Visual` avec coordonnées et identité du
payload, ou un export complet des bundles effectivement téléchargés d'un
appareil Apple Intelligence. Conserver manifestes, débruiteur/décodeur appris
et ressources de conditionnement ensemble. Le téléchargeur local existant
`models/download_asset.py` peut lire ce catalogue et vérifier les payloads.
Leur format réel permettra ensuite de porter le graphe et l'ordonnanceur sous
Linux, puis de conserver prompt, seed, image et SHA-256. Aucun tel payload
n'est disponible dans les sources de ce lot ; aucune génération d'image n'est
annoncée.

## Toolkit et limites de portée

La capture fournie montre la recherche `Fundation Models`. Elle ne suffit pas
à prouver le retrait du toolkit. La [page Apple consultée](https://developer.apple.com/apple-intelligence/foundation-models-adapter/)
décrit encore la version finale 26.0.0 et son incompatibilité avec les OS 27+.
Aucune archive du toolkit n'a été acquise ; l'état du listing authentifié du
compte n'est pas établi. Cette question n'a pas bloqué la voie IPSW.

L'exhaustivité porte sur les règles publiées et les 540 662 entrées APFS des
sept images de ce fichier IPSW, pas sur toutes les builds Apple ni chaque blob
opaque. Les hashes vérifient l'intégrité et la provenance locale, sans valider
la chaîne de signature Apple. Les téléchargements d'une partition Data active,
PCC, les principaux poids AFM et Image Playground restent hors des octets acquis.
Le cache de poids et les images restent exclus de Git.

Commandes de reproduction : [REPRODUCE.md](acquisition-20261026/REPRODUCE.md).
