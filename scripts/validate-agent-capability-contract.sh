#!/usr/bin/env bash
# Validate agent-agnostic contract against live harness endpoints.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

CONTRACT_FILE="${SCRIPT_DIR}/../config/agent-capability-contract.json"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd jq
require_cmd curl

[[ -f "$CONTRACT_FILE" ]] || {
  echo "Missing capability contract file: $CONTRACT_FILE" >&2
  exit 1
}

jq -e '.workflow == ["discover","plan","execute","verify","learn"]' "$CONTRACT_FILE" >/dev/null

aidb_health="$(curl -fsS --max-time 5 --connect-timeout 3 "${AIDB_URL%/}/health")"
hybrid_health="$(curl -fsS --max-time 5 --connect-timeout 3 "${HYBRID_URL%/}/health")"

# Required behavior checks from contract + live state.
jq -e '.required_behaviors.autonomous_capability_discovery == true and .required_behaviors.risk_tiered_tool_execution == true' "$CONTRACT_FILE" >/dev/null

echo "$hybrid_health" | jq -e '.ai_harness.capability_discovery_enabled == true and .ai_harness.capability_discovery_on_query == true' >/dev/null
echo "$aidb_health" | jq -e '.tool_execution_policy.allow_high_risk_tools == false' >/dev/null

echo "PASS: agent capability contract is valid and enforced by live harness settings."
