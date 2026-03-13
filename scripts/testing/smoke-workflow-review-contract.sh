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
jq -e '.reviewer_gate.last_review.review_type == "acceptance"' "${TMP_DIR}/run.json" >/dev/null
jq -e '.reviewer_gate.last_review.task_class == "continue_editor_rescue"' "${TMP_DIR}/run.json" >/dev/null

cat > "${TMP_DIR}/patch-start.json.payload" <<'EOF'
{
  "query": "Validate repo refactor patch review persistence",
  "blueprint_id": "repo-refactor-guarded",
  "intent_contract": {
    "user_intent": "Validate repo refactor patch review persistence",
    "definition_of_done": [
      "patch review classification persists",
      "reviewed agent is recorded"
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
  --data @"${TMP_DIR}/patch-start.json.payload" > "${TMP_DIR}/patch-start.json"
patch_session_id="$(jq -r '.session_id // empty' "${TMP_DIR}/patch-start.json")"
[[ -n "${patch_session_id}" ]] || {
  echo "ERROR: repo patch workflow/run/start did not return session_id" >&2
  exit 1
}
jq -e '.blueprint_id == "repo-refactor-guarded"' "${TMP_DIR}/patch-start.json" >/dev/null
jq -e '.reviewer_gate.required == true and .reviewer_gate.status == "pending_review"' "${TMP_DIR}/patch-start.json" >/dev/null

cat > "${TMP_DIR}/patch-review.json.payload" <<EOF
{
  "session_id": "${patch_session_id}",
  "response": "Patch review confirms repo refactor diff keeps declarative guardrails and bounded service wiring.",
  "criteria": [
    "declarative guardrails",
    "bounded service wiring"
  ],
  "expected_keywords": [
    "patch review",
    "repo refactor"
  ],
  "min_criteria_ratio": 1.0,
  "min_keyword_ratio": 1.0,
  "reviewer": "codex",
  "review_type": "patch_review",
  "artifact_kind": "patch",
  "task_class": "repo_refactor",
  "reviewed_agent": "qwen",
  "reviewed_profile": "remote-coding"
}
EOF
curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/review/acceptance" \
  --data @"${TMP_DIR}/patch-review.json.payload" > "${TMP_DIR}/patch-review.json"
jq -e '.passed == true' "${TMP_DIR}/patch-review.json" >/dev/null
jq -e --arg sid "${patch_session_id}" '.session_id == $sid' "${TMP_DIR}/patch-review.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/workflow/run/${patch_session_id}" > "${TMP_DIR}/patch-run.json"
jq -e '.blueprint_title == "Repository Refactor (Guarded)"' "${TMP_DIR}/patch-run.json" >/dev/null
jq -e '.reviewer_gate.required == true and .reviewer_gate.status == "accepted"' "${TMP_DIR}/patch-run.json" >/dev/null
jq -e '.reviewer_gate.last_review.review_type == "patch_review"' "${TMP_DIR}/patch-run.json" >/dev/null
jq -e '.reviewer_gate.last_review.artifact_kind == "patch"' "${TMP_DIR}/patch-run.json" >/dev/null
jq -e '.reviewer_gate.last_review.task_class == "repo_refactor"' "${TMP_DIR}/patch-run.json" >/dev/null
jq -e '.reviewer_gate.last_review.reviewed_agent == "qwen"' "${TMP_DIR}/patch-run.json" >/dev/null
jq -e '.reviewer_gate.last_review.reviewed_profile == "remote-coding"' "${TMP_DIR}/patch-run.json" >/dev/null

cat > "${TMP_DIR}/reasoning-start.json.payload" <<'EOF'
{
  "query": "Validate remote reasoning review persistence",
  "blueprint_id": "remote-reasoning-escalation",
  "intent_contract": {
    "user_intent": "Validate remote reasoning review persistence",
    "definition_of_done": [
      "plan review classification persists",
      "reviewed profile is recorded"
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
  --data @"${TMP_DIR}/reasoning-start.json.payload" > "${TMP_DIR}/reasoning-start.json"
reasoning_session_id="$(jq -r '.session_id // empty' "${TMP_DIR}/reasoning-start.json")"
[[ -n "${reasoning_session_id}" ]] || {
  echo "ERROR: remote reasoning workflow/run/start did not return session_id" >&2
  exit 1
}
jq -e '.blueprint_id == "remote-reasoning-escalation"' "${TMP_DIR}/reasoning-start.json" >/dev/null
jq -e '.reviewer_gate.required == true and .reviewer_gate.status == "pending_review"' "${TMP_DIR}/reasoning-start.json" >/dev/null

cat > "${TMP_DIR}/reasoning-review.json.payload" <<EOF
{
  "session_id": "${reasoning_session_id}",
  "response": "Plan review confirms remote reasoning escalation preserves bounded evidence and explicit next-step validation.",
  "criteria": [
    "bounded evidence",
    "next-step validation"
  ],
  "expected_keywords": [
    "plan review",
    "remote reasoning"
  ],
  "min_criteria_ratio": 1.0,
  "min_keyword_ratio": 1.0,
  "reviewer": "codex",
  "review_type": "plan_review",
  "artifact_kind": "plan",
  "task_class": "remote_reasoning",
  "reviewed_agent": "claude",
  "reviewed_profile": "remote-reasoning"
}
EOF
curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/review/acceptance" \
  --data @"${TMP_DIR}/reasoning-review.json.payload" > "${TMP_DIR}/reasoning-review.json"
jq -e '.passed == true' "${TMP_DIR}/reasoning-review.json" >/dev/null
jq -e --arg sid "${reasoning_session_id}" '.session_id == $sid' "${TMP_DIR}/reasoning-review.json" >/dev/null

curl -fsS "${hdr[@]}" "${HYBRID_URL}/workflow/run/${reasoning_session_id}" > "${TMP_DIR}/reasoning-run.json"
jq -e '.blueprint_title == "Remote Reasoning Escalation"' "${TMP_DIR}/reasoning-run.json" >/dev/null
jq -e '.reviewer_gate.required == true and .reviewer_gate.status == "accepted"' "${TMP_DIR}/reasoning-run.json" >/dev/null
jq -e '.reviewer_gate.last_review.review_type == "plan_review"' "${TMP_DIR}/reasoning-run.json" >/dev/null
jq -e '.reviewer_gate.last_review.artifact_kind == "plan"' "${TMP_DIR}/reasoning-run.json" >/dev/null
jq -e '.reviewer_gate.last_review.task_class == "remote_reasoning"' "${TMP_DIR}/reasoning-run.json" >/dev/null
jq -e '.reviewer_gate.last_review.reviewed_agent == "claude"' "${TMP_DIR}/reasoning-run.json" >/dev/null
jq -e '.reviewer_gate.last_review.reviewed_profile == "remote-reasoning"' "${TMP_DIR}/reasoning-run.json" >/dev/null

printf 'PASS: workflow review contract smoke\n'
