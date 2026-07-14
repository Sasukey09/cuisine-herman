#!/bin/sh
# ---------------------------------------------------------------------------
# FoodGad — detecteur de secrets commites (arbre suivi + historique git).
# Sort en erreur (code 1) si une cle plausible est trouvee. A brancher en
# pre-commit ou en CI pour empecher qu'une cle n'entre jamais dans le depot.
#
# Usage: sh scripts/security/scan_secrets.sh
# ---------------------------------------------------------------------------
set -eu

# Patterns de cles courantes (Anthropic, OpenAI, AWS, cles privees, JWT secret).
PATTERNS='sk-ant-[A-Za-z0-9_-]{16}|sk-proj-[A-Za-z0-9_-]{16}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----'

FAIL=0

echo "[scan] arbre suivi..."
if git grep -nIE "${PATTERNS}" -- . ':(exclude)*.example' >/dev/null 2>&1; then
  echo "  SECRET TROUVE dans l'arbre suivi:" >&2
  git grep -nIE "${PATTERNS}" -- . ':(exclude)*.example' >&2 || true
  FAIL=1
else
  echo "  OK — aucun secret dans les fichiers suivis"
fi

echo "[scan] historique git..."
HITS="$(git log --all -p 2>/dev/null | grep -aoE "${PATTERNS}" | sort -u || true)"
if [ -n "${HITS}" ]; then
  echo "  SECRET TROUVE dans l'historique (purge requise: git filter-repo):" >&2
  echo "${HITS}" | sed 's/\(........\).*/\1.../' >&2   # tronque l'affichage
  FAIL=1
else
  echo "  OK — aucun secret dans l'historique"
fi

echo "[scan] .env ne doit pas etre suivi..."
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "  ERREUR: .env est suivi par git !" >&2
  FAIL=1
else
  echo "  OK — .env non suivi"
fi

[ "${FAIL}" -eq 0 ] && { echo "[scan] RESULTAT: propre"; exit 0; }
echo "[scan] RESULTAT: ECHEC — secrets a purger + cles a faire tourner" >&2
exit 1
