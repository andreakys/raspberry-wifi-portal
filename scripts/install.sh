#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="raspberry-wifi-portal.service"
INSTALL_DIR="/opt/raspberry-wifi-portal"
CONFIG_DIR="/etc/raspberry-wifi-portal"
ENV_FILE="${CONFIG_DIR}/portal.env"
VENV_DIR="${INSTALL_DIR}/.venv"

INSTALL_PACKAGES=true
START_SERVICE=true
INTERACTIVE=false
HOTSPOT_SSID_VALUE=""
HOTSPOT_PASSWORD_VALUE=""
PORTAL_PASSWORD_VALUE=""
PORTAL_PORT_VALUE=""
PROFILE_NAME=""

usage() {
  cat <<'EOF'
Uso:
  sudo ./scripts/install.sh [opzioni]

Opzioni:
  --interactive              Chiede SSID hotspot, password, porta e profilo recovery.
  --ssid VALUE               Imposta HOTSPOT_SSID.
  --password VALUE           Imposta HOTSPOT_PASSWORD (minimo 8 caratteri).
  --portal-password VALUE    Imposta la password di accesso al portale web.
  --port VALUE               Imposta PORTAL_PORT.
  --profile NAME             Applica stable, balanced o unstable.
  --install-dir PATH         Installa in una cartella diversa da /opt/raspberry-wifi-portal.
  --skip-apt                 Salta apt-get update/install.
  --no-start                 Installa e abilita il servizio senza avviarlo subito.
  -h, --help                 Mostra questo aiuto.

Esempi:
  sudo ./scripts/install.sh --interactive
  sudo ./scripts/install.sh --ssid Pi-Setup --password 'ChangeMe123!' --portal-password 'CambiaQuestaPassword!' --profile balanced
EOF
}

log() {
  printf '[raspberry-wifi-portal] %s\n' "$*"
}

die() {
  printf 'Errore: %s\n' "$*" >&2
  exit 1
}

read_default() {
  local prompt="$1"
  local default_value="$2"
  local answer=""

  read -r -p "${prompt} [${default_value}]: " answer
  printf '%s' "${answer:-${default_value}}"
}

generate_secret() {
  python3 -c 'import secrets; print(secrets.token_urlsafe(18))' 2>/dev/null || openssl rand -hex 18
}

get_env_value() {
  local key="$1"

  [[ -f "${ENV_FILE}" ]] || return 0
  awk -v key="${key}" '
    index($0, key "=") == 1 {
      print substr($0, length(key) + 2)
    }
  ' "${ENV_FILE}" | tail -n 1
}

set_env_value() {
  local key="$1"
  local value="$2"
  local tmp_file=""

  tmp_file="$(mktemp)"
  if [[ -f "${ENV_FILE}" ]]; then
    awk -v key="${key}" -v value="${value}" '
      BEGIN { updated = 0 }
      $0 ~ "^" key "=" {
        print key "=" value
        updated = 1
        next
      }
      { print }
      END {
        if (updated == 0) {
          print key "=" value
        }
      }
    ' "${ENV_FILE}" > "${tmp_file}"
  else
    printf '%s=%s\n' "${key}" "${value}" > "${tmp_file}"
  fi

  install -m 600 "${tmp_file}" "${ENV_FILE}"
  rm -f "${tmp_file}"
}

