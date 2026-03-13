#!/usr/bin/env bash
set -euo pipefail

# Verify workflow runtime helper endpoints surface active lesson refs.

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

TMP_DIR="$(mktemp -d /tmp/workflow-runtime-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT
json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")
hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")

cat > "${TMP_DIR}/start.json.payload" <<'EOF'
{
  "query": "Validate workflow runtime helper lesson references",
  "blueprint_id": "repo-refactor-guarded",
  "intent_contract": {
    "user_intent": "Validate workflow runtime helper lesson references",
    "definition_of_done": [
      "runtime helper responses surface active lesson refs"
    ],
    "depth_expectation": "standard",
    "spirit_constraints": [
      "bounded smoke only"
    ],
    "no_early_exit_without": [
      "live runtime helper responses"
    ]
  }
}
EOF

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/workflow/run/start" \
  --data @"${TMP_DIR}/start.json.payload" > "${TMP_DIR}/start.json"
session_id="$(jq -r '.session_id // empty' "${TMP_DIR}/start.json")"
[[ -n "${session_id}" ]] || {
  echo "ERROR: workflow/run/start did not return session_id" >&2
  exit 1
}

cat > "${TMP_DIR}/mode.json.payload" <<'EOF'
{
  "safety_mode": "plan-readonly"
}
EOF
curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/workflow/run/${session_id}/mode" \
  --data @"${TMP_DIR}/mode.json.payload" > "${TMP_DIR}/mode.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/mode.json" >/dev/null

cat > "${TMP_DIR}/event.json.payload" <<'EOF'
{
  "event_type": "note",
  "risk_class": "safe",
  "approved": false,
  "token_delta": 0,
  "tool_call_delta": 0,
  "detail": "bounded runtime helper lesson smoke"
}
EOF
curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/workflow/run/${session_id}/event" \
  --data @"${TMP_DIR}/event.json.payload" > "${TMP_DIR}/event.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/event.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/workflow/run/${session_id}/replay" > "${TMP_DIR}/replay.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/replay.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/workflow/blueprints" > "${TMP_DIR}/blueprints.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/blueprints.json" >/dev/null

printf 'PASS: workflow runtime helpers surface active lesson refs\n'
