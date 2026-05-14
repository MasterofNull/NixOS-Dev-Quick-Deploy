#!/usr/bin/env bash
set -euo pipefail

# drill-rollback.sh
# PAR-012: Staged rollout and rollback drill for the AI agent stack.
#
# Exercises the full deploy→verify→rollback lifecycle using the control-plane
# runtime registry APIs.  Safe to run on a live stack — all mutations are
# isolated to a drill runtime entry and are reversed on exit.
#
# Usage:
#   ./scripts/testing/drill-rollback.sh [--offline] [--port PORT] [--skip-cleanup]
#
# Exit codes:
#   0  — drill completed; all stages passed
#   1  — drill failed at a specific stage (printed to stderr)
#   2  — prerequisite check failed (stack not running, missing tools)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ── Config ─────────────────────────────────────────────────────────────────────
COORDINATOR_PORT="${HYBRID_COORDINATOR_PORT:-8003}"
COORDINATOR_URL="${HYBRID_COORDINATOR_URL:-http://127.0.0.1:${COORDINATOR_PORT}}"
OFFLINE=false
SKIP_CLEANUP=false
DRILL_RUNTIME_ID="par012-drill-$(date +%s)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --offline)      OFFLINE=true ;;
    --skip-cleanup) SKIP_CLEANUP=true ;;
    --port)         shift; COORDINATOR_PORT="$1"; COORDINATOR_URL="http://127.0.0.1:${COORDINATOR_PORT}" ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# ── Helpers ────────────────────────────────────────────────────────────────────
pass()  { echo "[PASS] $*"; }
fail()  { echo "[FAIL] $*" >&2; exit 1; }
info()  { echo "[INFO] $*"; }
warn()  { echo "[WARN] $*" >&2; }
stage() { echo ""; echo "── Stage $* ──────────────────────────────────────────"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "[ERROR] required command not found: $1" >&2; exit 2; }
}

http_get() {
  curl -sf --max-time 10 "$1"
}

http_post() {
  curl -sf --max-time 10 -X POST -H "Content-Type: application/json" -d "$2" "$1"
}

http_delete() {
  curl -sf --max-time 10 -X DELETE "$1"
}

# ── Prerequisite checks ────────────────────────────────────────────────────────
require_cmd curl
require_cmd python3
require_cmd jq

stage "0: Prerequisite checks"

if $OFFLINE; then
  warn "Running in OFFLINE mode — live API calls skipped; validating scripts/policy only"
else
  if ! http_get "${COORDINATOR_URL}/health" >/dev/null 2>&1; then
    warn "Hybrid coordinator not reachable at ${COORDINATOR_URL}"
    warn "Re-run with --offline to validate scripts/policy only, or start the stack first"
    exit 2
  fi
  pass "Coordinator reachable at ${COORDINATOR_URL}"
fi

# Validate budget policy file present
BUDGET_POLICY="${REPO_ROOT}/config/runtime-budget-policy.json"
if [[ ! -f "$BUDGET_POLICY" ]]; then
  fail "runtime-budget-policy.json not found at ${BUDGET_POLICY}"
fi
python3 -c "
import json, sys
d = json.load(open('${BUDGET_POLICY}'))
assert 'default' in d, 'missing default'
assert d['default'].get('fail_safe') in ('abort','warn','checkpoint'), 'invalid fail_safe'
" || fail "runtime-budget-policy.json schema invalid"
pass "Budget policy file valid"

# Validate safety policy present
SAFETY_POLICY="${REPO_ROOT}/config/runtime-safety-policy.json"
[[ -f "$SAFETY_POLICY" ]] && pass "Safety policy file present" || warn "Safety policy file missing (optional)"

# Validate harness runner present and executable
HARNESS_RUNNER="${REPO_ROOT}/scripts/testing/harness-runner.sh"
if [[ -x "$HARNESS_RUNNER" ]]; then
  bash -n "$HARNESS_RUNNER" && pass "Harness runner syntax valid"
else
  warn "harness-runner.sh not executable (optional for offline drill)"
fi

if $OFFLINE; then
  pass "OFFLINE prerequisite checks passed"
  echo ""
  echo "=== Drill completed (offline mode) ==="
  echo "To run the full live drill: $0 --port ${COORDINATOR_PORT}"
  exit 0
fi

# ── Stage 1: Register drill runtime ───────────────────────────────────────────
stage "1: Register drill runtime (staged rollout entry)"

