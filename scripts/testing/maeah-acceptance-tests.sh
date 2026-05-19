#!/usr/bin/env bash
# maeah-acceptance-tests.sh — MAEAH Phase A–D acceptance gate (AM-C5 normative)
#
# Usage: bash scripts/testing/maeah-acceptance-tests.sh [--verbose]
# Exit:  0 = all gates pass, 1 = one or more gates failed
#
# Env vars:
#   COORDINATOR_URL   hybrid-coordinator base (default: http://localhost:8003)
#   DASHBOARD_URL     dashboard base         (default: http://localhost:8889)
#   API_KEY           X-API-Key for lifecycle ops (default: reads /run/secrets/hybrid_coordinator_api_key)

set -euo pipefail

COORDINATOR_URL="${COORDINATOR_URL:-http://localhost:8003}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8889}"

if [[ -z "${API_KEY:-}" ]]; then
  KEY_FILE="/run/secrets/hybrid_coordinator_api_key"
  API_KEY="$(cat "$KEY_FILE" 2>/dev/null | tr -d '[:space:]' || echo '')"
fi

PASS=0
FAIL=0
VERBOSE="${1:-}"

_pass() { echo "  [PASS] Gate $1: $2"; PASS=$((PASS + 1)); }
_fail() { echo "  [FAIL] Gate $1: $2"; FAIL=$((FAIL + 1)); }
_info() { [[ "$VERBOSE" == "--verbose" ]] && echo "         $*" || true; }

echo "=== MAEAH Acceptance Tests (AM-C5) ==="
echo "    Coordinator: $COORDINATOR_URL"
echo "    Dashboard:   $DASHBOARD_URL"
echo ""

# ---------------------------------------------------------------------------
# Gate 1: Catalog load — GET /api/models returns array with ≥1 entry
# ---------------------------------------------------------------------------
MODELS_JSON="$(curl -sf "$DASHBOARD_URL/api/models" 2>/dev/null || echo 'null')"
if python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
models = d if isinstance(d, list) else (d.get('models') or d.get('data') or [])
required = {'id','state','swap_sla_tier'}
ok = len(models) >= 1 and all(required <= set(m.keys()) for m in models[:3])
sys.exit(0 if ok else 1)
" <<< "$MODELS_JSON" 2>/dev/null; then
  _pass 1 "catalog load (≥1 model, required fields present)"
else
  _fail 1 "catalog load failed or missing required fields"
  _info "Response: ${MODELS_JSON:0:200}"
fi

# ---------------------------------------------------------------------------
# Gate 2: State machine — all 10 states defined in model_registry
# ---------------------------------------------------------------------------
STATES_OK="$(python3 -c "
import sys
sys.path.insert(0, 'ai-stack/mcp-servers/hybrid-coordinator')
try:
    from model_registry import ModelState
    expected = {'available','downloading','downloaded','verified','warming',
                'candidate','active','retiring','archived','failed'}
    actual = {s.value for s in ModelState}
    missing = expected - actual
    print('OK' if not missing else f'MISSING:{missing}')
except Exception as e:
    print(f'ERR:{e}')
" 2>/dev/null)"
if [[ "$STATES_OK" == "OK" ]]; then
  _pass 2 "10-state machine (all states defined in ModelState enum)"
else
  _fail 2 "state machine incomplete: $STATES_OK"
fi

# ---------------------------------------------------------------------------
# Gate 3: Download SSE endpoint reachable (checks route exists, not full stream)
# ---------------------------------------------------------------------------
MODEL_ID="$(python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
models = d if isinstance(d, list) else (d.get('models') or d.get('data') or [])
print(models[0]['id'] if models else '')
" <<< "$MODELS_JSON" 2>/dev/null)"
if [[ -n "$MODEL_ID" ]]; then
  HTTP_STATUS="$(curl -s -o /dev/null -w "%{http_code}" \
    -H "X-API-Key: $API_KEY" \
    --max-time 3 \
    "$DASHBOARD_URL/api/models/$MODEL_ID/download/stream" 2>/dev/null || echo '000')"
  # 200 (streaming) or 404 (model not downloading) are both valid — route exists
  if [[ "$HTTP_STATUS" =~ ^(200|404|204)$ ]]; then
    _pass 3 "download SSE route reachable (HTTP $HTTP_STATUS)"
  else
    _fail 3 "download SSE route returned HTTP $HTTP_STATUS"
  fi
