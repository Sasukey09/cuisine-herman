# Sauvegarde & restauration — FoodGad (PostgreSQL)

> Bloquant B3 du rapport de recette. Objectif : aucune perte de données catastrophique
> possible, et une restauration **prouvée** (une sauvegarde jamais restaurée n'est pas
> une sauvegarde).

## Objectifs

| Indicateur | Cible |
|---|---|
| RPO (perte de données max) | ≤ 24 h (backup quotidien) ; ≤ 5 min avec PITR |
| RTO (temps de restauration) | ≤ 1 h |
| Rétention | 7 jours (Render, selon plan) + 30 j off-box |

## Deux couches de sauvegarde

### Couche 1 — Sauvegardes gérées par Render (PRIMAIRE)

Le plan Postgres **payant** (`plan: basic-1gb` dans [render.yaml](../render.yaml)) active :
- une **sauvegarde quotidienne** automatique,
- la **restauration point-in-time (PITR)** (jusqu'à la seconde, sur la fenêtre de rétention).

> ⚠️ Le plan `free` n'a **aucune** sauvegarde. Le passage en plan payant est la
> condition sine qua non de ce dispositif — c'est une action à réaliser dans le
> dashboard Render (ou en appliquant ce blueprint sur une base recréée).

**Restaurer via Render** : Dashboard → base `cuisine-db` → *Backups* / *Recovery* →
choisir un backup ou un instant PITR → *Restore* (crée une nouvelle instance).
Basculer ensuite `DATABASE_URL` des services vers l'instance restaurée.

### Couche 2 — Dump logique off-box (DÉFENSE EN PROFONDEUR)

Protège contre la perte du compte/région Render. Dump `pg_dump` compressé, poussé
vers un stockage S3-compatible (Cloudflare R2), indépendant de Render.

```sh
DATABASE_URL="$PROD_DATABASE_URL" \
S3_BUCKET=foodgad-backups \
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_ENDPOINT_URL=https://<compte>.r2.cloudflarestorage.com \
sh scripts/backup/pg_backup.sh
```

Planification (au choix) :
- **Render Cron Job** : nouveau service `type: cronjob`, image = backend (ajouter
  `postgresql-client` à l'image), commande = `sh scripts/backup/pg_backup.sh`,
  schedule `0 2 * * *` (02:00 UTC).
- **Cron externe** (VM/CI) exécutant le même script avec le `DATABASE_URL` de prod.

## Restauration

```sh
TARGET_DATABASE_URL="postgres://.../base_cible" \
sh scripts/backup/pg_restore.sh foodgad-20260714T020000Z.sql.gz
```

Le schéma initial exige l'extension `vector` (pgvector) : le script la crée si besoin.
Après restauration, appliquer les migrations manquantes : `alembic upgrade head`.

## Drill de restauration (le TEST exigé)

`verify_restore.sh` restaure un dump dans une base **jetable** et vérifie que les
tables métier clés reviennent non vides, puis supprime la base de drill.

```sh
ADMIN_DATABASE_URL="postgres://user@host:5432/postgres" \
sh scripts/backup/verify_restore.sh foodgad-20260714T020000Z.sql.gz
```

Sortie attendue :
```
[drill] verification d'integrite (tables cles non vides)
  organizations: 3
  users: 5
  ...
[drill] RESULTAT: SUCCES — la sauvegarde est restaurable.
```

**Cadence du drill** : à chaque déploiement majeur, et au minimum **mensuel**.
Consigner la date et le résultat dans le journal d'exploitation.

## Vérifications de mise en production (checklist)

- [ ] Base Postgres sur plan payant (backups activés) — *action Render, hors code*
- [ ] Bucket `foodgad-backups` créé (R2/S3), credentials en variables d'env
- [ ] Cron de dump off-box planifié (quotidien)
- [ ] Drill de restauration exécuté avec succès (`verify_restore.sh`) — date consignée
- [ ] `DATABASE_URL` de bascule documenté pour l'astreinte

> Note d'audit : la configuration, les scripts et la procédure sont livrés dans le
> dépôt. Le **provisioning du plan payant**, la création du bucket et l'**exécution
> réelle du premier drill** sont des actions d'exploitation à réaliser dans
> l'infrastructure — elles ne peuvent pas être effectuées depuis le code.
