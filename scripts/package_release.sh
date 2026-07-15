#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_NAME="$(basename "${PROJECT_DIR}")"
PROJECT_PARENT="$(cd "${PROJECT_DIR}/.." && pwd)"
OUTPUT_DIR="${PROJECT_DIR}/release"
ARCHIVE_NAME="raspberry-wifi-portal-$(date +%Y%m%d-%H%M%S).tar.gz"
ARCHIVE_PATH="${OUTPUT_DIR}/${ARCHIVE_NAME}"

mkdir -p "${OUTPUT_DIR}"
tar \
  --exclude="${PROJECT_NAME}/.agents" \
  --exclude="${PROJECT_NAME}/.codex" \
  --exclude="${PROJECT_NAME}/.codex-remote-attachments" \
  --exclude="${PROJECT_NAME}/.git" \
  --exclude="${PROJECT_NAME}/.git.*" \
  --exclude="${PROJECT_NAME}/.venv" \
  --exclude="${PROJECT_NAME}/output" \
  --exclude="${PROJECT_NAME}/release" \
  --exclude="${PROJECT_NAME}/tmp" \
  --exclude="${PROJECT_NAME}/__pycache__" \
  --exclude="${PROJECT_NAME}/scripts/__pycache__" \
  --exclude="${PROJECT_NAME}/services/__pycache__" \
  --exclude="${PROJECT_NAME}/tests/__pycache__" \
  -czf "${ARCHIVE_PATH}" \
  -C "${PROJECT_PARENT}" \
  "${PROJECT_NAME}"

echo "Pacchetto creato: ${ARCHIVE_PATH}"
