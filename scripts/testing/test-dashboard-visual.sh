#!/usr/bin/env bash
# test-dashboard-visual.sh — visual + API smoke test for AI Command Center dashboard
# Uses chromium (headless) for screenshots + curl for API validation
# Works without playwright Python module.
set -euo pipefail

DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8889}"
OUT_DIR="${1:-/tmp/dashboard-test-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT_DIR"

PASS=0; FAIL=0

ok()   { echo "  PASS $*"; ((PASS++)) || true; }
fail() { echo "  FAIL $*"; ((FAIL++)) || true; }
info() { echo "  INFO $*"; }

echo "=== Dashboard Visual + API Smoke Test ==="
echo "  URL: $DASHBOARD_URL"
echo "  Output: $OUT_DIR"
echo ""

# ── Section 1: API endpoint health ────────────────────────────────────────────
echo "── API Endpoints ──"
api_check() {
  local ep="$1"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${DASHBOARD_URL}/api${ep}" 2>/dev/null)
  if [[ "$status" == "200" ]]; then
    ok "${ep} → ${status}"
  else
    fail "${ep} → ${status}"
  fi
}
api_check "/metrics"
api_check "/metrics/system"
api_check "/services"
api_check "/ai/metrics"
api_check "/health/layered"
api_check "/models"
api_check "/aistack/knowledge/observatory"
api_check "/stats/learning"
api_check "/harness/overview"
api_check "/firewall/status"
api_check "/traces/drift"
api_check "/deployments/history"
api_check "/audit/operator/events"
api_check "/eval/trend"
api_check "/stats/circuit-breakers"

# ── Section 2: Data quality checks ────────────────────────────────────────────
echo ""
echo "── Data Quality ──"
metrics=$(curl -s --max-time 5 "${DASHBOARD_URL}/api/metrics" 2>/dev/null)
sys=$(curl -s --max-time 5 "${DASHBOARD_URL}/api/metrics/system" 2>/dev/null)
aim=$(curl -s --max-time 5 "${DASHBOARD_URL}/api/ai/metrics" 2>/dev/null)
know=$(curl -s --max-time 5 "${DASHBOARD_URL}/api/aistack/knowledge/observatory" 2>/dev/null)

# Local AI routing
local_pct=$(echo "$metrics" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('llm_routing_local_pct','null'))" 2>/dev/null)
[[ "$local_pct" != "null" ]] && ok "Local AI%: ${local_pct}%" || fail "Local AI% missing"

# System CPU
cpu_pct=$(echo "$sys" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['cpu']['usage_percent'])" 2>/dev/null)
[[ -n "$cpu_pct" ]] && ok "CPU usage: ${cpu_pct}%" || fail "CPU usage missing"

# GPU
gpu_pct=$(echo "$sys" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['gpu']['busy_percent'])" 2>/dev/null)
[[ -n "$gpu_pct" ]] && ok "GPU busy: ${gpu_pct}%" || fail "GPU busy missing"

# Knowledge vectors
vectors=$(echo "$know" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_points','null'))" 2>/dev/null)
[[ "$vectors" != "null" && "$vectors" -gt 0 ]] && ok "Knowledge vectors: ${vectors}" || fail "Knowledge vectors missing"

# Database health
pg_status=$(echo "$aim" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['database_metrics']['postgresql']['status'])" 2>/dev/null)
rd_status=$(echo "$aim" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['database_metrics']['redis']['status'])" 2>/dev/null)
[[ "$pg_status" == "online" ]] && ok "PostgreSQL: online" || fail "PostgreSQL status: ${pg_status:-missing}"
[[ "$rd_status" == "online" ]] && ok "Redis: online" || fail "Redis status: ${rd_status:-missing}"

# ── Section 3: Screenshots ─────────────────────────────────────────────────────
echo ""
echo "── Screenshots ──"
CHROMIUM="${CHROMIUM:-chromium}"
if command -v "$CHROMIUM" &>/dev/null; then
  "$CHROMIUM" --headless=new \
    --screenshot="${OUT_DIR}/overview.png" \
    --window-size=1600,900 \
    --virtual-time-budget=8000 \
    "$DASHBOARD_URL" 2>/dev/null && ok "Overview screenshot → ${OUT_DIR}/overview.png" || fail "Screenshot failed"
else
  info "chromium not in PATH — skipping screenshots (set CHROMIUM= env var)"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Summary: ${PASS} passed · ${FAIL} failed ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
