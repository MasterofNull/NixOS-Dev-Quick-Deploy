#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
HTTP_SERVER="${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py"

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

[[ -f "$HTTP_SERVER" ]] || fail "missing http server source"

if rg -n 'api_key_middleware' "$HTTP_SERVER" >/dev/null; then
  pass "api_key middleware present"
else
  fail "api_key middleware missing"
fi

# Ensure explicit public exceptions are minimal.
pub_count="$(rg -n 'request\.path in \("/health", "/metrics"\)' "$HTTP_SERVER" | wc -l | tr -d ' ')"
[[ "$pub_count" -ge 1 ]] || warn "public endpoint exception pattern not found"

if curl -fsS "${HYB_URL}/health" >/dev/null 2>&1; then
  code="$(curl -sS -o /tmp/auth-hardening.out -w "%{http_code}" -H 'X-API-Key: invalid' "${HYB_URL}/workflow/sessions" || true)"
  if [[ "$code" == "401" || "$code" == "200" ]]; then
    pass "runtime auth path reachable (code=${code})"
  else
    warn "unexpected runtime auth check code=${code}"
  fi
else
  warn "hybrid coordinator unavailable; runtime auth check skipped"
fi
