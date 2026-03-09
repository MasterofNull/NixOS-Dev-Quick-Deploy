#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../../config/service-endpoints.sh
source "${ROOT_DIR}/config/service-endpoints.sh"

UPDATE_SCRIPT="${SCRIPT_DIR}/update-llama-cpp.sh"
DEBUG_SCRIPT="${SCRIPT_DIR}/aq-llama-debug"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"

usage() {
  cat <<'EOF'
Usage: scripts/ai/ai-model-manager.sh <command> [args...]

Compatibility shim for current declarative/model-debug tooling.

Commands:
  status                 Show current model status from hybrid-coordinator
  debug [args...]        Run aq-llama-debug
  check-update [args...] Run update-llama-cpp.sh --check
  update [args...]       Run update-llama-cpp.sh
  reload [args...]       POST /reload-model to hybrid-coordinator
EOF
}

if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi

hybrid_auth_args=()
if [[ -n "${HYBRID_API_KEY}" ]]; then
  hybrid_auth_args=(-H "X-API-Key: ${HYBRID_API_KEY}")
fi

command="${1:-help}"
shift || true

echo "scripts/ai/ai-model-manager.sh is a compatibility shim over current model tooling." >&2

case "${command}" in
  help|-h|--help)
    usage
    ;;
  status)
    curl -fsS "${hybrid_auth_args[@]}" "${HYBRID_URL%/}/model/status"
    ;;
  debug)
    exec "${DEBUG_SCRIPT}" "$@"
    ;;
  check-update)
    exec "${UPDATE_SCRIPT}" --check "$@"
    ;;
  update)
    exec "${UPDATE_SCRIPT}" "$@"
    ;;
  reload)
    curl -fsS "${hybrid_auth_args[@]}" \
      -H "Content-Type: application/json" \
      -X POST \
      "${HYBRID_URL%/}/reload-model" \
      -d "${1:-{}}"
    ;;
  *)
    echo "Unknown command: ${command}" >&2
    usage >&2
    exit 2
    ;;
esac
