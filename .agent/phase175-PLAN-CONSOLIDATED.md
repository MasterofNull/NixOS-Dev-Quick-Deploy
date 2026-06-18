---
title: "Phase 175: Local Inference + aq-chat — Consolidated Implementation Plan"
phase: "Phase 4 — Consolidated Plan"
status: complete
date: 2026-06-17
slices: ["175-A", "175-B", "175-C"]
agents:
  - "claude-sonnet-4-6 (175-A owner)"
  - "gemini (175-B + shared)"
  - "qwen3-35b (175-B local verification)"
---

# Phase 175 — Consolidated Implementation Plan

## Scope Summary

| Slice | Owner | Rebuild? | Focus |
|-------|-------|----------|-------|
| 175-A | Claude | No | P0 correctness fixes: routing, wrong backend, coordinator streaming, shell injection, context pruning |
| 175-B | Claude + Gemini | Yes | Switchboard SSOT, circuit breaker, grammar enforcement, unified runtime bootstrap |
| 175-C | Claude | No | Feedback loop: collaborative review board protocol + AIDB seeding automation |

---

## Slice 175-A — Immediate Correctness Fixes (no rebuild)

### A1 — Fix routing substring over-matching
**File:** `scripts/ai/chat_intent.py`
**Change:** Bound conversational phrase matching to utterances ≤ 3 tokens. Add a secondary "requires-context" gate: if the query contains "current state of", "recent", "open issues", "last N commits", "does X exist" → route agentic regardless of phrase match.
**Test:** `"what is the best way to fix this AppArmor denial?"` → should route agentic, not fast-path.

### A2 — Fix `collective_memory_search_handler` wrong backend
**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py:838`
**Change:** Replace body with `return await _query_qdrant_direct(query, "knowledge", limit)`.
**Test:** Tool call to `collective_memory_search` → returns Qdrant results, not pgvector.

### A3 — Fix context pruner — preserve tool call/result pairs
**File:** `ai-stack/local-agents/agent_executor.py`, pruning block
**Change:** When pruning due to context length, always remove `(assistant tool_call, tool result)` pairs together. Never leave a dangling `role:tool` message without its preceding `role:assistant` call. Preserve system prompt and user message.
**Test:** Long session with 5+ tool calls → context pruned without structural corruption.

### A4 — Fix shell injection in `local_agent_runtime.py`
**File:** `ai-stack/local-agents/local_agent_runtime.py:90`
**Change:** Sanitize all subprocess arguments. Replace any `$()` construction with explicit argument passing. Use `shlex.quote()` on any user-controlled values passed to subprocess.
**Security test:** Tool result containing `$(whoami)` should not execute.

### A5 — Fix malformed ISO timestamp in `agent_executor.py`
**File:** `ai-stack/local-agents/agent_executor.py:466`
**Change:** Replace `datetime.now(timezone.utc).isoformat() + "Z"` with `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"` (same fix as Phase 174 in training_ingest.py).
**Test:** `agent-run-events.jsonl` timestamps parse cleanly with `datetime.fromisoformat()`.

### A6 — Add explicit CoT elicitation to agent task prompt
**File:** `ai-stack/local-agents/agent_executor.py`, `_get_system_prompt()` or task prefix
**Change:** Prepend `"Think step by step before calling any tools. State your reasoning before each action."` to the agent task message (not the system prompt, to avoid eating n_ctx). Require `"Thought: [reason]"` prefix before tool call JSON.
**Test:** Agent task trace shows Thought: prefixes before tool calls in telemetry.

### A7 — Wire coordinator streaming to aq-chat
**Files:** `scripts/ai/aq-chat`, `ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator_handlers.py`
**Change:** Add `"streaming_mode": True` to coordinator delegate payload in `aq-chat._build_coordinator_delegate_payload()`. Switch coordinator call from `httpx.post()` to `httpx.stream()`. Parse coordinator SSE events and forward to aq-chat terminal output.
**UX Test:** Agentic query produces streaming output in real time; user sees progress.

### A8 — Fix KeyboardInterrupt orphan subprocess
**File:** `scripts/ai/aq-chat`, run loop
**Change:** Catch `KeyboardInterrupt` before the coordinator call. On interrupt, send coordinator cancellation signal if task-id is known. Display "Task cancelled" to user.
**Test:** Ctrl-C during coordinator call → no zombie subprocess; subsequent messages work immediately.

---

## Slice 175-B — Rebuild-Required Changes

### B1 — Switchboard: inject SSOT guards in `proxy()` for local targets
**File:** `ai-stack/switchboard/switchboard.py`, `proxy()` handler
**Change:** Add pre-flight guard for local targets:
```python
if target_type == "local":
    payload.setdefault("chat_template_kwargs", {})["enable_thinking"] = False
    payload.setdefault("stream_options", {})["include_usage"] = True
    if is_tool_calling_profile(profile):
        payload["frequency_penalty"] = 0.0
        payload["repeat_penalty"] = payload.get("repeat_penalty", 1.08)
        payload["repeat_last_n"] = payload.get("repeat_last_n", 64)
```
This is the minimum viable SSOT guard while the full proxy refactor is scoped.

### B2 — Switchboard: add llama.cpp circuit breaker
**File:** `ai-stack/switchboard/switchboard.py`, `_call_upstream_with_resilience()`
**Change:** Remove `breaker = None` for `service_name == "llama"`. Create a circuit breaker for the local llama.cpp path with the same open/half-open/closed semantics as remote paths.

### B3 — Switchboard: fix `local-tool-calling` token budget
**File:** `ai-stack/switchboard/switchboard.py`, profile definition (~line 394)
**Change:** `"maxInputTokens": 6000` (was 12000). `"maxOutputTokens": 2048` stays. Total 8048 < n_ctx=8192.

