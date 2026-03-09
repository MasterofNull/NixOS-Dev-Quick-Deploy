#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../../config/service-endpoints.sh
source "${ROOT_DIR}/config/service-endpoints.sh"

MODEL_MANAGER="${SCRIPT_DIR}/ai-model-manager.sh"

usage() {
  cat <<'EOF'
Usage: scripts/ai/llama-model-cli.sh <command> [args...]

Compatibility shim for llama.cpp operator workflows.

Commands:
  list                   Alias for model status
  status                 Alias for model status
  logs [N]               Show llama-cpp service logs
  debug [args...]        Run aq-llama-debug
  update [args...]       Run update-llama-cpp.sh
  reload [json-payload]  Trigger /reload-model
EOF
}

command="${1:-help}"
shift || true

echo "scripts/ai/llama-model-cli.sh is a compatibility shim over ai-model-manager.sh and systemd logs." >&2

case "${command}" in
  help|-h|--help)
    usage
    ;;
  list|status)
    exec "${MODEL_MANAGER}" status "$@"
    ;;
  debug)
    exec "${MODEL_MANAGER}" debug "$@"
    ;;
  update)
    exec "${MODEL_MANAGER}" update "$@"
    ;;
  reload)
    exec "${MODEL_MANAGER}" reload "${1:-{}}"
    ;;
  logs)
    lines="${1:-80}"
    exec journalctl --no-pager -u llama-cpp.service -n "${lines}"
    ;;
  *)
    echo "Unknown command: ${command}" >&2
    usage >&2
    exit 2
    ;;
esac
