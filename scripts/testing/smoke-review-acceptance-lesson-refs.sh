#!/usr/bin/env bash
set -euo pipefail

# Verify review acceptance responses surface active lesson refs for reviewer traceability.

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

TMP_DIR="$(mktemp -d /tmp/review-acceptance-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT
hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")
json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")

cat > "${TMP_DIR}/start.json.payload" <<'EOF'
{
  "query": "Validate review acceptance lesson references",
  "blueprint_id": "coding-bugfix-safe",
  "intent_contract": {
    "user_intent": "Validate review acceptance lesson references",
    "definition_of_done": [
      "review acceptance returns active lesson refs"
    ],
    "depth_expectation": "standard",
    "spirit_constraints": [
      "bounded smoke only"
    ],
    "no_early_exit_without": [
      "live review response"
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

cat > "${TMP_DIR}/review.json.payload" <<EOF
{
  "session_id": "${session_id}",
  "response": "Acceptance review confirms the bounded bugfix path preserves explicit validation evidence and rollback notes.",
  "criteria": [
    "validation evidence",
    "rollback notes"
  ],
  "expected_keywords": [
    "acceptance review",
    "bugfix"
  ],
  "min_criteria_ratio": 1.0,
  "min_keyword_ratio": 1.0,
  "reviewer": "codex",
  "review_type": "acceptance",
  "artifact_kind": "response",
  "task_class": "coding_bugfix",
  "reviewed_agent": "qwen",
  "reviewed_profile": "remote-coding"
}
EOF

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/review/acceptance" \
  --data @"${TMP_DIR}/review.json.payload" > "${TMP_DIR}/review.json"

jq -e '.passed == true' "${TMP_DIR}/review.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/review.json" >/dev/null
jq -e '.reviewer_gate.status == "accepted"' "${TMP_DIR}/review.json" >/dev/null

printf 'PASS: review acceptance surfaces active lesson refs\n'