apply_profile() {
  local profile_name="$1"
  local profile_path="${INSTALL_DIR}/deploy/profiles/${profile_name}.env"

  [[ -f "${profile_path}" ]] || die "Profilo recovery non trovato: ${profile_name}"

  while IFS='=' read -r key value || [[ -n "${key:-}" ]]; do
    [[ -z "${key:-}" ]] && continue
    [[ "${key}" == \#* ]] && continue
    set_env_value "${key}" "${value:-}"
  done < "${profile_path}"
}

copy_project_to_install_dir() {
  local script_dir=""
  local project_dir=""
  local staging_dir=""

  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  project_dir="$(cd "${script_dir}/.." && pwd)"
  staging_dir="$(mktemp -d)"

  log "Preparo i file da ${project_dir}"
  mkdir -p "${staging_dir}/source"

  if command -v tar >/dev/null 2>&1; then
    (
      cd "${project_dir}"
      tar \
        --exclude='./.git' \
        --exclude='./.venv' \
        --exclude='./release' \
        --exclude='./tmp' \
        --exclude='./output' \
        --exclude='./__pycache__' \
        --exclude='./services/__pycache__' \
        -cf - .
    ) | (
      cd "${staging_dir}/source"
      tar -xf -
    )
  else
    cp -a "${project_dir}/." "${staging_dir}/source/"
    rm -rf \
      "${staging_dir}/source/.git" \
      "${staging_dir}/source/.venv" \
      "${staging_dir}/source/release" \
      "${staging_dir}/source/tmp" \
      "${staging_dir}/source/output" \
      "${staging_dir}/source/__pycache__" \
      "${staging_dir}/source/services/__pycache__"
  fi

  [[ -n "${INSTALL_DIR}" && "${INSTALL_DIR}" != "/" ]] || die "INSTALL_DIR non valido"

  log "Installo in ${INSTALL_DIR}"
  rm -rf "${INSTALL_DIR}"
  install -d -m 755 "${INSTALL_DIR}"
  cp -a "${staging_dir}/source/." "${INSTALL_DIR}/"
  rm -rf "${staging_dir}"
  chmod +x "${INSTALL_DIR}/scripts/"*.sh || true
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interactive)
      INTERACTIVE=true
      shift
      ;;
    --ssid)
      HOTSPOT_SSID_VALUE="${2:-}"
      [[ -n "${HOTSPOT_SSID_VALUE}" ]] || die "--ssid richiede un valore"
      shift 2
      ;;
    --password)
      HOTSPOT_PASSWORD_VALUE="${2:-}"
      [[ -n "${HOTSPOT_PASSWORD_VALUE}" ]] || die "--password richiede un valore"
      shift 2
      ;;
    --portal-password)
      PORTAL_PASSWORD_VALUE="${2:-}"
      [[ -n "${PORTAL_PASSWORD_VALUE}" ]] || die "--portal-password richiede un valore"
      shift 2
      ;;
    --port)
      PORTAL_PORT_VALUE="${2:-}"
      [[ -n "${PORTAL_PORT_VALUE}" ]] || die "--port richiede un valore"
      shift 2
      ;;
    --profile)
      PROFILE_NAME="${2:-}"
      [[ -n "${PROFILE_NAME}" ]] || die "--profile richiede stable, balanced o unstable"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="${2:-}"
      [[ -n "${INSTALL_DIR}" ]] || die "--install-dir richiede un percorso"
      VENV_DIR="${INSTALL_DIR}/.venv"
      shift 2
      ;;
    --skip-apt)
      INSTALL_PACKAGES=false
      shift
      ;;
    --no-start)
      START_SERVICE=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Opzione non riconosciuta: $1"
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  die "Esegui questo script come root: sudo ./scripts/install.sh"
fi

if [[ "${INTERACTIVE}" == true ]]; then
  HOTSPOT_SSID_VALUE="${HOTSPOT_SSID_VALUE:-$(read_default 'SSID hotspot temporaneo' 'Pi-Setup')}"
  HOTSPOT_PASSWORD_VALUE="${HOTSPOT_PASSWORD_VALUE:-$(read_default 'Password hotspot temporaneo' 'ChangeMe123!')}"
  PORTAL_PASSWORD_VALUE="${PORTAL_PASSWORD_VALUE:-$(read_default 'Password accesso portale (vuoto = genera sicura)' '')}"
  PORTAL_PORT_VALUE="${PORTAL_PORT_VALUE:-$(read_default 'Porta HTTP portale' '80')}"
  PROFILE_NAME="${PROFILE_NAME:-$(read_default 'Profilo recovery (stable/balanced/unstable)' 'balanced')}"
fi

