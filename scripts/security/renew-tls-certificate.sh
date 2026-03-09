#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../../config/service-endpoints.sh
source "${ROOT_DIR}/config/service-endpoints.sh"

MODE="status"
DOMAIN=""
EMAIL=""
USE_SUDO=0

usage() {
  cat <<'EOF'
Usage: scripts/security/renew-tls-certificate.sh [--status] [--renew] [--domain NAME] [--email EMAIL] [--sudo]

Compatibility shim for declarative TLS ingress.
- --status: show nginx + ACME/certbot status and current certificate paths
- --renew: trigger available ACME/certbot renewal units

The supported long-term path is declarative:
  mySystem.ingress.enable = true;
  mySystem.ingress.domain = "...";
  mySystem.ingress.useAcme = true;
  mySystem.ingress.acmeEmail = "...";
EOF
}

run_cmd() {
  if [[ "${USE_SUDO}" == 1 && "${EUID}" -ne 0 ]]; then
    sudo "$@"
  else
    "$@"
  fi
}

show_status() {
  echo "TLS ingress status"
  echo "  dashboard: ${DASHBOARD_URL}"
  echo ""
  if systemctl list-unit-files 'acme-*.service' --no-legend 2>/dev/null | grep -q '^acme-'; then
    echo "ACME services:"
    systemctl list-units 'acme-*.service' 'acme-*.timer' --no-pager --no-legend 2>/dev/null || true
  else
    echo "No ACME units found."
  fi
  echo ""
  echo "Ingress-related services:"
  systemctl status nginx.service --no-pager --lines=0 2>/dev/null || true
  systemctl status certbot.timer certbot.service --no-pager --lines=0 2>/dev/null || true
  echo ""
  for dir in /var/lib/acme /etc/letsencrypt/live; do
    if [[ -d "${dir}" ]]; then
      echo "Certificate files under ${dir}:"
      find "${dir}" -maxdepth 3 \( -name '*.pem' -o -name '*.crt' \) 2>/dev/null | sort | sed 's/^/  /'
    fi
  done
  if [[ -n "${DOMAIN}" ]]; then
    echo ""
    echo "Requested domain hint: ${DOMAIN}"
  fi
  if [[ -n "${EMAIL}" ]]; then
    echo "Requested email hint: ${EMAIL}"
  fi
}

trigger_renewal() {
  local found=0
  while IFS= read -r unit; do
    [[ -n "${unit}" ]] || continue
    found=1
    echo "Starting ${unit}"
    run_cmd systemctl start "${unit}"
  done < <(systemctl list-unit-files 'acme-*.service' --no-legend 2>/dev/null | awk '{print $1}')

  if [[ "${found}" -eq 0 ]]; then
    if command -v certbot >/dev/null 2>&1; then
      echo "Running certbot renew"
      run_cmd certbot renew
      found=1
    fi
  fi

  if [[ "${found}" -eq 0 ]]; then
    echo "No ACME or certbot renewal path detected on this host." >&2
    echo "Configure mySystem.ingress.useAcme=true or install certbot before using --renew." >&2
    exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --status)
      MODE="status"
      shift
      ;;
    --renew)
      MODE="renew"
      shift
      ;;
    --domain)
      DOMAIN="${2:?missing value for --domain}"
      shift 2
      ;;
    --email)
      EMAIL="${2:?missing value for --email}"
      shift 2
      ;;
    --sudo)
      USE_SUDO=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

echo "scripts/security/renew-tls-certificate.sh is a compatibility shim for declarative ingress TLS." >&2
case "${MODE}" in
  status) show_status ;;
  renew) trigger_renewal ;;
esac
