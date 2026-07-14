# Migrer FoodGad en Europe (Francfort)

**Dashboard : https://dashboard.render.com**

## Pourquoi

Les services tournent en **Oregon** (`gcp-us-west1-1.origin.onrender.com`, vérifié par DNS)
alors que tous les restaurants sont en France. Mesuré : `/health` — un endpoint qui ne fait
**rien** — met **266 ms**. C'est du réseau pur, sur **chaque** requête de **chaque** écran.

Francfort supprime ~200 ms partout. C'est le plus gros gain de performance perçue disponible,
et il ne coûte rien.

## ⚠️ Le piège qui fait tout perdre

**Render ne peut pas déplacer un service existant.** Il faut en créer de nouveaux — donc une
**nouvelle base Postgres, VIDE**.

> **Si tu recrées les services sans migrer les données d'abord, tu perds tout** : produits,
> factures, recettes, historique de prix, conversations de l'assistant.

L'étape 1 n'est pas optionnelle.

---

## Étape 1 — Sauvegarder la base actuelle (À FAIRE EN PREMIER)

1. Dashboard → `cuisine-db` → **Connect** → copie l'**External Database URL**
   (elle ressemble à `postgres://user:pass@dpg-xxxxx.oregon-postgres.render.com/cuisine`).

2. Sur ta machine (il faut `pg_dump`, fourni avec PostgreSQL) :

```bash
pg_dump "<EXTERNAL_DATABASE_URL_ACTUELLE>" -Fc -f cuisine-backup.dump
```

3. **Vérifie que le fichier n'est pas vide** avant d'aller plus loin :

```bash
ls -lh cuisine-backup.dump          # doit peser plus que quelques ko
pg_restore --list cuisine-backup.dump | head   # doit lister des tables
```

Ne passe à l'étape 2 que si ces deux commandes te rassurent.

---

## Étape 2 — Créer les nouveaux services à Francfort

`render.yaml` déclare déjà `region: frankfurt`. Mais **ne réutilise pas les mêmes noms** : les
anciens services existent encore, et tu veux pouvoir revenir en arrière si ça se passe mal.

Dans le dashboard : **New → Blueprint** → choisis le dépôt → Render lit `render.yaml`.
Renomme les services au moment de la création :

| Ancien | Nouveau |
|---|---|
| `cuisine-db` | `cuisine-db-eu` |
| `cuisine-redis` | `cuisine-redis-eu` |
| `cuisine-backend` | `cuisine-backend-eu` |

