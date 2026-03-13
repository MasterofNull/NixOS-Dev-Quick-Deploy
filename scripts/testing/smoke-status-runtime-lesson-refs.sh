#!/usr/bin/env bash
set -euo pipefail

HYBRID_URL="${HYBRID_COORDINATOR_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY="${HYBRID_COORDINATOR_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_COORDINATOR_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"

if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi

if [[ -z "${HYBRID_API_KEY}" ]]; then
  echo "HYBRID_COORDINATOR_API_KEY is required" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d /tmp/status-runtime-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")
json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")

curl -fsS "${hdr[@]}" "${HYBRID_URL}/status" > "${TMP_DIR}/status.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/status.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/stats" > "${TMP_DIR}/stats.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/stats.json" >/dev/null

runtime_id="lesson-parity-runtime-$$"

cat > "${TMP_DIR}/register.json.payload" <<JSON
{
  "runtime_id": "${runtime_id}",
  "name": "Lesson parity runtime",
  "profile": "default",
  "status": "ready",
  "runtime_class": "generic",
  "transport": "http",
  "tags": ["lesson-parity", "smoke"],
  "source": "smoke-status-runtime-lesson-refs"
}
JSON

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/control/runtimes/register" \
  --data @"${TMP_DIR}/register.json.payload" > "${TMP_DIR}/register.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/register.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/control/runtimes" > "${TMP_DIR}/list.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/list.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/control/runtimes/${runtime_id}" > "${TMP_DIR}/get.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/get.json" >/dev/null

cat > "${TMP_DIR}/runtime-status.json.payload" <<JSON
{
  "status": "degraded",
  "note": "lesson ref parity smoke"
}
JSON

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/control/runtimes/${runtime_id}/status" \
  --data @"${TMP_DIR}/runtime-status.json.payload" > "${TMP_DIR}/runtime-status.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/runtime-status.json" >/dev/null

cat > "${TMP_DIR}/deploy.json.payload" <<JSON
{
  "deployment_id": "lesson-parity-deploy",
  "version": "smoke",
  "profile": "default",
  "target": "local",
  "status": "deployed",
  "note": "lesson ref parity smoke"
}
JSON

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/control/runtimes/${runtime_id}/deployments" \
  --data @"${TMP_DIR}/deploy.json.payload" > "${TMP_DIR}/deploy.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/deploy.json" >/dev/null

cat > "${TMP_DIR}/rollback.json.payload" <<JSON
{
  "to_deployment_id": "lesson-parity-deploy",
  "reason": "lesson ref parity smoke"
}
JSON

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/control/runtimes/${runtime_id}/rollback" \
  --data @"${TMP_DIR}/rollback.json.payload" > "${TMP_DIR}/rollback.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/rollback.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/control/runtimes/schedule/policy" > "${TMP_DIR}/schedule-policy.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/schedule-policy.json" >/dev/null

cat > "${TMP_DIR}/schedule.json.payload" <<JSON
{
  "objective": "select a bounded runtime for lesson reference parity smoke",
  "requirements": {
    "transport": "http",
    "tags": ["lesson-parity"]
  }
}
JSON

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/control/runtimes/schedule/select" \
  --data @"${TMP_DIR}/schedule.json.payload" > "${TMP_DIR}/schedule.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/schedule.json" >/dev/null

echo "PASS: status, stats, and runtime control endpoints surface active lesson refs"
