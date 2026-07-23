#!/bin/sh
# ---------------------------------------------------------------------------
# FoodGad — declenche un build Codemagic via l'API, depuis TON terminal.
#
# Ce script ne contient AUCUN secret. Il lit le token depuis TES variables
# d'environnement, jamais depuis un argument (pour ne pas finir dans
# l'historique shell) ni depuis ce depot.
#
# NE JAMAIS coller ton token dans un chat, un fichier commite, ou un log. Si un
# token a deja ete colle quelque part (chat, ticket, capture d'ecran), il doit
# etre revoque et regenere avant toute utilisation.
#
# Usage (dans TON terminal, jamais partage) :
#   export CODEMAGIC_TOKEN="ton_token"       # Codemagic -> User settings -> Integrations -> Codemagic API
#   sh scripts/codemagic/trigger_build.sh                 # ios-testflight sur main
#   sh scripts/codemagic/trigger_build.sh android-internal
#   sh scripts/codemagic/trigger_build.sh ios-testflight une-autre-branche
#
# Defauts : workflow=ios-testflight, branch=main.
#   -> `main` porte l'app complete ET la conformite export (ITSAppUses...=false),
#      donc le build TestFlight est directement testable, sans "Missing Compliance".
#
# CODEMAGIC_APP_ID a une valeur par defaut (l'app FoodGad). Ce n'est PAS un
# secret : c'est l'identifiant visible dans l'URL Codemagic. Le token reste le
# seul element sensible. Surcharge-le si tu vises une autre app.
# ---------------------------------------------------------------------------
set -eu

: "${CODEMAGIC_TOKEN:?CODEMAGIC_TOKEN requis (export CODEMAGIC_TOKEN=... dans ton terminal, jamais ici)}"

APP_ID="${CODEMAGIC_APP_ID:-6a53ba58f6d78b82b281fd26}"   # app FoodGad
WORKFLOW="${1:-ios-testflight}"
BRANCH="${2:-main}"

echo "[codemagic] declenchement: app=${APP_ID} workflow=${WORKFLOW} branch=${BRANCH}"

RESPONSE=$(
  curl -sS -X POST "https://api.codemagic.io/builds" \
    -H "Content-Type: application/json" \
    -H "x-auth-token: ${CODEMAGIC_TOKEN}" \
    -d "{\"appId\":\"${APP_ID}\",\"workflowId\":\"${WORKFLOW}\",\"branch\":\"${BRANCH}\"}"
)

# Extraction du buildId sans dependre de jq (portable POSIX).
BUILD_ID=$(printf '%s' "${RESPONSE}" | sed -n 's/.*"buildId"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

if [ -n "${BUILD_ID}" ]; then
  echo "[codemagic] build demarre : ${BUILD_ID}"
  echo "[codemagic] suivi : https://codemagic.io/app/${APP_ID}/build/${BUILD_ID}"
  if [ "${WORKFLOW}" = "ios-testflight" ]; then
    echo "[codemagic] a la fin, l'IPA part sur TestFlight (submit_to_testflight: true)."
  fi
else
  echo "[codemagic] ECHEC — reponse de l'API :" >&2
  printf '%s\n' "${RESPONSE}" >&2
  echo "[codemagic] Verifie CODEMAGIC_TOKEN, l'app id, le nom du workflow et la branche." >&2
  exit 1
fi
