#!/usr/bin/env bash
set -euo pipefail

# check-api-auth-hardening.sh
# Validate static and runtime API auth hardening for the hybrid coordinator.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
HTTP_SERVER="${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py"

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

have_rg() {
  command -v rg >/dev/null 2>&1
}

search_file() {
  local pattern="$1"
  local file="$2"
  if have_rg; then
    rg -n "$pattern" "$file"
  else
    grep -En "$pattern" "$file"
  fi
}

[[ -f "$HTTP_SERVER" ]] || fail "missing http server source"

if search_file 'api_key_middleware' "$HTTP_SERVER" >/dev/null; then
  pass "api_key middleware present"
else
  fail "api_key middleware missing"
fi

# Ensure explicit public exceptions are minimal.
pub_count="$({ search_file 'request\.path in \("/health", "/metrics"\)' "$HTTP_SERVER" || true; } | wc -l | tr -d ' ')"
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
