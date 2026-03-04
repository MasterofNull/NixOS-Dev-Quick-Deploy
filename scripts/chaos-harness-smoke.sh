#!/usr/bin/env bash
set -euo pipefail

HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi

headers=(-H 'Content-Type: application/json')
if [[ -n "${HYBRID_API_KEY}" ]]; then
  headers+=(-H "X-API-Key: ${HYBRID_API_KEY}")
fi

if ! curl -fsS "${HYB_URL}/health" >/dev/null 2>&1; then
  warn "hybrid coordinator unavailable at ${HYB_URL}; skipping chaos smoke"
  exit 0
fi

# malformed payload to ensure server returns controlled 4xx/5xx json
code="$(curl -sS -o /tmp/chaos-query.out -w "%{http_code}" "${headers[@]}" "${HYB_URL}/query" --data '{"prompt":""}' || true)"
if [[ "$code" == "401" && -z "${HYBRID_API_KEY}" ]]; then
  pass "auth guard active under malformed request without API key"
elif [[ "$code" != "400" ]]; then
  fail "expected 400 on empty query payload, got ${code}"
else
  pass "input validation under malformed request"
fi

# invalid action for workflow/session advance should be handled safely
sid_resp="$(curl -sS -o /tmp/chaos-session.out -w "%{http_code}" "${headers[@]}" "${HYB_URL}/workflow/session/start" --data '{"query":"chaos test"}' || true)"
if [[ "$sid_resp" == "401" && -z "${HYBRID_API_KEY}" ]]; then
  pass "auth guard active for workflow/session/start without API key"
  exit 0
fi
[[ "$sid_resp" == "200" ]] || fail "expected 200 for workflow/session/start, got ${sid_resp}"
sid="$(jq -r '.session_id // empty' /tmp/chaos-session.out)"
[[ -n "$sid" ]] || fail "failed to create session"
code="$(curl -sS -o /tmp/chaos-advance.out -w "%{http_code}" "${headers[@]}" "${HYB_URL}/workflow/session/${sid}/advance" --data '{"action":"explode"}' || true)"
if [[ "$code" != "400" ]]; then
  fail "expected 400 for invalid action, got ${code}"
fi
pass "workflow guards under invalid transition input"
