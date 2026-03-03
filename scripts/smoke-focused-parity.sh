#!/usr/bin/env bash
set -euo pipefail

HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
API_KEY="${HYBRID_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_api_key}"

if [[ -z "$API_KEY" && -r "$HYBRID_API_KEY_FILE" ]]; then
  API_KEY="$(tr -d '[:space:]' < "$HYBRID_API_KEY_FILE")"
fi
if [[ -z "$API_KEY" ]]; then
  for candidate in /run/secrets/hybrid_coordinator_api_key /run/secrets/hybrid_api_key; do
    if [[ -r "$candidate" ]]; then
      API_KEY="$(tr -d '[:space:]' < "$candidate")"
      break
    fi
  done
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

hdr=(-H "Content-Type: application/json")
if [[ -n "$API_KEY" ]]; then
  hdr+=(-H "X-API-Key: ${API_KEY}")
fi

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

curl -fsS "${hdr[@]}" "${HYB_URL}/workflow/blueprints" >"${tmp_dir}/blueprints.json"
jq -e '.count >= 1' "${tmp_dir}/blueprints.json" >/dev/null || fail "workflow/blueprints count"
pass "workflow/blueprints"

curl -fsS "${hdr[@]}" "${HYB_URL}/workflow/run/start" \
  --data '{"query":"focused parity smoke","safety_mode":"plan-readonly","token_limit":64,"tool_call_limit":2}' \
  >"${tmp_dir}/run-start.json"
sid="$(jq -r '.session_id' "${tmp_dir}/run-start.json")"
[[ -n "$sid" && "$sid" != "null" ]] || fail "workflow/run/start missing session_id"
pass "workflow/run/start"

curl -fsS "${hdr[@]}" "${HYB_URL}/workflow/run/${sid}/event" \
  --data '{"event_type":"tool_call","risk_class":"safe","approved":true,"token_delta":10,"tool_call_delta":1,"detail":"safe call"}' \
  >"${tmp_dir}/run-event-safe.json"
jq -e '.usage.tool_calls_used == 1' "${tmp_dir}/run-event-safe.json" >/dev/null || fail "safe event usage update"
pass "workflow/run/{id}/event safe"

curl -fsS "${hdr[@]}" "${HYB_URL}/workflow/run/${sid}/mode" \
  --data '{"safety_mode":"execute-mutating","confirm":true}' \
  >"${tmp_dir}/run-mode.json"
jq -e '.safety_mode == "execute-mutating"' "${tmp_dir}/run-mode.json" >/dev/null || fail "run mode switch"
pass "workflow/run/{id}/mode"

curl -fsS "${hdr[@]}" "${HYB_URL}/workflow/run/${sid}/isolation" >"${tmp_dir}/run-isolation-get.json"
jq -e '.resolved_profile.workspace_root != null' "${tmp_dir}/run-isolation-get.json" >/dev/null || fail "run isolation get"
pass "workflow/run/{id}/isolation get"

curl -fsS "${hdr[@]}" "${HYB_URL}/workflow/run/${sid}/isolation" \
  --data '{"profile":"execute-guarded","workspace_root":"/var/lib/nixos-ai-stack/mutable/program/agent-runs","network_policy":"loopback"}' \
  >"${tmp_dir}/run-isolation-set.json"
jq -e '.isolation.profile == "execute-guarded"' "${tmp_dir}/run-isolation-set.json" >/dev/null || fail "run isolation set"
pass "workflow/run/{id}/isolation set"

code="$(curl -sS -o "${tmp_dir}/run-event-blocked.json" -w "%{http_code}" "${hdr[@]}" \
  "${HYB_URL}/workflow/run/${sid}/event" \
  --data '{"event_type":"tool_call","risk_class":"review-required","approved":false,"token_delta":1,"tool_call_delta":1}' || true)"
[[ "$code" == "403" ]] || fail "review-required event should block without approval"
pass "workflow/run/{id}/event review gate"