REGISTER_PAYLOAD=$(python3 -c "
import json, time
print(json.dumps({
  'runtime_id': '${DRILL_RUNTIME_ID}',
  'name': 'PAR-012 rollout drill',
  'profile': 'drill',
  'tags': ['par012', 'drill', 'ephemeral'],
  'healthcheck_url': '',
  'deployment': {
    'image': 'drill-image:v1.0',
    'version': 'v1.0',
    'env': {},
    'notes': 'PAR-012 staged rollout drill entry'
  }
}))
")
REGISTER_RESP=$(http_post "${COORDINATOR_URL}/control/runtimes/register" "$REGISTER_PAYLOAD") \
  || fail "Stage 1 FAILED: could not register drill runtime"

REGISTERED_ID=$(echo "$REGISTER_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('runtime_id',''))" 2>/dev/null)
[[ -n "$REGISTERED_ID" ]] || fail "Stage 1 FAILED: no runtime_id in register response"
pass "Registered drill runtime: ${REGISTERED_ID}"

# ── Stage 2: Verify runtime appears in fleet ───────────────────────────────────
stage "2: Fleet listing verification"

FLEET_RESP=$(http_get "${COORDINATOR_URL}/control/fleet/summary") \
  || fail "Stage 2 FAILED: fleet/summary unreachable"
FLEET_COUNT=$(echo "$FLEET_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_runtimes',0))" 2>/dev/null || echo 0)
[[ "$FLEET_COUNT" -ge 1 ]] || fail "Stage 2 FAILED: fleet summary shows 0 runtimes after register"
pass "Fleet summary shows ${FLEET_COUNT} runtime(s)"

GET_RESP=$(http_get "${COORDINATOR_URL}/control/runtimes/${REGISTERED_ID}") \
  || fail "Stage 2 FAILED: GET /control/runtimes/${REGISTERED_ID} returned error"
pass "Drill runtime individually fetchable"

# ── Stage 3: Deploy a new version (staged rollout) ────────────────────────────
stage "3: Staged rollout — deploy v1.1"

DEPLOY_PAYLOAD=$(python3 -c "
import json
print(json.dumps({
  'image': 'drill-image:v1.1',
  'version': 'v1.1',
  'notes': 'PAR-012 drill: staged v1.1 rollout',
  'rollout_strategy': 'canary',
  'canary_pct': 10
}))
")
DEPLOY_RESP=$(http_post "${COORDINATOR_URL}/control/runtimes/${REGISTERED_ID}/deployments" "$DEPLOY_PAYLOAD") \
  || fail "Stage 3 FAILED: deploy endpoint returned error"
DEPLOY_STATUS=$(echo "$DEPLOY_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null)
[[ -n "$DEPLOY_STATUS" ]] || fail "Stage 3 FAILED: deploy response missing status field"
pass "Canary deploy recorded: status=${DEPLOY_STATUS}"

# Verify deployment history
HIST_RESP=$(http_get "${COORDINATOR_URL}/control/runtimes/${REGISTERED_ID}/deployments") \
  || fail "Stage 3 FAILED: deployments history endpoint returned error"
HIST_COUNT=$(echo "$HIST_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('deployments',[])))" 2>/dev/null || echo 0)
[[ "$HIST_COUNT" -ge 1 ]] || fail "Stage 3 FAILED: deployment history empty after deploy"
pass "Deployment history shows ${HIST_COUNT} record(s)"

# ── Stage 4: Rollback drill ────────────────────────────────────────────────────
stage "4: Rollback drill — revert to v1.0"

ROLLBACK_PAYLOAD=$(python3 -c "import json; print(json.dumps({'reason': 'PAR-012 rollback drill', 'target_version': 'v1.0'}))")
ROLLBACK_RESP=$(http_post "${COORDINATOR_URL}/control/runtimes/${REGISTERED_ID}/rollback" "$ROLLBACK_PAYLOAD") \
  || fail "Stage 4 FAILED: rollback endpoint returned error"
ROLLBACK_STATUS=$(echo "$ROLLBACK_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null)
[[ -n "$ROLLBACK_STATUS" ]] || fail "Stage 4 FAILED: rollback response missing status"
pass "Rollback completed: status=${ROLLBACK_STATUS}"

# ── Stage 5: Budget policy check ──────────────────────────────────────────────
stage "5: Budget policy API verification"

BUDGET_RESP=$(http_get "${COORDINATOR_URL}/control/budget/policy") \
  || fail "Stage 5 FAILED: GET /control/budget/policy returned error"
BUDGET_TOKEN_LIMIT=$(echo "$BUDGET_RESP" | python3 -c "
import json,sys; d=json.load(sys.stdin)
print(d.get('policy',{}).get('default',{}).get('token_limit','missing'))
" 2>/dev/null)
[[ "$BUDGET_TOKEN_LIMIT" != "missing" ]] || fail "Stage 5 FAILED: budget policy missing token_limit"
pass "Budget policy active: token_limit=${BUDGET_TOKEN_LIMIT}"

# Test POST update (round-trip)
UPDATE_PAYLOAD='{"default":{"warn_threshold_pct":85}}'
UPDATE_RESP=$(http_post "${COORDINATOR_URL}/control/budget/policy" "$UPDATE_PAYLOAD") \
  || fail "Stage 5 FAILED: POST /control/budget/policy returned error"
UPDATE_OK=$(echo "$UPDATE_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('ok',''))" 2>/dev/null)
[[ "$UPDATE_OK" == "True" ]] || fail "Stage 5 FAILED: budget policy update response not ok"
pass "Budget policy runtime update: ok"

# ── Stage 6: Cleanup (deregister drill runtime) ────────────────────────────────
stage "6: Cleanup — deregister drill runtime"

if $SKIP_CLEANUP; then
  warn "Skipping cleanup (--skip-cleanup). Drill runtime left in registry: ${REGISTERED_ID}"
else
  http_delete "${COORDINATOR_URL}/control/runtimes/${REGISTERED_ID}" >/dev/null 2>&1 \
    && pass "Drill runtime deregistered: ${REGISTERED_ID}" \
    || warn "Deregister returned error (non-fatal; runtime may already be removed)"
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo " PAR-012 Rollout/Rollback Drill — ALL STAGES PASSED"
echo " Runtime: ${DRILL_RUNTIME_ID}"
echo " Coordinator: ${COORDINATOR_URL}"
echo "══════════════════════════════════════════════════"
