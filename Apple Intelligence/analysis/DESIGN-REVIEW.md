# Revue de conception : confidentialité, contrôle et filtrage

Onze constats de conception ancrés dans des textes du firmware. Les risques de surblocage, de minimisation ou d’opacité sont des inférences sur ces textes, sans mesure du comportement réel. Les contrepreuves protectrices sont conservées. **Aucun défaut opt-out ou consentement manquant n’est établi par ce corpus.**

Date : 26 octobre 2026. Build déclarée : iOS 27.2 / 24B115 ; comparaison 24B5089g quand indiquée.

[Méthode, portée et niveaux de certitude](README.md). Tous les comportements runtime restent non vérifiés.

## Fonctions publiques, détails de conception

Les [contrôles parentaux](https://support.apple.com/en-ie/guide/child-safety/k4n88xwnliel/27/web/1.0) et les [réglages par fonction](https://support.apple.com/en-ie/guide/iphone/iph3fed3f2c3/27/ios/27) sont publics. Apple explique aussi les [garde-fous et leurs limites](https://developer.apple.com/documentation/foundationmodels/improving-the-safety-of-generative-model-output?changes=_2), dont le [mode de transformation permissive](https://developer.apple.com/documentation/foundationmodels/systemlanguagemodel/guardrails/permissivecontenttransformations). Cette revue examine la taxonomie précise et les consignes trouvées, sans présenter l’existence du filtrage comme secrète.

| ID | Constat ou limite | Type |
| --- | --- | --- |
| D-01 | Sujets sensibles : refus global, même éducatif, et variante adolescente non modifiable | Revue de conception |
| D-02 | Bloquer les connaissances du monde conserve des sources web structurées et les données personnelles | Revue de conception |
| D-03 | Restrictions Math/Writing : absence d’indices et frontières pédagogiques difficiles à anticiper | Revue de conception |
| D-04 | Adolescents : règle de non-dissimulation vis-à-vis de nombreuses autorités | Revue de conception |
| D-05 | Style et sécurité sont fusionnés dans un template de refus | Revue de conception |
| D-06 | Restriction légale : message modèle ordonnant un refus du sujet, au-delà du résultat | Revue de conception |
| D-07 | Photos Memories : cadrage émotionnel et culturel imposé, avec contexte de vie détaillé | Revue de conception |
| D-08 | Mail/Writing Tools : composition reliée à un outil de récupération de données personnelles très large | Revue de conception |
| D-09 | Spotlight multi-agents : inférence de relations et heuristiques familiales rigides | Revue de conception |
| D-10 | Siri : contexte personnel conditionnel étendu et restitution discrète des sources | Revue de conception |
| D-11 | Siri AI : explication de l’identité centrée sur le nom marketing | Revue de conception |

## D-01 — Sujets sensibles : refus global, même éducatif, et variante adolescente non modifiable

**Observation firmware — C3.** Deux templates déclinent toute requête touchant 13 familles de sujets : violence, armes, explosifs, sexualité, abus, argot sexuel, substances, jeu, activités dangereuses, produits ménagers dangereux, biens soumis à âge, haine, et radicalisation/doxxing/stalking/hacking/harcèlement. Ils excluent explicitement les exemptions fiction, recherche et éducation ; refus préréglé sans alternative. La variante u18_model_guidelines_restricted dit que Sensitive Topics=Reduce ne peut pas être changé pour les comptes adolescents ; la variante suffixée _mdm propose Allow dans Siri Parental Controls. Les deux prévoient des exceptions de soutien pour détresse, risque imminent, abus/grooming et préjudice à autrui.

**Interprétation — C2.** La granularité « touche un sujet », sans exception de recherche/éducation, peut écarter des questions légitimes de prévention, histoire ou sécurité. C'est un risque de surblocage dans la politique rédigée ; pas une mesure de faux positifs. Le nom _mdm et le texte différent montrent des variantes ; ils ne prouvent pas à eux seuls leur sélection par MDM.

**Portée et éléments non établis.**

- Le corpus ne montre pas quel compte reçoit quelle variante, l'état effectif des réglages, ni l'impossibilité réelle de les modifier dans l'interface. Il ne démontre aucun biais envers une population déterminée. Les exceptions de crise contredisent l'idée d'un refus universel de toute aide.

**Rapport à la documentation publique.** Le réglage Sensitive Topics est public. La documentation consultée décrit une réduction des réponses ; elle n'explicite pas cette taxonomie ni la suppression des exemptions éducatives. L'existence du filtre n'est donc pas cachée. [PUB-04](https://support.apple.com/en-ie/guide/child-safety/k4n88xwnliel/27/web/1.0)

**Intérêt de revue.** Transparence sur le périmètre des contrôles parentaux et accès à une information utile.

**Amélioration proposée.** Expliciter les catégories, les exceptions de prévention/éducation et les règles selon âge ; mesurer séparément faux positifs et protection effective.

**Preuves et provenance.**

- [prompts/P-e8288f737ec7-13.txt](../prompts/P-e8288f737ec7-13.txt) — SHA-256 `e8288f737ec77bdf055df80ea6d05e08c72246e9a229282d5cb9e0bcf5292cca`. Localisation : ligne 1 ; ancre '## Decline Protocol'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/PCC/agent_instructions_metadata/agent_instructions.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json) — SHA-256 `f1e9109eb2d75e30f5512cb20916fe32ec0e393644f5ec4664709796d3b91157`. Localisation : $["templates"][7]["template"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json`.
- [prompts/P-ab2bf348a804-14.txt](../prompts/P-ab2bf348a804-14.txt) — SHA-256 `ab2bf348a804ac6f813927bf0a841ab19b650d3938c2137f2e000c87c0d6ccb9`. Localisation : ligne 1 ; ancre '## Decline Protocol'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/PCC/agent_instructions_metadata/agent_instructions.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json) — SHA-256 `f1e9109eb2d75e30f5512cb20916fe32ec0e393644f5ec4664709796d3b91157`. Localisation : $["templates"][8]["template"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json`.

## D-02 — Bloquer les connaissances du monde conserve des sources web structurées et les données personnelles

**Observation firmware — C3.** knowledge_restriction refuse aussi les réponses de connaissances intégrées au modèle (histoire, sciences, personnes, explications conceptuelles), les recommandations non nommées et les parties factuelles de questions composées. Le texte de refus mentionne l'information du web. Le même template conserve explicitement les données personnelles on-device et autorise find avec weather, sports, stocks, flights, media, maps et web_images.

**Interprétation — C2.** Le périmètre est sémantique, pas une interdiction de tout accès réseau. La formulation de refus peut faire croire qu'une question conceptuelle a besoin d'internet. Un parent peut aussi mal interpréter ce contrôle comme fermant toutes les recherches externes ; plusieurs sources structurées restent autorisées dans le template.

**Portée et éléments non établis.**

- Aucun contournement opérationnel ni appel réel n'est établi. Broad World Knowledge est le nom public, plus large que le seul web ; la restriction autorise séparément les tâches appareil. Le template ne prouve pas un accès illimité aux données personnelles.

**Rapport à la documentation publique.** Apple documente Broad World Knowledge. Le firmware détaille ses frontières avec les recherches de domaine et les données personnelles ; ce sont des précisions de mise en œuvre. [PUB-04](https://support.apple.com/en-ie/guide/child-safety/k4n88xwnliel/27/web/1.0)

**Intérêt de revue.** Compréhension des réglages et distinction réseau, connaissances du modèle et données locales.

**Amélioration proposée.** Présenter les frontières entre connaissances du modèle, web structuré et données locales, et faire correspondre le message de refus à la raison réelle.

**Preuves et provenance.**

- [prompts/P-e6c0881b76fa-9.txt](../prompts/P-e6c0881b76fa-9.txt) — SHA-256 `e6c0881b76fa2b82b0eae1fd7dc2572eef65d46bda21f1264837703d0b66010b`. Localisation : ligne 1 ; ancre '# Web Content and World Knowledge Restriction'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/PCC/agent_instructions_metadata/agent_instructions.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json) — SHA-256 `f1e9109eb2d75e30f5512cb20916fe32ec0e393644f5ec4664709796d3b91157`. Localisation : $["templates"][1]["template"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json`.

## D-03 — Restrictions Math/Writing : absence d’indices et frontières pédagogiques difficiles à anticiper

**Observation firmware — C3.** math_restriction bloque les équations algébriques, problèmes à mettre en équation, preuves et calculs d'aire/volume, calcul différentiel, statistiques/probabilités, trigonométrie et tout problème ressemblant à un devoir. Il interdit aussi indices, formules et noms de méthode. Il permet arithmétique simple, conversions et questions mathématiques factuelles. writing_restriction interdit rédaction, correction et réécriture y compris exemples/plans, mais permet résumé, réorganisation en tableaux/listes, évaluation du texte, texte dicté et explication de concepts rédactionnels.

**Interprétation — C2.** Le critère ressemblant à un devoir et l'interdiction d'indices peuvent bloquer une aide d'apprentissage minimale. Les frontières « résumé autorisé / réécriture interdite » reposent sur une classification sémantique pouvant être difficile à prédire ; aucune incohérence réelle n'a été testée.

**Portée et éléments non établis.**

- Ces restrictions sont des templates conditionnels présents dans le firmware, pas des défauts activés. Les nombreuses exceptions autorisées empêchent d'affirmer un blocage total des outils d'écriture ou des mathématiques.

**Rapport à la documentation publique.** Math Assistance et Writing Assistance sont documentés, avec un motif lié aux devoirs. Les catégories et interdictions d'indices examinées ici sont plus précises que cette présentation publique. [PUB-04](https://support.apple.com/en-ie/guide/child-safety/k4n88xwnliel/27/web/1.0)

**Intérêt de revue.** Lisibilité des contrôles scolaires et autonomie d'apprentissage.

**Amélioration proposée.** Expliquer les limites avec exemples ; proposer des contrôles plus fins pour indices pédagogiques, réécriture et résumés.

**Preuves et provenance.**

- [prompts/P-fd5e34c27c6d-10.txt](../prompts/P-fd5e34c27c6d-10.txt) — SHA-256 `fd5e34c27c6dbd94914087f97b4651973b4870f79483bf94ba6f2c86d9395b45`. Localisation : ligne 1 ; ancre '# Math-Help Restriction'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/PCC/agent_instructions_metadata/agent_instructions.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json) — SHA-256 `f1e9109eb2d75e30f5512cb20916fe32ec0e393644f5ec4664709796d3b91157`. Localisation : $["templates"][2]["template"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json`.
- [prompts/P-db0ad3ad1195-15.txt](../prompts/P-db0ad3ad1195-15.txt) — SHA-256 `db0ad3ad1195d04aeec569131d7a30af185d3609f5ed42513cad9d9358626cbe`. Localisation : ligne 1 ; ancre '# Writing-Help Restriction'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/PCC/agent_instructions_metadata/agent_instructions.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json) — SHA-256 `f1e9109eb2d75e30f5512cb20916fe32ec0e393644f5ec4664709796d3b91157`. Localisation : $["templates"][10]["template"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json`.

## D-04 — Adolescents : règle de non-dissimulation vis-à-vis de nombreuses autorités

**Observation firmware — C3.** u18_model_guidelines_base vise explicitement 13–17 ans. Sa rubrique Privacy, Authority, and Concealment permet les bases de sécurité (mots de passe, 2FA, déconnexion) et encourage un adulte sur appareil partagé ; elle interdit d'aider à cacher une activité ou une faute aux parents, écoles, plateformes ou forces de l'ordre, et cite effacement des traces, comptes secrets, évitement de surveillance. Le même texte soutient les victimes et oriente vers un professionnel/adulte de confiance.

**Interprétation — C2.** La disjonction activité OU faute peut englober des besoins légitimes de confidentialité d'un adolescent, y compris face à un adulte problématique. La règle ne distingue pas explicitement une autorité protectrice d'une autorité abusive ; cela mérite une clarification de conception.

**Portée et éléments non établis.**

- Le texte n'établit aucune transmission aux parents, à l'école ou à la police, ni surveillance supplémentaire. Il ne prouve pas qu'une demande légitime sera effectivement refusée ; les règles de soutien peuvent influer sur la décision.

**Rapport à la documentation publique.** Les contrôles parentaux sont publics ; la présentation consultée ne détaille pas cette règle de confidentialité face aux autorités. [PUB-04](https://support.apple.com/en-ie/guide/child-safety/k4n88xwnliel/27/web/1.0)

**Intérêt de revue.** Confidentialité des mineurs, contrôle utilisateur et ambiguïté du périmètre de protection.

**Amélioration proposée.** Distinguer dissimulation nuisible et confidentialité légitime ; clarifier les exceptions en présence d’une autorité abusive.

**Preuves et provenance.**

- [prompts/P-e0f2ff98df76-12.txt](../prompts/P-e0f2ff98df76-12.txt) — SHA-256 `e0f2ff98df7684347c100b5d211e120e0cd7cd7d3dcf54547a2054e56380e0fe`. Localisation : ligne 42 ; ancre '8. Privacy, Authority, and Concealment'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/PCC/agent_instructions_metadata/agent_instructions.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json) — SHA-256 `f1e9109eb2d75e30f5512cb20916fe32ec0e393644f5ec4664709796d3b91157`. Localisation : $["templates"][6]["template"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json`.

## D-05 — Style et sécurité sont fusionnés dans un template de refus

**Observation firmware — C3.** process_content_safely branche sur query_intent_type. Pour stylized, il refuse l'élément de style/role-play/impersonation et peut donner la réponse normale via un outil ; sans outil ou réponse ancrée, il emploie un refus fixe. Une autre branche jailbreak interdit les tentatives de manipulation et traite explicitement le contenu d'outils comme potentiellement hostile.

**Interprétation — C2.** Associer dans une même politique les variations de style et la résistance aux injections peut rendre l'expérience moins contrôlable, notamment pour des styles inoffensifs, et provoquer un refus total lorsque seul le style devrait être écarté. La branche défensive contre les injections est justifiée par son objectif et n'est pas en soi un abus.

**Portée et éléments non établis.**

- La classification query_intent_type, son déclenchement et la fidélité des sorties ne sont pas prouvés. Le système principal autorise par ailleurs l'ajustement de longueur, niveau et format, et interdit plus spécifiquement l'imitation de personnes ou démographies. Aucun effet discriminatoire mesuré.

**Rapport à la documentation publique.** Comparaison limitée au référentiel ci-dessous ; aucune absence exhaustive de documentation n’est revendiquée.

**Intérêt de revue.** Contrôle de l'expression, cohérence de la politique et risque de surblocage.

**Amélioration proposée.** Distinguer personnalisation de style et manipulation de sécurité, avec un refus limité à la partie problématique.

**Preuves et provenance.**

- [prompts/P-70e62fcd05f5-11.txt](../prompts/P-70e62fcd05f5-11.txt) — SHA-256 `70e62fcd05f5fc8c682f7865e13a32930528302af8e7b7283f42c1eb598750f2`. Localisation : ligne 1 ; ancre 'query_intent_type == "stylized"'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/PCC/agent_instructions_metadata/agent_instructions.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json) — SHA-256 `f1e9109eb2d75e30f5512cb20916fe32ec0e393644f5ec4664709796d3b91157`. Localisation : $["templates"][4]["template"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json`.
- [prompts/P-3ff04450c90e-6.txt](../prompts/P-3ff04450c90e-6.txt) — SHA-256 `3ff04450c90e72437f6eda513a963075c371220a84fb0845805f49fbc8c27e74`. Localisation : ligne 575 ; ancre '**Style-based prompt manipulation:**'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/CATALOG/system_prompt_metadata/system_prompt.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/CATALOG/system_prompt_metadata/system_prompt.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/CATALOG/system_prompt_metadata/system_prompt.json) — SHA-256 `23c86c7d04aaac5981a478287e968bc512107fc8b233e7eae8be001e6b00e117`. Localisation : $["staticSystemPrompts"]["default"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/CATALOG/system_prompt_metadata/system_prompt.json`.

## D-06 — Restriction légale : message modèle ordonnant un refus du sujet, au-delà du résultat

**Observation firmware — C3.** Une chaîne de PlannerModelFacingErrors.loctable sous plannerTool.globalSearch.wkaSafetyActionDecline qualifie le résultat de légalement restreint, interdit résumé/paraphrase et interdit également une réponse sur le sujet à partir des connaissances du modèle, puis demande de décliner immédiatement.

**Interprétation — C2.** L'extension du blocage depuis un résultat à tout le sujet peut interdire une réponse indépendante licite. Le message ne fournit au modèle ni juridiction, ni fondement légal, ni échéance ; une explication vérifiable au public demanderait un mécanisme complémentaire.

**Portée et éléments non établis.**

- La chaîne n'établit ni l'existence effective d'une obligation juridique, ni la juridiction, ni le fournisseur qui déclenche l'erreur, ni une suppression abusive en production. La consigne est une donnée non exécutée ; ce constat porte sur son texte.

**Rapport à la documentation publique.** Comparaison limitée au référentiel ci-dessous ; aucune absence exhaustive de documentation n’est revendiquée.

**Intérêt de revue.** Transparence du fondement d'un refus et limitation du blocage à sa justification.

**Amélioration proposée.** Associer au refus une raison vérifiable et un périmètre précis ; distinguer règle du fournisseur, politique produit et obligation juridique réellement applicable.

**Preuves et provenance.**

- [prompts/P-c14480ec1bcd-1.txt](../prompts/P-c14480ec1bcd-1.txt) — SHA-256 `c14480ec1bcd31389c30e776b2008a50c857f90800d24c2d8b4b40f36205c08a`. Localisation : ligne 1 ; ancre 'CONTENT RESTRICTION:'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlow.framework/PlannerModelFacingErrors.loctable`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlow.framework/PlannerModelFacingErrors.loctable](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlow.framework/PlannerModelFacingErrors.loctable) — SHA-256 `55706ab96c230f90740b31c5738b4b9fb2b3b8e110c9e492d9066570616c34af`. Localisation : $["en"]["plannerTool.globalSearch.wkaSafetyActionDecline"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlow.framework/PlannerModelFacingErrors.loctable`.

## D-07 — Photos Memories : cadrage émotionnel et culturel imposé, avec contexte de vie détaillé

**Observation firmware — C3.** Le template de scénario demande des récits sans religion, politique, négativité, tristesse ou provocation ; il exclut musique, artistes et titres des plans/chapitres, les périodes/heures des chapitres/légendes, et les références culturelles spécifiques des titres. Son entrée prévoit présence d'enfants/animaux, relations avec l'utilisateur, domicile et lieux principaux des photos. Un autre template dédié aux titres accepte des lieux/dates demandés et des jeux de mots mesurés : il existe donc plusieurs politiques de génération.

**Interprétation — C2.** Le filtrage éditorial peut empêcher de représenter fidèlement deuil, commémorations, cérémonies religieuses ou événements politiques présents dans une photothèque personnelle. Le contexte domicile/relations accroît la sensibilité de l'entrée du modèle et mérite une minimisation par tâche. Ces templates correspondent à des tâches distinctes (scénario et titre) ; leurs différences ne sont pas une contradiction établie et ne permettent pas de généraliser une règle à toute l’interface Photos.

**Portée et éléments non établis.**

- Le texte ne prouve ni analyse de toutes les photos, ni inclusion systématique de ces champs, ni transmission cloud, ni conservation, ni comportement observé. Une préférence pour un récit positif ne prouve pas une volonté de manipulation politique.

**Rapport à la documentation publique.** Apple annonce un usage du contexte personnel avec sélection des données nécessaires ; les champs et exclusions détaillés de ce scénario sont une surface supplémentaire d'audit de cette promesse. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Fidélité aux souvenirs de l'utilisateur, contrôle créatif et minimisation des données personnelles.

**Amélioration proposée.** Permettre un choix éditorial explicite, dont un récit fidèle aux événements difficiles ; limiter le contexte personnel aux besoins du scénario.

**Preuves et provenance.**

- [prompts/P-07379219e29e-89.txt](../prompts/P-07379219e29e-89.txt) — SHA-256 `07379219e29e4391c9653544d94a24611952b7d79f28236a4389f8fb49019dec`. Localisation : ligne 1 ; ancre 'Here are the story guidelines'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/PhotosIntelligence.framework/PhotosIntelligence`.
  Cache physique : `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.28` ; SHA-256 complet `c8b612e814a4c26ede6b3edf16a337191c94dff64b0a342332f667b815c09a3b` ; offset `0x2b14570` ; longueur 3202 octets.
- [prompts/P-f100c1d99f7f-88.txt](../prompts/P-f100c1d99f7f-88.txt) — SHA-256 `f100c1d99f7fd57c3ccf88077bf084e2bac847f95c69508a131f4741f53557ec`. Localisation : ligne 1 ; ancre 'The title should be:'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/PhotosIntelligence.framework/PhotosIntelligence`.
  Cache physique : `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.28` ; SHA-256 complet `c8b612e814a4c26ede6b3edf16a337191c94dff64b0a342332f667b815c09a3b` ; offset `0x2b13fc0` ; longueur 1448 octets.

## D-08 — Mail/Writing Tools : composition reliée à un outil de récupération de données personnelles très large

**Observation firmware — C3.** Le template TextComposerRuntime attend texte sélectionné, contexte du brouillon incluant en-têtes, historique mail et métadonnées optionnelles de style/préférences/informations personnelles. ask_pqa est décrit pour événements, pièces d'identité (permis/passeport), contacts, liens, textes, transactions et réservations ; des exemples demandent numéros de passeport et permis. La logique ordonne récupération si un fait essentiel manque et réemploi de l'historique. Elle interdit toutefois ask_pqa pour noms/adresses destinataires et signature de base, et autorise des valeurs génériques si le fait n'est pas essentiel. Un template writing_tools de Siri privilégie revue UI pour contenu composé, insertion immédiate pour données récupérées. Les deux templates proviennent de composants distincts ; aucun enchaînement d’exécution entre TextComposerRuntime et le template Siri n’est démontré.

**Interprétation — C2.** La surface documentaire dépasse la simple transformation du texte sélectionné : une fonctionnalité de composition peut demander des identifiants administratifs ou informations financières au contexte personnel lorsque le besoin le justifie. Les frontières d'essentialité, la revue des insertions factuelles sensibles et le contrôle par l'utilisateur méritent vérification ; la portée déclarée de l'outil ne prouve pas qu'il obtient ces données sans contrôle.

**Portée et éléments non établis.**

- Aucun consentement manquant, défaut opt-out, permission effectivement contournée, résultat d'outil, accès réel à des documents, stockage ou envoi PCC n'est établi. Les consignes de minimisation ci-dessus sont des contrepreuves d'un accès indiscriminé. show_review_ui=false exprime une préférence de présentation ; le runtime peut imposer d'autres contrôles.

**Rapport à la documentation publique.** L'usage de données inter-apps est public. Ce constat précise la portée d'un template et ne démontre pas que des données non nécessaires quittent l'appareil. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Minimisation en composition, champs sensibles et intervention utilisateur.

**Amélioration proposée.** Rendre visibles les sources et champs sensibles utilisés, contrôler les insertions et documenter les autorisations de récupération personnelle.

**Preuves et provenance.**

- [prompts/P-26bd49486b71-222.txt](../prompts/P-26bd49486b71-222.txt) — SHA-256 `26bd49486b71c83e17608b521cc35e91d4bca4f23e5a3444be5b8e0fe6e5ed6f`. Localisation : ligne 237 ; ancre '### ask_pqa'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/TextComposerRuntime.framework/TextComposerRuntime`.
  Cache physique : `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.69` ; SHA-256 complet `bb6028880684ec5952353b4f4f9988fb5a80f3c74959c7235b33bde08345e142` ; offset `0x6c054a0` ; longueur 56026 octets.
- [prompts/P-32dbf92b4981-16.txt](../prompts/P-32dbf92b4981-16.txt) — SHA-256 `32dbf92b49816aa970b7c900856b672455d50a90463c00dcf6a1ae26c551382e`. Localisation : ligne 92 ; ancre '## Review UI'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/PCC/agent_instructions_metadata/agent_instructions.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json) — SHA-256 `f1e9109eb2d75e30f5512cb20916fe32ec0e393644f5ec4664709796d3b91157`. Localisation : $["templates"][11]["template"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/agent_instructions_metadata/agent_instructions.json`.

## D-09 — Spotlight multi-agents : inférence de relations et heuristiques familiales rigides

**Observation firmware — C3.** Des littéraux _CoreSpotlight_FoundationModels décrivent un spécialiste analysant communications, calendrier et signaux organisationnels pour identifier des relations. Les fragments famille imposent ton informel, moments personnels (soir/week-end) et titres informels ; plafonnent la confiance sous 0,3 pour adresses pro ; attribuent 0,0 aux signaux organisationnels pour les relations familiales. Ils produisent identifiant e-mail, fréquence, ton, motifs de sujets/titres, score et raisonnement. Un template d'hydration exige une étape explicite pour lire corps de mails/documents, à réserver aux requêtes de contenu ; les métadonnées seules suffisent pour auteur/date/comptage.

**Interprétation — C2.** Il s'agit d'un mécanisme potentiel de profilage relationnel au service de la recherche personnelle. Les règles famille peuvent défavoriser familles travaillant ensemble, emplois atypiques ou usages formels de la messagerie. L'hydration explicite fournit une séparation utile entre métadonnées et contenu, mais ne garantit pas la nécessité de chaque requête.

**Portée et éléments non établis.**

- La présence de littéraux ne prouve ni exécution ni persistance de profils, ni envoi à Apple, ni activation pour chaque recherche. Les scores ne sont pas des taux d'erreur mesurés. Les instructions exigent des motifs vérifiables et déconseillent la lecture du corps lorsque les métadonnées suffisent.

**Rapport à la documentation publique.** Le contexte inter-apps est annoncé publiquement. La documentation générale ne décrit pas ces heuristiques de relations familiales ; il s'agit de détails d'implémentation observés, pas d'un profilage commercial établi. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Profilage relationnel, équité des heuristiques et séparation métadonnées/contenu.

**Amélioration proposée.** Rendre une relation inférée corrigeable ; vérifier les heuristiques sur des situations familiales et professionnelles variées.

**Preuves et provenance.**

- [prompts/P-5878f554bae3-120.txt](../prompts/P-5878f554bae3-120.txt) — SHA-256 `5878f554bae31fcb9429a51038f81ba0d34e4c35e1c8a7ef7f881fead3386373`. Localisation : ligne 1 ; ancre 'You are a relationship analysis specialist.'.
  Chemin source firmware : `/System/Library/Frameworks/_CoreSpotlight_FoundationModels.framework/_CoreSpotlight_FoundationModels`.
  Cache physique : `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.48` ; SHA-256 complet `d48cd7db2f123e6010c50f98d1479fdd54b50118a7b997b3bf99abd84081426f` ; offset `0x1d85aa0` ; longueur 318 octets.
- [prompts/P-03f7f9419323-119.txt](../prompts/P-03f7f9419323-119.txt) — SHA-256 `03f7f941932363cdc3a353a1c3778c521cdf2a5f253744dc5b0efb3367c07a0e`. Localisation : ligne 3 ; ancre 'FAMILY MUST BE INFORMAL'.
  Chemin source firmware : `/System/Library/Frameworks/_CoreSpotlight_FoundationModels.framework/_CoreSpotlight_FoundationModels`.
  Cache physique : `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.48` ; SHA-256 complet `d48cd7db2f123e6010c50f98d1479fdd54b50118a7b997b3bf99abd84081426f` ; offset `0x1d85760` ; longueur 784 octets.
- [prompts/P-2b6b5a9ed6be-118.txt](../prompts/P-2b6b5a9ed6be-118.txt) — SHA-256 `2b6b5a9ed6be1f217b9a8fde4f40ba8dc89f1859693aede32b2ada5acc345c3b`. Localisation : ligne 5 ; ancre 'FAMILY MUST BE PERSONAL TIME'.
  Chemin source firmware : `/System/Library/Frameworks/_CoreSpotlight_FoundationModels.framework/_CoreSpotlight_FoundationModels`.
  Cache physique : `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.48` ; SHA-256 complet `d48cd7db2f123e6010c50f98d1479fdd54b50118a7b997b3bf99abd84081426f` ; offset `0x1d85020` ; longueur 994 octets.
- [prompts/P-68b67f53f0b0-117.txt](../prompts/P-68b67f53f0b0-117.txt) — SHA-256 `68b67f53f0b0b505cd39f583d17ceffcd0847735c40eb859a1442170088df518`. Localisation : ligne 10 ; ancre 'Family members'.
  Chemin source firmware : `/System/Library/Frameworks/_CoreSpotlight_FoundationModels.framework/_CoreSpotlight_FoundationModels`.
  Cache physique : `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.48` ; SHA-256 complet `d48cd7db2f123e6010c50f98d1479fdd54b50118a7b997b3bf99abd84081426f` ; offset `0x1d849f0` ; longueur 702 octets.
- [prompts/P-be9c3746e1da-188.txt](../prompts/P-be9c3746e1da-188.txt) — SHA-256 `be9c3746e1daba1754369bfcbdd984013839c84f1834dcefa58ddccc12354792`. Localisation : ligne 3 ; ancre '**HYDRATION STAGE**'.
  Chemin source firmware : `/System/Library/Frameworks/_CoreSpotlight_FoundationModels.framework/_CoreSpotlight_FoundationModels`.
  Cache physique : `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.48` ; SHA-256 complet `d48cd7db2f123e6010c50f98d1479fdd54b50118a7b997b3bf99abd84081426f` ; offset `0x1da25f0` ; longueur 1077 octets.

## D-10 — Siri : contexte personnel conditionnel étendu et restitution discrète des sources

**Observation firmware — C3.** Le pré-message système peut inclure nom/genre utilisateur, genre de voix, extraits de conversations, conversations passées, instructions/description de skills et contexte écran, chacun derrière une condition. Le prompt système interdit de narrer les sources personnelles avec des formules du type « d'après vos messages » et demande une impression de compréhension partagée. Il exige par ailleurs citations/entités d'origine pour les réponses sur données personnelles, protection des informations sensibles, absence de connexions personnelles non demandées et confirmation automatique par les outils soumis à sécurité.

**Interprétation — C2.** Des historiques et éléments d'écran peuvent élargir le contexte au-delà de la requête courante lorsque le runtime les fournit. La discrétion narrative peut rendre moins saillante l'origine d'une information, tout en laissant des citations visuelles ; le risque porte sur la lisibilité, pas sur une suppression prouvée de toute attribution.

**Portée et éléments non établis.**

- Les conditions démontrent une capacité d'inclusion, pas un enregistrement permanent, une consultation de toutes les conversations, une transmission PCC ou un consentement absent. Le corpus ne montre pas qui remplit ces champs, leurs durées de rétention ni les réglages effectifs.

**Rapport à la documentation publique.** Apple documente le contexte personnel et la sélection de données nécessaires. Ce constat précise les champs et les consignes d'affichage, sans démontrer une contradiction factuelle avec cette promesse. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Périmètre du contexte, provenance intelligible et contrôle des données visibles par l'assistant.

**Amélioration proposée.** Conserver une provenance lisible, y compris lorsque la narration reste naturelle, et exposer les catégories de contexte incluses.

**Preuves et provenance.**

- [prompts/P-0d4fd7936173-4.txt](../prompts/P-0d4fd7936173-4.txt) — SHA-256 `0d4fd793617352548f59e8964f4967138b8a117045691ccb1b1aa8e48c7fbfbd`. Localisation : ligne 26 ; ancre '{%- if chunks_retrieved %}'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/CATALOG/system_prompt_metadata/system_prompt.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/system_prompt_metadata/system_prompt.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/system_prompt_metadata/system_prompt.json) — SHA-256 `5ce0bf8f35fd347276fb183f2fad59926b6c5a5309ce42b99d5042bc124ed95a`. Localisation : $["prerequestMessageTemplates"][0]["responseTemplate"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/PCC/system_prompt_metadata/system_prompt.json`.
- [prompts/P-3ff04450c90e-6.txt](../prompts/P-3ff04450c90e-6.txt) — SHA-256 `3ff04450c90e72437f6eda513a963075c371220a84fb0845805f49fbc8c27e74`. Localisation : ligne 526 ; ancre '**Never narrate your sources:**'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/CATALOG/system_prompt_metadata/system_prompt.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/CATALOG/system_prompt_metadata/system_prompt.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/CATALOG/system_prompt_metadata/system_prompt.json) — SHA-256 `23c86c7d04aaac5981a478287e968bc512107fc8b233e7eae8be001e6b00e117`. Localisation : $["staticSystemPrompts"]["default"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/CATALOG/system_prompt_metadata/system_prompt.json`.

## D-11 — Siri AI : explication de l’identité centrée sur le nom marketing

**Observation firmware — C3.** La rubrique sur les questions d’identité demande de présenter le rôle de Siri plutôt que son architecture et de ne pas aborder techniquement l’AI spontanément. Pour le nom marketing « Siri AI » et son suffixe « AI », elle impose l’expansion Apple Intelligence et exclut artificial intelligence. Cette règle vise l’explication de l’identité Siri AI, pas toute question générique sur l’intelligence artificielle. Le même prompt se décrit comme logiciel sans sentiments et prévoit un tag baseline_ai_disclaimer à la première réponse informationnelle selon exceptions.

**Interprétation — C2.** La réponse sur l’identité met l’accent sur la marque et ses fonctions, ce qui peut donner une explication moins technique à l’utilisateur. L’expansion prescrite du nom commercial n’est pas en elle-même une définition fausse de ce nom ; le point discutable est la limitation de l’explication architecturale. Les mentions logicielles et l’avertissement sont des contrepoids.

**Portée et éléments non établis.**

- Cette rédaction ne prouve ni absence d'avertissement à l'écran, ni négation explicite du caractère génératif, ni sortie trompeuse en production. L'interface peut donner des explications indépendantes du prompt.

**Rapport à la documentation publique.** Comparaison limitée au référentiel ci-dessous ; aucune absence exhaustive de documentation n’est revendiquée.

**Intérêt de revue.** Explicabilité de l'identité, distinction marque/nature technique et transparence de l'interface.

**Amélioration proposée.** Permettre une explication technique claire de la nature générative de Siri AI quand elle est demandée.

**Preuves et provenance.**

- [prompts/P-3ff04450c90e-6.txt](../prompts/P-3ff04450c90e-6.txt) — SHA-256 `3ff04450c90e72437f6eda513a963075c371220a84fb0845805f49fbc8c27e74`. Localisation : ligne 578 ; ancre '**Questions about AI in relation to your identity:**'.
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/da_DK/CATALOG/system_prompt_metadata/system_prompt.json`.
- [extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/CATALOG/system_prompt_metadata/system_prompt.json](../extracted/rootfs/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/CATALOG/system_prompt_metadata/system_prompt.json) — SHA-256 `23c86c7d04aaac5981a478287e968bc512107fc8b233e7eae8be001e6b00e117`. Localisation : $["staticSystemPrompts"]["default"].
  Chemin source firmware : `/System/Library/PrivateFrameworks/IntelligenceFlowPlannerSupport.framework/asset_root/en_US/CATALOG/system_prompt_metadata/system_prompt.json`.

## Références publiques Apple consultées

- [PUB-01 — Apple Intelligence & Privacy](https://www.apple.com/legal/privacy/data/en/intelligence-engine/). Consultation : 2026-10-26.
- [PUB-02 — Private Cloud Compute: A new frontier for AI privacy in the cloud](https://security.apple.com/blog/private-cloud-compute/). Consultation : 2026-10-26.
- [PUB-03 — Improving the safety of generative model output](https://developer.apple.com/documentation/foundationmodels/improving-the-safety-of-generative-model-output?changes=_2). Consultation : 2026-10-26.
- [PUB-04 — Block or allow access to Siri and Apple Intelligence features](https://support.apple.com/en-ie/guide/child-safety/k4n88xwnliel/27/web/1.0). Consultation : 2026-10-26.
- [PUB-05 — Turn off and restrict access to Apple Intelligence features on iPhone](https://support.apple.com/en-ie/guide/iphone/iph3fed3f2c3/27/ios/27). Consultation : 2026-10-26.
- [PUB-06 — Improve Siri & Apple Intelligence & Privacy](https://www.apple.com/legal/privacy/data/en/improve-intelligence/). Consultation : 2026-10-26.
- [PUB-07 — Adding server-side intelligence with Private Cloud Compute](https://developer.apple.com/documentation/FoundationModels/adding-server-side-intelligence-with-private-cloud-compute/). Consultation : 2026-10-26.
- [PUB-08 — permissiveContentTransformations](https://developer.apple.com/documentation/foundationmodels/systemlanguagemodel/guardrails/permissivecontenttransformations). Consultation : 2026-10-26.
