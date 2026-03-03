#!/usr/bin/env bash
set -euo pipefail

HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

if ! curl -fsS "${HYB_URL}/health" >/dev/null 2>&1; then
  warn "hybrid coordinator unavailable at ${HYB_URL}; skipping chaos smoke"
  exit 0
fi

# malformed payload to ensure server returns controlled 4xx/5xx json
code="$(curl -sS -o /tmp/chaos-query.out -w "%{http_code}" -H 'Content-Type: application/json' "${HYB_URL}/query" --data '{"prompt":""}' || true)"
if [[ "$code" != "400" ]]; then
  fail "expected 400 on empty query payload, got ${code}"
fi
pass "input validation under malformed request"

# invalid action for workflow/session advance should be handled safely
sid="$(curl -fsS -H 'Content-Type: application/json' "${HYB_URL}/workflow/session/start" --data '{"query":"chaos test"}' | jq -r '.session_id')"
[[ -n "$sid" ]] || fail "failed to create session"
code="$(curl -sS -o /tmp/chaos-advance.out -w "%{http_code}" -H 'Content-Type: application/json' "${HYB_URL}/workflow/session/${sid}/advance" --data '{"action":"explode"}' || true)"
if [[ "$code" != "400" ]]; then
  fail "expected 400 for invalid action, got ${code}"
fi
pass "workflow guards under invalid transition input"
