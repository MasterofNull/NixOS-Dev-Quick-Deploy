# Workflow Executor Integration Guide

**Date:** 2026-04-09
**Status:** ✅ Basic executor implemented, LLM integration pending
**Priority:** Critical for agent delegation features

---

## Problem: Missing Execution Backend

### Discovery

During Phase 1 implementation, we attempted to delegate work to sub-agents using:
```bash
harness-rpc.js sub-agent --task "..." --agent qwen
```

**Expected behavior:**
- Create workflow session
- Execute workflow using LLM
- Update session with results
- Complete or fail with output

**Actual behavior:**
- Created workflow session ✅
- Saved to `.workflow-sessions.json` ✅
- **Never executed** ❌
- Sessions stuck "in_progress" with 0 tokens/tools used

### Root Cause

[`http_server.py:7725-7757`](../ai-stack/mcp-servers/hybrid-coordinator/http_server.py#L7725-L7757):

```python
async def handle_workflow_run_start(request: web.Request) -> web.Response:
    # ... validation ...
    session = _build_workflow_run_session(...)

    # Save session
    async with _workflow_sessions_lock:
        sessions = await _load_workflow_sessions()
        sessions[session_id] = session
        await _save_workflow_sessions(sessions)

    return web.json_response(session)  # ← Returns immediately!
```

**What's missing:**
- No LLM API calls
- No background task to process sessions
- No workflow execution loop
- No agent process spawning

The coordinator is a **tracking/coordination layer only**.

---

## Solution: WorkflowExecutor Service

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  Coordinator (http_server.py)                       │
│  - Accepts /workflow/run/start requests             │
│  - Creates sessions in .workflow-sessions.json      │
│  - Returns session ID immediately                   │
└─────────────────────┬───────────────────────────────┘
                      │
                      │ Sessions saved to disk
                      ▼
┌─────────────────────────────────────────────────────┐
│  WorkflowExecutor (workflow_executor.py)            │
│  - Polls for in_progress sessions                   │
│  - Executes workflows using LLM APIs                │
│  - Updates sessions with results                    │
│  - Respects budget limits                           │
└─────────────────────┬───────────────────────────────┘
                      │
                      │ Calls LLM API
                      ▼
┌─────────────────────────────────────────────────────┐
│  LLM Provider (Anthropic/OpenAI/Local)              │
│  - Processes prompts                                │
│  - Returns tool calls                               │
│  - Executes workflow phases                         │
└─────────────────────────────────────────────────────┘
```

### Components

**1. WorkflowExecutor** ([`workflow_executor.py`](../ai-stack/mcp-servers/hybrid-coordinator/workflow_executor.py))
- Main execution loop
- Session polling (configurable interval)
- Concurrent execution (max_concurrent limit)
- Budget enforcement
- Error handling

**2. WorkflowPhaseExecutor** (future)
- Individual phase execution
- LLM prompt generation
- Tool call handling
- Result validation

---

## Current Implementation Status

### ✅ Completed

1. **Basic Executor Framework**
   - Async polling loop
   - Session loading/saving
   - Concurrent execution support
   - Budget respect (tokens/tool calls)
   - Error handling
   - Graceful shutdown

2. **Test Coverage**
   - 4 tests, 100% passing
   - Session discovery
   - Execution lifecycle
   - Budget limits
   - Error scenarios

3. **Mock Execution**
   - Sessions complete successfully
   - Events added to trajectory
   - Status updates work correctly

### ⏳ TODO: LLM Integration

**Required for production use:**

```python
# Current (mock):
async def _execute_session(self, session_id, session):
    await asyncio.sleep(1.0)  # Simulate work
    await self._update_session(session_id, {"status": "completed"})

# Needed (real):
async def _execute_session(self, session_id, session):
    objective = session["objective"]

    # 1. Generate prompt from objective
    prompt = self._build_prompt(objective, session)

    # 2. Call LLM API
    response = await self.llm_client.create_message(
        model="claude-3-5-sonnet-20250219",
        messages=[{"role": "user", "content": prompt}],
        tools=self._get_available_tools(session),
    )

    # 3. Process tool calls
    for tool_call in response.tool_calls:
        result = await self._execute_tool(tool_call, session)
        # Add to trajectory...

    # 4. Update session
    await self._update_session(session_id, {
        "status": "completed",
        "usage": {"tokens_used": response.usage.total_tokens},
        "result": response.content
    })
```

---

## Integration Options

### Option 1: Background Task in Coordinator (Recommended)

**Modify `http_server.py` startup:**

```python
from workflow_executor import WorkflowExecutor

async def start_http_server():
    # ... existing setup ...

    # Start workflow executor as background task
    executor = WorkflowExecutor(
        sessions_file=".workflow-sessions.json",
        poll_interval=2.0,
        max_concurrent=3,
    )

    executor_task = asyncio.create_task(executor.run())

    # ... start aiohttp server ...

    try:
        await asyncio.gather(
            executor_task,
            runner.run(),
        )
    finally:
        executor.stop()
```

**Pros:**
- Single process
- Shared memory access
- Easy deployment
- Automatic lifecycle

**Cons:**
- Coordinator process does more work
- Restart affects all sessions

### Option 2: Separate Executor Process

**Run standalone:**
```bash
# Terminal 1: Coordinator
python3 ai-stack/mcp-servers/hybrid-coordinator/server.py

# Terminal 2: Executor
python3 -m workflow_executor
```

**Pros:**
- Isolation
- Independent scaling
- Easier debugging
- Can restart separately

**Cons:**
- Two processes to manage
- Need systemd/supervisor
- File-based communication only

### Option 3: systemd Service

**`/etc/systemd/system/workflow-executor.service`:**
```ini
[Unit]
Description=AI Harness Workflow Executor
After=network.target hybrid-coordinator.service

[Service]
Type=simple
User=hyperd
WorkingDirectory=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy
ExecStart=/usr/bin/python3 -m workflow_executor
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Testing

### Unit Tests

```bash
python3 -m pytest ai-stack/mcp-servers/hybrid-coordinator/test_workflow_executor.py -v
```

### Integration Test

1. Start executor:
```bash
python3 -m workflow_executor
```

2. Create test session:
```bash
node scripts/ai/harness-rpc.js sub-agent \
  --task "Simple test task" \
  --safety-mode plan-readonly
```

3. Watch executor logs - should show:
```
INFO - Workflow executor started
INFO - Started execution of session abc123de
INFO - Completed session abc123de
```

4. Check session status:
```bash
node scripts/ai/harness-rpc.js run-replay --id <session_id>
```

Should show `"status": "completed"`.

---

## Performance Tuning

### Configuration Parameters

```python
executor = WorkflowExecutor(
    sessions_file=".workflow-sessions.json",
    poll_interval=2.0,      # Seconds between polls (lower = more responsive, higher = less CPU)
    max_concurrent=3,        # Max parallel executions (depends on API rate limits)
)
```

**Recommendations:**
- **Development:** `poll_interval=1.0`, `max_concurrent=2`
- **Production:** `poll_interval=5.0`, `max_concurrent=5`
- **High-load:** `poll_interval=2.0`, `max_concurrent=10` (with API key rotation)

### Resource Limits

Sessions respect budget limits:
```json
{
  "budget": {
    "token_limit": 8000,
    "tool_call_limit": 40
  },
  "usage": {
    "tokens_used": 1234,
    "tool_calls_used": 5
  }
}
```

Executor stops processing when budget exceeded.

---

## Monitoring

### Session Status

```bash
# List all sessions
jq 'keys[]' .workflow-sessions.json

# Check specific session
jq '.["<session-id>"]' .workflow-sessions.json

# Count by status
jq '[.[] | .status] | group_by(.) | map({status: .[0], count: length})' .workflow-sessions.json
```

### Executor Health

```bash
# Check if running
ps aux | grep workflow_executor

# Check logs (if using systemd)
journalctl -u workflow-executor -f

# Manual log check
tail -f /var/log/workflow-executor.log
```

---

## Troubleshooting

### Problem: Sessions stay "in_progress"

**Symptoms:**
- Sessions created but never complete
- `tokens_used` stays at 0

**Causes:**
1. Executor not running
2. LLM integration not implemented
3. API key missing/invalid
4. Budget already exceeded

**Fix:**
```bash
# Check executor is running
ps aux | grep workflow_executor

# Check executor logs
journalctl -u workflow-executor -n 50

# Manually trigger execution
python3 -m workflow_executor
```

### Problem: Sessions fail immediately

**Symptoms:**
- Status changes to "failed"
- Error in trajectory

**Causes:**
1. Invalid session data
2. LLM API error
3. Tool execution failure

**Fix:**
```bash
# Check session error
jq '.["<session-id>"].error' .workflow-sessions.json

# Check trajectory
jq '.["<session-id>"].trajectory' .workflow-sessions.json
```

---

## Next Steps

1. **Implement LLM Integration** (Priority: Critical)
   - Add Anthropic API client
   - Implement prompt generation
   - Handle streaming responses
   - Process tool calls

2. **Add Tool Execution**
   - File operations
   - Git commands
   - Test runners
   - Build systems

3. **Improve Error Handling**
   - Retry logic
   - Exponential backoff
   - Dead letter queue
   - Circuit breaker

4. **Add Observability**
   - Structured logging
   - Metrics (Prometheus)
   - Tracing (OpenTelemetry)
   - Alerts

5. **Scale for Production**
   - Database instead of JSON file
   - Distributed executor pool
   - Session sharding
   - Load balancing

---

## Related Documentation

- [Memory System Design](./memory-system-design.md)
- [Harness Parity Analysis](../../.agent/workflows/ai-harness-comprehensive-analysis-v2-2026-04-09.md)
- [Master Roadmap](../../.agents/plans/MASTER-ROADMAP-2026-04-09.md)

---

**Document Version:** 1.0.0
**Last Updated:** 2026-04-09
**Next Review:** After LLM integration complete
