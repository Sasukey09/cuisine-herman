# Rotation des clés API — FoodGad

> Important I5 du rapport de recette. L'audit a relevé que des clés de production
> (`sk-ant-…`, `sk-proj-…`, clé Mistral, clés S3/MinIO) étaient **lisibles en clair**
> dans le fichier local `.env`. Un secret qui a été exposé sur un poste doit être
> considéré comme compromis et **remplacé**.

## État vérifié (dépôt)

- `.env` **n'est pas** suivi par git (confirmé) — voir `.gitignore`.
- **Aucune** clé n'apparaît dans l'arbre suivi ni dans l'historique git (vérifié
  avec `scripts/security/scan_secrets.sh`).

Il n'y a donc **rien à purger du dépôt**. La rotation est une action d'exploitation :
générer de nouvelles clés chez chaque fournisseur, puis mettre à jour les secrets
côté Render/Vercel et le `.env` local. **Cela ne peut pas être fait depuis le code.**

## Clés à faire tourner

| Secret | Où le régénérer | Où le mettre à jour |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys → révoquer + créer | Render (web + worker, `sync:false`) |
| `OPENAI_API_KEY` | platform.openai.com → API keys → révoquer + créer | Render (web) |
| `MISTRAL_API_KEY` | console.mistral.ai → API Keys | Render (web) |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` (R2/S3) | Cloudflare R2 / fournisseur S3 → nouveau token | Render (web) |
| `SECRET_KEY` (JWT) | généré par Render en prod (`generateValue`) ; en local : `openssl rand -hex 32` | Render (auto) + `.env` local |
| `GRAFANA_USER` / `GRAFANA_PASSWORD` | changer dans la config Grafana | monitoring local |
| `POSTGRES_PASSWORD` | via le fournisseur de base | `DATABASE_URL` (injecté par Render) |

> Faire tourner `SECRET_KEY` **déconnecte tous les utilisateurs** (les JWT signés
> avec l'ancienne clé deviennent invalides) — le faire à une heure creuse.

## Procédure

1. Générer la nouvelle clé chez le fournisseur (garder l'ancienne active le temps
   du basculement quand c'est possible).
2. Mettre à jour la variable dans **Render** (Dashboard → service → Environment)
   et **Vercel** si concernée, puis redéployer.
3. Mettre à jour le `.env` **local** (jamais commité).
4. **Révoquer** l'ancienne clé chez le fournisseur.
5. Vérifier le bon fonctionnement (`/ai/chat`, ingestion OCR, upload S3).

## Prévention (déjà en place / recommandé)

- `scripts/security/scan_secrets.sh` : détecte toute clé dans l'arbre ou
  l'historique — à brancher en **pre-commit** et/ou en **CI** (échoue le build si
  un secret est trouvé).
- Ne jamais `git add -f` un `.env` ou un keystore.
- Préférer les secrets gérés (Render `sync:false`, `generateValue`) au stockage
  sur disque.

## Résidu opérationnel (hors code)

La génération effective des nouvelles clés et leur mise à jour dans Render/Vercel
sont à réaliser par l'exploitant. Le dépôt fournit la vérification (aucun secret
commité) et l'outillage de prévention.
