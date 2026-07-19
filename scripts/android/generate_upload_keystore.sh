#!/bin/sh
# ---------------------------------------------------------------------------
# FoodGad — genere la cle de signature (upload key) pour la release Android et
# le fichier android/key.properties attendu par build.gradle.kts.
#
# A executer UNE FOIS sur la machine de release (ou dans un secret manager CI).
# Le keystore et key.properties sont gitignores: ils ne doivent JAMAIS entrer
# dans le depot. Perdre l'upload key = ne plus pouvoir publier de mise a jour
# (sauf reset via Google Play App Signing) -> sauvegarder hors-ligne.
#
# Usage:
#   sh scripts/android/generate_upload_keystore.sh
#   (repond aux invites keytool, puis renseigne les mots de passe)
# ---------------------------------------------------------------------------
set -eu

ANDROID_DIR="mobile/android"
KEYSTORE="${ANDROID_DIR}/upload-keystore.jks"
PROPS="${ANDROID_DIR}/key.properties"
ALIAS="${KEY_ALIAS:-upload}"

if [ -f "${KEYSTORE}" ]; then
  echo "ERREUR: ${KEYSTORE} existe deja — abandon pour ne pas ecraser la cle." >&2
  exit 1
fi

command -v keytool >/dev/null 2>&1 || {
  echo "ERREUR: keytool introuvable (installer un JDK)." >&2; exit 1;
}

echo "Generation de l'upload key (RSA 2048, validite 10000 jours)..."
keytool -genkeypair -v \
  -keystore "${KEYSTORE}" \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias "${ALIAS}"

# keytool a demande les mots de passe du store et de la cle de facon interactive.
printf "Mot de passe du keystore (storePassword): "; stty -echo; read STORE_PW; stty echo; echo
printf "Mot de passe de la cle (keyPassword, souvent identique): "; stty -echo; read KEY_PW; stty echo; echo

cat > "${PROPS}" <<EOF
storePassword=${STORE_PW}
keyPassword=${KEY_PW}
keyAlias=${ALIAS}
storeFile=upload-keystore.jks
EOF

echo "OK:"
echo "  - ${KEYSTORE}  (a sauvegarder hors-ligne, jamais commite)"
echo "  - ${PROPS}     (gitignore)"
echo
echo "Verifier ensuite: cd mobile && flutter build appbundle --release"
