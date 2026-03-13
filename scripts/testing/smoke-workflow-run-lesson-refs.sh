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

TMP_DIR="$(mktemp -d /tmp/workflow-run-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

cat > "${TMP_DIR}/run-start.json.payload" <<'EOF'
{
  "query": "continue editor rescue with lesson traceability",
  "blueprint_id": "continue-editor-rescue",
  "requesting_agent": "codex",
  "requester_role": "orchestrator"
}
EOF

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "${HYBRID_URL}/workflow/run/start" \
  --data @"${TMP_DIR}/run-start.json.payload" > "${TMP_DIR}/run-start.json"

session_id="$(jq -r '.session_id // empty' "${TMP_DIR}/run-start.json")"
[[ -n "${session_id}" ]] || {
  echo "ERROR: workflow/run/start did not return session_id" >&2
  exit 1
}

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  "${HYBRID_URL}/workflow/run/${session_id}" > "${TMP_DIR}/run.json"

jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/run.json" >/dev/null
jq -e '.reviewer_gate.required == true' "${TMP_DIR}/run.json" >/dev/null

printf 'PASS: workflow/run/{session_id} surfaces active lesson refs\n'
