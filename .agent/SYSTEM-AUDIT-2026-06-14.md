# System Audit — 2026-06-14

## Summary: 28 OK / 5 GAPS / 2 STUBS

## Remediation Update: 2026-06-14

The follow-up local-agent tool contract pass resolved or guarded most findings below:

- `GAP-1` fixed: `ai_coordination.py` imports `os`, so `run_opencode_handler` can resolve environment aliases.
- `GAP-2` fixed in handler contract: `recommend_agent_for_task_handler` no longer calls `/federated/recommend`; it reads `/control/agents/roles` and scores locally.
- `GAP-3` fixed in auth contract: `/control/prsi/` is present in `LOOPBACK_AGENT_PREFIXES`.
- `GAP-4` fixed in handler contract: `get_workflow_status_handler` uses `/workflow/orchestrate/{workflow_id}`.
- `STUB-1` fixed in handler contract: `query_context_handler` calls `/memory/recall`.
- `STUB-2` fixed in handler contract: `delegate_to_remote_handler` calls `/control/ai-coordinator/delegate`.

Regression coverage: `scripts/testing/test-local-agent-store-memory-contract.py` now checks these local-agent tool endpoint contracts and PRSI loopback authorization.

---

## GAPS (need fixing)

### GAP-1 — `run_opencode_handler` missing `import os` — NameError at runtime
**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py` lines 301, 302, 307
**Severity:** HIGH — `run_opencode` tool crashes with `NameError: name 'os' is not defined` whenever
`opencode` binary is present in PATH (the early-return `if not opencode_bin` masks the bug when the
binary is absent — but on any machine with opencode installed it will fail).
**Root cause:** `os` is used in `run_opencode_handler` via `os.getenv()` and `{**os.environ}` but
`os` is never imported at module level (only `asyncio`, `json`, `logging`, `typing`, `httpx`,
`tool_registry`, and `shutil` are imported; `asyncio`/`shutil` are re-imported locally inside the
function body).
**Fix:** Add `import os` to the top-level imports in `ai_coordination.py`.

### GAP-2 — `recommend_agent_for_task_handler` calls non-existent `/federated/recommend` endpoint (401 + no route)
**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py` line 375
**Live probe:** `POST /federated/recommend` → `{"error":"unauthorized","mode":"api-key"}` (HTTP 401)
**Root cause:** The path `/federated/` is NOT in `LOOPBACK_AGENT_PREFIXES`
(`ai-stack/mcp-servers/hybrid-coordinator/middleware/auth.py` lines 72–114), AND no route handler
for `POST /federated/recommend` exists anywhere in the coordinator source (only
`/discovery/capabilities` handles federated data — via `federated_mcp_handlers.py`).
**Fix (two-step):**
1. Either register a `POST /federated/recommend` handler in the coordinator (or redirect to the
   agent-pool scoring endpoint), AND add `"/federated/"` to `LOOPBACK_AGENT_PREFIXES`.
2. Or point `recommend_agent_for_task_handler` to an existing endpoint (e.g. `/discovery/capabilities`
   + local scoring, or the agent pool endpoint at `/control/agents`).

### GAP-3 — `get_prsi_pending_handler` / `prsi_orchestrate_handler` hit 401 from loopback
**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py` lines 350, 363–365
**Live probe:** `GET /control/prsi/pending` → `{"error":"unauthorized","mode":"api-key"}` (HTTP 401)
**Root cause:** `/control/prsi/` is NOT in `LOOPBACK_AGENT_PREFIXES`. The existing entries for
`/control/` only cover: `ai-coordinator/`, `llm/`, `agents/`, `agents`, `review/`, `runtimes`,
`runtimes/`, `reasoning/`, `budget/`, `fleet/`, `intent/`. The `/control/prsi/` sub-path is absent.
**Fix:** Add `"/control/prsi/"` to `LOOPBACK_AGENT_PREFIXES` in
`ai-stack/mcp-servers/hybrid-coordinator/middleware/auth.py`.

### GAP-4 — `get_workflow_status_handler` calls wrong URL (`/workflow/status/{id}` → 404)
**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py` line 244
**Live probe:** `GET /workflow/status/t` → `404: Not Found`
**Root cause:** The coordinator registers `GET /workflow/orchestrate/{task_id}` (file:
`workflow/workflow_session_handlers.py` line 1419), not `/workflow/status/{id}`.
**Fix:** Change `f"{HYBRID_COORDINATOR_URL}/workflow/status/{workflow_id}"` →
`f"{HYBRID_COORDINATOR_URL}/workflow/orchestrate/{workflow_id}"` in `get_workflow_status_handler`.

