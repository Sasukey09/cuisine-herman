# Cuisine Herman — App mobile (Flutter)

App mobile native consommant la même API FastAPI que le web. Cette base couvre
l'**authentification** (login/inscription, refresh de token, stockage sécurisé),
la **navigation** et trois écrans branchés sur l'API : **Tableau de bord**,
**Produits** et **Assistant IA**. Elle est structurée par *feature* pour ajouter
les autres écrans (factures, recettes, vidéo, indicateurs…) au même moule.

## Prérequis
- Flutter SDK ≥ 3.3 (`flutter --version`)
- Le backend qui tourne (Docker) et est joignable depuis l'appareil/émulateur.

## Générer les dossiers natifs
Ce dossier ne contient que `pubspec.yaml` + `lib/` (le code). Génère les dossiers
de plateforme (android/ios/web) sans toucher au code fourni :

```bash
cd mobile
flutter create --org com.cuisineherman --project-name cuisine_herman_mobile --platforms=android,ios,web .
flutter pub get
```
`flutter create` n'écrase pas les fichiers existants (`pubspec.yaml`, `lib/…`).

## URL de l'API selon la cible
`lib/core/config.dart` lit `API_BASE_URL` (dart-define), défaut `http://10.0.2.2:8000/api/v1`.

| Cible | URL à utiliser |
|---|---|
| Émulateur Android | `http://10.0.2.2:8000/api/v1` (défaut) |
| Simulateur iOS | `http://localhost:8000/api/v1` |
| Appareil physique | `http://<IP-LAN-de-ta-machine>:8000/api/v1` |

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.50:8000/api/v1
```

> Note : les apps natives ne sont pas soumises au CORS (réglage navigateur
> uniquement), donc rien à changer côté backend. Sur Android, le trafic HTTP en
> clair est autorisé en debug ; pour la prod, sers l'API en HTTPS.

## Lancer
```bash
flutter run            # choisis un appareil/émulateur
```

## Structure
```
lib/
  core/        config, stockage token, client API (Dio + refresh), providers Riverpod
  app/         router (garde d'auth) + shell à bottom-nav
  features/
    auth/      repository, controller (état), écran de connexion
    dashboard/ repository + écran (alertes marges, top produits)
    products/  repository + écran (liste)
    assistant/ repository + écran (chat IA)
```
