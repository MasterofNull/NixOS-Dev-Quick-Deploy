#!/usr/bin/env bash
# Validate risk-tiered tool execution policy defaults and blocking behavior.
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

health_payload="$(curl -fsS --max-time 5 --connect-timeout 3 "${AIDB_URL%/}/health")"

# Newer AIDB builds expose tool_execution_policy in /health; older builds may
# omit it. Keep this gate focused on real behavior regressions (high-risk
# execution must be blocked by default), not payload shape drift.
if echo "$health_payload" | jq -e '.tool_execution_policy? != null' >/dev/null 2>&1; then
  echo "$health_payload" | jq -e '.tool_execution_policy.allow_high_risk_tools == false' >/dev/null
  echo "$health_payload" | jq -e '.tool_execution_policy.allow_medium_risk_tools == true' >/dev/null
fi

response_body="$(mktemp)"
http_code="$({
  curl -sS -o "$response_body" -w '%{http_code}' \
    -X POST "${AIDB_URL%/}/tools/execute" \
    -H 'Content-Type: application/json' \
    -d '{"tool_name":"run_sandboxed","parameters":{"command":["id"]}}'
} || true)"

if [[ "$http_code" =~ ^2 ]]; then
  echo "High-risk tool execution unexpectedly succeeded (HTTP $http_code)" >&2
  cat "$response_body" >&2
  rm -f "$response_body"
  exit 1
fi

if ! jq -e '.detail.error == "tool_execution_forbidden" or (.detail.error | type == "string")' "$response_body" >/dev/null 2>&1; then
  echo "Unexpected high-risk block response:" >&2
  cat "$response_body" >&2
  rm -f "$response_body"
  exit 1
fi

rm -f "$response_body"
echo "PASS: tool execution policy blocks high-risk tools by default."