### B4 — Switchboard: fix streaming regex fragmentation for `<think>` tags
**File:** `ai-stack/switchboard/switchboard.py:53`
**Change:** Replace regex `_THINK_BLOCK_RE.finditer` with a state-machine stream processor that buffers across chunk boundaries. State: `NORMAL`, `IN_TAG_OPEN`, `IN_THINK`, `IN_TAG_CLOSE`. Only emit content when state is `NORMAL`.

### B5 — Add grammar-constrained generation to `build_llama_payload()`
**File:** `ai-stack/mcp-servers/shared/llm_config.py`
**Change:** Add optional `json_schema` parameter to `build_llama_payload()`. When `task_type="tool_call"` and a schema is provided, inject into payload as `"json_schema": {"name": "tool_call", "schema": ...}`.
**File:** `ai-stack/local-agents/agent_executor.py`
**Change:** Generate generic tool call JSON schema from `ToolRegistry.get_schemas_summary()` at session start; pass to `build_llama_payload(task_type="tool_call")` for all tool-calling turns.

### B6 — Fix `local_agent_runtime.py` fallback to bypass switchboard telemetry
**File:** `ai-stack/local-agents/local_agent_runtime.py`, `_post_completion_with_fallback()`
**Change:** When switchboard is unreachable, fail the task cleanly rather than falling back to direct llama.cpp. Return `{"status": "switchboard_unavailable"}` to coordinator. This prevents silent bypass of telemetry, circuit breakers, and hint injection.

### B7 — Coordinator: fix zombie subprocess on timeout
**File:** `ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator_handlers.py:1373`
**Change:** After timeout, send SIGTERM to subprocess PID; wait 5s; if still running, SIGKILL. Log subprocess cleanup to telemetry.

### B8 — Fix `_sanitize_json` control char handling
**File:** `ai-stack/local-agents/tool_registry.py:606`
**Change:** Add catch-all `elif ord(ch) < 0x20: result.append(f"\\u{ord(ch):04x}")` to cover `\x08` and all other low-order control chars.

---

## Slice 175-C — Feedback Loop & Collaborative Review Protocol

### C1 — Collaborative Review Board tools
**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py`
**Add tools:**
- `post_review_finding(board_key, component, severity, finding, file_line, agent_name)` → writes to coordinator working memory under board_key
- `read_review_board(board_key)` → returns all findings posted to board

### C2 — AIDB seeding from PRD (`seed-rag-knowledge.py --from-prd`)
**File:** `scripts/data/seed-rag-knowledge.py`
**Add flag:** `--from-prd PATH` — parses severity matrix from a consolidated PRD, creates AIDB entries in `skills-patterns` and `best-practices` with component+severity tags. Timestamp is metadata only; vector embedding encodes finding content.

### C3 — WORKFLOW-CANON review board step
**File:** `.agent/WORKFLOW-CANON.md`
**Add Step 2a (between RESEARCH and PRD/PLAN):** "In multi-agent reviews: orchestrator creates review board key; each agent reads board before writing findings; each agent posts findings to board as they're discovered; consolidation reads full board."

### C4 — Delegate scripts review board injection
**Files:** `scripts/ai/delegate-to-gemini`, `scripts/ai/delegate-to-local`
**Add flag:** `--review-board KEY` — if provided, prepends a `read_review_board(KEY)` call result to the agent's prompt context before task execution.

### C5 — Seed Phase 175 findings to AIDB (post-consolidation)
Run after consolidation sign-off:
```bash
python3 scripts/data/seed-rag-knowledge.py --from-prd .agent/phase175-PRD-CONSOLIDATED.md \
  --collections skills-patterns best-practices
```
This permanently seeds the P0/P1 findings so future agents query them automatically.

---

## Validation Criteria

### After Slice A:
```bash
# A1 — routing fix
echo '"what is the best way to fix this AppArmor denial?"' | python3 -c \
  "import sys; from scripts.ai import chat_intent; print(chat_intent.classify(sys.stdin.read()))"
# Expected: agentic

# A2 — memory search fix
aq-chat "Use collective_memory_search to find patterns about coordinator delegation"
# Expected: Qdrant results, not empty/wrong content

# A7 — coordinator streaming
aq-chat "what are the current open issues in the system?"
# Expected: streaming output appears token-by-token, not 30s wait then dump
```

### After Slice B:
```bash
aq-qa 0
# Expected: 115+ passed, 0 failed

# B3 — token budget
curl -s http://127.0.0.1:8085/v1/models | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d)"
# Check local-tool-calling profile reports maxInputTokens=6000
```

### After Slice C:
```bash
python3 scripts/data/seed-rag-knowledge.py --from-prd .agent/phase175-PRD-CONSOLIDATED.md \
  --collections skills-patterns best-practices
# Expected: N entries seeded (N = P0 + P1 count from severity matrix)

# Verify retrieval
aq-chat "what do we know about switchboard proxy payload construction?"
# Expected: response references Phase 175 findings from AIDB
```

---

## Commit Strategy

Three commits:
1. `fix(inference): Phase 175A — routing classification, memory search backend, context pruner, shell injection, timestamp, CoT elicitation, coordinator streaming, KeyboardInterrupt (8 files, no rebuild)`
2. `feat(inference): Phase 175B — switchboard SSOT guards, circuit breaker, grammar enforcement, unified runtime bootstrap (rebuild required)`
3. `feat(agents): Phase 175C — collaborative review board protocol, AIDB seeding automation, WORKFLOW-CANON update`
