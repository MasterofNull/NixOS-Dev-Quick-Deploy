#!/usr/bin/env bash
# antigravity-health.sh — health check for the delegate-to-antigravity delegation path
#
# Checks:
#   1. delegate-to-antigravity script exists and is executable
#   2. gcloud ADC credentials present (primary auth)
#   3. Fallback auth available (SOPS key or env var)
#   4. Gemini REST API reachable (models list endpoint)
#   5. Optional: submit a minimal live delegation and verify output
#
# Usage:
#   scripts/health/antigravity-health.sh [--check|--smoke] [--json]
#
# Exit codes:
#   0  healthy
#   1  degraded / unhealthy
#   2  partial (some checks pass, API unreachable but auth present)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DELEGATE_BIN="${REPO_ROOT}/scripts/ai/delegate-to-antigravity"
ADC_PATH="${HOME}/.config/gcloud/application_default_credentials.json"
SOPS_KEY_PATH="/run/secrets/gemini_api_key"
MODELS_URL="https://generativelanguage.googleapis.com/v1beta/models"

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
  --check   Validate auth and script presence (default, no API call)
  --smoke   Also hit the Gemini models endpoint to verify API reachability
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
API_REACHABLE="unknown"

emit_result() {
  local exit_code="$1"
  if [[ "${JSON_OUTPUT}" -eq 1 ]]; then
    printf '{'
    printf '"status":%s,'        "$(json_escape "${STATUS}")"
    printf '"reason":%s,'        "$(json_escape "${REASON}")"
    printf '"auth_method":%s,'   "$(json_escape "${AUTH_METHOD}")"
    printf '"api_reachable":%s,' "$(json_escape "${API_REACHABLE}")"
    printf '"delegate_bin":%s'   "$(json_escape "${DELEGATE_BIN}")"
    printf '}\n'
  else
    printf 'status=%s\n'        "${STATUS}"
    printf 'reason=%s\n'        "${REASON}"
    printf 'auth_method=%s\n'   "${AUTH_METHOD}"
    printf 'api_reachable=%s\n' "${API_REACHABLE}"
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

# ── 2. Auth detection ─────────────────────────────────────────────────────────
if [[ -f "${ADC_PATH}" ]]; then
  # Verify the ADC file is parseable and contains a refresh_token
  VALID_ADC="$(python3 -c "
import json, sys
try:
    d = json.load(open('${ADC_PATH}'))
    print('yes' if d.get('refresh_token') else 'no_token')
except Exception as e:
    print('error:' + str(e))
" 2>/dev/null || echo 'error:parse')"
  if [[ "${VALID_ADC}" == "yes" ]]; then
    AUTH_METHOD="adc"
  else
    AUTH_METHOD="adc_invalid:${VALID_ADC}"
  fi
elif [[ -r "${SOPS_KEY_PATH}" ]]; then
  AUTH_METHOD="sops_key"
elif [[ -n "${GEMINI_API_KEY:-}" ]]; then
  AUTH_METHOD="env_var"
else
  STATUS="unhealthy"
  REASON="no auth available: ADC missing (${ADC_PATH}), SOPS key missing (${SOPS_KEY_PATH}), GEMINI_API_KEY not set. Run: gcloud auth application-default login"
  AUTH_METHOD="none"
  emit_result 1
fi

# Warn if ADC is present but invalid (still check API reachability with fallback)
if [[ "${AUTH_METHOD}" == adc_invalid:* ]]; then
  REASON="ADC file present but invalid (${AUTH_METHOD}); falling back to API key"
  if [[ -r "${SOPS_KEY_PATH}" ]]; then
    AUTH_METHOD="sops_key"
  elif [[ -n "${GEMINI_API_KEY:-}" ]]; then
    AUTH_METHOD="env_var"
  else
    STATUS="unhealthy"
    REASON="ADC invalid and no API key fallback available"
    emit_result 1
  fi
fi

# ── 3. API reachability (smoke mode only) ─────────────────────────────────────
if [[ "${MODE}" == "smoke" ]]; then
  # Resolve auth header for the models-list probe
  if [[ "${AUTH_METHOD}" == "adc" ]]; then
    ACCESS_TOKEN="$(python3 -c "
import json, urllib.request, urllib.parse
creds = json.load(open('${ADC_PATH}'))
data = urllib.parse.urlencode({
    'client_id':     creds['client_id'],
    'client_secret': creds['client_secret'],
    'refresh_token': creds['refresh_token'],
    'grant_type':    'refresh_token',
}).encode()
req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
print(resp.get('access_token', ''))
" 2>/dev/null || true)"
    AUTH_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"
  else
    KEY="$(cat "${SOPS_KEY_PATH}" 2>/dev/null | tr -d '[:space:]' || echo "${GEMINI_API_KEY:-}")"
    AUTH_HEADER="x-goog-api-key: ${KEY}"
  fi

  HTTP_CODE="$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "${AUTH_HEADER}" \
    --max-time 10 \
    "${MODELS_URL}" 2>/dev/null || echo "000")"

  if [[ "${HTTP_CODE}" =~ ^2 ]]; then
    API_REACHABLE="yes"
  elif [[ "${HTTP_CODE}" == "429" ]]; then
    API_REACHABLE="rate_limited"
  elif [[ "${HTTP_CODE}" == "000" ]]; then
    API_REACHABLE="unreachable"
  else
    API_REACHABLE="http_${HTTP_CODE}"
  fi

  if [[ "${API_REACHABLE}" == "yes" ]]; then
    STATUS="healthy"
    REASON="delegate-to-antigravity ready; auth=${AUTH_METHOD}; API reachable"
    emit_result 0
  elif [[ "${API_REACHABLE}" == "rate_limited" ]]; then
    STATUS="degraded"
    REASON="auth OK (${AUTH_METHOD}) but API rate limited (429)"
    emit_result 2
  else
    STATUS="degraded"
    REASON="auth OK (${AUTH_METHOD}) but API unreachable (${API_REACHABLE}) — check network"
    emit_result 2
  fi
fi

# ── Default --check result ────────────────────────────────────────────────────
API_REACHABLE="not_tested"
STATUS="healthy"
REASON="delegate-to-antigravity present and auth=${AUTH_METHOD} available (API not probed; run --smoke to test)"
emit_result 0