### GAP-5 — aq-qa 0.8.1 FAILING: delegate 24h success rate 14% (6/44 calls)
**Check:** `aq-qa 0.8.1` — delegate 24h success rate ≥ 50% — FAIL (14%, 6/44 calls)
**Severity:** MEDIUM — indicates the coordinator delegate path (`/control/ai-coordinator/delegate`)
is failing for ~86% of dispatches over the past 24h. The hints engine itself confirms this:
`"id":"runtime_tool_error_ai_coordinator_delegate"` with `"error": "http_status_502"`.
**Note:** Most likely caused by llama.cpp being INACTIVE (not loaded). All local delegate calls that
require inference return 502 when llama.cpp is down.
**Action:** Re-check after llama.cpp is loaded. If failure persists, investigate coordinator 502
error path in `ai_coordinator_handlers.py`.

---

## STUBS (placeholder returns, not wired)

### STUB-1 — `query_context_handler` always returns error
**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py` lines 177–181
```python
return {
    "success": False,
    "error": "Context memory integration not yet implemented",
}
```
The `query_context` tool is registered and presented to agents, but calling it always fails with
`"Context memory integration not yet implemented"`. The coordinator has a `/discovery/capabilities`
endpoint and `/memory/recall` — context querying can be redirected to `/memory/recall` (same pattern
as `get_working_memory_handler`).
**Fix:** Replace the placeholder with an HTTP call to `{HYBRID_COORDINATOR_URL}/memory/recall` with
`{"query": query, "memory_types": ["episodic","semantic"], "limit": max_results}`.

### STUB-2 — `delegate_to_remote_handler` uses wrong endpoint (`/query` not the delegate path)
**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py` lines 127–139
This handler calls `POST /query` (the RAG search endpoint), not the actual delegation endpoint
`/control/ai-coordinator/delegate`. The response from `/query` is an RAG search result, not an agent
task result. The tool will appear to "succeed" (200 OK) but the response is a keyword search result,
not agent output.
**Fix:** Point `delegate_to_remote_handler` to `POST /control/ai-coordinator/delegate` with the
correct payload schema `{"task": task, "agent": agent_type, "priority": priority}`.

---

## OK (verified working)

### Endpoint Probes (actual URLs from ai_coordination.py)

| Tool | URL called | Status | Notes |
|------|-----------|--------|-------|
| `get_hint` | `GET /hints?q=…` | **OK** | Returns hint objects; loopback-exempt |
| `store_memory` | `POST /memory/store` | **OK** | Returns `memory_id`; loopback-exempt |
| `get_working_memory` | `POST /memory/recall` | **OK** | Returns semantic results; loopback-exempt |
| `query_aidb` | `POST /search/tree` | **OK** | Returns ranked results; `/search/` in LOOPBACK |
| `collective_memory_search` | `POST /aidb/vector/search` | **OK** | Calls AIDB directly port 8002 |
| `harness_health` | `POST /qa/check` | **OK** (route exists) | Returns error when aq-qa runs from Nix store — stdout empty; loopback via `/qa/` prefix |
| `mesh_discovery` | `GET /discovery/capabilities` | **OK** | loopback-exempt via `/discovery/` |
| `get_workflow_status` | `GET /workflow/orchestrate/{id}` | **OK** (correct URL) | Returns 404 for missing IDs (expected); loopback via `/workflow/` |
| `get_prsi_pending` | `GET /control/prsi/pending` | **FAIL — 401** | Not in LOOPBACK_AGENT_PREFIXES (GAP-3) |
| `prsi_orchestrate` | `POST /control/prsi/actions/execute` | **FAIL — 401** | Same as above (GAP-3) |
| `recommend_agent_for_task` | `POST /federated/recommend` | **FAIL — 401+404** | No route + not loopback-exempt (GAP-2) |
| `delegate_to_remote` | `POST /query` | **STUB** (wrong endpoint) (STUB-2) |
| `query_context` | (no HTTP call) | **STUB** (returns hardcoded error) (STUB-1) |
| `run_opencode` | subprocess | **FAIL — NameError** if opencode in PATH (GAP-1) |

### Tool Infrastructure

- **TOOL_CATALOG:** 17 entries — OK (`_select_tools_for_task` selects 5 for "search" task)
- **`_slim_schema()`** — present and functional
- **`_select_tools_for_task()`** — present, called at task start
- **`_refresh_tools_from_result()`** (local_agent_runtime.py) — present, called after each tool result
- **`_refresh_active_tools()`** (agent_executor.py) — present, called in `_execute_with_tools`
- **Progressive disclosure (Phase A):** TOOL_CATALOG=17, selection + hot-swap both wired

