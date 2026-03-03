#!/usr/bin/env bash
set -euo pipefail

SWB_URL="${SWB_URL:-http://127.0.0.1:8085}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
TMP_DIR="$(mktemp -d /tmp/smoke-agent-harness-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

pass() { printf '[PASS] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_cmd curl
need_cmd jq

model_id="$(curl -fsS "${SWB_URL}/v1/models" | jq -r '.data[0].id // empty')"
[[ -n "$model_id" ]] || fail "could not detect switchboard model id"
pass "detected model: ${model_id}"

chat_req() {
  local profile="$1"
  local prompt="$2"
  local hdr="${TMP_DIR}/hdr-${profile}.txt"
  local body="${TMP_DIR}/body-${profile}.json"
  local payload="${TMP_DIR}/req-${profile}.json"
  cat >"$payload" <<EOF
{"model":"${model_id}","messages":[{"role":"user","content":"${prompt}"}],"temperature":0,"max_tokens":20}
EOF
  curl --max-time 90 -sS -D "$hdr" -o "$body" \
    -H 'Content-Type: application/json' \
    -H "X-AI-Profile: ${profile}" \
    "${SWB_URL}/v1/chat/completions" \
    --data @"$payload" || return 1
  tr -d '\r' <"$hdr" >"${hdr}.norm"
  rg -qi '^x-ai-profile:' "${hdr}.norm" || fail "${profile}: missing x-ai-profile header"
  rg -qi '^x-ai-retrieval-confidence:' "${hdr}.norm" || fail "${profile}: missing x-ai-retrieval-confidence header"
  jq -e '.choices[0].message.content? != null or .error? != null' "$body" >/dev/null || fail "${profile}: invalid response payload"
  pass "profile ${profile} chat request"
}

chat_req "continue-local" "smoke test continue local"
chat_req "embedded-assist" "smoke test embedded assist"

# embedding-local profile should allow /v1/embeddings and block chat.
emb_payload="${TMP_DIR}/req-embedding.json"
cat >"$emb_payload" <<EOF
{"model":"${model_id}","input":["smoke embedding profile"]}
EOF
curl --max-time 30 -sS -D "${TMP_DIR}/hdr-embedding.txt" -o "${TMP_DIR}/body-embedding.json" \
  -H 'Content-Type: application/json' \
  -H 'X-AI-Profile: embedding-local' \
  "${SWB_URL}/v1/embeddings" \
  --data @"$emb_payload" || fail "embedding-local: embeddings request failed"
jq -e '.data[0].embedding? != null or .error? != null' "${TMP_DIR}/body-embedding.json" >/dev/null || fail "embedding-local: invalid response"
pass "profile embedding-local embeddings request"

# remote-default: pass if remote works, or skip when explicitly unconfigured.
remote_payload="${TMP_DIR}/req-remote.json"
cat >"$remote_payload" <<EOF
{"model":"${model_id}","messages":[{"role":"user","content":"smoke remote profile"}],"temperature":0,"max_tokens":10}
EOF
if curl --max-time 30 -sS -D "${TMP_DIR}/hdr-remote.txt" -o "${TMP_DIR}/body-remote.json" \
  -H 'Content-Type: application/json' \
  -H 'X-AI-Profile: remote-default' \
  "${SWB_URL}/v1/chat/completions" \
  --data @"$remote_payload"; then
  if jq -e '.error.type == "route_configuration_error"' "${TMP_DIR}/body-remote.json" >/dev/null 2>&1; then
    warn "profile remote-default skipped (REMOTE_LLM_URL not configured)"
  else
    pass "profile remote-default chat request"
  fi
else
  warn "profile remote-default request failed; treating as non-blocking in this smoke run"
fi

# Workflow plan/session endpoints
plan_resp="${TMP_DIR}/workflow-plan.json"
curl -fsS "${HYB_URL}/workflow/plan?q=validate%20nixos%20deploy%20and%20continue%20chat" >"$plan_resp"
jq -e '.phases | length >= 5' "$plan_resp" >/dev/null || fail "workflow/plan: expected at least 5 phases"
pass "workflow/plan endpoint"

start_resp="${TMP_DIR}/workflow-start.json"
curl -fsS -H 'Content-Type: application/json' \
  "${HYB_URL}/workflow/session/start" \
  --data '{"query":"diagnose local and remote profile smoke failures"}' >"$start_resp"
session_id="$(jq -r '.session_id // empty' "$start_resp")"
[[ -n "$session_id" ]] || fail "workflow/session/start: missing session_id"
pass "workflow/session/start endpoint"

curl -fsS "${HYB_URL}/workflow/session/${session_id}" >"${TMP_DIR}/workflow-get.json"
jq -e '.status == "in_progress" or .status == "completed"' "${TMP_DIR}/workflow-get.json" >/dev/null || fail "workflow/session/get: invalid status"
pass "workflow/session/get endpoint"

curl -fsS "${HYB_URL}/workflow/session/${session_id}?lineage=true" >"${TMP_DIR}/workflow-lineage.json"
jq -e '.lineage | length >= 1' "${TMP_DIR}/workflow-lineage.json" >/dev/null || fail "workflow/session/get?lineage=true: missing lineage"
pass "workflow/session/get lineage endpoint"

curl -fsS "${HYB_URL}/workflow/sessions" >"${TMP_DIR}/workflow-list.json"
jq -e '.count >= 1' "${TMP_DIR}/workflow-list.json" >/dev/null || fail "workflow/sessions: expected at least one session"
pass "workflow/sessions endpoint"

curl -fsS -H 'Content-Type: application/json' \
  "${HYB_URL}/workflow/session/${session_id}/fork" \
  --data '{"note":"smoke branch test"}' >"${TMP_DIR}/workflow-fork.json"
forked_session_id="$(jq -r '.session_id // empty' "${TMP_DIR}/workflow-fork.json")"
[[ -n "${forked_session_id}" ]] || fail "workflow/session/fork: missing forked session id"
pass "workflow/session/fork endpoint"

curl -fsS "${HYB_URL}/workflow/tree" >"${TMP_DIR}/workflow-tree.json"
jq -e '.count >= 2 and (.edges | length >= 1)' "${TMP_DIR}/workflow-tree.json" >/dev/null || fail "workflow/tree expected at least one fork edge"
pass "workflow/tree endpoint"

curl -fsS -H 'Content-Type: application/json' \
  "${HYB_URL}/workflow/session/${session_id}/advance" \
  --data '{"action":"pass","note":"discover phase complete"}' >"${TMP_DIR}/workflow-advance.json"
jq -e '.current_phase_index >= 1 or .status == "completed"' "${TMP_DIR}/workflow-advance.json" >/dev/null || fail "workflow/session/advance did not progress"
pass "workflow/session/advance endpoint"

# Reviewer acceptance endpoint
review_payload="${TMP_DIR}/review.json"
cat >"$review_payload" <<'EOF'
{
  "query": "verify switchboard headers are present",
  "response": "Verified: x-ai-profile and x-ai-retrieval-confidence headers are present in responses.",
  "criteria": [
    "x-ai-profile",
    "x-ai-retrieval-confidence"
  ],
  "expected_keywords": [
    "verified",
    "headers"
  ],
  "min_criteria_ratio": 1.0,
  "min_keyword_ratio": 0.5,
  "run_harness_eval": false
}
EOF
curl -fsS -H 'Content-Type: application/json' \
  "${HYB_URL}/review/acceptance" \
  --data @"$review_payload" >"${TMP_DIR}/review-resp.json"
jq -e '.passed == true' "${TMP_DIR}/review-resp.json" >/dev/null || fail "review/acceptance expected pass=true"
pass "review/acceptance endpoint"

printf '\nAll parity smoke tests completed successfully.\n'
