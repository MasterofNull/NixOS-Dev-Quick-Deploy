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

hybrid_scorecard="$(curl -sS --max-time 5 --connect-timeout 3 "${HYBRID_URL%/}/harness/scorecard" || true)"
if [[ -z "$hybrid_scorecard" || "$hybrid_scorecard" == *"unauthorized"* || "$hybrid_scorecard" == *"401"* ]]; then
  if [[ -n "$HYBRID_API_KEY" ]]; then
    hybrid_scorecard="$(curl -fsS --max-time 5 --connect-timeout 3 -H "X-API-Key: ${HYBRID_API_KEY}" "${HYBRID_URL%/}/harness/scorecard")"
  else
    hybrid_scorecard="$(curl -fsS --max-time 5 --connect-timeout 3 "${HYBRID_URL%/}/stats")"
  fi
fi
aidb_health="$(curl -fsS --max-time 5 --connect-timeout 3 "${AIDB_URL%/}/health")"

# Ensure scorecards expose acceptance/discovery and optimization flags.
echo "$hybrid_scorecard" | jq -e '(.acceptance.total >= 0 and .discovery.invoked >= 0) or (.harness_stats.total_runs >= 0)' >/dev/null
# Ensure AIDB exposes tool and outbound policy surfaces.
echo "$aidb_health" | jq -e '.tool_execution_policy != null and .outbound_http_policy != null' >/dev/null

echo "PASS: GenAI observability and policy surfaces are available."