code="$(curl -sS -o "${tmp_dir}/run-event-budget.json" -w "%{http_code}" "${hdr[@]}" \
  "${HYB_URL}/workflow/run/${sid}/event" \
  --data '{"event_type":"token_use","risk_class":"safe","approved":true,"token_delta":1000,"tool_call_delta":0}' || true)"
[[ "$code" == "429" ]] || fail "budget overrun should return 429"
pass "workflow/run/{id}/event budget guard"

code="$(curl -sS -o "${tmp_dir}/run-event-isolation.json" -w "%{http_code}" "${hdr[@]}" \
  "${HYB_URL}/workflow/run/${sid}/event" \
  --data '{"event_type":"tool_call","risk_class":"safe","approved":true,"token_delta":1,"tool_call_delta":1,"execution":{"workspace_path":"/etc","process_exec":"bash","network_access":"egress"}}' || true)"
[[ "$code" == "403" ]] || fail "isolation violation should return 403"
pass "workflow/run/{id}/event isolation guard"

curl -fsS "${hdr[@]}" "${HYB_URL}/workflow/run/${sid}/replay" >"${tmp_dir}/run-replay.json"
jq -e '.count >= 2' "${tmp_dir}/run-replay.json" >/dev/null || fail "workflow/run/{id}/replay count"
pass "workflow/run/{id}/replay"

curl -fsS "${hdr[@]}" "${HYB_URL}/control/runtimes/register" \
  --data '{"name":"smoke-runtime","profile":"default","runtime_class":"sandboxed","transport":"http","endpoint_env_var":"HYB_URL","tags":["smoke"]}' \
  >"${tmp_dir}/runtime-register.json"
rid="$(jq -r '.runtime_id' "${tmp_dir}/runtime-register.json")"
[[ -n "$rid" && "$rid" != "null" ]] || fail "runtime register missing id"
pass "control/runtimes/register"

curl -fsS "${hdr[@]}" "${HYB_URL}/control/runtimes/${rid}/deployments" \
  --data '{"version":"v0.1.0","profile":"default","target":"local","status":"deployed"}' \
  >"${tmp_dir}/runtime-deploy.json"
jq -e '.deployment.status == "deployed"' "${tmp_dir}/runtime-deploy.json" >/dev/null || fail "runtime deployment status"
pass "control/runtimes/{id}/deployments"

curl -fsS "${hdr[@]}" "${HYB_URL}/control/runtimes/${rid}/rollback" \
  --data "{\"to_deployment_id\":\"$(jq -r '.deployment.deployment_id' "${tmp_dir}/runtime-deploy.json")\",\"reason\":\"smoke rollback\"}" \
  >"${tmp_dir}/runtime-rollback.json"
jq -e '.status == "recorded"' "${tmp_dir}/runtime-rollback.json" >/dev/null || fail "runtime rollback"
pass "control/runtimes/{id}/rollback"

curl -fsS "${hdr[@]}" "${HYB_URL}/control/runtimes/schedule/policy" >"${tmp_dir}/runtime-schedule-policy.json"
jq -e '.policy.selection.max_candidates >= 1' "${tmp_dir}/runtime-schedule-policy.json" >/dev/null || fail "runtime schedule policy"
pass "control/runtimes/schedule/policy"

curl -fsS "${hdr[@]}" "${HYB_URL}/control/runtimes/schedule/select" \
  --data '{"objective":"smoke schedule","requirements":{"runtime_class":"sandboxed","tags":["smoke"]}}' \
  >"${tmp_dir}/runtime-schedule-select.json"
jq -e '.selected.runtime_id != null' "${tmp_dir}/runtime-schedule-select.json" >/dev/null || fail "runtime schedule select"
pass "control/runtimes/schedule/select"

curl -fsS "${hdr[@]}" "${HYB_URL}/parity/scorecard" >"${tmp_dir}/parity-scorecard.json"
jq -e '.exists == true or .exists == false' "${tmp_dir}/parity-scorecard.json" >/dev/null || fail "parity scorecard endpoint"
pass "/parity/scorecard"

echo "Focused parity smoke checks passed."
