# Phase 68 Staff Eng / Implementation Review
# Role: Codex (Staff Eng) — proxy filled by Claude (Codex offline 2026-05-23)
**Status:** Codex offline — Claude providing Staff Eng perspective per team policy
**Date:** 2026-05-23
**PRD:** `.agents/plans/PHASE-68-70-AIOS-CONTINUITY-PRD.md`

---

## Review: Phase 68 Implementation Decisions

### 68.1 — workflow_checkpointer.py backtracking contract

**FINDING:** `workflow_checkpointer.py` currently stores step state in Redis DLQ (`WORKFLOW_DLQ_KEY`)
and Postgres `workflow_runs` table. The `backtrack_to(parent_node_id)` operation needs:
1. Mark all descendant steps as `status="pruned"` in Postgres.
2. Re-enqueue the parent step with `attempt_count += 1`.
3. If `attempt_count > max_depth`, escalate to `status="fatal"` and halt.

**No new Postgres table needed** — existing `workflow_steps` table can carry `status="pruned"`.
Add `backtrack_depth` column (IF NOT EXISTS) and `parent_step_id` foreign key (already likely present).

**Contract (approved):**
```python
async def backtrack_to(self, parent_node_id: str, reason: str = "") -> bool:
    """ReAct backtracking: prune descendants, re-enqueue parent. Returns True if backtracked."""
    # Returns False if max_depth exceeded (caller marks step fatal)
```

**Retryable vs fatal classification:**
- Retryable: `ConnectionError`, `TimeoutError`, `RateLimitError` (transient)
- Fatal: `ValidationError`, `PermissionError`, `SchemaError` (structural — re-planning needed)
- Unknown exceptions → retryable (fail-open for resilience)

**APPROVE** — existing DLQ pattern + Postgres step table sufficient. No new infrastructure.

---

### 68.2 — MCP JSON-RPC 2.0 adapter: spec compliance

**MCP 2025-11-05 required fields for `tools/call`:**
```json
{
  "jsonrpc": "2.0",
  "id": "<string|number>",
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": {}
  }
}
```

**Response (success):**
```json
{
  "jsonrpc": "2.0",
  "id": "<echo of request id>",
  "result": {
    "content": [{"type": "text", "text": "..."}],
    "isError": false
  }
}
```

**Error codes (JSON-RPC 2.0 standard):**
- `-32700` ParseError
- `-32600` InvalidRequest
- `-32601` MethodNotFound
- `-32602` InvalidParams
- `-32603` InternalError

**Adapter isolation:** shim wraps existing handlers via `dispatch_tool(name, arguments)` — same function, different envelope. ZERO changes to existing tool handler signatures.

**APPROVE** — thin shim pattern correct. Handlers unchanged. Error codes standardized.

---

### 68.3 — tools/list manifest

MCP `tools/list` response shape:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "aq_hints",
        "description": "...",
        "inputSchema": {
          "type": "object",
          "properties": { "query": {"type": "string"} },
          "required": ["query"]
        }
      }
    ]
  }
}
```

**Source:** Tool definitions can be auto-generated from existing `SAFE_COMMANDS` + tool handler docstrings.
No separate schema registry needed at this stage.

**APPROVE** — auto-generate from existing metadata.

---

## Implementation Sign-off Checklist

| Item | Status | Notes |
|------|--------|-------|
| backtrack_to() contract | APPROVE | Redis DLQ + Postgres pruned status |
| Retryable/fatal classification | APPROVE | Fail-open for unknown exceptions |
| JSON-RPC 2.0 envelope | APPROVE | Thin shim, handlers unchanged |
| Error code standardization | APPROVE | -32601 MethodNotFound for unknown tools |
| tools/list manifest | APPROVE | Auto-generate from docstrings |

---

*Note: Proxy review by Claude in Staff Eng / Codex role. Codex should re-review when available.*
