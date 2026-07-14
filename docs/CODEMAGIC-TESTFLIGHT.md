# Publier FoodGad sur TestFlight avec Codemagic

> Le workflow est dans [`codemagic.yaml`](../codemagic.yaml) (racine du dépôt).
> **Aucun secret n'est dans le dépôt** : tout ce qui est sensible (clé App Store
> Connect) se configure dans l'interface Codemagic, et n'est jamais partagé ici.

## Ce que tu configures dans Codemagic (une fois)

1. **Connecter le dépôt** : Codemagic → *Add application* → ton repo Git → sélectionner
   *codemagic.yaml* comme configuration.
2. **Ajouter la clé App Store Connect API** : Codemagic → *Teams → Integrations →
   App Store Connect* → coller **Issuer ID**, **Key ID** et le fichier **`.p8`**.
   Donne-lui un **nom** (étiquette).
3. **Aligner le nom** : reporter ce nom dans `codemagic.yaml` →
   `integrations.app_store_connect: <ce nom>` (par défaut `FoodGad ASC`).

## La seule valeur à vérifier dans le YAML

`environment.ios_signing.bundle_identifier` **doit être exactement** le Bundle ID
de ton app dans App Store Connect. La valeur par défaut est celle dérivée du projet
Flutter : `com.foodgad.foodgadMobile`. Si ton enregistrement Apple diffère, remplace
cette ligne (rien d'autre).

## Prérequis côté Apple (déjà en place chez toi)

- Compte **Apple Developer Program** actif.
- Une **app enregistrée** dans App Store Connect avec ce Bundle ID.
- La **signature** est gérée automatiquement par Codemagic à partir de la clé App
  Store Connect (`distribution_type: app_store` + `xcode-project use-profiles`) —
  rien à téléverser manuellement.

## Lancer une bêta

- Depuis l'interface Codemagic : *Start new build* → workflow **FoodGad iOS —
  TestFlight**.
- Ou via l'**API Codemagic** (le token reste chez toi) : `POST /builds` avec l'ID
  d'app et `workflow_id: ios-testflight`.

Chaque build incrémente automatiquement le numéro (`PROJECT_BUILD_NUMBER`), puis
l'IPA est envoyé à **TestFlight**. Les testeurs reçoivent la mise à jour via
l'app **TestFlight** sur leur iPhone.

## Notes propres à FoodGad

- Le dossier `mobile/ios` est **gitignoré et régénéré** par le workflow
  (`flutter create --platforms=ios`), comme `android/` l'est en CI GitHub. Ne le
  commite pas.
- Le backend de prod visé par l'app mobile est défini par `API_BASE_URL`
  ([mobile/lib/core/config.dart](../mobile/lib/core/config.dart)). Pour pointer la
  bêta ailleurs, ajoute `--dart-define=API_BASE_URL=...` à l'étape *Build IPA*.
- Android : je peux ajouter un second workflow `android-internal` (Google Play test
  interne) sur le même modèle si tu veux — demande-le.

## Ce que je ne fais pas

- Je ne déclenche pas le build ni la publication depuis mon environnement.
- Je ne prends pas ton **API token Codemagic** ni ta **clé App Store Connect** :
  ils restent chez toi / dans Codemagic. Me les coller les exposerait.
