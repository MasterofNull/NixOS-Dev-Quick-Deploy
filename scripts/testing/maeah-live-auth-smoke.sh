#!/usr/bin/env bash
# Post-recovery MAEAH live auth smoke for admin model lifecycle mutations.
set -euo pipefail

DASHBOARD_URL="${EDGEAI_DASHBOARD_URL:-${DASHBOARD_URL:-http://127.0.0.1:8889}}"
API_KEY="${EDGEAI_API_KEY:-${HYBRID_COORDINATOR_API_KEY:-${API_KEY:-}}}"
TIMEOUT="${EDGEAI_TIMEOUT_SECONDS:-5}"
SMOKE_ID="${MAEAH_AUTH_SMOKE_MODEL_ID:-local-auth-smoke}"

usage() {
  cat <<'EOF'
Usage:
  maeah-live-auth-smoke.sh --plan
  maeah-live-auth-smoke.sh --plan-json
  maeah-live-auth-smoke.sh --run

Purpose:
  Validate live /admin/v1/models mutation auth after dashboard/coordinator recovery.
  --plan and --plan-json are offline-safe and do not contact services.

Environment:
  EDGEAI_DASHBOARD_URL or DASHBOARD_URL   default http://127.0.0.1:8889
  EDGEAI_API_KEY or HYBRID_COORDINATOR_API_KEY or API_KEY
  EDGEAI_TIMEOUT_SECONDS                  default 5
  MAEAH_AUTH_SMOKE_MODEL_ID               default local-auth-smoke
EOF
}

plan_json() {
  python3 - "$DASHBOARD_URL" "$SMOKE_ID" <<'PY'
import json, sys
base, model_id = sys.argv[1], sys.argv[2]
steps = [
    {"name": "unauthenticated_admin_add_rejected", "method": "POST", "url": f"{base}/admin/v1/models", "expect_status": [403]},
    {"name": "internal_admin_add_allowed", "method": "POST", "url": f"{base}/admin/v1/models", "headers": ["X-Dashboard-Internal: 1"], "expect_status": [200, 409]},
    {"name": "internal_admin_delete_allowed", "method": "DELETE", "url": f"{base}/admin/v1/models/{model_id}", "headers": ["X-Dashboard-Internal: 1"], "expect_status": [200, 404]},
]
print(json.dumps({"ok": True, "offline": True, "model_id": model_id, "steps": steps}, sort_keys=True))
PY
}

plan_text() {
  local plan
  plan="$(plan_json)"
  python3 - "$plan" <<'PY'
import json, sys
plan = json.loads(sys.argv[1])
print("MAEAH live admin auth smoke plan")
print(f"model_id: {plan['model_id']}")
for idx, step in enumerate(plan["steps"], 1):
    headers = ", ".join(step.get("headers", [])) or "none"
    expected = ",".join(str(s) for s in step["expect_status"])
    print(f"{idx}. {step['name']}: {step['method']} {step['url']} headers=[{headers}] expect=[{expected}]")
PY
}

json_body() {
  python3 - "$SMOKE_ID" <<'PY'
import json, sys
model_id = sys.argv[1]
print(json.dumps({
    "id": model_id,
    "name": "Local Auth Smoke",
    "repo": "org/repo",
    "file": "model.gguf",
    "params": "smoke",
    "context_size": 4096,
    "ram_estimate_gb": 1.0,
    "hardware_targets": ["cpu_only"],
    "description": "Disposable auth smoke catalog entry; safe to delete.",
}, sort_keys=True))
PY
}

status_ok() {
  local status="$1" expected_csv="$2"
  IFS=',' read -r -a expected <<<"$expected_csv"
  local item
  for item in "${expected[@]}"; do
    [[ "$status" == "$item" ]] && return 0
  done
  return 1
}

curl_status() {
  local method="$1" url="$2" body="${3:-}" internal="${4:-0}"
  local -a args=(curl -sS -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" -X "$method" -H 'Accept: application/json')
  if [[ "$method" != "GET" ]]; then
    args+=(-H 'Content-Type: application/json')
    [[ -n "$body" ]] && args+=(-d "$body")
  fi
  if [[ "$internal" == "1" ]]; then
    args+=(-H 'X-Dashboard-Internal: 1')
  elif [[ -n "$API_KEY" ]]; then
    args+=(-H "X-API-Key: $API_KEY")
  fi
  args+=("$url")
  "${args[@]}" 2>/dev/null || printf '000'
}

run_live() {
  local body status failures=0
  body="$(json_body)"

  status="$(curl_status POST "$DASHBOARD_URL/admin/v1/models" "$body" 0)"
  if status_ok "$status" "403"; then
    echo "PASS unauthenticated_admin_add_rejected HTTP $status"
  else
    echo "FAIL unauthenticated_admin_add_rejected HTTP $status" >&2
    failures=$((failures + 1))
  fi

  status="$(curl_status POST "$DASHBOARD_URL/admin/v1/models" "$body" 1)"
  if status_ok "$status" "200,409"; then
    echo "PASS internal_admin_add_allowed HTTP $status"
  else
    echo "FAIL internal_admin_add_allowed HTTP $status" >&2
    failures=$((failures + 1))
  fi

  status="$(curl_status DELETE "$DASHBOARD_URL/admin/v1/models/$SMOKE_ID" '{}' 1)"
  if status_ok "$status" "200,404"; then
    echo "PASS internal_admin_delete_allowed HTTP $status"
  else
    echo "FAIL internal_admin_delete_allowed HTTP $status" >&2
    failures=$((failures + 1))
  fi

  [[ "$failures" -eq 0 ]]
}

case "${1:-}" in
  --help|-h|"") usage ;;
  --plan) plan_text ;;
  --plan-json) plan_json ;;
  --run) run_live ;;
  *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
esac
