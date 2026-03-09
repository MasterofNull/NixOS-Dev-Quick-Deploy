#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RENEW_SCRIPT="${ROOT_DIR}/scripts/security/renew-tls-certificate.sh"

usage() {
  cat <<'EOF'
Usage: scripts/security/apply-tls-certificates.sh [--status] [--renew] [renew-tls args...]

Compatibility shim over scripts/security/renew-tls-certificate.sh.
The supported long-term path is declarative ingress TLS via mySystem.ingress.*
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

[[ -x "${RENEW_SCRIPT}" ]] || { echo "Missing ${RENEW_SCRIPT}" >&2; exit 1; }

echo "scripts/security/apply-tls-certificates.sh is a compatibility shim over renew-tls-certificate.sh." >&2
if [[ $# -eq 0 ]]; then
  exec "${RENEW_SCRIPT}" --status
fi
exec "${RENEW_SCRIPT}" "$@"