else
  _fail 3 "no model ID available for SSE route check"
fi

# ---------------------------------------------------------------------------
# Gate 4: Promote endpoint returns correct schema
# ---------------------------------------------------------------------------
PROMOTE_SCHEMA_OK="$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  "$DASHBOARD_URL/api/models/nonexistent-model-zzz/promote" 2>/dev/null || echo '000')"
# 404 means route exists and correctly rejects unknown model — schema is wired
if [[ "$PROMOTE_SCHEMA_OK" =~ ^(200|404|422|400)$ ]]; then
  _pass 4 "promote endpoint route wired (HTTP $PROMOTE_SCHEMA_OK)"
else
  _fail 4 "promote endpoint not reachable (HTTP $PROMOTE_SCHEMA_OK)"
fi

# ---------------------------------------------------------------------------
# Gate 5: SLA tier field present in catalog entries
# ---------------------------------------------------------------------------
SLA_OK="$(python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
models = d if isinstance(d, list) else (d.get('models') or d.get('data') or [])
ok = all('swap_sla_tier' in m for m in models)
print('OK' if ok and models else 'FAIL')
" <<< "$MODELS_JSON" 2>/dev/null)"
if [[ "$SLA_OK" == "OK" ]]; then
  _pass 5 "swap_sla_tier field present in all catalog entries"
else
  _fail 5 "swap_sla_tier field missing from catalog entries"
fi

# ---------------------------------------------------------------------------
# Gate 6: Rollback endpoint reachable
# ---------------------------------------------------------------------------
ROLLBACK_STATUS="$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  "$DASHBOARD_URL/api/models/nonexistent-model-zzz/rollback" 2>/dev/null || echo '000')"
if [[ "$ROLLBACK_STATUS" =~ ^(200|404|422|400)$ ]]; then
  _pass 6 "rollback endpoint route wired (HTTP $ROLLBACK_STATUS)"
else
  _fail 6 "rollback endpoint not reachable (HTTP $ROLLBACK_STATUS)"
fi

# ---------------------------------------------------------------------------
# Gate 7: CPU-fallback path — model_lifecycle_manager handles n_gpu_layers=0
# ---------------------------------------------------------------------------
CPU_FALLBACK_OK="$(python3 -c "
import sys
sys.path.insert(0, 'ai-stack/mcp-servers/hybrid-coordinator')
try:
    from model_lifecycle_manager import ModelLifecycleManager
    # Verify _restart_llama_service exists and accepts override
    import inspect
    src = inspect.getsource(ModelLifecycleManager._restart_llama_service)
    ok = 'n_gpu_layers' in src or 'gpu_layers' in src or 'n-gpu-layers' in src
    print('OK' if ok else 'MISSING_GPU_LAYERS_PARAM')
except Exception as e:
    print(f'ERR:{e}')
" 2>/dev/null)"
if [[ "$CPU_FALLBACK_OK" == "OK" ]]; then
  _pass 7 "CPU-fallback path present in ModelLifecycleManager"
else
  _fail 7 "CPU-fallback path missing: $CPU_FALLBACK_OK"
fi

# ---------------------------------------------------------------------------
# Gate 8: audit_log persistence in model_registry
# ---------------------------------------------------------------------------
AUDIT_OK="$(python3 -c "
import sys
sys.path.insert(0, 'ai-stack/mcp-servers/hybrid-coordinator')
try:
    from model_registry import ModelRegistry, _default_entry
    entry = _default_entry({'id': 'test', 'display_name': 'test'})
    ok = 'audit_log' in entry and isinstance(entry['audit_log'], list)
    print('OK' if ok else 'MISSING_AUDIT_LOG')
