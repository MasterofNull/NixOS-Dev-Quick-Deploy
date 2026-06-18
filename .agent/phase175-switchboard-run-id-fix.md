# Phase 175 — switchboard run_id NameError fix (aq-chat 500 restoration)

## Root Cause

`run_id` was assigned only inside the `not is_stream` branch
(`ai-stack/switchboard/switchboard.py`, original line ~2889) but referenced in
the `_iter()` streaming closure at lines ~2946+2965.

Every aq-chat streaming request → `NameError: name 'run_id' is not defined`
→ abrupt generator abort → `"peer closed connection without sending complete
message body (incomplete chunked read)"` in `local_agent_runtime.py` → exit 1
→ coordinator returns `{"status": "local_agent_failed"}` → aq-chat 500.

## Fix

Hoist `run_id` assignment to line 2880 (before all if/else blocks) so the
streaming closure always has access to it:

```python
# run_id must be defined unconditionally — the streaming _iter() closure
# references it for token_usage events on all local paths, not just tool-calling.
run_id = (
    request.headers.get("x-agent-run-id")
    or (payload.get("session_id") if isinstance(payload, dict) else None)
    or "unknown-run"
)
```

The old inner `run_id = request.headers.get(...)` in the not-is_stream branch was removed.

## Error Cascade (full trace)

```
aq-chat
  └─ POST /control/ai-coordinator/delegate (coordinator)
       └─ subprocess: local_agent_runtime.py
            └─ POST http://127.0.0.1:8085/v1/chat/completions (switchboard)
                 stream=True, profile=local-tool-calling
                 └─ _iter() closure fires → NameError: run_id not defined
                      → generator aborts, connection closed mid-chunked-response
                 └─ runtime: incomplete chunked read → exit 1
            └─ coordinator: {"status": "local_agent_failed"}
  └─ 500 Internal Server Error
```

## Files Changed

- `ai-stack/switchboard/switchboard.py` — hoist run_id (line 2880)

## Post-fix

Switchboard restart required (no rebuild):
```bash
sudo systemctl restart ai-switchboard.service
```
