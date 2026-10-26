# Client public du modèle système (macOS)

Ce programme utilise **le modèle Apple installé et chargé par le système** via
`SystemLanguageModel.default`. Il ne charge pas les poids extraits de l'IPSW,
ne choisit pas de référence interne ModelCatalog et n'est pas une preuve
d'exécution d'un modèle précis de la build iOS 24B115.

## Installation et exécution

Sur un Mac compatible Apple Intelligence, macOS 26 ou ultérieur, avec Xcode 26 /
Swift 6.2 ou ultérieur et le SDK macOS correspondant : activer Apple Intelligence,
attendre la fin du téléchargement des modèles, puis :

```sh
cd 'Apple Intelligence/runtime/foundationmodels'
swift build -c release
.build/release/apple-system-model --availability
printf '%s\n' '{"prompt":"Résume en une phrase : Le train part à 18 h. Arriver dix minutes avant.","instructions":"Réponds en français."}' | .build/release/apple-system-model
```

Entrée : objet JSON UTF-8 sur stdin, `prompt: string` non vide,
`instructions?: string`. Ces deux champs sont les seuls permis. Texte seulement ;
pas de tenseur, image, audio, outil ou accès PCC dans ce client. Le budget de
contexte est celui de l'OS ; les dépassements/refus deviennent des erreurs JSON
avec code de sortie 2. La limite de requête de 1 MiB n'est pas une estimation du
budget de tokens. Tokenisation, normalisation, prétraitement et décodage sont
effectués par Foundation Models, sans supposer que le SentencePiece présent
dans un autre framework soit le tokenizer de ce modèle.

Sortie : JSON avec `backend`, `weight_identity`, `os`, `availability`, `status`,
`inference_performed` et, seulement après succès réel, `output.text: string`.
Le texte généré varie ; aucun exemple fabriqué de réponse Apple n'est livré.
`--availability` ne réalise pas d'inférence. Garder la sortie complète et
`sw_vers` comme preuve sur le Mac. L'API ne révèle pas les hashes des poids :
la preuve indique explicitement cette limite d'identité.

**Validation de livraison : code fourni, compilation et inférence macOS non
vérifiées sur le VPS Linux, qui ne possède ni SDK ni runtime Apple.** Ne pas
traiter cette procédure comme une preuve d'exécution réussie. Le lanceur de
bundles Core ML extraits est documenté séparément dans `../README.md`.

Sources Apple : [génération et disponibilité](https://developer.apple.com/documentation/foundationmodels/generating-content-and-performing-tasks-with-foundation-models),
[framework](https://developer.apple.com/foundation-models-framework/).
