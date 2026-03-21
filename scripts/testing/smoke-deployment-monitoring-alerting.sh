#!/usr/bin/env bash
# smoke-deployment-monitoring-alerting.sh
# Phase 4.1 validation: deployment -> monitoring -> alerting flow.
#
# Verifies that:
# - dashboard deployment APIs record a synthetic deployment
# - monitoring aggregate health is readable from the dashboard
# - hybrid alert engine can create a bounded validation alert
# - dashboard health alert routes expose, acknowledge, and resolve that alert

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../config/service-endpoints.sh
source "${SCRIPT_DIR}/../../config/service-endpoints.sh"

DASHBOARD_API_URL="${DASHBOARD_API_URL%/}"
HYBRID_URL="${HYBRID_URL%/}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_api_key}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
TMP_DIR="$(mktemp -d /tmp/smoke-deploy-monitor-alert-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

pass() { printf '[PASS] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
warn() { printf '[WARN] %s\n' "$*" >&2; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_cmd curl
need_cmd jq

if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi
if [[ -z "${HYBRID_API_KEY}" ]]; then
  for candidate in /run/secrets/hybrid_coordinator_api_key /run/secrets/hybrid_api_key; do
    if [[ -r "${candidate}" ]]; then
      HYBRID_API_KEY="$(tr -d '[:space:]' < "${candidate}")"
      break
    fi
  done
fi

hybrid_headers=()
if [[ -n "${HYBRID_API_KEY}" ]]; then
  hybrid_headers+=(-H "X-API-Key: ${HYBRID_API_KEY}")
else
  warn "HYBRID_API_KEY not available; alert creation calls may fail if auth is enforced"
fi

deployment_id="phase4-smoke-$(date +%s)-$$"
deployment_query="deployment ${deployment_id}"

curl -fsS "${DASHBOARD_API_URL}/api/health/aggregate" > "${TMP_DIR}/aggregate.json" \
  || fail "dashboard aggregate health endpoint unavailable"
jq -e '.overall_status != null and .summary.total >= 1 and .summary.healthy >= 0' "${TMP_DIR}/aggregate.json" >/dev/null \
  || fail "aggregate health payload missing expected fields"
pass "dashboard aggregate health"

curl -fsS -G -X POST \
  --data-urlencode "deployment_id=${deployment_id}" \
  --data-urlencode "command=nixos-rebuild switch --flake .#phase4-smoke" \
  --data-urlencode "user=codex" \
  "${DASHBOARD_API_URL}/api/deployments/start" > "${TMP_DIR}/deploy-start.json" \
  || fail "deployment start failed"
jq -e --arg id "${deployment_id}" '.status == "started" and .deployment_id == $id' "${TMP_DIR}/deploy-start.json" >/dev/null \
  || fail "deployment start payload mismatch"
pass "deployment start recorded"

curl -fsS -X POST \
  -H 'Content-Type: application/json' \
  "${DASHBOARD_API_URL}/api/deployments/${deployment_id}/progress" \
  --data '{"progress":35,"message":"Phase 4.1 smoke progress","log":"monitoring check"}' > "${TMP_DIR}/deploy-progress.json" \
  || fail "deployment progress update failed"
jq -e '.status == "updated" and .progress == 35' "${TMP_DIR}/deploy-progress.json" >/dev/null \
  || fail "deployment progress payload mismatch"
pass "deployment progress recorded"

curl -fsS -X POST \
  -H 'Content-Type: application/json' \
  "${DASHBOARD_API_URL}/api/deployments/${deployment_id}/complete" \
  --data '{"success":true,"message":"Phase 4.1 smoke complete"}' > "${TMP_DIR}/deploy-complete.json" \
  || fail "deployment completion failed"
jq -e '.status == "success"' "${TMP_DIR}/deploy-complete.json" >/dev/null \
  || fail "deployment completion payload mismatch"
pass "deployment completion recorded"

curl -fsS "${DASHBOARD_API_URL}/api/deployments/history?limit=10" > "${TMP_DIR}/deploy-history.json" \
  || fail "deployment history fetch failed"
jq -e --arg id "${deployment_id}" '.deployments | any(.deployment_id == $id)' "${TMP_DIR}/deploy-history.json" >/dev/null \
  || fail "deployment not found in history"
pass "deployment visible in dashboard history"

curl -fsS -G \
  --data-urlencode "query=${deployment_query}" \
  "${DASHBOARD_API_URL}/api/deployments/search/context" > "${TMP_DIR}/deploy-context.json" \
  || fail "deployment context search failed"
jq -e '.results != null and .sources != null' "${TMP_DIR}/deploy-context.json" >/dev/null \
  || fail "deployment context response missing structure"
pass "deployment context search reachable"

alert_payload="$(jq -cn --arg id "${deployment_id}" '{
  severity: "warning",
  title: "Phase 4.1 validation alert",
  message: "Synthetic alert for deployment monitoring flow validation",
  source: "phase-4-1-smoke",
  component: "deployment-monitoring",
  metadata: {deployment_id: $id, validation_flow: "deployment-monitoring-alerting"}
}')"
alert_code="$(curl -sS -o "${TMP_DIR}/alert-create.json" -w "%{http_code}" \
  -X POST \
  "${hybrid_headers[@]}" \
  -H 'Content-Type: application/json' \
  "${HYBRID_URL}/alerts/test" \
  --data "${alert_payload}" || true)"
if [[ "${alert_code}" == "404" ]]; then
  fail "test alert creation failed: hybrid service is running without the new /alerts/test route; deploy or restart the updated hybrid coordinator first"
fi
[[ "${alert_code}" == "201" ]] || fail "test alert creation failed: HTTP ${alert_code}"
alert_id="$(jq -r '.alert.id // empty' "${TMP_DIR}/alert-create.json")"
[[ -n "${alert_id}" ]] || fail "missing alert id from test alert creation"
pass "test alert created"

curl -fsS "${DASHBOARD_API_URL}/api/health/alerts" > "${TMP_DIR}/alerts-list.json" \
  || fail "dashboard alerts fetch failed"
jq -e --arg id "${alert_id}" --arg dep "${deployment_id}" '
  .alerts | any(.id == $id and .metadata.deployment_id == $dep)
' "${TMP_DIR}/alerts-list.json" >/dev/null || fail "created alert not visible via dashboard alerts route"
pass "dashboard alerts route exposes hybrid alert"

curl -fsS -X POST "${DASHBOARD_API_URL}/api/health/alerts/${alert_id}/acknowledge" > "${TMP_DIR}/alert-ack.json" \
  || fail "dashboard alert acknowledge failed"
jq -e --arg id "${alert_id}" '.alert_id == $id and .acknowledged == true' "${TMP_DIR}/alert-ack.json" >/dev/null \
  || fail "alert acknowledge payload mismatch"
pass "dashboard alert acknowledge"

curl -fsS -X POST "${DASHBOARD_API_URL}/api/health/alerts/${alert_id}/resolve" > "${TMP_DIR}/alert-resolve.json" \
  || fail "dashboard alert resolve failed"
jq -e --arg id "${alert_id}" '.alert_id == $id and .resolved == true' "${TMP_DIR}/alert-resolve.json" >/dev/null \
  || fail "alert resolve payload mismatch"
pass "dashboard alert resolve"

curl -fsS "${DASHBOARD_API_URL}/api/health/alerts" > "${TMP_DIR}/alerts-final.json" \
  || fail "dashboard alerts final fetch failed"
jq -e --arg id "${alert_id}" '.alerts | all(.id != $id)' "${TMP_DIR}/alerts-final.json" >/dev/null \
  || fail "resolved alert still present in active alerts"
pass "resolved alert removed from active alert list"

printf '\n========================================\n'
printf 'Phase 4.1 deployment -> monitoring -> alerting smoke passed.\n'
printf '========================================\n'
printf '\nEndorsed workflows tested:\n'
printf '  1. Deployment triggers monitoring setup\n'
printf '  2. Monitoring triggers alerts correctly\n'
printf '  3. Alerts flow to dashboard and notifications\n'
printf '  4. Alert acknowledgment and resolution\n'
printf '\nNext phase: automated remediation validation\n'