**Instance type du backend : `Starter` (7 $/mois), PAS `Free`.**
Le plan gratuit s'endort au bout de 15 min : ton premier appel du matin met **37 secondes**
(mesuré aujourd'hui). Aucun restaurateur n'attendra ça.

---

## Étape 3 — Restaurer les données dans la nouvelle base

1. `cuisine-db-eu` → **Connect** → copie sa **External Database URL**.
2. Restaure :

```bash
pg_restore --no-owner --no-acl -d "<NOUVELLE_EXTERNAL_DATABASE_URL>" cuisine-backup.dump
```

3. Vérifie que les données sont bien là :

```bash
psql "<NOUVELLE_EXTERNAL_DATABASE_URL>" -c "SELECT count(*) FROM products;"
psql "<NOUVELLE_EXTERNAL_DATABASE_URL>" -c "SELECT count(*) FROM invoices;"
psql "<NOUVELLE_EXTERNAL_DATABASE_URL>" -c "SELECT version_num FROM alembic_version;"
```

Le `version_num` doit être la dernière migration (`0011_ai_conversations` aujourd'hui).
S'il est là, l'app ne rejouera pas les migrations sur des données existantes.

---

## Étape 4 — Les variables d'environnement du nouveau backend

`cuisine-backend-eu` → **Environment**. Certaines sont générées par le blueprint, les autres
sont **à recopier depuis l'ancien service** (elles n'y sont pas automatiquement) :

| Variable | Valeur |
|---|---|
| `SECRET_KEY` | **générée par Render** — ne la copie PAS de l'ancien (autant en profiter pour la tourner) |
| `MISTRAL_API_KEY` | recopier depuis l'ancien service |
| `ANTHROPIC_API_KEY` | recopier depuis l'ancien service |
| `OPENAI_API_KEY` | recopier (si l'import vidéo hors YouTube est utilisé) |
| **`CORS_ORIGINS`** | **`https://cuisine-herman-gsqb.vercel.app`** — surtout PAS `*` (voir plus bas) |
| `OCR_ALLOW_STUB_FALLBACK` | `false` |

> ⚠️ **Changer `SECRET_KEY` déconnecte tout le monde** (les jetons existants deviennent
> invalides). C'est sans conséquence : il suffit de se reconnecter. Et c'est l'occasion de
> tourner une clé qui a beaucoup circulé.

### Le bug CORS actuel
L'ancien backend a `CORS_ORIGINS=*` — vérifié : il renvoie
`access-control-allow-origin: https://evil.test` à n'importe qui. **N'importe quel site peut
appeler ton API.** Ne reproduis pas ça sur le nouveau.

---

## Étape 5 — Faire pointer les clients vers le nouveau backend

Trois endroits, et il faut les trois :

1. **Vercel** (le site) → Settings → Environment Variables →
   `NEXT_PUBLIC_API_URL` = `https://cuisine-backend-eu.onrender.com/api/v1`
   → puis **Redeploy** (la variable est lue au build, pas à l'exécution).

2. **L'app mobile** → `mobile/lib/core/config.dart`, valeur par défaut de `apiBaseUrl`.
   Il faut **reconstruire l'APK** : l'URL est compilée dedans.

3. **Le compte démo** : `demo@herman.fr` existe dans la base restaurée, il fonctionnera.
   Profite-en pour tourner son mot de passe (l'écran Administration le permet maintenant).

---

## Étape 6 — Vérifier AVANT de supprimer l'ancien

```bash
NEW="https://cuisine-backend-eu.onrender.com"

# 1. le service démarre et voit ses dépendances
curl -s "$NEW/ready"          # postgres up, redis up, ocr configured

# 2. la latence a bien chuté (l'endpoint ne fait rien : c'est du réseau pur)
curl -s -o /dev/null -w "%{time_total}s\n" "$NEW/health"    # ~0.05s attendu, contre 0.266s

# 3. les données sont là
TOKEN=$(curl -s -X POST "$NEW/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=demo@herman.fr" --data-urlencode "password=<le mot de passe>" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
curl -s -H "Authorization: Bearer $TOKEN" "$NEW/api/v1/products/enriched?limit=5"
curl -s -H "Authorization: Bearer $TOKEN" "$NEW/api/v1/invoices/"

# 4. CORS n'est plus grand ouvert (aucun en-tête ne doit revenir)
curl -s -D- -o /dev/null -X OPTIONS "$NEW/api/v1/auth/token" \
  -H "Origin: https://evil.test" -H "Access-Control-Request-Method: POST" \
  | grep -i access-control-allow-origin
```

**Ne supprime les anciens services que quand les 4 vérifications passent.** Tant qu'ils
existent, le retour en arrière coûte un `NEXT_PUBLIC_API_URL` sur Vercel.

---

## Après la bascule

- Mettre à jour `mobile/lib/core/config.dart` et `mobile/README.md` (nouvelle URL).
- Mettre à jour `docs/` et `deployment` (l'ancienne URL traîne dans plusieurs fichiers).
- Vérifier que les **sauvegardes automatiques** sont activées sur `cuisine-db-eu`
  (elles ne le sont pas par défaut sur tous les plans) — et **tester une restauration une
  fois**. Une sauvegarde jamais restaurée n'est pas une sauvegarde.
