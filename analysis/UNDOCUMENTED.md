# Détails internes et comportements non établis

Treize entrées : neuf détails internes, une piste non rattachée à Apple Intelligence, une limite de corpus et deux observations comparatives. **Aucune exfiltration de prompts, aucun opt-out ignoré, aucun chargement non signé et aucune violation des garanties PCC ne sont démontrés.** La présence de mécanismes internes mérite documentation, sans être une preuve d’abus.

Date : 26 octobre 2026. Build déclarée : iOS 27.2 / 24B115 ; comparaison 24B5089g quand indiquée.

[Méthode, portée et niveaux de certitude](README.md). Tous les comportements runtime restent non vérifiés.

## Ce qui est déjà public — et doit rester distinct

- Apple décrit le traitement local et PCC, certaines métriques techniques et un rapport local activable : [notice de confidentialité](https://www.apple.com/legal/privacy/data/en/intelligence-engine/). L’[architecture PCC publiée](https://security.apple.com/blog/private-cloud-compute/) annonce un traitement éphémère ; les journaux locaux iOS ne suffisent pas à la réfuter.
- Le [programme volontaire d’amélioration Siri](https://www.apple.com/legal/privacy/data/en/improve-intelligence/) peut, selon consentement et fonction, conserver des interactions pour entraînement et revue, jusqu’à deux ans ou davantage pour un sous-ensemble revu. Ce canal n’est pas la conservation des requêtes par les nœuds PCC.
- [Foundation Models documente des API locales et PCC distinctes](https://developer.apple.com/documentation/FoundationModels/adding-server-side-intelligence-with-private-cloud-compute/). Découvrir un identifiant serveur n’établit donc pas un transfert « caché ».

| ID | Constat ou limite | Type |
| --- | --- | --- |
| U-01 | Canal UAF distinct pour configurations, filtres et désactivation de cas d’usage | Détail interne |
| U-02 | Alias d’usage mêlant adaptateurs locaux et identifiants serveur, avec variantes IFP et langue | Détail interne |
| U-03 | Fournisseur de sécurité : entitlements déclarés pour assets, sideload en lecture seule et reporting Biome | Détail interne |
| U-04 | Configurations de métriques de sécurité PCC/Siri : télémétrie autorisée et upload direct déclarés | Détail interne |
| U-05 | Journaux locaux et diagnostic sensible prévus ; collecte de prompts active non démontrée | Détail interne |
| U-06 | Rapport de transparence et métriques de sécurité sont des chemins distincts, avec exclusions et désactivation prévues | Détail interne |
| U-07 | PCCAsDefault et persistance : métadonnées de feature flags, sans valeur d’activation | Détail interne |
| U-08 | ModelManager/Policy.plist arbitre les ressources et priorités, sans politique d’export visible | Détail interne |
| U-09 | État opt-in indexé par primary DSID : lien de compte local suggéré, transmission non établie | Détail interne |
| U-10 | Piste OSM dans AssistantServices : endpoint d’upload, rattachement à Apple Intelligence non établi | Piste non confirmée |
| U-20 | Limite de comparaison bêta 2 / RC : les ressources rootfs bêta sont des stubs, pas des contenus comparables | Limite du corpus |
| U-21 | Delta statique attesté de ModelCatalog : noms HomeKit, planner serveur Axon et variantes de modèles | Delta statique |
| U-22 | Contrôle négatif ciblé : mêmes octets de chaînes pour UAF, ModelCatalogRuntime et ModelManagerServices | Contrôle négatif |

## U-01 — Canal UAF distinct pour configurations, filtres et désactivation de cas d’usage

**Observation firmware — C3.** Le fichier AssetSets/com.apple.MobileAsset.UAF.FM.Overrides.plist décrit 167 assets / 166 UsageTypes : model_config.all, safety.disabledusecases, filtres input/output par usage, listes retain et vip_and_blocked_provider. EnableCellular=true. La seule entrée metadata com.apple.fm.overrides.uaf.metadata porte IgnoreOSCompatibility=true. com.apple.modelcatalog compte 366 assets / 365 UsageTypes et déclare ExperimentalAssets={TrialFactor:ExperimentAssetsDirectory,TrialNamespace:UAF_AB_MODELCATALOG,TrialProject:UAF_AB}. Le catalogue comporte ses propres adaptateurs et assets metadata.

**Interprétation — C2.** La distribution des configurations de modèle et de sécurité dispose d’un plan d’assets séparé du binaire principal, avec possibilité déclarée de transfert cellulaire et d’assets expérimentaux. Ces structures permettent une évolution de configuration sans prouver qu’une version particulière a été téléchargée.

**Portée et éléments non établis.**

- Aucun payload override téléchargé dans la partition utilisateur n’est présent : contenu effectif, chronologie et application d’un override non établis.
- IgnoreOSCompatibility ne concerne ici que l’asset metadata ; ce n’est ni une désactivation générale de compatibilité, ni une preuve de contournement de signature.
- Le booléen EnableCellular ne démontre ni téléchargement automatique sans consentement ni contenu utilisateur téléversé.
- Aucun experiment assigné à un appareil ou utilisateur n’a été observé.

**Rapport à la documentation publique.** détail d’implémentation non décrit dans la documentation publique consultée par l’orchestrateur ; pas de contradiction établie [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Contrôle et traçabilité des changements : utile de publier les versions d’overrides, cas désactivés et expérience retenue, plutôt que déduire une bascule silencieuse déjà survenue.

**Preuves et provenance.**

- [extracted/rootfs/System/Library/UnifiedAssetFramework/AssetSets/com.apple.MobileAsset.UAF.FM.Overrides.plist](../extracted/rootfs/System/Library/UnifiedAssetFramework/AssetSets/com.apple.MobileAsset.UAF.FM.Overrides.plist) — SHA-256 `3f1df8800b01a484aebaeb03f3b1744e4867da22620fd63a7f3793274ff811c2`. Localisation : /EnableCellular; /Assets/0; /Assets/1; /Assets/166/IgnoreOSCompatibility; /UsageTypes.
  Chemin source firmware : `/System/Library/UnifiedAssetFramework/AssetSets/com.apple.MobileAsset.UAF.FM.Overrides.plist`.
- [extracted/rootfs/System/Library/UnifiedAssetFramework/AssetSets/com.apple.modelcatalog.plist](../extracted/rootfs/System/Library/UnifiedAssetFramework/AssetSets/com.apple.modelcatalog.plist) — SHA-256 `fbd703cfc378263a215199c0491868fc6859cddab74b10b93e70f25486b8ef92`. Localisation : /ExperimentalAssets; /SubjectToAppleIntelligenceWaitlist; /Assets/365; /UsageTypes.
  Chemin source firmware : `/System/Library/UnifiedAssetFramework/AssetSets/com.apple.modelcatalog.plist`.
- [extracted/rootfs/System/Library/Trial/NamespaceDescriptors/NamespaceDescriptor.UAF_AB_MODELCATALOG.plist](../extracted/rootfs/System/Library/Trial/NamespaceDescriptors/NamespaceDescriptor.UAF_AB_MODELCATALOG.plist) — SHA-256 `4b21c9a5005016092224deaf088cd45734e636c16597159610072459a97e8368`. Localisation : /Namespace Name.
  Chemin source firmware : `/System/Library/Trial/NamespaceDescriptors/NamespaceDescriptor.UAF_AB_MODELCATALOG.plist`.

## U-02 — Alias d’usage mêlant adaptateurs locaux et identifiants serveur, avec variantes IFP et langue

**Observation firmware — C3.** memoryCreation.GlobalTraits, QueryUnderstanding et Storyteller enregistrent, pour language_en et isIFPEnabled vrai/faux, les modèles instruct_300m et instruct_3b, des garde-fous et des identifiants com.apple.gm.server.instruct_server_v1.*. Dans GlobalTraits la bascule isIFPEnabled remplace les variantes 3b generic par generic_sparse sans supprimer les identifiants serveur. Siri.AgenticPlanner/language_en ne déclare qu’un identifiant instruct_server_v2.lw_planner_v4.generic. Le catalogue AssetSets répertorie les identifiants correspondants.

**Interprétation — C2.** Les alias sont des déclarations de dépendances/ressources par usage, langue et variante ; ils révèlent une topologie plus fine que la formule générale “on-device ou PCC”. Les deux branches IFP supportent des dépendances locales et des identifiants serveur.

**Portée et éléments non établis.**

- ENABLED dans UsageAliasValues n’est pas la preuve qu’une inférence ou un envoi réseau se produit ; ce n’est pas un journal d’exécution.
- L’étiquette server ne permet pas à elle seule de certifier l’opérateur du serveur, les garanties PCC, les données transportées ou la règle de routage.
- isIFPEnabled_false n’est pas le réglage utilisateur Apple Intelligence désactivée. Aucune correspondance avec un opt-out n’est démontrée.
- Le stockage exact des poids/adaptateurs et leur version runtime restent hors corpus.

**Rapport à la documentation publique.** L’existence d’inférences PCC pour demandes complexes est publique ; noms internes et graphe alias/modèle ne suffisent pas à établir un flux caché. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Le rapport doit préciser chaque couche : asset enregistré, ressource chargée, modèle sélectionné et transfert effectif sont quatre faits différents.

**Preuves et provenance.**

- [extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.GlobalTraits/isIFPEnabled_true_language_en.plist](../extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.GlobalTraits/isIFPEnabled_true_language_en.plist) — SHA-256 `cc0d8cbfa87429343d0cc25fb1bc32e96b9a4179e2198549d9773673e1c905fd`. Localisation : /UsageAliasValues/isIFPEnabled_true_language_en.
  Chemin source firmware : `/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.GlobalTraits/isIFPEnabled_true_language_en.plist`.
- [extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.GlobalTraits/isIFPEnabled_false_language_en.plist](../extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.GlobalTraits/isIFPEnabled_false_language_en.plist) — SHA-256 `fc0c2c545c341a1deb27b25f09afd4e58ce9b99b2d47a7e029af8e37d0305ea4`. Localisation : /UsageAliasValues/isIFPEnabled_false_language_en.
  Chemin source firmware : `/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.GlobalTraits/isIFPEnabled_false_language_en.plist`.
- [extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.QueryUnderstanding/isIFPEnabled_true_language_en.plist](../extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.QueryUnderstanding/isIFPEnabled_true_language_en.plist) — SHA-256 `8318067e35ff26b9d291dae11df8110893709165610c11b513ce83a3276d1879`. Localisation : /UsageAliasValues/isIFPEnabled_true_language_en.
  Chemin source firmware : `/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.QueryUnderstanding/isIFPEnabled_true_language_en.plist`.
- [extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.Storyteller/isIFPEnabled_true_language_en.plist](../extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.Storyteller/isIFPEnabled_true_language_en.plist) — SHA-256 `b7b6db953af48fc2f2e78a70abefddb806a01f573a4d1e0708aa179aff7f7db8`. Localisation : /UsageAliasValues/isIFPEnabled_true_language_en.
  Chemin source firmware : `/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.Storyteller/isIFPEnabled_true_language_en.plist`.
- [extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/Siri.AgenticPlanner/language_en.plist](../extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/Siri.AgenticPlanner/language_en.plist) — SHA-256 `5ffa412577b8f197714336e9ea8317ed32cb8b31efd523f89355bf0ccc24da6a`. Localisation : /UsageAliasValues/language_en/com.apple.modelcatalog.
  Chemin source firmware : `/System/Library/UnifiedAssetFramework/UsageAliases/Siri.AgenticPlanner/language_en.plist`.
- [extracted/rootfs/System/Library/UnifiedAssetFramework/AssetSets/com.apple.modelcatalog.plist](../extracted/rootfs/System/Library/UnifiedAssetFramework/AssetSets/com.apple.modelcatalog.plist) — SHA-256 `fbd703cfc378263a215199c0491868fc6859cddab74b10b93e70f25486b8ef92`. Localisation : /Assets/291; /Assets/317; /Assets/318; /Assets/319.
  Chemin source firmware : `/System/Library/UnifiedAssetFramework/AssetSets/com.apple.modelcatalog.plist`.
- [extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.QueryUnderstanding/isIFPEnabled_false_language_en.plist](../extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.QueryUnderstanding/isIFPEnabled_false_language_en.plist) — SHA-256 `26597dc2c9a9437c2b0dab8e2d98b7e579baca0de4fb932cbe30c1a62324bb26`. Localisation : /UsageAliasValues (branche isIFPEnabled_false_language_en).
  Chemin source firmware : `/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.QueryUnderstanding/isIFPEnabled_false_language_en.plist`.
- [extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.Storyteller/isIFPEnabled_false_language_en.plist](../extracted/rootfs/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.Storyteller/isIFPEnabled_false_language_en.plist) — SHA-256 `e16711a0f1517c6a028029a689afe0eed601be382b6ebcbd7c2b86a626d5cfe3`. Localisation : /UsageAliasValues (branche isIFPEnabled_false_language_en).
  Chemin source firmware : `/System/Library/UnifiedAssetFramework/UsageAliases/memoryCreation.Storyteller/isIFPEnabled_false_language_en.plist`.

## U-03 — Fournisseur de sécurité : entitlements déclarés pour assets, sideload en lecture seule et reporting Biome

**Observation firmware — C3.** Le Mach-O GenerativeExperiencesSafetyInferenceProvider contient un LC_CODE_SIGNATURE à 0xe18 pointant à 0xc840, un SuperBlob valide structurellement, un slot XML entitlements 5 à 0xcba3 (XML 0xcbab) et un slot DER 7. Le XML déclare modelcatalog.full-access, accessible-asset-types GenerativeModels/Overrides, Biome read-write limité au flux AppleIntelligence.Reporting.SafetyOverrides, chemins absolute-path.read-only dont purpose_auto, ressources préinstallées et /private/var/mobile/Library/com.apple.modelcatalog/sideload/. Le point d’extension safety est privé, sans interface utilisateur, exige inferenceprovidermanager et nomme le profil safety-inference-extension. ModelCatalog contient des littéraux pour sideload/assets, sideload/resources et une branche “sideloading disabled”.

**Interprétation — C2.** Le fournisseur peut être conçu pour lire des assets de sécurité provisionnés par plusieurs canaux et émettre des métriques de sécurité locales. Le mécanisme sideload est présent comme fonctionnalité interne conditionnelle.

**Portée et éléments non établis.**

- La chaîne cryptographique Apple du code n’a pas été vérifiée : seuls structure et octets d’entitlements sont analysés.
- Un entitlement déclaré ne prouve pas l’autorité effective face à ACL, signature, sandbox additionnelle, TCC ou politique du service.
- absolute-path.read-only n’autorise pas par cette clé l’écriture dans sideload ; le chemin seul ne prouve pas qu’un tiers peut y placer un modèle accepté.
- Aucune autorisation réseau spécifique ni envoi de contenu n’est déduit de Biome R/W ou de mach-lookup.
- La présence d’un identifiant client de service n’établit pas un identifiant publicitaire, personnel, stable ou transmis.

**Rapport à la documentation publique.** Les détails d’autorisation internes ne sont pas décrits par la documentation grand public ; aucune contradiction démontrée avec PCC ni sécurité des apps tierces. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Point d’audit précis : provenance/signature des assets sideload, séparation des rôles et granularité du reporting, sans revendiquer un contournement.

**Preuves et provenance.**

- [extracted/rootfs/System/Library/ExtensionKit/Extensions/GenerativeExperiencesSafetyInferenceProvider.appex/GenerativeExperiencesSafetyInferenceProvider](../extracted/rootfs/System/Library/ExtensionKit/Extensions/GenerativeExperiencesSafetyInferenceProvider.appex/GenerativeExperiencesSafetyInferenceProvider) — SHA-256 `68e8549527390ea0755ced08942f547b79d5ec258b522e1e7baa7af55d9a8c6b`. Localisation : Mach-O LC_CODE_SIGNATURE @0xe18 ; SuperBlob @0xc840 ; slot 5 @0xcba3, XML @0xcbab.
  Chemin source firmware : `/System/Library/ExtensionKit/Extensions/GenerativeExperiencesSafetyInferenceProvider.appex/GenerativeExperiencesSafetyInferenceProvider`.
- [extracted/rootfs/System/Library/ExtensionKit/ExtensionPoints/com.apple.modelmanager.inferenceprovider.safety.appexpt](../extracted/rootfs/System/Library/ExtensionKit/ExtensionPoints/com.apple.modelmanager.inferenceprovider.safety.appexpt) — SHA-256 `f8a9113f0ce65f287266607750763be503536a28380fd53b8e4ef9c88163ce3d`. Localisation : /com.apple.modelmanager.inferenceprovider.safety.
  Chemin source firmware : `/System/Library/ExtensionKit/ExtensionPoints/com.apple.modelmanager.inferenceprovider.safety.appexpt`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : cache offset 0x1b69c80; __TEXT,__cstring; VA 0x1b9f69c80.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
  Longueur du texte : 58 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : cache offset 0x1bb3f30; __TEXT,__cstring; VA 0x1b9fb3f30.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
  Longueur du texte : 61 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : cache offset 0x1b80b50; __TEXT,__cstring; VA 0x1b9f80b50.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
  Longueur du texte : 25 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : cache offset 0x1bb5cb0; __TEXT,__oslogstring; VA 0x1b9fb5cb0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
  Longueur du texte : 61 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).

## U-04 — Configurations de métriques de sécurité PCC/Siri : télémétrie autorisée et upload direct déclarés

**Observation firmware — C3.** DifferentialPrivacy/Configuration/Collections/com.apple.insights.pcc-safety-metrics.plist définit TelemetryAllowed=true, DirectUpload=true, PrivatizationAlgorithm=PINEResults et un BudgetKeyName. Le budget associé donne RefillInterval=3600, SessionSeconds=86400, SessionAmount=3, RefillAmount=20. SiriSafety définit trois canaux metrics/metadata/results avec les mêmes deux booléens, les algorithmes PINEMetrics/PINEMetadata/PINEResults et budgets distincts.

**Interprétation — C2.** Le firmware contient un chemin configuré pour exporter des résultats/métriques de sécurité via l’infrastructure DifferentialPrivacy, en plus de la seule génération de réponses. Le nom PCC ne désigne pas nécessairement un journal de prompts PCC ; le composant ici est un collecteur de métriques.

**Portée et éléments non établis.**

- TelemetryAllowed=true dans un schéma de collection ne constitue pas à lui seul le consentement global de l’utilisateur ni la preuve d’un opt-out ignoré.
- Le sens exact des unités du budget, les paramètres mathématiques PINE et leur garantie effective ne sont pas reconstruits.
- Aucun payload, destination réseau, fréquence réalisée, identifiant individuel ni contenu de prompt téléversé n’a été constaté.
- La documentation publique décrit déjà des analytics de performance sous consentement ; ces fichiers n’établissent pas une télémétrie secrète hors de ce cadre.

**Rapport à la documentation publique.** Compatible en principe avec les analytics publiquement décrits ; les noms de collections, budgets et algorithmes sont des détails non expliqués par cette notice. Consentement et privatisation effectifs restent à vérifier autrement. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Documenter le schéma de métriques et ses gates de consentement serait plus probant que qualifier DirectUpload d’exfiltration.

**Preuves et provenance.**

- [extracted/rootfs/System/Library/DifferentialPrivacy/Configuration/Collections/com.apple.insights.pcc-safety-metrics.plist](../extracted/rootfs/System/Library/DifferentialPrivacy/Configuration/Collections/com.apple.insights.pcc-safety-metrics.plist) — SHA-256 `eae1274c98777ff1db7f0bcad0028e8cdf436d5dd8e225ce8bca51dd88a5028e`. Localisation : /fedstats:com.apple.insights.pcc-safety-metrics.
  Chemin source firmware : `/System/Library/DifferentialPrivacy/Configuration/Collections/com.apple.insights.pcc-safety-metrics.plist`.
- [extracted/rootfs/System/Library/DifferentialPrivacy/Configuration/Budgets/fedstats.com.apple.insights.pcc-safety-metrics.plist](../extracted/rootfs/System/Library/DifferentialPrivacy/Configuration/Budgets/fedstats.com.apple.insights.pcc-safety-metrics.plist) — SHA-256 `1762bef19f631973bf58970e0479bd5e8d2740239fc954db494f8543b91eb42d`. Localisation : document entier.
  Chemin source firmware : `/System/Library/DifferentialPrivacy/Configuration/Budgets/fedstats.com.apple.insights.pcc-safety-metrics.plist`.
- [extracted/rootfs/System/Library/DifferentialPrivacy/Configuration/Collections/com.apple.priml.PFLMLHostPlugins.FedAutoEvalPlugin.SiriSafety.plist](../extracted/rootfs/System/Library/DifferentialPrivacy/Configuration/Collections/com.apple.priml.PFLMLHostPlugins.FedAutoEvalPlugin.SiriSafety.plist) — SHA-256 `842852965ef7d71e3dc8d815a41e32315c7ee397ec37719ec95e1fc7e0f534b2`. Localisation : clés pfl:...:metrics: ; metadata: ; results:.
  Chemin source firmware : `/System/Library/DifferentialPrivacy/Configuration/Collections/com.apple.priml.PFLMLHostPlugins.FedAutoEvalPlugin.SiriSafety.plist`.
- [extracted/rootfs/System/Library/DifferentialPrivacy/Configuration/Budgets/pfl.com.apple.priml.PFLMLHostPlugins.FedAutoEvalPlugin.SiriSafety.results.plist](../extracted/rootfs/System/Library/DifferentialPrivacy/Configuration/Budgets/pfl.com.apple.priml.PFLMLHostPlugins.FedAutoEvalPlugin.SiriSafety.results.plist) — SHA-256 `48c7c6d758c18239c3b939fdc4352da0d6f65eabe45c4aae4fffbcedaf380e54`. Localisation : document entier.
  Chemin source firmware : `/System/Library/DifferentialPrivacy/Configuration/Budgets/pfl.com.apple.priml.PFLMLHostPlugins.FedAutoEvalPlugin.SiriSafety.results.plist`.

## U-05 — Journaux locaux et diagnostic sensible prévus ; collecte de prompts active non démontrée

**Observation firmware — C3.** Le sous-système ModelManager déclare Signpost-Persisted=true et Privacy-Enable-Level=Private. IntelligenceFlow persiste le niveau Default et ses signposts ; IntelligencePlatform Enable/Persist=Info, avec TTL orchestration Default=7 et Info=2 (unité non documentée ici). FoundationModels contient la chaîne FMLogSensitivePromptAndResponse, ainsi que des formats OSLog SessionID/RequestID/TaggedID et prefix/id/requestID/turnID/sessionID. GenerativeExperiencesRuntime contient un format de journal montrant le prompt avant/après liste de validation ; les deux substitutions sont marquées %{sensitive}s.

**Interprétation — C2.** L’instrumentation permet des diagnostics potentiellement sensibles et des corrélations par requête/session dans le journal local. Les marqueurs sensitive montrent une intention de traitement protégé, sans démontrer la politique effective de redaction.

**Portée et éléments non établis.**

- Une chaîne FMLogSensitivePromptAndResponse n’établit ni que cette option est lue ni sa valeur par défaut ; aucun XREF de code contrôlant le gate n’a été reconstruit.
- La valeur Private dans une configuration de logging n’autorise pas à conclure que toutes données privées sont écrites en clair.
- Les formats de log ne prouvent ni leur exécution, ni la conservation de prompts en production, ni l’envoi à Apple.
- Les UUID/IDs de requête et session ne sont pas démontrés comme identifiants de personne ou de compte.
- Les TTL sont reproduits sans inventer leur unité.

**Rapport à la documentation publique.** La notice Apple distingue données de traitement PCC, métadonnées/analytics et rapport local explicite. Ces preuves de diagnostics côté appareil ne réfutent pas la non-conservation côté PCC. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Question de conception vérifiable : préciser conditions d’activation, redaction, destinations et rétention des diagnostics sensibles ; la collecte active ne peut être affirmée avec ces seuls littéraux.

**Preuves et provenance.**

- [extracted/rootfs/System/Library/Preferences/Logging/Subsystems/com.apple.modelmanager.plist](../extracted/rootfs/System/Library/Preferences/Logging/Subsystems/com.apple.modelmanager.plist) — SHA-256 `9538622c30171dc8f68b7d9b89b57155fbf13ca7611036e3168ae7dca09308fa`. Localisation : /DEFAULT-OPTIONS; /PolicyManager/TTL.
  Chemin source firmware : `/System/Library/Preferences/Logging/Subsystems/com.apple.modelmanager.plist`.
- [extracted/rootfs/System/Library/Preferences/Logging/Subsystems/com.apple.intelligenceflow.plist](../extracted/rootfs/System/Library/Preferences/Logging/Subsystems/com.apple.intelligenceflow.plist) — SHA-256 `db7ac36bfac4fd11c008c1db224fd2018c67c807311c92a616d5acb0ee38d4d1`. Localisation : /DEFAULT-OPTIONS.
  Chemin source firmware : `/System/Library/Preferences/Logging/Subsystems/com.apple.intelligenceflow.plist`.
- [extracted/rootfs/System/Library/Preferences/Logging/Subsystems/com.apple.intelligenceplatform.plist](../extracted/rootfs/System/Library/Preferences/Logging/Subsystems/com.apple.intelligenceplatform.plist) — SHA-256 `f3a686cc5b4a65789d735bfadf164d7eddf7c80b3e69bd2e6fb359c6ad4017aa`. Localisation : /DEFAULT-OPTIONS; /orchestration/TTL.
  Chemin source firmware : `/System/Library/Preferences/Logging/Subsystems/com.apple.intelligenceplatform.plist`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.21` — SHA-256 `979d3287ffc4b427c2ad20a07682b2573ca395eea75a9d23debb2206c28c10f8`. Localisation : cache offset 0x641c00; __TEXT,__cstring; VA 0x1d0a41c00.
  Chemin source firmware : `/System/Library/Frameworks/FoundationModels.framework/FoundationModels`.
  Longueur du texte : 31 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.21` — SHA-256 `979d3287ffc4b427c2ad20a07682b2573ca395eea75a9d23debb2206c28c10f8`. Localisation : cache offset 0x661140; __TEXT,__oslogstring; VA 0x1d0a61140.
  Chemin source firmware : `/System/Library/Frameworks/FoundationModels.framework/FoundationModels`.
  Longueur du texte : 79 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.21` — SHA-256 `979d3287ffc4b427c2ad20a07682b2573ca395eea75a9d23debb2206c28c10f8`. Localisation : cache offset 0x661260; __TEXT,__oslogstring; VA 0x1d0a61260.
  Chemin source firmware : `/System/Library/Frameworks/FoundationModels.framework/FoundationModels`.
  Longueur du texte : 108 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.40` — SHA-256 `bf39e35c9f86485d1ba75435aa052469de804fce09649f7443751b9d451ab361`. Localisation : cache offset 0x10015f0; __TEXT,__oslogstring; VA 0x2314015f0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeExperiencesRuntime.framework/GenerativeExperiencesRuntime`.
  Longueur du texte : 124 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).

## U-06 — Rapport de transparence et métriques de sécurité sont des chemins distincts, avec exclusions et désactivation prévues

**Observation firmware — C3.** GenerativeFunctionsInstrumentation contient des messages d’export de streams, de purge PrivateCloudCompute.RequestLog et GenerativeExperiences.TransparencyLog, “Transparency logging is disabled”, “Excluding event from transparency log”, et “Cross-user donations not supported on embedded platforms”. Des noms de propriétés reportToBiome, reportToOSLog, reportToPowerLog et samplingConfigs sont présents. GenerativeExperiencesRuntime contient “send AppleIntelligenceSafetyOverrides event”, un refus “Blocked from donating safety overrides metric” et une erreur de cas d’usage inconnu.

**Interprétation — C2.** Le code prévoit différents puits de diagnostic et des conditions de filtrage/autorisation ; le rapport de transparence utilisateur ne saurait être assimilé sans preuve à l’ensemble des analytics internes. Les contre-indications explicites empêchent de décrire un reporting inconditionnel.

**Portée et éléments non établis.**

- Aucune exhaustivité du rapport exporté n’est prouvée ; la liste d’événements exclus et les valeurs de sampling ne sont pas établies.
- Aucun flux inter-utilisateur, export automatique ou transfert hors appareil n’est déduit de “reportToBiome”.
- Les textes “disabled” et “blocked” prouvent l’existence de branches/messages, pas leur prise effective.

**Rapport à la documentation publique.** Le rapport Apple Intelligence local activable est public. Les streams et puits internes affinent son implémentation ; rien ne démontre que ce rapport constitue une copie serveur ou une collecte cachée. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Documenter les catégories incluses/exclues et le lien entre rapport utilisateur, Biome, PowerLog et OSLog favoriserait une transparence contrôlable.

**Preuves et provenance.**

- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7ba8460; __TEXT,__oslogstring; VA 0x1affa8460.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 66 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7ba84b0; __TEXT,__oslogstring; VA 0x1affa84b0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 73 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7ba8560; __TEXT,__oslogstring; VA 0x1affa8560.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 28 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7ba85d0; __TEXT,__oslogstring; VA 0x1affa85d0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 29 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7ba8610; __TEXT,__oslogstring; VA 0x1affa8610.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 56 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7ba8670; __TEXT,__oslogstring; VA 0x1affa8670.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 32 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7ba86a0; __TEXT,__oslogstring; VA 0x1affa86a0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 37 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7baa040; __TEXT,__swift5_reflstr; VA 0x1affaa040.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 15 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7baa0cd; __TEXT,__swift5_reflstr; VA 0x1affaa0cd.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 13 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7baa0e0; __TEXT,__swift5_reflstr; VA 0x1affaa0e0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 13 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.11` — SHA-256 `1abfa9f6ad6fe9f9ed53dacf846ebcb6c512814508cb47c5b0cd66c1c53abac0`. Localisation : cache offset 0x7baa0f0; __TEXT,__swift5_reflstr; VA 0x1affaa0f0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeFunctionsInstrumentation.framework/GenerativeFunctionsInstrumentation`.
  Longueur du texte : 16 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.40` — SHA-256 `bf39e35c9f86485d1ba75435aa052469de804fce09649f7443751b9d451ab361`. Localisation : cache offset 0x10014e0; __TEXT,__oslogstring; VA 0x2314014e0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeExperiencesRuntime.framework/GenerativeExperiencesRuntime`.
  Longueur du texte : 59 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.40` — SHA-256 `bf39e35c9f86485d1ba75435aa052469de804fce09649f7443751b9d451ab361`. Localisation : cache offset 0x1001520; __TEXT,__oslogstring; VA 0x231401520.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeExperiencesRuntime.framework/GenerativeExperiencesRuntime`.
  Longueur du texte : 43 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.40` — SHA-256 `bf39e35c9f86485d1ba75435aa052469de804fce09649f7443751b9d451ab361`. Localisation : cache offset 0x1001550; __TEXT,__oslogstring; VA 0x231401550.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeExperiencesRuntime.framework/GenerativeExperiencesRuntime`.
  Longueur du texte : 53 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).

## U-07 — PCCAsDefault et persistance : métadonnées de feature flags, sans valeur d’activation

**Observation firmware — C3.** FeatureFlags/Domain/IntelligenceFlow.plist contient les entrées PCCAsDefault, PCCUsePrefixID, OutputGuardrailOnPCC, UseIFParticipantPersistence, SystemResponseResultCollection, RemoteLocalSearch et AppExclusions, toutes avec DevelopmentPhase=FeatureComplete. GenerativeModels.plist contient ConversationPersistDefaultToTransient, AgentSessionKitSync et AgentSessionKitEnforceSyncableEntityConformance avec le même champ. Ces entrées ne portent pas de clé Enabled. À titre de contraste, ModelManager.plist donne explicitement Enabled=true pour exclaves et autres entrées.

**Interprétation — C2.** Ces noms exposent des axes de conception et de configuration (préférence PCC, persistance, synchronisation), mais le fichier de domaine n’est pas un relevé de la configuration effective.

**Portée et éléments non établis.**

- PCCAsDefault/FeatureComplete n’établit pas PCC activé par défaut pour chaque requête ou appareil.
- ConversationPersistDefaultToTransient suggère au contraire une option de persistance transitoire ; son activation n’est pas établie.
- Les mots Sync et Persistence ne prouvent aucun contenu utilisateur synchronisé sans consentement.
- DisclosureRequired, présent sur d’autres flags, est une métadonnée interne dont aucune sémantique UI/légale n’est reconstruite ici.

**Rapport à la documentation publique.** La documentation publique décrit le choix local/PCC ; la seule présence de noms de flags ne démontre aucun écart au consentement ou au routage annoncé. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Écarte une lecture abusive fréquente : disponibilité de code/flag ≠ fonctionnalité active ≠ défaut utilisateur.

**Preuves et provenance.**

- [extracted/rootfs/System/Library/FeatureFlags/Domain/IntelligenceFlow.plist](../extracted/rootfs/System/Library/FeatureFlags/Domain/IntelligenceFlow.plist) — SHA-256 `685555bfc3ac41a4ff8dee8ca996318bd3e1746bc48f75bcb03eeeca1d61e6a2`. Localisation : /PCCAsDefault; /PCCUsePrefixID; /UseIFParticipantPersistence; /SystemResponseResultCollection.
  Chemin source firmware : `/System/Library/FeatureFlags/Domain/IntelligenceFlow.plist`.
- [extracted/rootfs/System/Library/FeatureFlags/Domain/GenerativeModels.plist](../extracted/rootfs/System/Library/FeatureFlags/Domain/GenerativeModels.plist) — SHA-256 `1a49259ecacc6ba983eb909b89b6ecf6919fea538a8e55a769a9e88a4603858a`. Localisation : /ConversationPersistDefaultToTransient; /AgentSessionKitSync.
  Chemin source firmware : `/System/Library/FeatureFlags/Domain/GenerativeModels.plist`.
- [extracted/rootfs/System/Library/FeatureFlags/Domain/ModelManager.plist](../extracted/rootfs/System/Library/FeatureFlags/Domain/ModelManager.plist) — SHA-256 `23ffc65ccaba1ffd547fa8a51cd956f66c8fcf1b5a7270613e860cbde125f962`. Localisation : /exclaves/Enabled.
  Chemin source firmware : `/System/Library/FeatureFlags/Domain/ModelManager.plist`.

## U-08 — ModelManager/Policy.plist arbitre les ressources et priorités, sans politique d’export visible

**Observation firmware — C3.** ModelManager/Policy.plist répertorie 14 politiques (thermique, pression mémoire, caméra, audio, Siri, jeu...) avec assetPolicy et cancelPriority, une AllowList de 21 bundle IDs comprenant intelligenceflowd, Notes, Image Playground et Health. La politique XcodePlaygrounds spécifie unentitledBackgroundInferenceCap=60000000 et unentitledBackgroundInferenceWindow=3600 ; CarPlayNavigation ajoute des délais et timeout à 1.

**Interprétation — C2.** Ce fichier sert vraisemblablement à arbitrer chargement d’assets et inférences suivant pression système et contexte applicatif. Son AllowList ne doit pas être transposée à une liste d’apps autorisées à aspirer les données personnelles.

**Portée et éléments non établis.**

- Aucune clause d’upload, de contenu de prompt ou de consentement n’a été observée dans ce fichier précis. Cela ne prouve pas l’absence de ces contrôles ailleurs.
- Les unités du cap et des délais ne sont pas déduites des noms de clés.
- La présence de Health dans AllowList ne prouve ni lecture de dossiers de santé ni transmission de données Health.

**Rapport à la documentation publique.** Détail interne de gouvernance de ressources ; aucune contradiction identifiée avec la notice de vie privée. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Clarifie ce que Policy.plist autorise réellement à inférer ; ce n’est pas une preuve de politique de collecte ni une permission de lecture de tout contenu.

**Preuves et provenance.**

- [extracted/rootfs/System/Library/ModelManager/Policy.plist](../extracted/rootfs/System/Library/ModelManager/Policy.plist) — SHA-256 `0be5d7ebbb0ff35f9f1e863d98bb4ae9e7d7a2d8751212a5d1ab4d0d05bed3f0`. Localisation : /Policies; /AllowList; /Policies/XcodePlaygrounds; /Policies/CarPlayNavigation.
  Chemin source firmware : `/System/Library/ModelManager/Policy.plist`.

## U-09 — État opt-in indexé par primary DSID : lien de compte local suggéré, transmission non établie

**Observation firmware — C3.** GenerativeModels contient le diagnostic “Device has primary DSID, using to key opt-in status.”, les notifications “Set new value for opt-in toggle”, “Sending distributed notification on auto opt-in change.”, “Opted in via buddy but device is signed in, skipping extra notification update.” et “Setting GMOptIn.isOptedIn to %{bool}d from %s %s.” Les octets sont confirmés dans le cache .01 aux offsets 0x6e13010–0x6e13130. Des diagnostics voisins prévoient aussi le blocage de donation de métriques safety guardrails.

**Interprétation — C2.** Un chemin de gestion du consentement associe apparemment son état au primary DSID sur un appareil connecté, puis notifie des changements locaux. La portée de cet identifiant est différente des identifiants de requête analysés dans U-05.

**Portée et éléments non établis.**

- Le littéral auto opt-in ne démontre pas qu’un utilisateur est inscrit sans acte ou contre son choix ; les conditions et valeurs par défaut ne sont pas reconstruites.
- La chaîne DSID décrit un index d’état local, pas un champ de requête PCC ni un payload analytique observé.
- Aucune transmission, présence de DSID dans un prompt, stabilité d’un identifiant analytique ni contournement de consentement n’est établie.
- Une branche “using to key” reste une possibilité de code ; aucune exécution sur appareil n’a été faite.

**Rapport à la documentation publique.** Les déclarations publiques d’analytics non liés au compte ou de non-identification PCC portent sur des transmissions. Un index de consentement local par DSID ne les réfute pas. [PUB-01](https://www.apple.com/legal/privacy/data/en/intelligence-engine/)

**Intérêt de revue.** Question de transparence utile : expliquer la portée par compte/appareil du choix, sa migration et les conditions d’auto opt-in, sans inventer une inscription forcée.

**Preuves et provenance.**

- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.01` — SHA-256 `6633388923338f070d075cdbcd8d79fa5bbc156853d03244f114956428d8c86d`. Localisation : cache offset 0x6e13010; __TEXT,__oslogstring; VA 0x187213010.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeModels.framework/GenerativeModels`.
  Longueur du texte : 52 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.01` — SHA-256 `6633388923338f070d075cdbcd8d79fa5bbc156853d03244f114956428d8c86d`. Localisation : cache offset 0x6e13050; __TEXT,__oslogstring; VA 0x187213050.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeModels.framework/GenerativeModels`.
  Longueur du texte : 70 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.01` — SHA-256 `6633388923338f070d075cdbcd8d79fa5bbc156853d03244f114956428d8c86d`. Localisation : cache offset 0x6e130a0; __TEXT,__oslogstring; VA 0x1872130a0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeModels.framework/GenerativeModels`.
  Longueur du texte : 55 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.01` — SHA-256 `6633388923338f070d075cdbcd8d79fa5bbc156853d03244f114956428d8c86d`. Localisation : cache offset 0x6e130e0; __TEXT,__oslogstring; VA 0x1872130e0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeModels.framework/GenerativeModels`.
  Longueur du texte : 79 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.01` — SHA-256 `6633388923338f070d075cdbcd8d79fa5bbc156853d03244f114956428d8c86d`. Localisation : cache offset 0x6e13130; __TEXT,__oslogstring; VA 0x187213130.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeModels.framework/GenerativeModels`.
  Longueur du texte : 49 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.01` — SHA-256 `6633388923338f070d075cdbcd8d79fa5bbc156853d03244f114956428d8c86d`. Localisation : cache offset 0x6e133e0; __TEXT,__oslogstring; VA 0x1872133e0.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeModels.framework/GenerativeModels`.
  Longueur du texte : 38 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.01` — SHA-256 `6633388923338f070d075cdbcd8d79fa5bbc156853d03244f114956428d8c86d`. Localisation : cache offset 0x6e13410; __TEXT,__oslogstring; VA 0x187213410.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeModels.framework/GenerativeModels`.
  Longueur du texte : 62 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.01` — SHA-256 `6633388923338f070d075cdbcd8d79fa5bbc156853d03244f114956428d8c86d`. Localisation : cache offset 0x6e13450; __TEXT,__oslogstring; VA 0x187213450.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeModels.framework/GenerativeModels`.
  Longueur du texte : 44 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.01` — SHA-256 `6633388923338f070d075cdbcd8d79fa5bbc156853d03244f114956428d8c86d`. Localisation : cache offset 0x6e13480; __TEXT,__oslogstring; VA 0x187213480.
  Chemin source firmware : `/System/Library/PrivateFrameworks/GenerativeModels.framework/GenerativeModels`.
  Longueur du texte : 54 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).

## U-10 — Piste OSM dans AssistantServices : endpoint d’upload, rattachement à Apple Intelligence non établi

**Observation firmware — C3.** AssistantServices contient, dans un voisinage de chaînes, OSMDataCollection, -[AFOpportuneSpeakingModuleDataCollection init], /tmp/OSM/, l’URL https://osmdatacollectionproxy.usspk02.orchard.apple.com/upload et -[AFOpportuneSpeakingModuleDataCollection _deleteSpeakablesOlderThan:]. Le même voisinage contient des libellés ContactId, SpeakableId et SpeakableFeatures. Ces octets figurent dans le cache .07, offsets 0x10d0d92–0x10d0eea. Aucun contact avec cet endpoint n’a été effectué.

**Interprétation — C1.** Les noms suggèrent un composant de collecte de données lié au choix des annonces Siri, avec un endpoint d’upload intégré. La simple proximité de chaînes ne reconstitue pas le schéma de données ni un appel réseau.

**Portée et éléments non établis.**

- Aucun flux réseau ni payload observé ; aucun lien démontré avec les prompts Apple Intelligence, PCC ou l’exécution Foundation Models.
- Le composant peut être historique, expérimental ou soumis à consentement ; aucun de ces régimes n’est établi.
- ContactId est un libellé de code ; aucune donnée de contact effectivement collectée, adressage personnel ou possibilité de réidentifier n’a été constaté.
- Le caractère caché ou non documenté de ce composant particulier n’a pas été démontré par une recherche documentaire spécialisée. Il s’agit d’une piste bornée, pas d’un finding d’exfiltration.

**Rapport à la documentation publique.** Ne pas comparer directement ce mécanisme OSM aux garanties PCC : son rattachement à Apple Intelligence n’est pas établi dans cette analyse.

**Intérêt de revue.** Piste séparée à conserver parmi les limites ; ne justifie pas une accusation de transfert de prompts.

**Preuves et provenance.**

- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.07` — SHA-256 `e04a82e00d64131e6c69f48e064db1425726f46d50af5c51d067a181b46d3050`. Localisation : cache offset 0x10d0d92; __TEXT,__cstring; VA 0x1994d0d92.
  Chemin source firmware : `/System/Library/PrivateFrameworks/AssistantServices.framework/AssistantServices`.
  Longueur du texte : 17 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.07` — SHA-256 `e04a82e00d64131e6c69f48e064db1425726f46d50af5c51d067a181b46d3050`. Localisation : cache offset 0x10d0da4; __TEXT,__cstring; VA 0x1994d0da4.
  Chemin source firmware : `/System/Library/PrivateFrameworks/AssistantServices.framework/AssistantServices`.
  Longueur du texte : 47 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.07` — SHA-256 `e04a82e00d64131e6c69f48e064db1425726f46d50af5c51d067a181b46d3050`. Localisation : cache offset 0x10d0dd4; __TEXT,__cstring; VA 0x1994d0dd4.
  Chemin source firmware : `/System/Library/PrivateFrameworks/AssistantServices.framework/AssistantServices`.
  Longueur du texte : 9 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.07` — SHA-256 `e04a82e00d64131e6c69f48e064db1425726f46d50af5c51d067a181b46d3050`. Localisation : cache offset 0x10d0dde; __TEXT,__cstring; VA 0x1994d0dde.
  Chemin source firmware : `/System/Library/PrivateFrameworks/AssistantServices.framework/AssistantServices`.
  Longueur du texte : 63 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.07` — SHA-256 `e04a82e00d64131e6c69f48e064db1425726f46d50af5c51d067a181b46d3050`. Localisation : cache offset 0x10d0e40; __TEXT,__cstring; VA 0x1994d0e40.
  Chemin source firmware : `/System/Library/PrivateFrameworks/AssistantServices.framework/AssistantServices`.
  Longueur du texte : 9 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.07` — SHA-256 `e04a82e00d64131e6c69f48e064db1425726f46d50af5c51d067a181b46d3050`. Localisation : cache offset 0x10d0e52; __TEXT,__cstring; VA 0x1994d0e52.
  Chemin source firmware : `/System/Library/PrivateFrameworks/AssistantServices.framework/AssistantServices`.
  Longueur du texte : 11 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.07` — SHA-256 `e04a82e00d64131e6c69f48e064db1425726f46d50af5c51d067a181b46d3050`. Localisation : cache offset 0x10d0e5e; __TEXT,__cstring; VA 0x1994d0e5e.
  Chemin source firmware : `/System/Library/PrivateFrameworks/AssistantServices.framework/AssistantServices`.
  Longueur du texte : 17 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.07` — SHA-256 `e04a82e00d64131e6c69f48e064db1425726f46d50af5c51d067a181b46d3050`. Localisation : cache offset 0x10d0eea; __TEXT,__cstring; VA 0x1994d0eea.
  Chemin source firmware : `/System/Library/PrivateFrameworks/AssistantServices.framework/AssistantServices`.
  Longueur du texte : 70 octets ; hash portant sur le cache physique entier.
  Témoin en clair : [analysis/evidence/routing-dsc-literals.jsonl](../analysis/evidence/routing-dsc-literals.jsonl).

## U-20 — Limite de comparaison bêta 2 / RC : les ressources rootfs bêta sont des stubs, pas des contenus comparables

**Observation firmware — C3.** Les manifestes locaux identifient le même type iPhone18,3 et ProductVersion 27.2, avec builds 24B5089g et 24B115. Dans fs_root bêta, 1 334 des 1 339 fichiers sont vides. Les 75 chemins présents à la fois dans fs_root bêta et extracted/rootfs RC sont tous vides côté bêta. Les cinq fichiers bêta non vides sont des artefacts binaires de modèles de durée/batterie/Recipe, hors des ressources AI textuelles comparées.

**Interprétation — C3.** La différence de taille entre un stub bêta et un fichier RC ne peut pas être attribuée à une modification du firmware. La comparaison directe des prompts, Policy.plist, UsageAliases et catalogues rootfs n’est pas réalisable à partir de cette extraction bêta.

**Portée et éléments non établis.**

- Aucun ajout/suppression de prompt ou de politique entre ces builds n’est établi à partir des stubs.
- Les libellés « bêta 2 » et « RC » sont ceux des dossiers et du mandat : les clés de version des manifestes attestent ici la version/build, pas le rang de bêta, la date de publication ou la signature Apple.
- L’absence d’une ressource dans l’extraction bêta ne démontre pas son absence dans le firmware.

**Rapport à la documentation publique.** Sans objet : limitation du corpus local, pas contradiction à une déclaration publique Apple.

**Intérêt de revue.** Limite méthodologique essentielle : évite de présenter un écart d’extraction comme un changement silencieux Apple Intelligence.

**Preuves et provenance.**

- [analysis/evidence/beta2-BuildManifest.plist](../analysis/evidence/beta2-BuildManifest.plist) — SHA-256 `3f8dae55cdf0a6b3d3b3092b01775f5eae6028a4e6ab534dbaccec548f97064a`. Localisation : ProductVersion=27.2; ProductBuildVersion=24B5089g; SupportedProductTypes=[iPhone18,3].
  Chemin source firmware : `BuildManifest.plist (IPSW)`.
- [review/BuildManifest.plist](../review/BuildManifest.plist) — SHA-256 `abba3b0916614585b2213b723cd4e1a34c9939ed3ba839f3fd3fe155179ddc96`. Localisation : ProductVersion=27.2; ProductBuildVersion=24B115; SupportedProductTypes=[iPhone18,3].
  Chemin source firmware : `BuildManifest.plist (IPSW)`.
- `/workspace/recherche/apple-sec/ios272beta2/.blacksmith/fs-inventory.json` — SHA-256 `e7f6a765363acede4f11559e72455fd67fe508ba9ee8b365567fc6fe1a4db95a`. Localisation : entries : 1339 kind=file, dont 1334 size=0.
  Chemin source firmware : `fs_root (inventaire d’extraction)`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/fs_root/System/Library/LaunchDaemons/com.apple.modelcatalogd.plist` — SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Localisation : 0 octet; témoin de stub extrait.
  Chemin source firmware : `/System/Library/LaunchDaemons/com.apple.modelcatalogd.plist`.
- [extracted/rootfs/System/Library/LaunchDaemons/com.apple.modelcatalogd.plist](../extracted/rootfs/System/Library/LaunchDaemons/com.apple.modelcatalogd.plist) — SHA-256 `1f5c8f34fa3acd90b83e4d975b3e5a621b071d0bb3bd898c5edc74e7f03d09a5`. Localisation : Fichier RC non vide, 2473 octets.
  Chemin source firmware : `/System/Library/LaunchDaemons/com.apple.modelcatalogd.plist`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/fs_root/System/Library/LaunchDaemons/com.apple.modelmanagerd.plist` — SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Localisation : 0 octet; témoin de stub extrait.
  Chemin source firmware : `/System/Library/LaunchDaemons/com.apple.modelmanagerd.plist`.
- [extracted/rootfs/System/Library/LaunchDaemons/com.apple.modelmanagerd.plist](../extracted/rootfs/System/Library/LaunchDaemons/com.apple.modelmanagerd.plist) — SHA-256 `c974ff4a344ff496721ee97b3c1f35afecc0d7f8e56ef3176eece340249809ab`. Localisation : Fichier RC non vide, 686 octets.
  Chemin source firmware : `/System/Library/LaunchDaemons/com.apple.modelmanagerd.plist`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/fs_root/System/Library/LaunchDaemons/com.apple.intelligenceflowd.plist` — SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Localisation : 0 octet; témoin de stub extrait.
  Chemin source firmware : `/System/Library/LaunchDaemons/com.apple.intelligenceflowd.plist`.
- [extracted/rootfs/System/Library/LaunchDaemons/com.apple.intelligenceflowd.plist](../extracted/rootfs/System/Library/LaunchDaemons/com.apple.intelligenceflowd.plist) — SHA-256 `f06a7d5386a9ebd5a267803b120ed6477092ecef0d03dec81a09c681b11b9a43`. Localisation : Fichier RC non vide, 2836 octets.
  Chemin source firmware : `/System/Library/LaunchDaemons/com.apple.intelligenceflowd.plist`.
- [analysis/evidence/beta-fs-comparison.json](../analysis/evidence/beta-fs-comparison.json) — SHA-256 `a3e22efd5a15bee8c026d0409d6302913d9e34ba6c4fcbc93d4a68a5d2b6f2cf`. Localisation : counts et common_paths : 75 chemins communs, 0 contenu bêta non vide.
  Chemin source firmware : `Comparaison des extractions`.

## U-21 — Delta statique attesté de ModelCatalog : noms HomeKit, planner serveur Axon et variantes de modèles

**Observation firmware — C3.** Sur le même chemin Mach-O /System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog, les sections __TEXT,__cstring et __TEXT,__oslogstring donnent 4 847 littéraux distincts bêta et 4 859 RC (4 846 communs). Treize littéraux apparaissent dans ces sections RC sans équivalent textuel exact dans les sections bêta comparées ; un littéral bêta n’a pas d’équivalent textuel exact dans les sections RC comparées. Les nouveaux noms incluent com.apple.fm.language.instruct_3b.homekit_documentation_search, ses adapter_metadata_override générique et generic_sparse, com.apple.fm.language.instruct_server_v2.axon_planner / ServerV2AxonPlanner, afm_cider_mt_v1 et afm_cider_speech_mt_v1. Le nom s2s_mt_v1 n’est retrouvé que côté bêta dans ces sections. La section __oslogstring est identique octet pour octet ; les différences sont dans __cstring.

**Interprétation — C1.** Ces différences attestent une évolution de noms et configurations compilés du catalogue. Les noms suggèrent une compatibilité avec une recherche de documentation HomeKit et un planner Axon associé à une famille nommée serveur.

**Portée et éléments non établis.**

- Ni activation par défaut, ni déclenchement effectif, ni sélection d’un modèle, ni appel réseau/PCC réel ne sont prouvés par ces littéraux.
- L’ajout d’un nom compilé ne démontre pas l’ajout d’une fonction côté utilisateur.
- L’absence du nom s2s_mt_v1 est limitée aux sections comparées du framework ModelCatalog ; aucun retrait global du firmware ou du service n’est établi.
- Il ne s’agit pas d’un diff de code ou d’un inventaire exhaustif de tous les noms des deux firmwares.

**Rapport à la documentation publique.** PCC est public (PUB-07). Le delta de littéraux est établi ; cette revue ne démontre pas que les changements sont absents de toutes les annonces Apple. Aucun changement comportemental silencieux ne peut être affirmé.

**Intérêt de revue.** Delta de catalogue interne mesurable entre les deux builds. L’angle transparence porte sur la granularité du routage prévu ; aucune collecte dissimulée n’est démontrée.

**Preuves et provenance.**

- [analysis/evidence/beta2-BuildManifest.plist](../analysis/evidence/beta2-BuildManifest.plist) — SHA-256 `3f8dae55cdf0a6b3d3b3092b01775f5eae6028a4e6ab534dbaccec548f97064a`. Localisation : ProductVersion=27.2; ProductBuildVersion=24B5089g; SupportedProductTypes=[iPhone18,3].
  Chemin source firmware : `BuildManifest.plist (IPSW)`.
- [review/BuildManifest.plist](../review/BuildManifest.plist) — SHA-256 `abba3b0916614585b2213b723cd4e1a34c9939ed3ba839f3fd3fe155179ddc96`. Localisation : ProductVersion=27.2; ProductBuildVersion=24B115; SupportedProductTypes=[iPhone18,3].
  Chemin source firmware : `BuildManifest.plist (IPSW)`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/dsc/dyld_shared_cache_arm64e.15` — SHA-256 `f7099c1d6559d81846283ef065fda97f4997ce4a1b92f8800147e67d2ffe19ec`. Localisation : beta: __TEXT,__cstring, cache offset 0x28974f0, 306654 octets, SHA256 section=a80faf1f1e145835a77bc32f96a1fd1935b8a190d4973858a508f8262df58d60.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/dsc/dyld_shared_cache_arm64e.15` — SHA-256 `f7099c1d6559d81846283ef065fda97f4997ce4a1b92f8800147e67d2ffe19ec`. Localisation : beta: __TEXT,__oslogstring, cache offset 0x28e22d0, 7945 octets, SHA256 section=0202849a778d19b11db00a143e871d163ce74e5b55693c3cb510ba41fda64d24.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : rc: __TEXT,__cstring, cache offset 0x1b69880, 307566 octets, SHA256 section=a4b623f7831c98db9b61b9bc4ba78d0d2ff23cbaa2cd1747dbdde4e264a80e93.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : rc: __TEXT,__oslogstring, cache offset 0x1bb49f0, 7945 octets, SHA256 section=0202849a778d19b11db00a143e871d163ce74e5b55693c3cb510ba41fda64d24.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1b6adfa, 12 octets : Axon.Planner.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1b72410, 62 octets : com.apple.fm.language.instruct_3b.homekit_documentation_search.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1b74cd0, 53 octets : com.apple.fm.language.instruct_server_v2.axon_planner.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1b7b270, 88 octets : com.apple.fm.language.instruct_3b.homekit_documentation_search.adapter_metadata_override.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1b7ccb4, 15 octets : afm_cider_mt_v1.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1b7ccd0, 22 octets : afm_cider_speech_mt_v1.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1b84e40, 116 octets : Invalid configuration for com.apple.fm.language.instruct_3b.homekit_documentation_search.adapter_metadata_override: .
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1b8b830, 81 octets : Invalid configuration for com.apple.fm.language.instruct_server_v2.axon_planner: .
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1b91a80, 26 octets : HomeKitDocumentationSearch.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1b92d10, 19 octets : ServerV2AxonPlanner.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1bacae0, 96 octets : com.apple.fm.language.instruct_3b.homekit_documentation_search.adapter_metadata_override.generic.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1bacb50, 103 octets : com.apple.fm.language.instruct_3b.homekit_documentation_search.adapter_metadata_override.generic_sparse.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.15` — SHA-256 `0c53b067311a0656ac14d9031c3fafbff4c0c889aa2df761d134d500c7b1280d`. Localisation : __TEXT,__cstring, cache offset 0x1bb18c0, 111 octets : com.apple.fm.language.instruct_3b.homekit_documentation_search.adapter_metadata_override?variant=generic_sparse.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/dsc/dyld_shared_cache_arm64e.15` — SHA-256 `f7099c1d6559d81846283ef065fda97f4997ce4a1b92f8800147e67d2ffe19ec`. Localisation : __TEXT,__cstring, cache offset 0x28aa834, 9 octets : s2s_mt_v1.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalog.framework/ModelCatalog`.
- [analysis/evidence/beta-dsc-comparison.json](../analysis/evidence/beta-dsc-comparison.json) — SHA-256 `d216782e99c3d448598c706633516542cf47ab53431475818bbff1559f3bb464`. Localisation : section_comparison[ModelCatalog] : ensembles et 14 témoins avec offsets/longueurs.
  Chemin source firmware : `Comparaison DSC ciblée`.

## U-22 — Contrôle négatif ciblé : mêmes octets de chaînes pour UAF, ModelCatalogRuntime et ModelManagerServices

**Observation firmware — C3.** Les sections __TEXT,__cstring et __TEXT,__oslogstring sont identiques octet pour octet entre les deux builds, pour chacun des trois mêmes chemins Mach-O : UnifiedAssetFramework, ModelCatalogRuntime et ModelManagerServices. Les ensembles contiennent respectivement 2 114, 398 et 419 littéraux distincts. Les offsets et adresses virtuelles ont changé, mais les tailles et SHA-256 des six paires de sections sont identiques.

**Interprétation — C3.** Aucun changement de contenu textuel n’est observé dans ces sections précises.

**Portée et éléments non établis.**

- L’identité de ces sections de chaînes ne prouve pas l’identité du code, des politiques externes, des catalogues téléchargés ou du comportement runtime.
- L’absence de changement dans ces sections ne permet pas de conclure qu’Apple Intelligence est inchangé entre bêta et RC.

**Rapport à la documentation publique.** Sans objet : constat comparatif borné sur les octets du firmware, pas revendication de conformité globale.

**Intérêt de revue.** Contrôle négatif évitant de surinterpréter la comparaison des builds ou un déplacement d’adresse comme une évolution comportementale.

**Preuves et provenance.**

- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/dsc/dyld_shared_cache_arm64e.42` — SHA-256 `0f75eb60c7a4d4f6dfb8b8228d880a503899da1160cb1b4b60025ff5c396e0e7`. Localisation : beta: __TEXT,__cstring, cache offset 0x6500420, 6718 octets, SHA256 section=3717d1ee2568b4f697e1c26d131ebd0e1dffe88c99d03b07a34f6669a102facc.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalogRuntime.framework/ModelCatalogRuntime`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/dsc/dyld_shared_cache_arm64e.42` — SHA-256 `0f75eb60c7a4d4f6dfb8b8228d880a503899da1160cb1b4b60025ff5c396e0e7`. Localisation : beta: __TEXT,__oslogstring, cache offset 0x6505030, 19114 octets, SHA256 section=1c22ffc0dabe87bfd00b8527c942c326082537747c28113cff591980d000038d.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalogRuntime.framework/ModelCatalogRuntime`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.42` — SHA-256 `48b5ec2984c8b649ea145c8fcef0bfa3b4d48596759fd7928c4189a9baae37e2`. Localisation : rc: __TEXT,__cstring, cache offset 0x65a1430, 6718 octets, SHA256 section=3717d1ee2568b4f697e1c26d131ebd0e1dffe88c99d03b07a34f6669a102facc.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalogRuntime.framework/ModelCatalogRuntime`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.42` — SHA-256 `48b5ec2984c8b649ea145c8fcef0bfa3b4d48596759fd7928c4189a9baae37e2`. Localisation : rc: __TEXT,__oslogstring, cache offset 0x65a6040, 19114 octets, SHA256 section=1c22ffc0dabe87bfd00b8527c942c326082537747c28113cff591980d000038d.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelCatalogRuntime.framework/ModelCatalogRuntime`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/dsc/dyld_shared_cache_arm64e.07` — SHA-256 `06209ff4ace3b8cd1e76027eba8c7ade8e7170b613106e3bbab20ff2ca5eda8b`. Localisation : beta: __TEXT,__oslogstring, cache offset 0x7a5a330, 7515 octets, SHA256 section=23e85954d96e29a5c054df8acf320776bdf6db982e1ef19753dc2a152ba1b936.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelManagerServices.framework/ModelManagerServices`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/dsc/dyld_shared_cache_arm64e.07` — SHA-256 `06209ff4ace3b8cd1e76027eba8c7ade8e7170b613106e3bbab20ff2ca5eda8b`. Localisation : beta: __TEXT,__cstring, cache offset 0x7a5c090, 10538 octets, SHA256 section=4640de0bb7116058364018f928b50511d9a9ffebabb1b34406509738e486e378.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelManagerServices.framework/ModelManagerServices`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.07` — SHA-256 `e04a82e00d64131e6c69f48e064db1425726f46d50af5c51d067a181b46d3050`. Localisation : rc: __TEXT,__oslogstring, cache offset 0x7110330, 7515 octets, SHA256 section=23e85954d96e29a5c054df8acf320776bdf6db982e1ef19753dc2a152ba1b936.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelManagerServices.framework/ModelManagerServices`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.07` — SHA-256 `e04a82e00d64131e6c69f48e064db1425726f46d50af5c51d067a181b46d3050`. Localisation : rc: __TEXT,__cstring, cache offset 0x7112090, 10538 octets, SHA256 section=4640de0bb7116058364018f928b50511d9a9ffebabb1b34406509738e486e378.
  Chemin source firmware : `/System/Library/PrivateFrameworks/ModelManagerServices.framework/ModelManagerServices`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/dsc/dyld_shared_cache_arm64e.28` — SHA-256 `e93f50926d4f697c427f8939b0a74e496663051d4af58bc7f9d65bdbdd5baa4c`. Localisation : beta: __TEXT,__cstring, cache offset 0x5e362c0, 47046 octets, SHA256 section=dca9f3ea2f2740a616143735a6b4a57578b555e495ceb3d10c0e1508ee2d359e.
  Chemin source firmware : `/System/Library/PrivateFrameworks/UnifiedAssetFramework.framework/UnifiedAssetFramework`.
- `/workspace/recherche/apple-sec/ios272beta2/artifacts/ios-firmware/iPhone18,3/27.2/24B5089g/dsc/dyld_shared_cache_arm64e.28` — SHA-256 `e93f50926d4f697c427f8939b0a74e496663051d4af58bc7f9d65bdbdd5baa4c`. Localisation : beta: __TEXT,__oslogstring, cache offset 0x5e41a90, 61639 octets, SHA256 section=ba0c1b10d6c6aca59b0d83193c669a4dc70976f3c43e49f34994f2eaeff55c13.
  Chemin source firmware : `/System/Library/PrivateFrameworks/UnifiedAssetFramework.framework/UnifiedAssetFramework`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.28` — SHA-256 `c8b612e814a4c26ede6b3edf16a337191c94dff64b0a342332f667b815c09a3b`. Localisation : rc: __TEXT,__cstring, cache offset 0x548e2c0, 47046 octets, SHA256 section=dca9f3ea2f2740a616143735a6b4a57578b555e495ceb3d10c0e1508ee2d359e.
  Chemin source firmware : `/System/Library/PrivateFrameworks/UnifiedAssetFramework.framework/UnifiedAssetFramework`.
- `/workspace/recherche/apple-sec/ios272rc/_ipsw/dsc-24B115/dyld_shared_cache_arm64e.28` — SHA-256 `c8b612e814a4c26ede6b3edf16a337191c94dff64b0a342332f667b815c09a3b`. Localisation : rc: __TEXT,__oslogstring, cache offset 0x5499a90, 61639 octets, SHA256 section=ba0c1b10d6c6aca59b0d83193c669a4dc70976f3c43e49f34994f2eaeff55c13.
  Chemin source firmware : `/System/Library/PrivateFrameworks/UnifiedAssetFramework.framework/UnifiedAssetFramework`.
- [analysis/evidence/beta-dsc-comparison.json](../analysis/evidence/beta-dsc-comparison.json) — SHA-256 `d216782e99c3d448598c706633516542cf47ab53431475818bbff1559f3bb464`. Localisation : section_comparison : trois contrôles négatifs, six paires de SHA256 section identiques.
  Chemin source firmware : `Comparaison DSC ciblée`.

## Références publiques Apple consultées

- [PUB-01 — Apple Intelligence & Privacy](https://www.apple.com/legal/privacy/data/en/intelligence-engine/). Consultation : 2026-10-26.
- [PUB-02 — Private Cloud Compute: A new frontier for AI privacy in the cloud](https://security.apple.com/blog/private-cloud-compute/). Consultation : 2026-10-26.
- [PUB-03 — Improving the safety of generative model output](https://developer.apple.com/documentation/foundationmodels/improving-the-safety-of-generative-model-output?changes=_2). Consultation : 2026-10-26.
- [PUB-04 — Block or allow access to Siri and Apple Intelligence features](https://support.apple.com/en-ie/guide/child-safety/k4n88xwnliel/27/web/1.0). Consultation : 2026-10-26.
- [PUB-05 — Turn off and restrict access to Apple Intelligence features on iPhone](https://support.apple.com/en-ie/guide/iphone/iph3fed3f2c3/27/ios/27). Consultation : 2026-10-26.
- [PUB-06 — Improve Siri & Apple Intelligence & Privacy](https://www.apple.com/legal/privacy/data/en/improve-intelligence/). Consultation : 2026-10-26.
- [PUB-07 — Adding server-side intelligence with Private Cloud Compute](https://developer.apple.com/documentation/FoundationModels/adding-server-side-intelligence-with-private-cloud-compute/). Consultation : 2026-10-26.
- [PUB-08 — permissiveContentTransformations](https://developer.apple.com/documentation/foundationmodels/systemlanguagemodel/guardrails/permissivecontenttransformations). Consultation : 2026-10-26.
