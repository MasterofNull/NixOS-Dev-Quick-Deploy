#!/usr/bin/env bash
set -euo pipefail

# Verify bounded delegated remote lanes either succeed directly or settle into explicit fallback with a final non-failure contract.

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

TMP_DIR="$(mktemp -d /tmp/remote-delegation-lanes-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

run_lane() {
  local profile="$1"
  local out_file="${TMP_DIR}/${profile}.json"

  cat > "${TMP_DIR}/${profile}.payload" <<EOF
{
  "profile": "${profile}",
  "task": "Return READY and one evidence bullet only.",
  "requesting_agent": "codex",
  "requester_role": "orchestrator",
  "messages": [
    {"role": "user", "content": "Reply in the delegated contract with READY and exactly one evidence bullet."}
  ],
  "max_tokens": 96,
  "temperature": 0
}
EOF

  curl -fsS \
    -H "X-API-Key: ${HYBRID_API_KEY}" \
    -H "Content-Type: application/json" \
    -X POST "${HYBRID_URL}/control/ai-coordinator/delegate" \
    --data @"${TMP_DIR}/${profile}.payload" > "${out_file}"

  jq -e '.status == "ok"' "${out_file}" >/dev/null
  jq -e '.orchestration.requester_role == "orchestrator"' "${out_file}" >/dev/null
  jq -e '.active_lesson_refs | length >= 1' "${out_file}" >/dev/null
  jq -e '.delegation_feedback.final.is_failure == false' "${out_file}" >/dev/null
  jq -e '.response.choices[0].message.content | test("(^READY\\b|result:)")' "${out_file}" >/dev/null

  if [[ "${profile}" == "remote-free" ]]; then
    jq -e '.selected_runtime.profile == "remote-free"' "${out_file}" >/dev/null
    jq -e '.fallback.applied == false or .fallback.to_profile == "remote-free"' "${out_file}" >/dev/null
  else
    jq -e --arg profile "${profile}" '.selected_runtime.profile == $profile or .selected_runtime.profile == "remote-free"' "${out_file}" >/dev/null
    jq -e --arg profile "${profile}" '.fallback.applied == false or (.fallback.from_profile == $profile and .fallback.to_profile == "remote-free")' "${out_file}" >/dev/null
  fi
}

run_lane "remote-free"
run_lane "remote-coding"
run_lane "remote-reasoning"

printf 'PASS: delegated remote lanes settle into final bounded outputs\n'
