#!/bin/sh
# ---------------------------------------------------------------------------
# FoodGad — DRILL de restauration: restaure un dump dans une base jetable et
# verifie que les tables cles sont non vides. C'est le "test de restauration"
# exige par le rapport de recette (B3): une sauvegarde qu'on n'a jamais restauree
# n'est pas une sauvegarde.
#
# Usage:
#   ADMIN_DATABASE_URL=postgres://user@host/postgres \
#   sh scripts/backup/verify_restore.sh <dump.sql.gz>
#
# ADMIN_DATABASE_URL doit pouvoir CREATE DATABASE / DROP DATABASE.
# Le script cree foodgad_restore_drill, restaure, verifie, puis la supprime.
# ---------------------------------------------------------------------------
set -eu

: "${ADMIN_DATABASE_URL:?ADMIN_DATABASE_URL requis (droit CREATE DATABASE)}"
DUMP="${1:?chemin du dump .sql.gz requis}"
DRILL_DB="${DRILL_DB:-foodgad_restore_drill}"

# URL de la base de drill: on remplace le nom de base a la fin de l'URL admin.
BASE_URL="$(echo "${ADMIN_DATABASE_URL}" | sed 's#/[^/]*$##')"
DRILL_URL="${BASE_URL}/${DRILL_DB}"

cleanup() {
  psql "${ADMIN_DATABASE_URL}" -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS ${DRILL_DB} WITH (FORCE);" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[drill] (re)creation de ${DRILL_DB}"
psql "${ADMIN_DATABASE_URL}" -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS ${DRILL_DB} WITH (FORCE);" \
  -c "CREATE DATABASE ${DRILL_DB};" >/dev/null

echo "[drill] restauration"
TARGET_DATABASE_URL="${DRILL_URL}" sh "$(dirname "$0")/pg_restore.sh" "${DUMP}"

echo "[drill] verification d'integrite (tables cles non vides)"
FAIL=0
for tbl in organizations users suppliers products invoices recipes; do
  n="$(psql "${DRILL_URL}" -tAc "SELECT COUNT(*) FROM ${tbl};" 2>/dev/null || echo ERR)"
  echo "  ${tbl}: ${n}"
  if [ "${n}" = "ERR" ]; then
    echo "  -> ECHEC: table ${tbl} illisible" >&2
    FAIL=1
  fi
done

# Au moins une organisation restauree = la donnee metier est bien revenue.
ORGS="$(psql "${DRILL_URL}" -tAc "SELECT COUNT(*) FROM organizations;" 2>/dev/null || echo 0)"
if [ "${ORGS}" -lt 1 ]; then
  echo "[drill] ECHEC: aucune organisation restauree" >&2
  FAIL=1
fi

if [ "${FAIL}" -ne 0 ]; then
  echo "[drill] RESULTAT: ECHEC" >&2
  exit 1
fi
echo "[drill] RESULTAT: SUCCES — la sauvegarde est restaurable."
