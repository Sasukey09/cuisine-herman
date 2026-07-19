#!/bin/sh
# ---------------------------------------------------------------------------
# FoodGad — restauration d'un dump logique dans une base cible.
#
# Usage:
#   TARGET_DATABASE_URL=postgres://... sh scripts/backup/pg_restore.sh <dump.sql.gz>
#
# ATTENTION: restaure DANS la base pointee par TARGET_DATABASE_URL. Ne jamais
# pointer sur la base de production sans etre certain de l'intention. Pour un
# drill, cibler une base jetable (voir verify_restore.sh).
# ---------------------------------------------------------------------------
set -eu

: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL requis}"
DUMP="${1:?chemin du dump .sql.gz requis}"

[ -f "${DUMP}" ] || { echo "[restore] dump introuvable: ${DUMP}" >&2; exit 1; }

echo "[restore] schema vector (extension requise par le schema initial)"
psql "${TARGET_DATABASE_URL}" -v ON_ERROR_STOP=1 \
  -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null 2>&1 || true

echo "[restore] ${DUMP} -> TARGET_DATABASE_URL"
gunzip -c "${DUMP}" | psql "${TARGET_DATABASE_URL}" -v ON_ERROR_STOP=1

echo "[restore] OK"
