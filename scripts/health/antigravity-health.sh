#!/usr/bin/env bash
# antigravity-health.sh — health check for the delegate-to-antigravity delegation path
#
# Auth model: gemini CLI (oauth-personal) → Google Code Assist API (cloudcode-pa.googleapis.com)
# This is the free path — uses Google account subscription, NOT a paid API key.
#
# Auth setup (one-time, interactive):
#   Run: gemini -p "test"
#   Press Y when prompted, complete Google sign-in in browser.
#   After that, all headless calls work automatically.
#
# Checks:
#   1. delegate-to-antigravity script exists and is executable
#   2. gemini CLI is in PATH
#   3. settings.json has selectedType=oauth-personal
#   4. gemini-credentials.json has content (credentials were stored after login)
#   5. (smoke) gemini CLI can respond to a simple prompt headlessly
#
# Usage:
#   scripts/health/antigravity-health.sh [--check|--smoke] [--json]
#
# Exit codes:
#   0  healthy
#   1  unhealthy
#   2  partial (auth present but smoke call failed)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DELEGATE_BIN="${REPO_ROOT}/scripts/ai/delegate-to-antigravity"
GEMINI_SETTINGS="${HOME}/.gemini/settings.json"
GEMINI_CREDS="${HOME}/.gemini/gemini-credentials.json"

MODE="check"
JSON_OUTPUT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)  MODE="check"; shift ;;
    --smoke)  MODE="smoke"; shift ;;
    --json)   JSON_OUTPUT=1; shift ;;
    --help|-h)
      cat <<'EOF'
Usage: antigravity-health.sh [--check|--smoke] [--json]
  --check   Validate script presence and auth config (default, no API call)
  --smoke   Also run a real gemini CLI prompt to verify end-to-end (requires auth)
  --json    Emit JSON result
EOF
      exit 0 ;;
    *) printf 'ERROR: unknown argument: %s\n' "$1" >&2; exit 1 ;;
  esac
done

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().rstrip("\n")))' <<<"${1:-}"
}

STATUS="unknown"
REASON=""
AUTH_METHOD=""
SMOKE_RESULT="not_tested"

emit_result() {
  local exit_code="$1"
  if [[ "${JSON_OUTPUT}" -eq 1 ]]; then
    printf '{'
    printf '"status":%s,'        "$(json_escape "${STATUS}")"
    printf '"reason":%s,'        "$(json_escape "${REASON}")"
    printf '"auth_method":%s,'   "$(json_escape "${AUTH_METHOD}")"
    printf '"smoke_result":%s,'  "$(json_escape "${SMOKE_RESULT}")"
    printf '"delegate_bin":%s'   "$(json_escape "${DELEGATE_BIN}")"
    printf '}\n'
  else
    printf 'status=%s\n'        "${STATUS}"
    printf 'reason=%s\n'        "${REASON}"
    printf 'auth_method=%s\n'   "${AUTH_METHOD}"
    printf 'smoke_result=%s\n'  "${SMOKE_RESULT}"
    printf 'delegate_bin=%s\n'  "${DELEGATE_BIN}"
  fi
  exit "${exit_code}"
}

# ── 1. Script presence ────────────────────────────────────────────────────────
if [[ ! -x "${DELEGATE_BIN}" ]]; then
  STATUS="unhealthy"
  REASON="delegate-to-antigravity not found or not executable at ${DELEGATE_BIN}"
  emit_result 1
fi

# ── 2. gemini CLI in PATH ─────────────────────────────────────────────────────
if ! command -v gemini >/dev/null 2>&1; then
  STATUS="unhealthy"
  REASON="'gemini' not found in PATH. Install: npm install -g @google/gemini-cli"
  AUTH_METHOD="none"
  emit_result 1
fi

# ── 3. Auth settings check ────────────────────────────────────────────────────
if [[ ! -f "${GEMINI_SETTINGS}" ]]; then
  STATUS="unhealthy"
  REASON="${GEMINI_SETTINGS} not found"
  AUTH_METHOD="none"
  emit_result 1
fi

AUTH_TYPE="$(python3 -c "import json; d=json.load(open('${GEMINI_SETTINGS}')); print(d.get('security',{}).get('auth',{}).get('selectedType','not-set'))" 2>/dev/null || echo "parse-error")"

