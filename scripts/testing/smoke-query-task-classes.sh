#!/usr/bin/env bash
set -euo pipefail

# Verify query responses expose orchestration, coaching, and lesson task-class metadata.

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

TMP_DIR="$(mktemp -d /tmp/query-task-classes-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

post_query_with_retry() {
  local payload_file="$1"
  local output_file="$2"
  local attempt=1
  local max_attempts=8
  local http_code
  local retry_after

  while (( attempt <= max_attempts )); do
    http_code="$(
      curl -sS -o "${output_file}" -w '%{http_code}' \
        -H "X-API-Key: ${HYBRID_API_KEY}" \
        -H "Content-Type: application/json" \
        -X POST "${HYBRID_URL}/query" \
        --data @"${payload_file}"
    )"
    if [[ "${http_code}" == "429" ]]; then
      retry_after="$(jq -r '.retry_after_seconds // 2' "${output_file}" 2>/dev/null || printf '2')"
      sleep "${retry_after}"
      attempt=$((attempt + 1))
      continue
    fi
    [[ "${http_code}" == "200" ]] || {
      echo "ERROR: /query returned HTTP ${http_code}" >&2
      cat "${output_file}" >&2
      return 1
    }
    return 0
  done

  echo "ERROR: /query remained rate-limited after ${max_attempts} attempts" >&2
  cat "${output_file}" >&2 || true
  return 1
}

cat > "${TMP_DIR}/bugfix.json.payload" <<'EOF'
{
  "query": "debug this failing regression safely and keep the bugfix bounded with explicit validation",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "continue",
  "requesting_agent": "continue",
  "requester_role": "orchestrator"
}
EOF

post_query_with_retry "${TMP_DIR}/bugfix.json.payload" "${TMP_DIR}/bugfix.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/bugfix.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/bugfix.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/bugfix.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/bugfix.json" >/dev/null

cat > "${TMP_DIR}/hardening.json.payload" <<'EOF'
{
  "query": "harden this nixos service declaratively and preserve health checks plus rollback guidance",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "codex",
  "requesting_agent": "codex",
  "requester_role": "orchestrator"
}
EOF

post_query_with_retry "${TMP_DIR}/hardening.json.payload" "${TMP_DIR}/hardening.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/hardening.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/hardening.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/hardening.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/hardening.json" >/dev/null

cat > "${TMP_DIR}/prsi.json.payload" <<'EOF'
{
  "query": "run one pessimistic self-improvement cycle with rollback and strict validation gates",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "codex",
  "requesting_agent": "codex",
  "requester_role": "orchestrator"
}
EOF

post_query_with_retry "${TMP_DIR}/prsi.json.payload" "${TMP_DIR}/prsi.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/prsi.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/prsi.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/prsi.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/prsi.json" >/dev/null

cat > "${TMP_DIR}/continue.json.payload" <<'EOF'
{
  "query": "continue editor rescue: codium extension is failing and continue-local may be broken",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "continue",
  "requesting_agent": "continue",
  "requester_role": "orchestrator"
}
EOF

post_query_with_retry "${TMP_DIR}/continue.json.payload" "${TMP_DIR}/continue.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/continue.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/continue.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/continue.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/continue.json" >/dev/null

cat > "${TMP_DIR}/deploy.json.payload" <<'EOF'
{
  "query": "deploy this nixos service safely and include rollback plus live verification",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "codex",
  "requesting_agent": "codex",
  "requester_role": "orchestrator"
}
EOF

post_query_with_retry "${TMP_DIR}/deploy.json.payload" "${TMP_DIR}/deploy.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/deploy.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/deploy.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/deploy.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/deploy.json" >/dev/null

cat > "${TMP_DIR}/review.json.payload" <<'EOF'
{
  "query": "review this patch safely and call out regressions first with concrete evidence",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "codex",
  "requesting_agent": "codex",
  "requester_role": "orchestrator"
}
EOF

post_query_with_retry "${TMP_DIR}/review.json.payload" "${TMP_DIR}/review.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/review.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/review.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/review.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/review.json" >/dev/null

cat > "${TMP_DIR}/research.json.payload" <<'EOF'
{
  "query": "research and summarize a source-bounded web dataset with retrieval evidence and explicit stop conditions",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "continue",
  "requesting_agent": "continue",
  "requester_role": "orchestrator"
}
EOF

post_query_with_retry "${TMP_DIR}/research.json.payload" "${TMP_DIR}/research.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/research.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/research.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/research.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/research.json" >/dev/null

cat > "${TMP_DIR}/skills.json.payload" <<'EOF'
{
  "query": "sync this approved agentskill source into the shared skill registry and expose it to local agents with validation",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "codex",
  "requesting_agent": "codex",
  "requester_role": "orchestrator"
}
EOF

post_query_with_retry "${TMP_DIR}/skills.json.payload" "${TMP_DIR}/skills.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/skills.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/skills.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/skills.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/skills.json" >/dev/null

cat > "${TMP_DIR}/delegate.json.payload" <<'EOF'
{
  "query": "delegate this bounded coordinator task and keep sub-agent fan-out disabled while returning a reviewable artifact",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "codex",
  "requesting_agent": "codex",
  "requester_role": "orchestrator"
}
EOF

post_query_with_retry "${TMP_DIR}/delegate.json.payload" "${TMP_DIR}/delegate.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/delegate.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/delegate.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/delegate.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/delegate.json" >/dev/null

printf 'PASS: query task-class smoke\n'
