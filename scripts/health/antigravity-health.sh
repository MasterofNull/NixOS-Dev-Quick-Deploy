#!/usr/bin/env bash
# antigravity-health.sh — health check for the delegate-to-antigravity delegation path
#
# NOTE: generativelanguage.googleapis.com only accepts API keys.
# gcloud ADC / OAuth2 Bearer tokens are rejected with ACCESS_TOKEN_SCOPE_INSUFFICIENT.
# Auth is always via x-goog-api-key header (free-tier AI Studio key, no billing needed).
#
# Checks:
#   1. delegate-to-antigravity script exists and is executable
#   2. API key available (SOPS /run/secrets/gemini_api_key or GEMINI_API_KEY env var)
#   3. (smoke) Gemini REST API reachable using key
#
# Usage:
#   scripts/health/antigravity-health.sh [--check|--smoke] [--json]
#
# Exit codes:
#   0  healthy
#   1  unhealthy
#   2  partial (auth OK but API unreachable / rate limited)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DELEGATE_BIN="${REPO_ROOT}/scripts/ai/delegate-to-antigravity"
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
  --check   Validate script presence and API key availability (default, no API call)
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
API_KEY=""

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

# ── 2. API key detection ──────────────────────────────────────────────────────
# generativelanguage.googleapis.com only accepts API keys, not OAuth2/ADC.
if [[ -r "${SOPS_KEY_PATH}" ]] && [[ -s "${SOPS_KEY_PATH}" ]]; then
  API_KEY="$(tr -d '[:space:]' < "${SOPS_KEY_PATH}")"
  AUTH_METHOD="sops_key"
elif [[ -n "${GEMINI_API_KEY:-}" ]]; then
  API_KEY="${GEMINI_API_KEY}"
  AUTH_METHOD="env_var"
else
  STATUS="unhealthy"
  REASON="no API key found: SOPS key missing (${SOPS_KEY_PATH}), GEMINI_API_KEY not set. Create a free key at https://aistudio.google.com/apikey then: sops <secrets-file> → gemini_api_key: AIza..."
  AUTH_METHOD="none"
  emit_result 1
fi

# ── 3. API reachability (smoke mode only) ─────────────────────────────────────
if [[ "${MODE}" == "smoke" ]]; then
  HTTP_CODE="$(curl -s -o /dev/null -w "%{http_code}" \
    -H "x-goog-api-key: ${API_KEY}" \
    --max-time 10 \
    "${MODELS_URL}" 2>/dev/null)" || HTTP_CODE="000"

  case "${HTTP_CODE}" in
    2??)  API_REACHABLE="yes" ;;
    429)  API_REACHABLE="rate_limited" ;;
    000)  API_REACHABLE="unreachable" ;;
    *)    API_REACHABLE="http_${HTTP_CODE}" ;;
  esac

  case "${API_REACHABLE}" in
    yes)
      STATUS="healthy"
      REASON="delegate-to-antigravity ready; auth=${AUTH_METHOD}; API reachable"
      emit_result 0
      ;;
    rate_limited)
      STATUS="degraded"
      REASON="API key valid (${AUTH_METHOD}) but rate limited (429) — wait and retry"
      emit_result 2
      ;;
    *)
      STATUS="unhealthy"
      REASON="API key present (${AUTH_METHOD}) but API unreachable (${API_REACHABLE}) — check key validity or network"
      emit_result 1
      ;;
  esac
fi

# ── Default --check result ────────────────────────────────────────────────────
API_REACHABLE="not_tested"
STATUS="healthy"
REASON="delegate-to-antigravity present; auth=${AUTH_METHOD} available (run --smoke to test API reachability)"
emit_result 0