if [[ -n "${HOTSPOT_PASSWORD_VALUE}" && ${#HOTSPOT_PASSWORD_VALUE} -lt 8 ]]; then
  die "La password hotspot deve contenere almeno 8 caratteri"
fi

if [[ -n "${PORTAL_PASSWORD_VALUE}" && ${#PORTAL_PASSWORD_VALUE} -lt 10 ]]; then
  die "La password portale deve contenere almeno 10 caratteri"
fi

if [[ -n "${PORTAL_PORT_VALUE}" && ! "${PORTAL_PORT_VALUE}" =~ ^[0-9]+$ ]]; then
  die "La porta deve essere numerica"
fi

if [[ -n "${PROFILE_NAME}" && ! "${PROFILE_NAME}" =~ ^(stable|balanced|unstable)$ ]]; then
  die "Profilo recovery non valido: ${PROFILE_NAME}"
fi

if [[ "${INSTALL_PACKAGES}" == true ]]; then
  log "Installo dipendenze di sistema"
  apt-get update
  apt-get install -y python3 python3-pip python3-venv network-manager
fi

copy_project_to_install_dir

log "Creo virtual environment Python"
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${INSTALL_DIR}/requirements.txt"

log "Preparo configurazione in ${ENV_FILE}"
install -d -m 755 "${CONFIG_DIR}"
if [[ ! -f "${ENV_FILE}" ]]; then
  install -m 600 "${INSTALL_DIR}/deploy/portal.env.example" "${ENV_FILE}"
fi

GENERATED_PORTAL_PASSWORD=false
existing_portal_password="$(get_env_value PORTAL_PASSWORD)"
if [[ -z "${PORTAL_PASSWORD_VALUE}" && -z "${existing_portal_password}" ]]; then
  PORTAL_PASSWORD_VALUE="$(generate_secret)"
  GENERATED_PORTAL_PASSWORD=true
fi

existing_portal_session_secret="$(get_env_value PORTAL_SESSION_SECRET)"
if [[ -z "${existing_portal_session_secret}" ]]; then
  set_env_value "PORTAL_SESSION_SECRET" "$(generate_secret)"
fi

existing_portal_title="$(get_env_value PORTAL_TITLE)"
if [[ -z "${existing_portal_title}" || "${existing_portal_title}" == "Raspberry Pi Wi-Fi Setup" || "${existing_portal_title}" == "Wi-Fi Setup" || "${existing_portal_title}" == "Pi Network Manager" ]]; then
  set_env_value "PORTAL_TITLE" "VT Network Manager"
fi

[[ -z "${HOTSPOT_SSID_VALUE}" ]] || set_env_value "HOTSPOT_SSID" "${HOTSPOT_SSID_VALUE}"
[[ -z "${HOTSPOT_PASSWORD_VALUE}" ]] || set_env_value "HOTSPOT_PASSWORD" "${HOTSPOT_PASSWORD_VALUE}"
[[ -z "${PORTAL_PASSWORD_VALUE}" ]] || set_env_value "PORTAL_PASSWORD" "${PORTAL_PASSWORD_VALUE}"
[[ -z "${PORTAL_PORT_VALUE}" ]] || set_env_value "PORTAL_PORT" "${PORTAL_PORT_VALUE}"
[[ -z "${PROFILE_NAME}" ]] || apply_profile "${PROFILE_NAME}"

log "Installo servizio systemd"
install -m 644 "${INSTALL_DIR}/systemd/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

if [[ "${START_SERVICE}" == true ]]; then
  systemctl restart "${SERVICE_NAME}"
  log "Servizio avviato"
else
  log "Servizio abilitato ma non avviato (--no-start)"
fi

portal_address="$(awk -F= '/^HOTSPOT_ADDRESS=/{print $2}' "${ENV_FILE}" | tail -n 1 | cut -d/ -f1)"
hotspot_ssid="$(awk -F= '/^HOTSPOT_SSID=/{print $2}' "${ENV_FILE}" | tail -n 1)"
portal_password="$(get_env_value PORTAL_PASSWORD)"

echo
echo "Installazione completata."
echo "Hotspot: ${hotspot_ssid:-Pi-Setup}"
echo "Portale: http://${portal_address:-192.168.4.1}"
echo "Password portale: ${portal_password}"
if [[ "${GENERATED_PORTAL_PASSWORD}" == true ]]; then
  echo "Password generata automaticamente: conservala o cambiala in ${ENV_FILE}."
fi
echo "Configurazione: ${ENV_FILE}"
echo
echo "Comandi utili:"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
