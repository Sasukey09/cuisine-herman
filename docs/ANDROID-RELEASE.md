# Release Android signée & publiable — FoodGad

> Bloquant B4 du rapport de recette. Avant : le build de release était signé avec
> la **clé de debug** → non publiable sur le Play Store. Désormais : signature de
> release réelle via `key.properties`, avec repli debug uniquement quand le
> keystore est absent (CI / clone frais).

## Ce qui a changé (dans le dépôt)

- [`mobile/android/app/build.gradle.kts`](../mobile/android/app/build.gradle.kts) :
  un `signingConfigs.release` lit `android/key.properties` ; le `buildType release`
  l'utilise si présent, sinon retombe sur debug (le build ne casse jamais).
- [`mobile/.gitignore`](../mobile/.gitignore) : `**/key.properties`, `*.jks`,
  `*.keystore` exclus — un keystore ne peut pas être commité par accident.
- [`scripts/android/generate_upload_keystore.sh`](../scripts/android/generate_upload_keystore.sh) :
  génère l'upload key + `key.properties`.

## Générer la clé (une fois, sur la machine de release)

```sh
sh scripts/android/generate_upload_keystore.sh
```

Ou manuellement :

```sh
keytool -genkeypair -v -keystore mobile/android/upload-keystore.jks \
  -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

Puis créer `mobile/android/key.properties` :

```properties
storePassword=<mot de passe du keystore>
keyPassword=<mot de passe de la clé>
keyAlias=upload
storeFile=upload-keystore.jks
```

> `storeFile` est relatif au dossier `mobile/android/`.

## Construire l'artefact publiable

```sh
cd mobile
flutter build appbundle --release   # .aab pour le Play Store (recommandé)
flutter build apk --release         # .apk (distribution directe)
```

Vérifier la signature :

```sh
jarsigner -verify -verbose -certs build/app/outputs/bundle/release/app-release.aab
# ou pour un APK :
$ANDROID_SDK/build-tools/<ver>/apksigner verify --print-certs \
  build/app/outputs/flutter-apk/app-release.apk
```

La sortie doit montrer le certificat **upload** (et non « Android Debug »).

## Sécurité & continuité

- **Ne jamais committer** `upload-keystore.jks` ni `key.properties` (gitignorés).
- **Sauvegarder le keystore hors-ligne** (coffre / secret manager). Le perdre =
  ne plus pouvoir publier de mise à jour, sauf réinitialisation via **Google Play
  App Signing** (activer cette option est fortement recommandé : Google détient
  alors la clé de signature d'app, l'upload key ne sert qu'à téléverser).
- En CI de release : injecter le keystore et `key.properties` depuis des secrets,
  jamais depuis le dépôt.

## Résidu opérationnel (hors code)

La **génération et la garde du keystore de production** ne peuvent pas être faites
depuis le dépôt (une vraie clé secrète, détenue par l'éditeur). La configuration
est prête ; il reste à exécuter le script sur la machine de release et à archiver
le keystore. Après quoi l'application est **publiable**.
