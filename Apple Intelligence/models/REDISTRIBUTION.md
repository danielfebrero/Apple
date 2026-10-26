# Stockage et redistribution des poids

Vérification effectuée le 26 octobre 2026. **Aucun nouveau binaire de modèle,
tokenizer ou bundle de firmware n'est autorisé à la publication par ce travail.**
Le dépôt publie des manifestes, des descriptions d'interface et du code ; les
octets extraits sont conservés dans le cache local exclu de Git.

## Sources vérifiées

- [Licence iOS/iPadOS 27](https://www.apple.com/legal/sla/docs/iOS27_iPadOS27.pdf),
  §§1(a), 2(a)-(d), 3 : logiciel et données concédés sous licence, restrictions
  de copie/distribution et transfert sous conditions. Aucune permission générale
  de republier les poids extraits sur un dépôt public n'y a été trouvée.
- [Index Apple des licences](https://www.apple.com/legal/sla/) : l'accord qui
  accompagne le produit peut différer de la version publique consultée.
- Les métadonnées et catalogues locaux ne constituent pas une licence de
  redistribution. Une URL de téléchargement publique, un hash ou un modèle
  non chiffré ne constituent pas une telle permission.

Les dates, URL et empreintes des réponses HTTP indépendantes sont dans
[`public-sources.json`](public-sources.json). Une page DocC HTML peut être une
enveloppe JavaScript : son hash identifie la réponse HTTP, pas une capture de
la documentation rendue. Le PDF complet n'est pas ajouté au dépôt.

**Conclusion de publication : droits de redistribution des poids non établis.**
Ce constat borné n'est pas une détermination juridique de tous les usages de
recherche possibles. Une licence distincte applicable à un composant doit être
examinée avant de modifier cette décision pour ce composant.

## Mécanisme de stockage

Les manifestes publics identifient les fichiers avec leur provenance, leur taille
et SHA-256. Le cache local est adressé par contenu ; les bundles d'exécution
sont reconstruits avec leurs chemins relatifs d'origine. Les octets identiques
peuvent ainsi être partagés entre plusieurs modèles sans gonfler l'historique Git.
Ce cache est régénérable par extraction depuis une copie locale autorisée du
firmware ; aucune IPSW ni image DMG n'est commitée. Voir
[`inventory.md`](inventory.md) et [`../runtime/README.md`](../runtime/README.md)
pour les commandes réellement livrées.

Git LFS ou une release GitHub ne résoudraient que le volume ; ils ne donneraient
pas de droit de redistribution. Ils ne sont donc pas utilisés pour ces poids.
Ne pas ajouter le cache avec `git add -f`. Les nouveaux fichiers publiés doivent
être du code, de la documentation, des manifestes ou des preuves sans binaires.

## Modèles téléchargés par le système

Les références UAF/ModelCatalog de la partition système ne contiennent pas les
assets de la partition de données. Aucun jeton d'authentification, compte Apple,
clé de déchiffrement ou URL signée n'est collecté ou publié ici. Pour le modèle
public Foundation Models, utiliser le téléchargement géré par Apple Intelligence
sur une plateforme éligible, puis contrôler `SystemLanguageModel.availability`.
Cette API ne permet pas de sélectionner par SHA-256 un poids extrait de 24B115 ;
une exécution de cette API doit être attribuée au modèle installé par l'OS.

## Existant préservé

Le corpus déjà publié avant cette mission est conservé. La présente vérification
porte sur l'ajout des poids et ressources de modèles de cette mission ; elle
ne constitue pas une nouvelle analyse des droits de tout l'historique du dépôt.