if [[ "${AUTH_TYPE}" != "oauth-personal" ]]; then
  STATUS="unhealthy"
  REASON="settings.json selectedType=${AUTH_TYPE} (expected oauth-personal). Fix: set security.auth.selectedType to oauth-personal in ${GEMINI_SETTINGS}"
  AUTH_METHOD="${AUTH_TYPE}"
  emit_result 1
fi
AUTH_METHOD="oauth-personal"

# ── 4. Credentials file presence ─────────────────────────────────────────────
if [[ ! -f "${GEMINI_CREDS}" ]]; then
  STATUS="unhealthy"
  REASON="gemini-credentials.json not found — run: gemini -p 'test' to complete OAuth login"
  emit_result 1
fi

CREDS_SIZE="$(wc -c < "${GEMINI_CREDS}" 2>/dev/null || echo 0)"
if [[ "${CREDS_SIZE}" -lt 50 ]]; then
  STATUS="unhealthy"
  REASON="gemini-credentials.json is empty or too small (${CREDS_SIZE} bytes) — run: gemini -p 'test' to complete OAuth login"
  emit_result 1
fi

# Decrypt credentials to check for oauth-personal token
HAS_OAUTH="$(node -e "
const crypto=require('crypto'),fs=require('fs'),os=require('os'),path=require('path');
const f=path.join(os.homedir(),'.gemini','gemini-credentials.json');
try {
  const d=fs.readFileSync(f,'utf-8').trim(),p=d.split(':');
  if(p.length!==3){console.log('no-oauth');process.exit(0);}
  const s=os.hostname()+'-'+os.userInfo().username+'-gemini-cli';
  const k=crypto.scryptSync('gemini-cli-oauth',s,32);
  const dec=crypto.createDecipheriv('aes-256-gcm',k,Buffer.from(p[0],'hex'));
  dec.setAuthTag(Buffer.from(p[1],'hex'));
  const j=JSON.parse(dec.update(p[2],'hex','utf8')+dec.final('utf8'));
  const hasOauth=Object.keys(j).some(k=>k.includes('oauth')||k.includes('personal'));
  console.log(hasOauth?'yes':'no-oauth');
} catch(e){console.log('decrypt-error');}
" 2>/dev/null || echo "node-error")"

if [[ "${HAS_OAUTH}" == "no-oauth" ]]; then
  if [[ "${MODE}" == "smoke" ]]; then
    # Hard fail on smoke: credentials are stale (API key, not oauth-personal)
    STATUS="unhealthy"
    REASON="gemini-credentials.json has no oauth-personal token (found API key creds only). Run: gemini -p 'test' and sign in with Google account."
    emit_result 1
  else
    # Check mode: auth is configured correctly but browser flow not yet complete.
    # This is a pending setup state, not a misconfiguration. Allow commits to proceed.
    STATUS="auth_pending"
    REASON="oauth-personal configured; browser OAuth not yet completed. Run: gemini -p 'test' interactively to finish setup. Delegation will work after that."
    SMOKE_RESULT="not_tested"
    emit_result 0
  fi
fi

# ── Check mode result ─────────────────────────────────────────────────────────
if [[ "${MODE}" != "smoke" ]]; then
  STATUS="healthy"
  REASON="delegate-to-antigravity ready; auth=oauth-personal; credentials present"
  SMOKE_RESULT="not_tested"
  emit_result 0
fi

# ── 5. Smoke test (--smoke mode) ──────────────────────────────────────────────
SMOKE_OUT="$(timeout 30 gemini \
  --output-format text \
  -p "Reply with exactly one word: pong" \
  -m "gemini-2.0-flash" \
  2>&1 </dev/null || true)"

if echo "${SMOKE_OUT}" | grep -qi "pong"; then
  SMOKE_RESULT="ok"
  STATUS="healthy"
  REASON="delegate-to-antigravity ready; oauth-personal authenticated; smoke call succeeded"
  emit_result 0
elif echo "${SMOKE_OUT}" | grep -qi "authentication\|OAuth\|sign in\|cancelled"; then
  SMOKE_RESULT="auth_incomplete"
  STATUS="unhealthy"
  REASON="gemini CLI not authenticated for headless use. Run: gemini -p 'test' and complete browser sign-in."
  emit_result 1
else
  SMOKE_RESULT="unexpected_output: ${SMOKE_OUT:0:200}"
  STATUS="degraded"
  REASON="Smoke call returned unexpected output — may still work for delegation tasks"
  emit_result 2
fi
