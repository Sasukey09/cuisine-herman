# Déploiement — FoodGad

Objectif : mettre le backend (API) et le frontend en ligne avec une **URL publique HTTPS**,
prérequis indispensable pour une app mobile.

```
Mobile / Web  ──HTTPS──▶  Frontend (Vercel)  ──HTTPS──▶  Backend API (Render)
                                                            ├─ Postgres (Render)
                                                            ├─ Redis (Render)
                                                            └─ Stockage S3 (Cloudflare R2)
```

Chemin recommandé (le plus simple, ~gratuit pour tester) : **Render** (backend+DB+Redis)
+ **Vercel** (frontend). Une option auto-hébergée (VPS/Docker) est décrite à la fin.

---

## 0. Prérequis
- Un compte **GitHub** (le code doit y être poussé).
- Un compte **Render.com** et **Vercel.com** (gratuits).
- (Optionnel) Un compte **Cloudflare** pour le stockage des fichiers (R2).
- (Optionnel) Une clé **Mistral** pour l'OCR réel.

## 1. Pousser le code sur GitHub
Le projet n'est pas encore un dépôt git. Dans le dossier du projet :
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<toi>/foodgad.git
git push -u origin main
```
> ⚠️ Vérifie que `.env` et `.env.production` ne sont **pas** poussés (ils sont dans `.gitignore`).
> Ne commit jamais de secrets.

## 2. Backend + base + Redis sur Render (Blueprint)
1. Render → **New** → **Blueprint** → sélectionne ton repo.
2. Render détecte [`render.yaml`](render.yaml) et propose de créer : la base Postgres,
   Redis, le service **backend** et le **worker**. Clique **Apply**.
3. Renseigne les variables marquées `sync: false` :
   - `CORS_ORIGINS` → l'URL de ton frontend (tu l'auras à l'étape 4 ; mets une valeur
     provisoire puis reviens la corriger).
   - (Stockage) `S3_ENDPOINT`, `S3_PUBLIC_ENDPOINT`, `S3_BUCKET`, `MINIO_ACCESS_KEY`,
     `MINIO_SECRET_KEY` → voir étape 3.
   - (IA & vidéo) `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` → voir étape 7.
   - (OCR réel) `MISTRAL_API_KEY` → voir étape 7.
4. Au démarrage, le conteneur exécute **automatiquement les migrations** (`alembic upgrade head`,
   crée les tables + seed des unités). Vérifie les logs : « Running database migrations ».
5. Note l'URL du backend, ex. `https://cuisine-backend.onrender.com`.

**Test rapide :**
```
https://cuisine-backend.onrender.com/health   ->  {"status":"ok"}
https://cuisine-backend.onrender.com/ready    ->  état des dépendances
```

## 3. Stockage des fichiers (Cloudflare R2 — recommandé)
MinIO est pour le local ; en prod, utilise un S3 managé (R2 a une offre gratuite).
1. Cloudflare → **R2** → crée un bucket `cuisine-prod`.
2. Crée un **API Token** R2 (Access Key + Secret).
3. Dans Render (service backend), renseigne :
   - `S3_ENDPOINT` = `https://<account_id>.r2.cloudflarestorage.com`
   - `S3_PUBLIC_ENDPOINT` = domaine public du bucket (ou même valeur si non public)
   - `S3_BUCKET` = `cuisine-prod`
   - `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` = tes clés R2
> Sans ça, l'upload de factures fonctionne mais le fichier n'est pas conservé (dégradation propre).

## 4. Frontend sur Vercel
1. Vercel → **Add New** → **Project** → importe ton repo.
2. **Root Directory** : `frontend`.
3. **Environment Variables** :
   - `NEXT_PUBLIC_API_URL` = `https://cuisine-backend.onrender.com/api/v1`
4. **Deploy**. Note l'URL, ex. `https://foodgad.vercel.app`.

## 5. Relier les deux (CORS)
Retourne dans Render (backend) → variable `CORS_ORIGINS` = l'URL Vercel **exacte**
(sans slash final), ex. `https://foodgad.vercel.app`. Render redéploie.

## 6. Vérifications finales
1. Ouvre l'URL Vercel → page de connexion.
2. **Crée une organisation** (register) → tu es connecté en admin.
3. Crée un produit, importe une facture, calcule un coût de recette.
4. Si erreur réseau/CORS : vérifie `CORS_ORIGINS` (backend) et `NEXT_PUBLIC_API_URL` (front).

## 7. Clés API (IA, vidéo, OCR)
Renseigne ces variables sur le service **backend** Render (toutes en `sync: false`) :

| Variable | Sert à | Obligatoire ? |
|---|---|---|
| `ANTHROPIC_API_KEY` | Assistant IA (`/ai/chat`) **et** extraction de recette depuis une vidéo | Oui pour l'IA + la vidéo |
| `OPENAI_API_KEY` | Transcription Whisper des vidéos **sans sous-titres** (TikTok/Insta/FB) | Oui pour ces plateformes (YouTube avec sous-titres fonctionne sans) |
| `MISTRAL_API_KEY` | OCR réel des factures | Optionnel (sinon mode démo) |

**OCR réel :** mets `MISTRAL_API_KEY` puis passe `OCR_ALLOW_STUB_FALLBACK=false` et redéploie — l'app lira alors les vrais PDF/images (sinon elle renvoie des données d'exemple).

> Ces clés sont déjà déclarées dans [`render.yaml`](render.yaml) ; il suffit de coller les valeurs dans le dashboard Render. Ne les commit jamais.

---

## Option B — Auto-hébergement (VPS + Docker)
Sur un serveur (Hetzner, OVH, DigitalOcean…) avec Docker :
```bash
cp .env.production.example .env.production   # remplis les valeurs
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```
Puis place un reverse proxy HTTPS devant (Caddy = le plus simple, certificat auto) :
```
api.tondomaine.fr   -> backend:8000
app.tondomaine.fr   -> frontend:3000
```

---

## ✅ Checklist sécurité avant mise en ligne
- [ ] `SECRET_KEY` fort (généré, pas la valeur par défaut)
- [ ] `CORS_ORIGINS` limité à ton domaine frontend
- [ ] `OCR_ALLOW_STUB_FALLBACK=false` si OCR réel configuré
- [ ] `.env` / secrets **non commités**
- [ ] HTTPS partout (Render/Vercel le font ; en VPS, via Caddy)
- [ ] Sauvegardes Postgres activées (Render le propose)

> Limites connues à traiter ensuite (cf. audit) : ingestion OCR encore **synchrone**
> (à passer en tâche Celery), pas de **rate-limiting** sur l'auth, pas de **CI**.

---

## 📱 Et après : l'app mobile
Une fois le backend en HTTPS public et le front en ligne :
1. **PWA** : rends le front installable (plugin `next-pwa`) → « Ajouter à l'écran d'accueil ».
2. **Capacitor** : emballe le front React → stores Apple/Google + appareil photo
   (photographier une facture → OCR).
