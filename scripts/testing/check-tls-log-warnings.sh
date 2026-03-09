#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TLS_SCRIPT="${ROOT_DIR}/scripts/security/renew-tls-certificate.sh"
SINCE="${SINCE:-2 hours ago}"
MATCH_REGEX='(warn|error|failed|denied|expired|challenge)'
UNITS=(nginx.service certbot.service)

usage() {
  cat <<'EOF'
Usage: scripts/testing/check-tls-log-warnings.sh [--since "2 hours ago"] [--show-status]

Compatibility shim over declarative TLS status plus targeted journal scans.
- Scans nginx/certbot logs and any ACME units for warning/error patterns.
- Optionally prints the current TLS status shim first.
EOF
}

show_status=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since)
      [[ $# -ge 2 ]] || { echo "--since requires a value" >&2; exit 2; }
      SINCE="$2"
      shift 2
      ;;
    --show-status)
      show_status=true
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

if [[ "${show_status}" == true ]]; then
  "${TLS_SCRIPT}" --status
fi

if command -v systemctl >/dev/null 2>&1; then
  while IFS= read -r unit; do
    [[ -n "${unit}" ]] || continue
    UNITS+=("${unit}")
  done < <(systemctl list-unit-files 'acme-*.service' --no-legend 2>/dev/null | awk '{print $1}')
fi

echo "scripts/testing/check-tls-log-warnings.sh is a compatibility shim over declarative TLS status and journal scans." >&2

if ! command -v journalctl >/dev/null 2>&1; then
  echo "journalctl not available; skipping TLS log scan." >&2
  exit 0
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

for unit in "${UNITS[@]}"; do
  journalctl -u "${unit}" --since "${SINCE}" --no-pager 2>/dev/null || true
done >"${tmp}"

if rg -i "${MATCH_REGEX}" "${tmp}" >/dev/null 2>&1; then
  echo "TLS-related warnings detected since ${SINCE}:"
  rg -i "${MATCH_REGEX}" "${tmp}" || true
  exit 1
fi

echo "No TLS-related warning patterns detected since ${SINCE}."
