#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MAX_AGE_SECONDS="${SECURITY_AUDIT_MAX_AGE_SECONDS:-900}"
# shellcheck source=../../config/service-endpoints.sh
source "${ROOT_DIR}/config/service-endpoints.sh"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

pass() {
  printf '[PASS] %s\n' "$1"
}

fail() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

get_json() {
  local url="$1"
  local output="$2"
  curl -fsS --max-time 15 --connect-timeout 5 "$url" > "${output}" \
    || fail "request failed: ${url}"
}

post_json() {
  local url="$1"
  local output="$2"
  local payload="${3:-{}}"
  curl -fsS --max-time 15 --connect-timeout 5 \
    -H 'content-type: application/json' \
    -X POST \
    -d "${payload}" \
    "$url" > "${output}" \
    || fail "request failed: ${url}"
}

get_json "${DASHBOARD_URL%/}/index.html" "${TMP_DIR}/index.json"
pass "dashboard serves /index.html"

get_json "${DASHBOARD_API_URL%/}/api/security/audit" "${TMP_DIR}/security-audit.json"
jq -e '
  .status != null
  and .generated_at != null
  and .report_path != null
  and .dashboard_operator != null
  and .secrets_rotation != null
' "${TMP_DIR}/security-audit.json" >/dev/null \
  || fail "security audit endpoint missing expected report fields"
generated_at="$(jq -r '.generated_at' "${TMP_DIR}/security-audit.json")"
generated_epoch="$(date -d "${generated_at}" +%s 2>/dev/null || true)"
now_epoch="$(date +%s)"
if [[ -z "${generated_epoch}" ]] || (( now_epoch - generated_epoch > MAX_AGE_SECONDS )); then
  fail "security audit endpoint returned stale or invalid generated_at: ${generated_at}"
fi
pass "security audit report is available"

get_json "${DASHBOARD_API_URL%/}/api/insights/security/compliance" "${TMP_DIR}/compliance.json"
jq -e '
  .controls.content_security_policy == true
  and .controls.rate_limiting == true
  and .controls.operator_audit_log == true
  and .controls.tamper_evident_audit_sealing == true
  and .controls.dashboard_security_scan_automation == true
  and .controls.secrets_rotation_planning == true
' "${TMP_DIR}/compliance.json" >/dev/null \
  || fail "security compliance endpoint missing required controls"
pass "security compliance controls are exposed"

get_json "${DASHBOARD_API_URL%/}/api/audit/operator/summary?limit=50" "${TMP_DIR}/audit-summary.json"
jq -e '
  .append_only == true
  and .tamper_evident == true
  and (.total_events // 0) >= 1
' "${TMP_DIR}/audit-summary.json" >/dev/null \
  || fail "audit summary missing append-only or tamper-evident evidence"
pass "audit summary reports append-only tamper-evident state"

get_json "${DASHBOARD_API_URL%/}/api/audit/operator/events?limit=50&path_prefix=/api/security" "${TMP_DIR}/audit-security-events.json"
jq -e '
  (.events | length) >= 1
  and all(.events[]; .path | startswith("/api/security/"))
' "${TMP_DIR}/audit-security-events.json" >/dev/null \
  || fail "security route reads not captured in operator audit log"
pass "security route reads are captured in operator audit log"

get_json "${DASHBOARD_API_URL%/}/api/audit/operator/events?limit=50&contains=security%2Fcompliance" "${TMP_DIR}/audit-compliance-events.json"
jq -e '
  any(.events[]?; .path == "/api/insights/security/compliance")
' "${TMP_DIR}/audit-compliance-events.json" >/dev/null \
  || fail "security compliance read missing from operator audit log"
pass "security compliance reads are captured in operator audit log"

get_json "${DASHBOARD_API_URL%/}/api/audit/operator/integrity" "${TMP_DIR}/audit-integrity.json"
jq -e '
  .valid == true
  and .seal_algorithm == "sha256-chain-v1"
  and (.checked_events // 0) >= 1
' "${TMP_DIR}/audit-integrity.json" >/dev/null \
  || fail "audit integrity endpoint did not report a valid chain"
pass "audit integrity validates"

printf '\nPhase 4.3 smoke passed: security -> audit -> compliance flow is live.\n'
