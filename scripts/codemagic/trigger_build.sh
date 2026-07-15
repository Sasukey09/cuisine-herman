#!/bin/sh
# ---------------------------------------------------------------------------
# FoodGad — declenche un build Codemagic via l'API, depuis TON terminal.
#
# Ce script ne contient AUCUN secret. Il lit le token et l'app id depuis TES
# variables d'environnement, jamais depuis un argument (pour ne pas finir dans
# l'historique shell) ni depuis ce depot.
#
# NE JAMAIS coller ton token dans un chat, un fichier commite, ou un log. Si un
# token a deja ete colle quelque part (chat, ticket, capture d'ecran), il doit
# etre revoque et regenere avant toute utilisation.
#
# Usage (dans TON terminal, jamais partage) :
#   export CODEMAGIC_TOKEN="ton_token"
#   export CODEMAGIC_APP_ID="l'id de l'app dans Codemagic"
#   sh scripts/codemagic/trigger_build.sh [workflow] [branch]
#
# Defauts : workflow=ios-testflight, branch=chore/rebrand-and-go-blockers
#
# Trouver CODEMAGIC_APP_ID : ouvre l'app dans Codemagic, l'id est dans l'URL
# (https://codemagic.io/app/<APP_ID>), ou via GET /apps (voir list_apps.sh).
# ---------------------------------------------------------------------------
set -eu

: "${CODEMAGIC_TOKEN:?CODEMAGIC_TOKEN requis (export CODEMAGIC_TOKEN=... dans ton terminal, jamais ici)}"
: "${CODEMAGIC_APP_ID:?CODEMAGIC_APP_ID requis (id de l'app, visible dans l'URL Codemagic)}"

WORKFLOW="${1:-ios-testflight}"
BRANCH="${2:-chore/rebrand-and-go-blockers}"

echo "[codemagic] declenchement: app=${CODEMAGIC_APP_ID} workflow=${WORKFLOW} branch=${BRANCH}"

curl -sS -X POST "https://api.codemagic.io/builds" \
  -H "Content-Type: application/json" \
  -H "x-auth-token: ${CODEMAGIC_TOKEN}" \
  -d "{\"appId\":\"${CODEMAGIC_APP_ID}\",\"workflowId\":\"${WORKFLOW}\",\"branch\":\"${BRANCH}\"}"

echo
echo "[codemagic] Si la reponse contient un champ \"buildId\", le build a demarre."
echo "[codemagic] Suis-le sur https://codemagic.io/app/${CODEMAGIC_APP_ID}"
