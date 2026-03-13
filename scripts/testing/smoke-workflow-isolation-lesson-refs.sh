#!/usr/bin/env bash
set -euo pipefail

# Verify workflow isolation get/set responses surface active lesson refs.

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

TMP_DIR="$(mktemp -d /tmp/workflow-isolation-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT
hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")
json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")

cat > "${TMP_DIR}/start.json.payload" <<'EOF'
{
  "query": "Validate workflow isolation lesson references",
  "blueprint_id": "continue-editor-rescue",
  "intent_contract": {
    "user_intent": "Validate workflow isolation lesson references",
    "definition_of_done": [
      "workflow isolation responses surface active lesson refs"
    ],
    "depth_expectation": "standard",
    "spirit_constraints": [
      "bounded smoke only"
    ],
    "no_early_exit_without": [
      "live isolation responses"
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

curl -fsS "${hdr[@]}" "${HYBRID_URL}/workflow/run/${session_id}/isolation" > "${TMP_DIR}/isolation-get.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/isolation-get.json" >/dev/null

cat > "${TMP_DIR}/isolation-set.json.payload" <<'EOF'
{
  "profile": "workspace-write",
  "workspace_root": "/tmp/lesson-ref-smoke",
  "network_policy": "restricted"
}
EOF

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/workflow/run/${session_id}/isolation" \
  --data @"${TMP_DIR}/isolation-set.json.payload" > "${TMP_DIR}/isolation-set.json"

jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/isolation-set.json" >/dev/null
jq -e '.isolation.profile == "workspace-write"' "${TMP_DIR}/isolation-set.json" >/dev/null

printf 'PASS: workflow isolation surfaces active lesson refs\n'
