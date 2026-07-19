#!/bin/sh
# ---------------------------------------------------------------------------
# FoodGad — liste tes apps Codemagic pour retrouver CODEMAGIC_APP_ID.
# A executer dans TON terminal. Voir trigger_build.sh pour les regles de secret.
#
# Usage:
#   export CODEMAGIC_TOKEN="ton_token"
#   sh scripts/codemagic/list_apps.sh
# ---------------------------------------------------------------------------
set -eu

: "${CODEMAGIC_TOKEN:?CODEMAGIC_TOKEN requis}"

curl -sS "https://api.codemagic.io/apps" \
  -H "x-auth-token: ${CODEMAGIC_TOKEN}" \
  | grep -oE '"_id":"[^"]+"|"appName":"[^"]+"'
