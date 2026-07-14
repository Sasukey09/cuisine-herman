#!/bin/sh
# ---------------------------------------------------------------------------
# FoodGad — sauvegarde logique off-box de PostgreSQL (seconde couche).
#
# La couche PRIMAIRE est la sauvegarde geree par Render (plan payant: backup
# quotidien + PITR). Ce script est la defense en profondeur: un dump logique
# compresse, chiffre optionnellement, pousse hors du fournisseur (S3/R2), pour
# survivre a une perte de compte ou de region.
#
# Usage:
#   DATABASE_URL=postgres://... S3_BUCKET=foodgad-backups \
#   AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_ENDPOINT_URL=https://<r2> \
#   sh scripts/backup/pg_backup.sh
#
# Dependances: pg_dump (postgresql-client), gzip, aws-cli (ou rclone).
# ---------------------------------------------------------------------------
set -eu

: "${DATABASE_URL:?DATABASE_URL requis}"
: "${S3_BUCKET:?S3_BUCKET requis}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"        # UTC, triable
PREFIX="${BACKUP_PREFIX:-foodgad}"
FILE="${PREFIX}-${STAMP}.sql.gz"
TMP="$(mktemp -d)"
OUT="${TMP}/${FILE}"

echo "[backup] pg_dump -> ${OUT}"
# --no-owner/--no-acl: un dump restaurable sur un role different (le compte de restore).
pg_dump --no-owner --no-acl --format=plain "${DATABASE_URL}" | gzip -9 > "${OUT}"

SIZE="$(wc -c < "${OUT}")"
if [ "${SIZE}" -lt 1000 ]; then
  echo "[backup] ERREUR: dump anormalement petit (${SIZE} octets) — abandon" >&2
  exit 1
fi

DEST="s3://${S3_BUCKET}/${PREFIX}/${FILE}"
echo "[backup] upload -> ${DEST} (${SIZE} octets)"
if [ -n "${AWS_ENDPOINT_URL:-}" ]; then
  aws --endpoint-url "${AWS_ENDPOINT_URL}" s3 cp "${OUT}" "${DEST}"
else
  aws s3 cp "${OUT}" "${DEST}"
fi

echo "[backup] OK ${FILE}"
rm -rf "${TMP}"
