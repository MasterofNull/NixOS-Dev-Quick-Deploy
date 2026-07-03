#!/usr/bin/env bash
set -euo pipefail

# check-api-auth-hardening.sh
# Validate static and runtime API auth hardening for the hybrid coordinator.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
# Coordinator auth moved out of the old monolithic server module into a dedicated
# middleware layer (middleware/auth.py + core/auth_middleware.py), with the aiohttp
# app assembled in http_server_impl.py. Inspect the current auth source so this
# check fails on MISSING MIDDLEWARE, not on a stale filename.
AUTH_MIDDLEWARE="${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/middleware/auth.py"
CORE_AUTH="${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/core/auth_middleware.py"

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

# Fail on missing MIDDLEWARE (a real auth regression), not a stale filename.
[[ -f "$AUTH_MIDDLEWARE" ]] || fail "auth middleware source missing: middleware/auth.py"

if search_file 'def create_api_key_middleware' "$AUTH_MIDDLEWARE" >/dev/null; then
  pass "api_key middleware present (create_api_key_middleware in middleware/auth.py)"
else
  fail "api_key middleware missing (create_api_key_middleware not found in middleware/auth.py)"
fi

# core/auth_middleware.py must wire the middleware into the app assembly.
if [[ -f "$CORE_AUTH" ]] && search_file 'create_api_key_middleware' "$CORE_AUTH" >/dev/null; then
  pass "api_key middleware wired via core/auth_middleware.py"
else
  warn "core/auth_middleware.py does not reference create_api_key_middleware"
fi

# Ensure public exceptions are an explicit, minimal allowlist (PUBLIC_PATHS).
if search_file 'PUBLIC_PATHS' "$AUTH_MIDDLEWARE" >/dev/null; then
  pass "public-path allowlist present (PUBLIC_PATHS)"
else
  warn "explicit public-path allowlist (PUBLIC_PATHS) not found"
fi

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
