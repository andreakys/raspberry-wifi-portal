#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Esegui questo script come root: sudo ./scripts/uninstall.sh"
  exit 1
fi

SERVICE_NAME="raspberry-wifi-portal.service"
INSTALL_DIR="/opt/raspberry-wifi-portal"

systemctl stop "${SERVICE_NAME}" || true
systemctl disable "${SERVICE_NAME}" || true
rm -f "/etc/systemd/system/${SERVICE_NAME}"
systemctl daemon-reload

rm -rf "${INSTALL_DIR}"

echo "Applicazione rimossa. Il file /etc/raspberry-wifi-portal/portal.env e' stato lasciato intatto."
