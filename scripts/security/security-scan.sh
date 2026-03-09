#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AUDIT_SCRIPT="${ROOT_DIR}/scripts/security/security-audit.sh"
FIREWALL_SCRIPT="${ROOT_DIR}/scripts/security/firewall-audit.sh"
RUN_FIREWALL=true
PASSTHRU=()

usage() {
  cat <<'EOF'
Usage: scripts/security/security-scan.sh [--skip-firewall] [security-audit args...]

Compatibility shim over the supported declarative security tooling:
  1. scripts/security/security-audit.sh
  2. scripts/security/firewall-audit.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-firewall)
      RUN_FIREWALL=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      PASSTHRU+=("$1")
      shift
      ;;
  esac
done

[[ -x "${AUDIT_SCRIPT}" ]] || { echo "Missing ${AUDIT_SCRIPT}" >&2; exit 1; }
[[ -x "${FIREWALL_SCRIPT}" ]] || { echo "Missing ${FIREWALL_SCRIPT}" >&2; exit 1; }

echo "scripts/security/security-scan.sh is a compatibility shim over supported security tooling." >&2
"${AUDIT_SCRIPT}" "${PASSTHRU[@]}"
if [[ "${RUN_FIREWALL}" == true ]]; then
  echo "" >&2
  "${FIREWALL_SCRIPT}"
fi
