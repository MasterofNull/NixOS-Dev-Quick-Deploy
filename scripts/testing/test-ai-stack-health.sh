#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HEALTH_SHIM="${ROOT_DIR}/scripts/testing/check-ai-stack-health.sh"

usage() {
  cat <<'EOF'
Usage: scripts/testing/test-ai-stack-health.sh [--with-qa] [aq-qa args...]

Compatibility shim over scripts/testing/check-ai-stack-health.sh.
Use this legacy entrypoint when older docs or operators expect a test wrapper.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

echo "scripts/testing/test-ai-stack-health.sh is a compatibility shim over check-ai-stack-health.sh." >&2
exec "${HEALTH_SHIM}" "$@"
