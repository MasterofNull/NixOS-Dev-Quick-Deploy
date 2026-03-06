#!/usr/bin/env bash
# Validate agent-agnostic contract against live harness endpoints.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../config/service-endpoints.sh
source "${SCRIPT_DIR}/../../config/service-endpoints.sh"

CONTRACT_FILE="${SCRIPT_DIR}/../../config/agent-capability-contract.json"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd jq
require_cmd curl

HYBRID_API_KEY="${HYBRID_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi
if [[ -z "${HYBRID_API_KEY}" && -r "/run/secrets/hybrid_api_key" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < /run/secrets/hybrid_api_key)"
fi

AIDB_API_KEY="${AIDB_API_KEY:-}"
AIDB_API_KEY_FILE="${AIDB_API_KEY_FILE:-/run/secrets/aidb_api_key}"
if [[ -z "${AIDB_API_KEY}" && -r "${AIDB_API_KEY_FILE}" ]]; then
  AIDB_API_KEY="$(tr -d '[:space:]' < "${AIDB_API_KEY_FILE}")"
fi

hybrid_auth_args=()
if [[ -n "${HYBRID_API_KEY}" ]]; then
  hybrid_auth_args=(-H "X-API-Key: ${HYBRID_API_KEY}")
fi

aidb_auth_args=()
if [[ -n "${AIDB_API_KEY}" ]]; then
  aidb_auth_args=(-H "X-API-Key: ${AIDB_API_KEY}")
fi

[[ -f "$CONTRACT_FILE" ]] || {
  echo "Missing capability contract file: $CONTRACT_FILE" >&2
  exit 1
}

jq -e '.workflow == ["discover","plan","execute","verify","learn"]' "$CONTRACT_FILE" >/dev/null

aidb_health="$(curl -fsS --max-time 5 --connect-timeout 3 "${aidb_auth_args[@]}" "${AIDB_URL%/}/health")"
hybrid_health="$(curl -fsS --max-time 5 --connect-timeout 3 "${hybrid_auth_args[@]}" "${HYBRID_URL%/}/health")"

# Required behavior checks from contract + live state.
jq -e '.required_behaviors.autonomous_capability_discovery == true and .required_behaviors.risk_tiered_tool_execution == true' "$CONTRACT_FILE" >/dev/null

if echo "$hybrid_health" | jq -e '.ai_harness.capability_discovery_enabled? != null and .ai_harness.capability_discovery_on_query? != null' >/dev/null 2>&1; then
  echo "$hybrid_health" | jq -e '.ai_harness.capability_discovery_enabled == true and .ai_harness.capability_discovery_on_query == true' >/dev/null
else
  echo "$hybrid_health" | jq -e '.ai_harness.enabled == true' >/dev/null
fi

if echo "$aidb_health" | jq -e '.tool_execution_policy? != null' >/dev/null 2>&1; then
  echo "$aidb_health" | jq -e '.tool_execution_policy.allow_high_risk_tools == false' >/dev/null
fi

echo "PASS: agent capability contract is valid and enforced by live harness settings."
