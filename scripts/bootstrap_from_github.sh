#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Esegui questo script come root: sudo bash bootstrap_from_github.sh <repo-url> [branch] [opzioni-install]"
  exit 1
fi

REPO_URL="${1:-}"
BRANCH="main"
CLONE_DIR="/tmp/raspberry-wifi-portal-bootstrap"

if [[ -z "${REPO_URL}" ]]; then
  echo "Uso: sudo bash bootstrap_from_github.sh <repo-url> [branch] [opzioni-install]"
  echo "Esempio: sudo bash bootstrap_from_github.sh https://github.com/andreakys/raspberry-wifi-portal.git main --profile balanced"
  exit 1
fi

shift
if [[ $# -gt 0 && "${1}" != --* ]]; then
  BRANCH="$1"
  shift
fi

apt-get update
apt-get install -y git

rm -rf "${CLONE_DIR}"
git clone --depth 1 --branch "${BRANCH}" "${REPO_URL}" "${CLONE_DIR}"

cd "${CLONE_DIR}"
chmod +x scripts/install.sh
./scripts/install.sh "$@"

echo "Bootstrap completato da ${REPO_URL} (${BRANCH})."
