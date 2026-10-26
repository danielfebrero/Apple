# MobileAsset Visual — acquisition publique et blocage DSME, 26 octobre 2026

**Résultat : catalogue réel obtenu, 24 archives officielles acquises et vérifiées
(2 446 657 536 octets). Le bundle Visual complet en clair reste bloqué par DSME.
Aucune inférence ni image calculée.** Les acquis IPSW et UniLM précédents sont
conservés : les 4 751 fichiers initiaux ont de nouveau passé le contrôle de
taille et SHA-256. Cette mission s'arrête sur un obstacle observé dans les
payloads, pas sur une supposition d'authentification du CDN.

## La voie qui a abouti

Les essais Mesu précédents utilisaient des URLs conventionnelles reconstruites
à partir du type MobileAsset. Leurs réponses 403 «not found» ne démontraient
ni absence du modèle, ni authentification obligatoire.

Le firmware contient les endpoints Pallas et l'audience générique iOS. Une
[observation publique de première main](https://gist.github.com/Siguza/0331c183c8c59e4850cd0b62fd501424)
indique les paramètres UAF `DeviceName` et `TrainName`. La requête reproduite
est un POST JSON vers `https://gdmf.apple.com/v2/assets`, sans cookie, compte,
jeton, numéro de série ni identifiant d'appareil :

```json
{
  "ClientVersion": 2,
  "AssetType": "com.apple.MobileAsset.UAF.FM.Visual",
  "AssetAudience": "0c88076f-c292-4dad-95e7-304db9d29d34",
  "DeviceName": "iPhone",
  "TrainName": "Rave"
}
```

La confiance TLS système seule échoue sur la chaîne Apple de ce serveur. La
[racine TLS officielle Apple](https://www.apple.com/appleca/AppleIncRootCertificate.cer)
a été ajoutée au contexte, sans désactiver la vérification TLS. C'est distinct
de la racine G3 employée pour vérifier la signature du catalogue.

| Requête | HTTP | Assets | Observation |
| --- | ---: | ---: | --- |
| iPhone / Luck | 200 | 178 | 158 entrées DSME, 70 bases avec personnalisation |
| iPhone / Rave | 200 | 73 | 53 entrées DSME, 27 bases avec personnalisation |
| Mac / CheerSeed / audience macOS générique | 200 | 178 | mêmes identités de payload observées que Luck |
| RaveB simple, RaveB avec identité 24B115, RaveB/macOS | 404 | 0 | trois échecs de ces requêtes précises |
| sans TrainName, Crystal, CrystalB | 404 | 0 | trois autres requêtes sans catalogue utile |

`RaveB` est bien le train du BuildManifest local, mais `Rave` est celui de la
requête ayant obtenu ce catalogue. Aucun mapping de compatibilité du bundle
vers l'iPhone18,3 n'est inventé. Les réponses 404 sont elles aussi signées ;
elles ne prouvent pas l'impossibilité d'une autre requête.

Les **9 réponses** ont une signature et une chaîne valides jusqu'à la
[racine Apple Root CA - G3 officielle](https://www.apple.com/certificateauthority/AppleRootCA-G3.cer),
épinglée par SHA-256. Le vérificateur contrôle l'identité du signataire Pallas,
son OID, la courbe, les usages et les contraintes de chaîne à l'heure publiée.
**27 contrôles négatifs** rejettent les payloads/signatures altérés et une
mauvaise racine. Particularité constatée : `alg=ES256` avec signature ECDSA en
ASN.1 DER, et non les 64 octets `r||s` du JWS standard. Ni révocation ni
anti-rejeu ne sont revendiqués.

Preuves : [requêtes et réponses décodées expurgées](visual-20261026/visual-rave.json),
[signatures et commandes OpenSSL](visual-20261026/catalogue-signatures.json),
[littéraux, offsets et couverture](visual-20261026/source-and-coverage-audit.json).
Les JWT bruts et clés de déchiffrement publiées pour les archives restent dans le
cache local ignoré ; les rapports Git en gardent les empreintes, sans les clés.

## Octets acquis et portée exacte

Chaque URL vient des champs `__BaseURL`/`__RelativePath` du catalogue signé.
Chaque téléchargement est contrôlé par la taille exacte et la mesure Apple
`_MeasurementAlgorithm=SHA-1`. Un SHA-256 supplémentaire est calculé et
revérifié pour chaque archive. Le SHA-256 local n'est pas présenté comme une
empreinte publiée par Apple. Aucun poids binaire supplémentaire n'est poussé
dans Git.

Le lot sélectionné contient : deux bases exploratoires
`10.5000.81616.13.204122,0` et `10.5000.81503.13.204122,0`, le conditionnement,
l'upscaler, les styles/LoRA (emoji, personalized_emoji, style_scribble,
messages_backgrounds, animation, illustration, sketch et personnalisés),
skintone, prompts, allow-list et safety, cinq petits manifestes UAF bornés
27.2 et un témoin 27.4. Les 27 bases matérielles du catalogue Rave ne sont pas
toutes téléchargées : ce lot ne doit pas être appelé un miroir complet du
catalogue ni un bundle appareil résolu.

| Contrôle | Résultat |
| --- | ---: |
| Archives AEA acquises, taille et mesures conformes | 24 / 2 446 657 536 octets |
| Archives AEA déchiffrées, Apple Archive extraites | 24 |
| Fichiers extraits et SHA-256 inventoriés | 217 / 3 276 258 201 octets |
| Fichiers aussi comparés au SH2 des trailers AA | 215 |
| Fichiers explicitement protégés par DSME | 169 |
| Poids de génération vérifiés en clair | 0 |
| Images calculées | 0 |

Les deux fichiers du tout premier petit témoin de métadonnées 27.4 n'ont pas
été crédités d'une vérification SH2 AA dans l'inventaire initial ; leur archive
et leurs SHA-256 locaux sont vérifiés. Les trailers YEC ne sont pas validés.
Le lecteur AA refuse les formats non pris en charge ; il couvre le sous-ensemble
réel observé (AA01, opérations M/E/O, PBZX raw/XZ), pas toute la spécification.

L'audit initial comptait quinze noms `image_diffusion_v1`. La définition UAF
contient en réalité **18 assets logiques / 17 usages**, dont dix usages de
diffusion : cinq familles avec `generic` et `generic_alternate`. L'union des
noms d'assets et des templates donne quinze noms distincts, pas quinze réseaux
indépendants. Onze des dix-huit templates figurent dans le catalogue Rave et
ont au moins un payload acquis. Les six templates `generic_alternate` et
`com.apple.gm.image_generation_services.debiasing.metadata.generic` n'y sont
pas retournés. Leur résolution reste ouverte ; ils ne sont pas déclarés
inexistants.

Preuves exhaustives du lot : [audit d'acquisition](visual-20261026/acquisition-audit.json),
[sélection](visual-20261026/selection.json) et les 24 inventaires `*-files.json`.

## Obstacle observé : AEA ouverte, contenu DSME encore protégé

La clé `ArchiveDecryptionKey` fournie par Pallas ouvre l'enveloppe AEA avec
`ipsw fw aea`. Le [code primaire ipsw](https://github.com/blacktop/ipsw/blob/master/pkg/aea/decrypt.go)
implémente cette couche en Go. Le résultat est une Apple Archive avec chemins
et contenus ; cette réussite ne lève pas le chiffrement interne DSME.

Les fichiers `ContentProtection.plist`, lisibles après extraction, donnent
des nonces de 12 octets et tags de 16 octets pour les contenus protégés. Les
JSON et MIL concernés échouent réellement à la lecture UTF-8/JSON. Exemples :

- **Conditionnement** : 11 fichiers protégés, dont `face_encoder.mlmodelc`,
  `personalized_conditioning_producer.mlmodelc`, graphes MIL et poids.
- **Emoji** : 3 fichiers protégés, dont le LoRA `emoji.bin` de 25 798 464 octets
  et son descripteur. Il ne s'agit pas du débruiteur complet.
- **Bases** : 8 fichiers protégés par variante, dont `Restore/BuildManifest.plist`
  et le cryptex DMG, avec `compressed=true` et `offset`. Aucun inventaire interne
  des débruiteurs/décodeurs/tokenizers ne peut être validé depuis ces DMG encore
  protégés. Le nom d'un ticket `mobileassetx86macosap` ne prouve pas une cible Mac.
- **Métadonnées UAF** : de petits plists lisibles avec bornes OS seulement,
  sans poids ni mapping matériel. Cinq témoins annoncent 27.2–27.2.9999 ; le
  premier témoin 4.50.1 annonce 27.4–27.4.9999.

Dans le cache firmware `.42`, les littéraux exacts vérifiés incluent
`IOService:/IOResources/AppleKeyStore`, `aks_get_dsme_key`, les messages de
récupération de clé DSME, `ContentProtection.plist` et l'échec de vérification
d'un tag GCM. Ils attestent le chemin AppleKeyStore/IOKit attendu par le code,
sans reconstituer à eux seuls tout le graphe d'appels. Aucune unicité de la clé
par appareil n'est établie. Aucun accès à cette clé n'a été obtenu sur Linux.

Les catalogues publics effectivement reçus n'offrent aucun payload Visual
de génération sans cette couche : les entrées sans `_ContentEncryption` sont
les petites métadonnées UAF. Les recherches ciblées de sources publiques sur
DSME/`aks_get_dsme_key`, les ressources déposées et le code AEA d'ipsw n'ont pas
fourni de déchiffreur DSME ni de bundle en clair supplémentaire. Cela borne les
voies examinées, sans prétendre à une impossibilité universelle.

## Ce qui manque et ce qu'un appareil doit fournir

Pour lever l'obstacle, il faut un export **après traitement DSME par le système
Apple**, avec la variante effectivement sélectionnée et les dépendances du
pipeline. Sur un appareil compatible où Apple Intelligence/Image Playground
a terminé ses téléchargements :

1. Relever la build OS, le modèle, les identités matérielles et la sélection
   UAF effective. Le rapprochement `.815xx` avec `ApChipID=0x8150` serait une
   spéculation : aucun mapping n'a été établi.
2. Exporter les dossiers `.asset` complets de FM.Visual, avec `Info.plist`,
   `AssetData`, `.AssetData` et `SecureAssetData` lorsqu'ils existent ; relever
   les symlinks et les montures cryptex et copier la vue résolue lisible si elle
   est accessible. Les emplacements exacts dépendent de l'OS ; ne pas inventer
   un chemin de montage universel.
3. Inclure le débruiteur/noise predictor, le décodeur appris, CLIP/tokenizer,
   conditionnement, modèles de sécurité, adaptateurs choisis et configurations
   de latents/scheduler. Le code VisualGeneration en atteste les noms attendus ;
   leur présence complète dans les octets en clair reste à vérifier.
4. Vérifier taille/SHA-256 et pouvoir parser les JSON, MIL et manifestes. Une
   simple copie des `.aea`, ou des mêmes fichiers encore protégés par
   `ContentProtection.plist`, reproduirait l'obstacle actuel. La copie d'un
   répertoire `.asset` seule peut aussi omettre une monture active.

Un compte Developer supplémentaire n'est pas démontré nécessaire pour les
téléchargements publics qui ont réussi. Aucun déploiement ou modification de
sécurité d'un appareil n'a été réalisé.

## Portage Linux : ce qui est établi et ce qui reste inconnu

Le transport, la vérification, AEA et AA/PBZX fonctionnent sous Debian. Le
conditionnement est livré comme Core ML compilé (`.mlmodelc` avec MIL et
`weights/weight.bin`), les styles comme `.mladapters/lora/*.bin`, et les bases
comme cryptex. C'est un inventaire des contenants et chemins, pas la lecture
des graphes chiffrés.

Après déchiffrement, il faudra inventorier opérations, quantification, formes,
normalisation et ordonnanceur avant d'évaluer les moteurs Linux existants.
Ni le support partiel MIL du dépôt, ni les modèles auxiliaires déjà exécutés,
ne démontrent la prise en charge du débruiteur. `diffusionTracker` n'est pas
utilisé comme substitut. Aucun chargement Core ML, benchmark image ou test
d'inférence n'a été annoncé. Une preuve future devra conserver prompt, seed,
poids/configs exacts, trajectoire de calcul et image finale calculée avec hash.

## Validation et reproduction

**29 tests Visual + 4 tests existants** passent : mesures, tailles, réutilisation,
publication concurrente, symlinks, traversal, troncatures, bornes de
décompression et contrôle SH2 des trailers. Le catalogue signé a également été
revérifié indépendamment. Les **4 751 anciens fichiers / 3 754 333 107 octets**
restent conformes ; aucune inférence précédente n'a été répétée comme résultat
nouveau.

[Commandes et limites de reproduction](visual-20261026/REPRODUCE.md).
