#!/usr/bin/env bash
set -euo pipefail

HYBRID_URL="${HYBRID_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"

if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi
if [[ -z "${HYBRID_API_KEY}" && -r "/run/secrets/hybrid_api_key" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < /run/secrets/hybrid_api_key)"
fi
[[ -n "${HYBRID_API_KEY}" ]] || {
  echo "ERROR: missing HYBRID_API_KEY or readable key file" >&2
  exit 2
}

TMP_JSON="$(mktemp /tmp/status-report-summary-XXXXXX.json)"
trap 'rm -f "${TMP_JSON}"' EXIT

http_code="$(
  curl -sS -o "${TMP_JSON}" -w '%{http_code}' \
    -H "X-API-Key: ${HYBRID_API_KEY}" \
    "${HYBRID_URL}/control/ai-coordinator/status"
)"
[[ "${http_code}" == "200" ]] || {
  echo "ERROR: status returned HTTP ${http_code}" >&2
  cat "${TMP_JSON}" >&2
  exit 1
}

jq -e '.report_summary.available == true' "${TMP_JSON}" >/dev/null
jq -e '.report_summary.remote_profile_utilization.trend_24h != null' "${TMP_JSON}" >/dev/null
jq -e '.report_summary.routing.trend_24h != null' "${TMP_JSON}" >/dev/null
jq -e '.report_summary.retrieval.trend_24h != null' "${TMP_JSON}" >/dev/null
jq -e '.report_summary.continue_editor.trend_24h != null' "${TMP_JSON}" >/dev/null
jq -e '.report_summary.workflow_review.required_reviews >= 0' "${TMP_JSON}" >/dev/null

printf 'PASS: ai-coordinator status exposes compact aq-report summary\n'