### Agent Run Events (Phase E)

- **`_emit_agent_event()`** — present at `agent_executor.py:431`
- **All 7 event types emitted:** `agent_step_start` (L899), `agent_tool_intent` (L1011), `agent_tool_result` (L1033), `agent_synthesis_start` (L1002), `agent_complete` (L658), `agent_failed` (L566/L586/L680), `agent_stall` (L783–784)
- **Stall watchdog:** `call_later` at L792
- **`harness_paths.AGENT_RUN_EVENTS`** — imported with fallback at L63–72
- **agent-run-events.jsonl** — file exists, 2.76 MB, has correct 27-key schema
- **aq-agent-loop events:** `agent_step_start`, `agent_complete`, `agent_failed` all emitted (lines 99, 208, 232, 241)

### Working Memory Lifecycle (Phase F)

- **`_store_prune_checkpoint()`** — module-level async function at `agent_executor.py:165`; uses `memory_type: "semantic"` (L177) with `"working_memory"` tag (L180)
- **Auto-prefetch block** — present at L736–758, before the tool use loop (L760)
- **Recall uses `memory_types: ["semantic"]`** — at L744
- **Pinned+sliding prune calls `_store_prune_checkpoint`** — at L937
- **`MEMORY_TYPE_ALIASES`** has `"working": "semantic"` — in `ai_coordination.py`
- **`get_working_memory_handler`** queries `["semantic"]` — confirmed at L395

### aq-chat Phases B–D

- **`from chat_intent import ToolMode, classify_chat_intent`** — imports successfully
- **`self.tool_mode`** — set at `aq-chat:108`, used consistently; `local_tools_enabled` is a compat `@property` (L186–189)
- **`_build_fast_path_payload()`** — present at L511; sets `stream: True`, `max_tokens: 1024`, `enable_thinking: False`, `frequency_penalty: 0.0`
- **`_write_routing_event()`** — present at L531; uses `asyncio.create_task` (L567)
- **Phase B.4 coordinator import** — present at `ai_coordinator_handlers.py:1494–1508` with fallback phrase set
- **Phase 169 system_prompt event** — emitted at `ai_coordinator_handlers.py:1557–1584`

### Switchboard Profiles

- **`local-tool-calling` injectHints:** `True` — OK
- **`continue-local` injectHints:** `True` — OK

### Memory Broker (live round-trip)

- **Store → Recall** — write returns `memory_id`, recall returns stored content with `score: 1.32` — OK

### aq-qa Phase 0 Summary

- **116 passed / 1 failed** — only failure is `0.8.1` (delegate success rate 14%, likely due to
  llama.cpp INACTIVE)

---

## Requires llama.cpp (inference tests deferred)

The following could not be fully verified because llama.cpp is not loaded:

1. **End-to-end local agent run** — `aq-agent-loop` with tool use; all 7 event types in sequence
2. **aq-chat `local-tool-calling` profile** — actual inference turn with tool call round-trip
3. **Working memory prune+checkpoint round-trip** — requires >8-message context window, needs active model
4. **`delegate_to_remote_handler` (STUB-2)** — cannot verify actual agent task execution
5. **aq-qa 0.8.1** — delegate success rate (14%) may normalise once llama.cpp is active
6. **`/qa/check` via `harness_health_handler`** — returns `aq-qa produced empty stdout` (aq-qa runs from Nix store; `--json` flag may not be available in that store copy)

---

## Issues to Record in issues-backlog.md

1. **GAP-1 (HIGH):** `os` not imported in `ai_coordination.py` → `run_opencode` NameError —
   `ai-stack/local-agents/builtin_tools/ai_coordination.py:299` — add `import os`
2. **GAP-2 (MEDIUM):** `/federated/recommend` has no route and is not loopback-exempt —
   `ai_coordination.py:375` + `middleware/auth.py`
3. **GAP-3 (MEDIUM):** `/control/prsi/` not in `LOOPBACK_AGENT_PREFIXES` →
   `get_prsi_pending` and `prsi_orchestrate` tools always 401 for local agents —
   `middleware/auth.py`
4. **GAP-4 (LOW):** `get_workflow_status_handler` uses `/workflow/status/` (404) instead of
   `/workflow/orchestrate/` — `ai_coordination.py:244`
5. **STUB-1 (MEDIUM):** `query_context` tool hardcoded failure — `ai_coordination.py:177–181`
6. **STUB-2 (MEDIUM):** `delegate_to_remote` calls `/query` (RAG search) instead of
   `/control/ai-coordinator/delegate` — `ai_coordination.py:130`
