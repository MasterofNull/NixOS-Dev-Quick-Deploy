#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REFRESH_SCRIPT="${ROOT_DIR}/scripts/observability/collect-ai-metrics.sh"
SERVICE_NAME="${SERVICE_NAME:-command-center-dashboard-api.service}"
USE_SUDO=0
LOG_LINES="${LOG_LINES:-50}"
CACHE_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/nixos-system-dashboard/ai_metrics.json"

usage() {
  cat <<'EOF'
Usage: scripts/governance/manage-dashboard-collectors.sh [--sudo] <status|start|stop|restart|logs|refresh>

Compatibility shim over the declarative dashboard service plus legacy cache refresh.

Commands:
  status   Show dashboard service state and cache freshness
  start    Start dashboard service, then refresh legacy cache
  stop     Stop dashboard service
  restart  Restart dashboard service, then refresh legacy cache
  logs     Show recent dashboard service logs
  refresh  Refresh the legacy dashboard cache from the live API
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
  echo "scripts/governance/manage-dashboard-collectors.sh is a compatibility shim over the dashboard service and collect-ai-metrics.sh." >&2
  if command -v systemctl >/dev/null 2>&1; then
    systemctl status "${SERVICE_NAME}" --no-pager --lines=0 2>/dev/null || true
  fi
  if [[ -f "${CACHE_FILE}" ]]; then
    printf 'Legacy cache: %s\n' "${CACHE_FILE}"
    stat --format='  modified: %y' "${CACHE_FILE}" 2>/dev/null || true
    stat --format='  size: %s bytes' "${CACHE_FILE}" 2>/dev/null || true
  else
    printf 'Legacy cache missing: %s\n' "${CACHE_FILE}"
  fi
}

refresh_cache() {
  "${REFRESH_SCRIPT}"
}

cmd="status"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sudo)
      USE_SUDO=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    status|start|stop|restart|logs|refresh)
      cmd="$1"
      shift
      ;;
    *)
      echo "Unknown option or command: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "${cmd}" in
  status)
    show_status
    ;;
  start)
    run_cmd systemctl start "${SERVICE_NAME}"
    refresh_cache
    ;;
  stop)
    run_cmd systemctl stop "${SERVICE_NAME}"
    ;;
  restart)
    run_cmd systemctl restart "${SERVICE_NAME}"
    refresh_cache
    ;;
  logs)
    if [[ "${USE_SUDO}" == 1 && "${EUID}" -ne 0 ]]; then
      exec sudo journalctl -u "${SERVICE_NAME}" -n "${LOG_LINES}" --no-pager
    fi
    exec journalctl -u "${SERVICE_NAME}" -n "${LOG_LINES}" --no-pager
    ;;
  refresh)
    refresh_cache
    ;;
esac
