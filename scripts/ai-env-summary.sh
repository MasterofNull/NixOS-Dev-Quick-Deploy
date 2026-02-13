#!/usr/bin/env bash
#
# ai-env-summary.sh
# Print a concise summary of the current AI environment for this host.
#

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Load defaults from config so we see the same values as the deployer.
if [[ -f "$SCRIPT_DIR/config/variables.sh" ]]; then
  # shellcheck disable=SC1091
  . "$SCRIPT_DIR/config/variables.sh"
fi
# shellcheck disable=SC1091
[[ -f "$SCRIPT_DIR/config/service-endpoints.sh" ]] && . "$SCRIPT_DIR/config/service-endpoints.sh"

REGISTRY_PATH="${EDGE_MODEL_REGISTRY:-$SCRIPT_DIR/config/edge-model-registry.json}"

echo "AI Environment Summary"
echo "======================"
echo ""
echo "Host profile (role):                ${HOST_PROFILE:-undefined}"
echo "AI profile (edge LLM behavior):    ${AI_PROFILE:-undefined}"
echo "AI stack profile (personal/guest): ${AI_STACK_PROFILE:-undefined}"
echo "AI enabled mode:                   ${AI_ENABLED:-auto}"
echo "AIDB base URL:                     ${AIDB_BASE_URL:-${AIDB_URL:-http://${SERVICE_HOST:-localhost}:${AIDB_PORT:-8091}}}"
echo "AIDB project name:                 ${AIDB_PROJECT_NAME:-NixOS-Dev-Quick-Deploy}"
echo "Edge model registry:               ${REGISTRY_PATH}"

if [[ -f "$REGISTRY_PATH" ]]; then
  if command -v jq >/dev/null 2>&1; then
    model_count="$(jq '.models | length' "$REGISTRY_PATH" 2>/dev/null || echo "unknown")"
    echo "Registered edge models:            ${model_count}"
  else
    echo "Registered edge models:            (install jq to inspect ${REGISTRY_PATH})"
  fi
else
  echo "Registered edge models:            (registry file not found)"
fi

echo ""
echo "Tip: Adjust AI_PROFILE and AI_STACK_PROFILE in your environment before running"
echo "      deployment or local stack scripts to switch between personal and guest setups."
