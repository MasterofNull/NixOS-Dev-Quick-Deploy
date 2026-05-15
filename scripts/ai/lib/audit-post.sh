#!/usr/bin/env bash
# lib/audit-post.sh — Standalone audit event poster (Phase 56.1)
# Called by delegation scripts' nohup subshells to avoid nested quoting.
#
# Usage: audit-post.sh <coord_url> <event_type> <agent> <outcome> <latency_ms> <task_id> <summary>
#
# Always exits 0 — must never kill the calling workflow.

_coord_url="${1:-http://127.0.0.1:8003}"
_event_type="${2:-task_completed}"
_agent="${3:-unknown}"
_outcome="${4:-success}"
_latency_ms="${5:-0}"
_task_id="${6:-}"
_summary="${7:-}"

payload="$(python3 - <<PYEOF
import json, sys
print(json.dumps({
    "event_type": "${_event_type}",
    "agent":      "${_agent}",
    "outcome":    "${_outcome}",
    "latency_ms": int("${_latency_ms}") if "${_latency_ms}".isdigit() else 0,
    "task_id":    "${_task_id}",
    "summary":    "${_summary}"[:400],
}))
PYEOF
)" 2>/dev/null || exit 0

curl -sf -X POST "${_coord_url}/api/agent-events" \
    -H 'Content-Type: application/json' \
    -d "$payload" \
    --max-time 5 >/dev/null 2>&1 || true
