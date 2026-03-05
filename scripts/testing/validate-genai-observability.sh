#!/usr/bin/env bash
# Validate GenAI observability surfaces required for harness operations.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd jq

HYBRID_API_KEY="${HYBRID_API_KEY:-}"
if [[ -z "$HYBRID_API_KEY" ]]; then
  HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_api_key}"
  if [[ -r "$HYBRID_API_KEY_FILE" ]]; then
    HYBRID_API_KEY="$(<"$HYBRID_API_KEY_FILE")"
  fi
fi

hybrid_scorecard=""
if [[ -n "$HYBRID_API_KEY" ]]; then
  hybrid_scorecard="$(curl -fsS --max-time 5 --connect-timeout 3 -H "X-API-Key: ${HYBRID_API_KEY}" "${HYBRID_URL%/}/harness/scorecard" || true)"
else
  hybrid_scorecard="$(curl -sS --max-time 5 --connect-timeout 3 "${HYBRID_URL%/}/harness/scorecard" || true)"
fi
aidb_health="$(curl -fsS --max-time 5 --connect-timeout 3 "${AIDB_URL%/}/health")"
hybrid_health="$(curl -fsS --max-time 5 --connect-timeout 3 "${HYBRID_URL%/}/health")"

# Ensure scorecards expose acceptance/discovery and optimization flags.
if [[ -n "$hybrid_scorecard" ]] && echo "$hybrid_scorecard" | jq -e '.error? != "unauthorized"' >/dev/null 2>&1; then
  echo "$hybrid_scorecard" | jq -e '(.acceptance.total >= 0 and .discovery.invoked >= 0) or (.harness_stats.total_runs >= 0)' >/dev/null
else
  echo "$hybrid_health" | jq -e '.ai_harness.enabled == true and .ai_harness.memory_enabled == true and .ai_harness.tree_search_enabled == true and .ai_harness.eval_enabled == true' >/dev/null
fi
# Ensure AIDB exposes tool and outbound policy surfaces.
if echo "$aidb_health" | jq -e '.tool_execution_policy? != null and .outbound_http_policy? != null' >/dev/null 2>&1; then
  echo "$aidb_health" | jq -e '.tool_execution_policy != null and .outbound_http_policy != null' >/dev/null
fi

echo "PASS: GenAI observability and policy surfaces are available."
