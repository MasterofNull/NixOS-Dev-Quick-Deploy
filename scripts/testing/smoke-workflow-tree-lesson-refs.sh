#!/usr/bin/env bash
set -euo pipefail

# Verify workflow tree and session-branch helpers surface active lesson refs.

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

TMP_DIR="$(mktemp -d /tmp/workflow-tree-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT
json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")
hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")

cat > "${TMP_DIR}/start.json.payload" <<'EOF'
{
  "query": "Validate workflow tree lesson references",
  "blueprint_id": "deploy-rollback-safe-ops",
  "intent_contract": {
    "user_intent": "Validate workflow tree lesson references",
    "definition_of_done": [
      "workflow tree and branch helpers surface active lesson refs"
    ],
    "depth_expectation": "standard",
    "spirit_constraints": [
      "bounded smoke only"
    ],
    "no_early_exit_without": [
      "tree and branch responses"
    ]
  }
}
EOF

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/workflow/session/start" \
  --data @"${TMP_DIR}/start.json.payload" > "${TMP_DIR}/start.json"
session_id="$(jq -r '.session_id // empty' "${TMP_DIR}/start.json")"
[[ -n "${session_id}" ]] || {
  echo "ERROR: workflow/session/start did not return session_id" >&2
  exit 1
}
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/start.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/workflow/tree" > "${TMP_DIR}/tree.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/tree.json" >/dev/null

cat > "${TMP_DIR}/fork.json.payload" <<'EOF'
{
  "note": "lesson ref parity smoke"
}
EOF
curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/workflow/session/${session_id}/fork" \
  --data @"${TMP_DIR}/fork.json.payload" > "${TMP_DIR}/fork.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/fork.json" >/dev/null
forked_session_id="$(jq -r '.session_id // empty' "${TMP_DIR}/fork.json")"
[[ -n "${forked_session_id}" ]] || {
  echo "ERROR: workflow/session fork did not return session_id" >&2
  exit 1
}

cat > "${TMP_DIR}/advance.json.payload" <<'EOF'
{
  "action": "note",
  "note": "bounded lesson ref parity smoke"
}
EOF
curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/workflow/session/${session_id}/advance" \
  --data @"${TMP_DIR}/advance.json.payload" > "${TMP_DIR}/advance.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/advance.json" >/dev/null

printf 'PASS: workflow tree and branch helpers surface active lesson refs\n'
