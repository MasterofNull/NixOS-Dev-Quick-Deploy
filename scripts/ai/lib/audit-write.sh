#!/usr/bin/env bash
# lib/audit-write.sh — Source-safe delegation audit helper (Phase 56.1 / 56.7)
#
# Source this file from delegate-to-* scripts. All functions are no-op on error
# so they cannot kill the calling script (set -e safe, no `exit` calls).
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/audit-write.sh"
#   audit_event_start  gemini  task-id  "summary ≤400 chars"
#   audit_event_end    gemini  task-id  success  1234  "summary"

# Coordinator URL — read from env, fall back to default
_AUDIT_COORD_URL="${HYBRID_COORDINATOR_URL:-http://127.0.0.1:8003}"

# Write one event to POST /api/agent-events.
# Degrades gracefully: if coordinator is down the calling script continues.
_audit_post_event() {
    local agent="$1" task_id="$2" event_type="$3" outcome="$4" latency_ms="$5" summary="$6"
    # Truncate summary to 400 chars (token budget)
    summary="${summary:0:400}"
    local payload
    payload="$(python3 -c "
import json, sys
print(json.dumps({
    'event_type': sys.argv[1],
    'agent':      sys.argv[2],
    'outcome':    sys.argv[3],
    'latency_ms': int(sys.argv[4]) if sys.argv[4].isdigit() else 0,
    'summary':    sys.argv[5],
    'task_id':    sys.argv[6],
}))" "$event_type" "$agent" "$outcome" "$latency_ms" "$summary" "$task_id" 2>/dev/null)" || return 0
    curl -sf -X POST "${_AUDIT_COORD_URL}/api/agent-events" \
        -H 'Content-Type: application/json' \
        -d "$payload" \
        --max-time 5 \
        >/dev/null 2>&1 || true
}

# Record the start of a delegation task.
#   audit_event_start <agent> <task_id> <summary>
audit_event_start() {
    local agent="${1:-unknown}" task_id="${2:-}" summary="${3:-}"
    _AUDIT_DELEGATION_START_EPOCH="$(date +%s%3N 2>/dev/null || echo 0)"
    _audit_post_event "$agent" "$task_id" "delegation_start" "running" "0" "$summary" || true
}

# Record the completion (success or error) of a delegation task.
#   audit_event_end <agent> <task_id> <success|error|skip> <latency_ms> <summary>
audit_event_end() {
    local agent="${1:-unknown}" task_id="${2:-}" outcome="${3:-success}" latency_ms="${4:-0}" summary="${5:-}"
    # Compute latency from start epoch if caller passes 0
    if [[ "$latency_ms" == "0" && -n "${_AUDIT_DELEGATION_START_EPOCH:-}" ]]; then
        local now_ms; now_ms="$(date +%s%3N 2>/dev/null || echo 0)"
        latency_ms=$(( now_ms - _AUDIT_DELEGATION_START_EPOCH ))
    fi
    local event_type="task_completed"
    [[ "$outcome" == "error" ]] && event_type="error_resolution"
    _audit_post_event "$agent" "$task_id" "$event_type" "$outcome" "$latency_ms" "$summary" || true
}
