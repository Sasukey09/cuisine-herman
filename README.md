# Cuisine Herman

Gestion des coûts pour la restauration : on importe une facture, l'OCR en extrait les lignes,
les prix remontent dans les fiches techniques, et le coût matière de chaque recette se met à jour
tout seul.

**En ligne** — site : https://cuisine-herman-gsqb.vercel.app · API : https://cuisine-backend-t7pv.onrender.com

---

## Ce que ça fait

| Module | En un mot |
|---|---|
| **Factures & OCR** | PDF ou photo → lignes extraites → produits rapprochés → historique de prix |
| **Produits & fournisseurs** | Catalogue, dernier coût, variation, comparaison entre fournisseurs |
| **Recettes** | Fiches techniques, coût matière/portion, food cost %, marge |
| **Suivi des prix** | Hausses/baisses détectées, alertes, économies possibles en changeant de fournisseur |
| **Assistant IA** | Claude, branché sur les vraies données du restaurant ; conversations persistées |
| **Import vidéo / PDF** | Un lien YouTube ou une fiche PDF → recette chiffrée |
| **No-code** | Indicateurs personnalisés (formules), champs personnalisés, générateur de rapports |
| **RGPD** | Export complet, droit à l'effacement, registre d'audit |

## Les trois surfaces

| | Où | Stack |
|---|---|---|
| **API** | `backend/` | FastAPI · SQLAlchemy · Alembic · PostgreSQL · Celery/Redis |
| **Site** | `frontend/` | Next.js 15 · React 19 · TypeScript · Tailwind · shadcn · React Query |
| **Mobile** | `mobile/` | Flutter · Riverpod · Dio (mode hors connexion) |

Les trois parlent à **la même API** : les données sont partagées.

---

## Démarrer en local

```bash
cp .env.example .env
# SECRET_KEY est OBLIGATOIRE — le backend refuse de démarrer sans :
python -c "import secrets; print(secrets.token_urlsafe(48))"   # colle le résultat dans .env

docker compose up -d          # postgres + redis + minio + backend
cd frontend && npm install && npm run dev
```

- API : http://localhost:8000 · docs interactives : http://localhost:8000/docs
- Site : http://localhost:3000

**Mobile** — les dossiers natifs sont regénérés (ils ne sont pas versionnés) :

```bash
cd mobile
flutter create --org com.cuisineherman --project-name cuisine_herman_mobile --platforms=android,ios,web .
flutter pub get
flutter run          # pointe par défaut sur l'API de production
```

## Tests

```bash
cd backend  && pytest              # ~240 tests
cd frontend && npm run lint && npx tsc --noEmit
cd mobile   && flutter test && flutter analyze
```

**Tout code qui touche la base est testé contre une vraie base.** Les tests `*_real_db.py` sont
ignorés (`skip`) sans `DATABASE_URL` — un poste sans Postgres reste utilisable — et tournent en CI
contre un vrai Postgres. Ce n'est pas une préférence de style : trois bugs de production sont passés
à travers une suite verte parce que chaque test mockait la session, et un `Mock` n'a pas de clés
étrangères à violer. L'histoire est dans [`docs/tests.md`](docs/tests.md).

## Contribuer

**Ne pousse jamais directement sur `main`.** Render et Vercel déploient automatiquement depuis
`main` : un push direct part en production *avant* que la CI ait fini.

```
branche → push → CI verte (4 jobs) → merge dans main
```

La CI (`.github/workflows/ci.yml`) vérifie :

- **Backend** — Postgres réel (que les tests **utilisent** vraiment), migrations rejouées depuis
  zéro **avant** la suite, ~240 tests, **et le démarrage avec la commande exacte de production**
  (gunicorn). Cette dernière étape existe parce qu'un jour la CI était verte pendant que le
  conteneur de production était incapable de démarrer.
- **Web** — lint, types, build
- **Mobile** — analyze, tests, **APK release**, et une assertion que la permission `INTERNET`
  est bien dans le manifeste fusionné (sans elle, l'app n'a aucun réseau en release)
- **Dépendances** — `pip-audit`, **bloquant** : zéro vulnérabilité connue tolérée

## Documentation

| Fichier | Contenu |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Ce qui existe réellement, et ce qui n'existe pas |
| [`docs/tests.md`](docs/tests.md) | Pourquoi on teste contre une vraie base — et les trois bugs qui l'ont prouvé |
| [`docs/MIGRATION-FRANKFURT.md`](docs/MIGRATION-FRANKFURT.md) | Déplacer l'infra en Europe sans perdre les données |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Render + Vercel |
| [`MONITORING.md`](MONITORING.md) | Prometheus / Grafana |
| [`.env.example`](.env.example) | Toutes les variables, commentées |
