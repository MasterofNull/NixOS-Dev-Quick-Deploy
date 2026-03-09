#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COLLECT_SCRIPT="${ROOT_DIR}/scripts/observability/collect-ai-metrics.sh"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-300}"
RUN_ONCE=0

usage() {
  cat <<'EOF'
Usage: scripts/ai/ai-metrics-auto-updater.sh [--once] [--interval SECONDS]

Compatibility shim over the current dashboard cache refresh flow.
- --once: refresh legacy AI dashboard cache once and exit
- default: run a bounded foreground refresh loop
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --once)
      RUN_ONCE=1
      shift
      ;;
    --interval)
      [[ $# -ge 2 ]] || { echo "--interval requires a value" >&2; exit 2; }
      INTERVAL_SECONDS="$2"
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

echo "scripts/ai/ai-metrics-auto-updater.sh is a compatibility shim over collect-ai-metrics.sh." >&2
if [[ "${RUN_ONCE}" -eq 1 ]]; then
  exec "${COLLECT_SCRIPT}"
fi

while true; do
  "${COLLECT_SCRIPT}" || true
  sleep "${INTERVAL_SECONDS}"
done