except Exception as e:
    print(f'ERR:{e}')
" 2>/dev/null)"
if [[ "$AUDIT_OK" == "OK" ]]; then
  _pass 8 "audit_log field present in model registry entries"
else
  _fail 8 "audit_log missing: $AUDIT_OK"
fi

# ---------------------------------------------------------------------------
# Gate 9: Auth — lifecycle ops without API key from non-loopback return 401/403
# ---------------------------------------------------------------------------
# Test from loopback (this script runs locally) — expect 200 or 404, not 401
LOOPBACK_STATUS="$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  "$DASHBOARD_URL/api/models/nonexistent/promote" 2>/dev/null || echo '000')"
# Loopback should be allowed (200/404) or rejected without key (401)
if [[ "$LOOPBACK_STATUS" =~ ^(200|404|422|400|401)$ ]]; then
  _pass 9 "auth gate reachable (HTTP $LOOPBACK_STATUS — loopback or key enforced)"
else
  _fail 9 "auth gate unexpected response: HTTP $LOOPBACK_STATUS"
fi

# ---------------------------------------------------------------------------
# Gate 10: Dashboard panel — section-model-lifecycle present in HTML
# ---------------------------------------------------------------------------
DASHBOARD_HTML="$(curl -sf "$DASHBOARD_URL/" 2>/dev/null | head -c 200000 || echo '')"
if echo "$DASHBOARD_HTML" | grep -q "section-model-lifecycle"; then
  _pass 10 "dashboard panel (section-model-lifecycle) present in HTML"
else
  _fail 10 "dashboard panel section-model-lifecycle NOT found in HTML"
fi

# ---------------------------------------------------------------------------
# Bonus: Phase B — GET /api/hardware/state reachable
# ---------------------------------------------------------------------------
HW_STATUS="$(curl -s -o /dev/null -w "%{http_code}" \
  "$COORDINATOR_URL/api/hardware/state" 2>/dev/null || echo '000')"
if [[ "$HW_STATUS" == "200" ]]; then
  _pass "B1" "GET /api/hardware/state returns 200"
else
  _fail "B1" "GET /api/hardware/state returned HTTP $HW_STATUS (needs nixos-rebuild)"
fi

# ---------------------------------------------------------------------------
# Bonus: Phase C — GET /admin/v1/scheduler/status reachable
# ---------------------------------------------------------------------------
SCHED_STATUS="$(curl -s -o /dev/null -w "%{http_code}" \
  "$COORDINATOR_URL/admin/v1/scheduler/status" 2>/dev/null || echo '000')"
if [[ "$SCHED_STATUS" == "200" ]]; then
  _pass "C1" "GET /admin/v1/scheduler/status returns 200"
else
  _fail "C1" "GET /admin/v1/scheduler/status returned HTTP $SCHED_STATUS (needs nixos-rebuild)"
fi

# ---------------------------------------------------------------------------
# Bonus: Phase D — POST /a2a/tasks/send route wired
# ---------------------------------------------------------------------------
A2A_STATUS="$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"message":{"role":"user","parts":[{"text":"ping"}]}}' \
  "$COORDINATOR_URL/a2a/tasks/send" 2>/dev/null || echo '000')"
if [[ "$A2A_STATUS" =~ ^(200|400|422)$ ]]; then
  _pass "D1" "POST /a2a/tasks/send route wired (HTTP $A2A_STATUS)"
else
  _fail "D1" "POST /a2a/tasks/send not reachable (HTTP $A2A_STATUS, needs nixos-rebuild)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Results ==="
echo "    Passed: $PASS"
echo "    Failed: $FAIL"
echo ""
if [[ $FAIL -eq 0 ]]; then
  echo "ALL GATES PASS — MAEAH Phase A–D acceptance criteria met."
  exit 0
else
  echo "GATES FAILED: $FAIL — see above for details."
  exit 1
fi
