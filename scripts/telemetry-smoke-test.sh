#!/usr/bin/env bash
# Telemetry smoke test for hybrid coordinator + dashboard pipeline.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HYBRID_URL="${HYBRID_URL:-http://${SERVICE_HOST:-localhost}:8092}"
AIDB_URL="${AIDB_URL:-http://${SERVICE_HOST:-localhost}:8091}"
HYBRID_TELEMETRY_PATH="${HYBRID_TELEMETRY_PATH:-$HOME/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl}"
DASHBOARD_DATA_DIR="${DASHBOARD_DATA_DIR:-$HOME/.local/share/nixos-system-dashboard}"

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "✗ Missing required command: $1"
        exit 1
    fi
}

require_cmd curl

info "Checking AIDB MCP health..."
curl -sf --max-time 5 "${AIDB_URL}/health" >/dev/null
success "AIDB MCP is healthy"

info "Checking Hybrid Coordinator health..."
curl -sf --max-time 5 "${HYBRID_URL}/health" >/dev/null
success "Hybrid Coordinator is healthy"

before_count=0
if [[ -f "$HYBRID_TELEMETRY_PATH" ]]; then
    before_count=$(wc -l < "$HYBRID_TELEMETRY_PATH" | tr -d ' ')
fi

info "Triggering hybrid coordinator telemetry event..."
curl -sf --max-time 5 -X POST "${HYBRID_URL}/augment_query" \
    -H "Content-Type: application/json" \
    -d '{"query":"Telemetry smoke test: validate local routing metrics.","agent_type":"local"}' \
    >/dev/null

sleep 1

after_count=0
if [[ -f "$HYBRID_TELEMETRY_PATH" ]]; then
    after_count=$(wc -l < "$HYBRID_TELEMETRY_PATH" | tr -d ' ')
fi

if [[ "$after_count" -le "$before_count" ]]; then
    warn "Hybrid telemetry did not grow (before=$before_count, after=$after_count)"
else
    success "Hybrid telemetry updated (before=$before_count, after=$after_count)"
fi

info "Regenerating dashboard metrics..."
rm -f "${DASHBOARD_DATA_DIR}/collector.lock" 2>/dev/null || true
"${PROJECT_ROOT}/scripts/generate-dashboard-data.sh" >/dev/null
success "Dashboard data regenerated"

if command -v jq >/dev/null 2>&1; then
    local_rate=$(jq -r '.summary.local_usage_rate' "${DASHBOARD_DATA_DIR}/telemetry.json" 2>/dev/null || echo "0")
    info "Dashboard local usage rate: ${local_rate}%"
else
    info "Dashboard telemetry saved to ${DASHBOARD_DATA_DIR}/telemetry.json"
fi
