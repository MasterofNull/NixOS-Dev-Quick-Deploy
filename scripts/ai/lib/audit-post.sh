#!/usr/bin/env bash
# lib/audit-post.sh — Standalone audit event poster (Phase 56.1 / 56.7 / 56.9)
# Called by delegation scripts' nohup subshells to avoid nested quoting.
#
# Usage: audit-post.sh <coord_url> <event_type> <agent> <outcome> <latency_ms> <task_id> <summary> [sub_type] [prompt] [log_file]
#
# Always exits 0 — must never kill the calling workflow.

_coord_url="${1:-http://127.0.0.1:8003}"
_event_type="${2:-task_completed}"
_agent="${3:-unknown}"
_outcome="${4:-success}"
_latency_ms="${5:-0}"
_task_id="${6:-}"
_summary="${7:-}"
_sub_type="${8:-}"
_prompt="${9:-}"
_log_file="${10:-}"

# Use sys.argv for all dynamic values — shell expansion inside Python heredoc
# is a code-injection surface when summary/task fields contain quotes or backslashes.
payload="$(python3 -c "
import json, sys
event_type, sub_type, agent, outcome, latency_raw, task_id, summary = sys.argv[1:8]
try:
    latency_ms = int(latency_raw) if latency_raw.isdigit() else 0
except (ValueError, TypeError):
    latency_ms = 0
print(json.dumps({
    'event_type': event_type,
    'sub_type':   sub_type,
    'agent':      agent,
    'outcome':    outcome,
    'latency_ms': latency_ms,
    'task_id':    task_id,
    'summary':    summary[:400],
}))
" "$_event_type" "$_sub_type" "$_agent" "$_outcome" "$_latency_ms" "$_task_id" "$_summary" 2>/dev/null)" || exit 0

curl -sf -X POST "${_coord_url}/api/agent-events" \
    -H 'Content-Type: application/json' \
    -d "$payload" \
    --max-time 5 >/dev/null 2>&1 || true

# Handle session saving if requested
if [[ -n "$_prompt" && -n "$_log_file" && -f "$_log_file" ]]; then
    _session_dir=".agents/sessions"
    [[ -d "$_session_dir" ]] || mkdir -p "$_session_dir"
    _ts="$(date +%Y%m%d-%H%M%S)"
    _session_file="${_session_dir}/${_agent}-${_ts}-${_task_id}.json"

    python3 -c "
import json, sys, os
agent, task_id, prompt, log_file, session_file = sys.argv[1:6]
try:
    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        response = f.read()
except Exception:
    response = '(failed to read log file)'

session = {
    'sessionId': task_id,
    'title': f'Delegation: {agent} ({task_id})',
    'agent': agent,
    'history': [
        {'role': 'user', 'content': prompt},
        {'role': 'assistant', 'content': response}
    ]
}
with open(session_file, 'w', encoding='utf-8') as f:
    json.dump(session, f, indent=2)
" "$_agent" "$_task_id" "$_prompt" "$_log_file" "$_session_file" 2>/dev/null || true
fi
