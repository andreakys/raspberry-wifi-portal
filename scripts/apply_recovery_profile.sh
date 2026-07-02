#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Esegui questo script come root: sudo ./scripts/apply_recovery_profile.sh <stable|balanced|unstable>"
  exit 1
fi

PROFILE_NAME="${1:-}"
if [[ -z "${PROFILE_NAME}" ]]; then
  echo "Uso: sudo ./scripts/apply_recovery_profile.sh <stable|balanced|unstable>"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROFILE_PATH="${PROJECT_DIR}/deploy/profiles/${PROFILE_NAME}.env"
TARGET_DIR="/etc/raspberry-wifi-portal"
TARGET_FILE="${TARGET_DIR}/portal.env"

if [[ ! -f "${PROFILE_PATH}" ]]; then
  echo "Profilo non trovato: ${PROFILE_PATH}"
  exit 1
fi

mkdir -p "${TARGET_DIR}"
touch "${TARGET_FILE}"

set_kv() {
  local key="$1"
  local value="$2"

  if grep -qE "^${key}=" "${TARGET_FILE}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${TARGET_FILE}"
  else
    printf "%s=%s\n" "${key}" "${value}" >> "${TARGET_FILE}"
  fi
}

while IFS='=' read -r key value; do
  [[ -z "${key}" ]] && continue
  set_kv "${key}" "${value}"
done < "${PROFILE_PATH}"

systemctl restart raspberry-wifi-portal.service
echo "Profilo '${PROFILE_NAME}' applicato. Servizio riavviato."
