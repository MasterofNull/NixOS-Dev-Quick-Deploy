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

TMP_DIR="$(mktemp -d /tmp/workflow-orchestrate-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")
hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")

cat > "${TMP_DIR}/orchestrate.json.payload" <<'JSON'
{
  "prompt": "Run a bounded lesson-reference parity orchestration smoke without nested delegation.",
  "backend": "codex",
  "max_iterations": 1,
  "require_approval": false,
  "context": {
    "requesting_agent": "codex",
    "requester_role": "orchestrator"
  }
}
JSON

post_status="$(
  curl -sS -o "${TMP_DIR}/orchestrate.json" -w '%{http_code}' \
    "${json_hdr[@]}" -X POST "${HYBRID_URL}/workflow/orchestrate" \
    --data @"${TMP_DIR}/orchestrate.json.payload"
)"

jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/orchestrate.json" >/dev/null

task_id="$(jq -r '.task_id // .id // empty' "${TMP_DIR}/orchestrate.json")"
if [[ -z "${task_id}" ]]; then
  echo "PASS: workflow orchestrate entrypoint surfaces active lesson refs (HTTP ${post_status})"
  exit 0
fi

curl -sS "${hdr[@]}" "${HYBRID_URL}/workflow/orchestrate/${task_id}" > "${TMP_DIR}/orchestrate-status.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/orchestrate-status.json" >/dev/null

echo "PASS: workflow orchestrate endpoints surface active lesson refs"
