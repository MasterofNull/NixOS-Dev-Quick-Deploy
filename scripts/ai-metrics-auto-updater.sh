#!/usr/bin/env bash
# AI Metrics Auto-Updater
# Continuously updates AI effectiveness metrics for real-time dashboard display
# Created: 2025-12-22
# Purpose: Test continuous improvement and telemetry systems

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
UPDATE_INTERVAL=5  # Update every 5 seconds
LOG_FILE="/tmp/ai-metrics-updater.log"
PID_FILE="/tmp/ai-metrics-updater.pid"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Check if already running
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        log "AI metrics updater already running (PID: $OLD_PID)"
        exit 0
    fi
fi

# Save our PID
echo $$ > "$PID_FILE"

log "Starting AI metrics auto-updater (PID: $$)"
log "Update interval: ${UPDATE_INTERVAL}s"

# Cleanup on exit
cleanup() {
    log "Stopping AI metrics updater"
    rm -f "$PID_FILE"
    exit 0
}

trap cleanup EXIT INT TERM

# Main update loop
update_count=0

while true; do
    update_count=$((update_count + 1))

    # Run AI metrics collector
    if bash "$SCRIPT_DIR/collect-ai-metrics.sh" 2>/dev/null; then
        # Read the results
        METRICS_FILE="$HOME/.local/share/nixos-system-dashboard/ai_metrics.json"

        if [[ -f "$METRICS_FILE" ]]; then
            effectiveness=$(jq -r '.effectiveness.overall_score // 0' "$METRICS_FILE" 2>/dev/null || echo "0")
            local_pct=$(jq -r '.effectiveness.local_query_percentage // 0' "$METRICS_FILE" 2>/dev/null || echo "0")
            tokens_saved=$(jq -r '.effectiveness.estimated_tokens_saved // 0' "$METRICS_FILE" 2>/dev/null || echo "0")

            if [[ $((update_count % 12)) -eq 0 ]]; then  # Log every minute (12 * 5s)
                log "Update #${update_count}: Effectiveness=${effectiveness}/100, Local=${local_pct}%, Tokens saved=${tokens_saved}"
            fi
        fi
    else
        log "WARNING: AI metrics collection failed"
    fi

    sleep "$UPDATE_INTERVAL"
done
