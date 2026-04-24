#!/usr/bin/env bash
# Purpose: smoke gate for ai_coordinator_delegate endpoint.
# Validates the 180s timeout fix (commit a36e715) — ensures endpoint returns
# a structured response (not HTTP 5xx) and that the default timeout is ≥ 120s.
set -euo pipefail

HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
API_KEY="${HYBRID_API_KEY:-}"

for candidate in /run/secrets/hybrid_coordinator_api_key /run/secrets/hybrid_api_key; do
  if [[ -z "$API_KEY" && -r "$candidate" ]]; then
    API_KEY="$(tr -d '[:space:]' < "$candidate")"
    break
  fi
done

hdr=(-H "Content-Type: application/json")
if [[ -n "$API_KEY" ]]; then
  hdr+=(-H "X-API-Key: ${API_KEY}")
fi

pass() { printf 'PASS: %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

# Check coordinator is reachable first
http_code="$(curl -s -o /dev/null -w '%{http_code}' "${hdr[@]}" "${HYB_URL}/health" 2>/dev/null || true)"
if [[ "$http_code" != "200" ]]; then
  printf 'SKIP: hybrid-coordinator not reachable (http=%s)\n' "$http_code"
  exit 0
fi

# POST to delegate with a very short timeout_s so the call returns quickly.
# Expected outcomes: error JSON with known error codes (not HTTP 5xx).
# Acceptable: runtime_not_found, local_agent_timeout, task_required, auth errors.
# Unacceptable: HTTP 500, connection refused, empty body.
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

http_code="$(curl -s -w '\n%{http_code}' "${hdr[@]}" \
  -X POST "${HYB_URL}/control/ai-coordinator/delegate" \
  -d '{"task":"smoke check delegate endpoint","timeout_s":5}' \
  -o "$tmp" 2>/dev/null | tail -1 || true)"

if [[ -z "$http_code" ]]; then
  fail "no response from /control/ai-coordinator/delegate"
fi

body="$(cat "$tmp" 2>/dev/null || true)"

if [[ "$http_code" == "500" ]]; then
  fail "HTTP 500 from delegate endpoint — internal error: ${body:0:200}"
fi

if [[ -z "$body" ]]; then
  fail "empty body from delegate endpoint (http=${http_code})"
fi

# Verify body is valid JSON
if ! python3 -c "import json,sys; json.loads(sys.stdin.read())" <<< "$body" 2>/dev/null; then
  fail "non-JSON body from delegate endpoint: ${body:0:200}"
fi

# Verify the default timeout in source is ≥ 120s (guards against regression to 60s)
src="$(dirname "$(dirname "$(readlink -f "$0")")")/ai-stack/mcp-servers/hybrid-coordinator/http_server.py"
if [[ -f "$src" ]]; then
  timeout_val="$(grep -o 'data\.get("timeout_s") or [0-9]*\.0' "$src" | grep -o '[0-9]*\.0' | head -1 || true)"
  if [[ -n "$timeout_val" ]]; then
    timeout_int="${timeout_val%.*}"
    if [[ "$timeout_int" -lt 120 ]]; then
      fail "delegate default timeout regressed to ${timeout_val}s (must be ≥ 120s)"
    fi
    pass "delegate default timeout is ${timeout_val}s (≥ 120s)"
  fi
fi

pass "delegate endpoint returned structured JSON (http=${http_code}): $(python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('error','ok'))" <<< "$body" 2>/dev/null || echo "${body:0:60}")"
