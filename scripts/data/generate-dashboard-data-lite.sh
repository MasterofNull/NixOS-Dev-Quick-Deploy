#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MAIN_SCRIPT="${ROOT_DIR}/scripts/data/generate-dashboard-data.sh"

usage() {
  cat <<'EOF'
Usage: scripts/data/generate-dashboard-data-lite.sh [--output FILE] [--api-url URL]

Compatibility shim over scripts/data/generate-dashboard-data.sh --lite-mode.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

echo "scripts/data/generate-dashboard-data-lite.sh is a compatibility shim over generate-dashboard-data.sh." >&2
exec "${MAIN_SCRIPT}" --lite-mode "$@"
