#!/usr/bin/env bash
set -euo pipefail

# Verify workflow plan/hints/start APIs preserve reviewer-contract expectations.

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

TMP_DIR="$(mktemp -d /tmp/workflow-review-smoke-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT
hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")
json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")
plan_query='validate workflow review contract'

curl -fsS "${hdr[@]}" "${HYBRID_URL}/workflow/plan?q=${plan_query// /%20}" > "${TMP_DIR}/plan.json"
jq -e '.phases | length >= 5' "${TMP_DIR}/plan.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/hints?q=${plan_query// /%20}" > "${TMP_DIR}/hints.json"
jq -e '(.hints // []) | length >= 1' "${TMP_DIR}/hints.json" >/dev/null

cat > "${TMP_DIR}/start.json.payload" <<'EOF'
{
  "query": "Validate workflow review contract persistence",
  "blueprint_id": "continue-editor-rescue",
  "intent_contract": {
    "user_intent": "Validate workflow review contract persistence",
    "definition_of_done": [
      "session stores blueprint title",
      "reviewer gate persists acceptance"
    ],
    "depth_expectation": "standard",
    "spirit_constraints": [
      "bounded smoke only"
    ],
    "no_early_exit_without": [
      "live session retrieval"
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
jq -e '.blueprint_id == "continue-editor-rescue"' "${TMP_DIR}/start.json" >/dev/null
jq -e '.reviewer_gate.required == true and .reviewer_gate.status == "pending_review"' "${TMP_DIR}/start.json" >/dev/null

cat > "${TMP_DIR}/review.json.payload" <<EOF
{
  "session_id": "${session_id}",
  "response": "Session stores blueprint title Continue / Editor Rescue and reviewer gate persists acceptance.",
  "criteria": [
    "blueprint title",
    "reviewer gate"
  ],
  "expected_keywords": [
    "continue / editor rescue",
    "acceptance"
  ],
  "min_criteria_ratio": 1.0,
  "min_keyword_ratio": 1.0,
  "reviewer": "codex"
}
EOF
curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/review/acceptance" \
  --data @"${TMP_DIR}/review.json.payload" > "${TMP_DIR}/review.json"
jq -e '.passed == true' "${TMP_DIR}/review.json" >/dev/null
jq -e --arg sid "${session_id}" '.session_id == $sid' "${TMP_DIR}/review.json" >/dev/null
jq -e '.reviewer_gate.required == true and .reviewer_gate.status == "accepted"' "${TMP_DIR}/review.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/workflow/run/${session_id}" > "${TMP_DIR}/run.json"
jq -e '.blueprint_title == "Continue / Editor Rescue"' "${TMP_DIR}/run.json" >/dev/null
jq -e '.reviewer_gate.required == true and .reviewer_gate.status == "accepted"' "${TMP_DIR}/run.json" >/dev/null
jq -e '(.reviewer_gate.history // []) | length >= 1' "${TMP_DIR}/run.json" >/dev/null
jq -e '.trajectory_count >= 2' "${TMP_DIR}/run.json" >/dev/null

printf 'PASS: workflow review contract smoke\n'
