#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COLLECT_SCRIPT="${ROOT_DIR}/scripts/observability/collect-ai-metrics.sh"

usage() {
  cat <<'EOF'
Usage: scripts/data/generate-dashboard-data.sh [--lite-mode] [--output FILE] [--api-url URL]

Compatibility shim over the current dashboard API cache refresh flow.
- Refreshes the legacy dashboard cache from the declarative dashboard API
- Accepts --lite-mode for legacy callers, but both modes now use the same live API payload
EOF
}

args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lite-mode)
      shift
      ;;
    --output|--api-url)
      [[ $# -ge 2 ]] || { echo "$1 requires a value" >&2; exit 2; }
      args+=("$1" "$2")
      shift 2
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

echo "scripts/data/generate-dashboard-data.sh is a compatibility shim over collect-ai-metrics.sh." >&2
exec "${COLLECT_SCRIPT}" "${args[@]}"
