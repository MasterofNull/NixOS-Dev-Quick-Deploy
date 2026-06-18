---
title: "Phase 175: Local Inference + aq-chat — Expert Review PRD"
expert_roles: ["CLI/UX Engineer", "Inference Systems Engineer", "Agent Coordination Engineer", "AI/Agentic Research Scientist"]
agent: claude-sonnet-4-6
phase: "Phase 2 — Independent PRD Draft"
date: 2026-06-17
status: draft
---

# Phase 175: Local Inference + aq-chat — Expert Review PRD (Claude)

## Executive Summary

The local inference stack is architecturally sound at the macro level — the aq-chat → intent classification → coordinator/fast-path → switchboard → llama.cpp chain is the right design. The issues are at the seams: the routing boundary is too aggressive in classifying conversational prompts as agentic, the switchboard's proxy path bypasses the `build_llama_payload()` SSOT entirely, the llama.cpp path has no circuit breaker while every remote path does, and the agent loop has several silent failure modes that terminate tasks without surfacing the true error. None of these are fatal — they are fixable seam-level bugs in an otherwise correct architecture.

The most critical systemic gap is a **feedback loop deficit**: agent review findings, critique patterns, and quality signals are not being consistently routed back into the prompts that future agents receive. AIDB collections exist but are not uniformly written to. Each new agent dispatch starts cold and re-derives knowledge that has already been established. The PRD includes a design proposal for closing this loop without causing recency bias.

---

## Critical Findings — ROLE 1: CLI/UX Engineer

### F1.1 — Substring routing misclassification (P0)
**File:** `scripts/ai/chat_intent.py`, `_CONVERSATIONAL_INTENTS` check
**Impact:** "ok, implement the health check endpoint" matches "ok" as a substring → routed to fast-path (no tools). User gets a plan response instead of execution.
**Fix:** Conversational phrase matching must be bounded — match only when the phrase IS the utterance (len ≤ 3 words), not as a substring.

### F1.2 — Coordinator path is a black box (P0)
**File:** `scripts/ai/aq-chat`, `_build_coordinator_delegate_payload()`
**Impact:** Agentic tasks block for 30–300s with no output. The coordinator's SSE streaming path exists (`sse_request` in `ai_coordinator_handlers.py`) but `aq-chat` never enables it. Users cannot tell if the model is working or hung.
**Fix:** Enable `streaming_mode=True` in the coordinator delegate payload; switch from `httpx.post()` to `httpx.stream()` in `aq-chat`.

### F1.3 — KeyboardInterrupt during coordinator call orphans subprocess (P1)
**File:** `scripts/ai/aq-chat`, run loop `except KeyboardInterrupt: continue`
**Impact:** Ctrl-C swallows interrupt without cancelling coordinator call. `local_agent_runtime.py` subprocess keeps running, holding the llama.cpp slot for up to 210s. Next user message gets 503 `local_slot_busy`.
**Fix:** Catch KeyboardInterrupt before the coordinator call; send coordinator cancellation signal; then continue.

### F1.4 — No cold-start indicator (P2)
**Impact:** First message after service start takes 15–30s for model warm-up with no feedback to user. User assumes hang.
**Fix:** Check `/health` on startup; if model not warmed, show a one-time "Model warming up..." message.

---

## Critical Findings — ROLE 2: Inference Systems Engineer

### F2.1 — Main proxy bypasses `build_llama_payload()` SSOT entirely (P0)
**File:** `ai-stack/switchboard/switchboard.py`, `proxy()` handler (~line 2726–2768)
**Impact:** `build_llama_payload()` is called in exactly one place — a 4-token startup probe. Every production request flows through `proxy()` which constructs payloads inline. `repeat_penalty: 1.08`, `repeat_last_n: 64`, `stream_options: {include_usage: True}`, and `frequency_penalty: 0.0` for structured outputs are NEVER applied. Token usage in telemetry is always an estimate (fallback estimator), never actual.
**Fix:** Route all local proxy calls through `build_llama_payload()`. Minimum: apply `stream_options: {include_usage: True}` unconditionally for local streams so actual token counts reach telemetry.

### F2.2 — No circuit breaker for llama.cpp (P0)
**File:** `ai-stack/switchboard/switchboard.py`, `_call_upstream_with_resilience()` (~line 2358)
**Impact:** `breaker = None` when `service_name == "llama"`. When llama.cpp crashes, every in-flight request retries 3× with backoff before failing. Recovery blocked for up to 3600s. Remote providers have circuit breakers; the local path that serves 100% of local traffic does not.
**Fix:** Add llama.cpp circuit breaker with open/half-open/closed states; wire into `_call_upstream_with_resilience()` on the local path.

### F2.3 — `local-tool-calling` token budget exceeds n_ctx (P0)
**File:** `ai-stack/switchboard/switchboard.py`, profile definition (~line 394)
**Impact:** `maxInputTokens=12000` + `maxOutputTokens=2048` = 14048 total against `n_ctx=8192`. Code comment cites "16384 ctx headroom" — wrong. Any tool-calling session with moderate history silently overflows context, causing truncation or rejection.
**Fix:** Set `maxInputTokens=6000`, `maxOutputTokens=2048` (= 8048, within 8192 with margin).

### F2.4 — `enable_thinking` not verified in proxy path (P1)
**File:** `ai-stack/switchboard/switchboard.py`, proxy payload construction
**Impact:** `build_llama_payload()` correctly places `enable_thinking: false` in `chat_template_kwargs`. But since `proxy()` bypasses `build_llama_payload()`, if a caller omits the field, thinking tokens will fill the context window producing empty responses.
**Fix:** Add a pre-flight check in `proxy()` for local targets: if `chat_template_kwargs.enable_thinking` is not explicitly `false`, inject it.

---

## Critical Findings — ROLE 3: Agent Coordination Engineer

### F3.1 — `collective_memory_search_handler` routes to wrong backend (P0)
**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py:838`
**Impact:** Handler calls AIDB pgvector for `collection="knowledge"`, but `"knowledge"` is in `_QDRANT_COLLECTIONS` — should go through `_query_qdrant_direct`. Every `collective_memory_search` tool call silently queries the wrong backend and returns wrong content.
**Fix:** Replace body with `return await _query_qdrant_direct(query, "knowledge", limit)`.

### F3.2 — `_sanitize_json` misses control chars below `\x20` (P1)
**File:** `ai-stack/local-agents/tool_registry.py`, `_sanitize_json()`
**Impact:** Only escapes `\n`, `\r`, `\t`. `\x08` (backspace) and other low-order control chars emitted by Qwen3 pass through → `json.loads` rejects output → `parse_tool_call_from_llama` returns `None` → tool loop silently terminates with raw JSON as final answer.
**Fix:** Add catch-all: `elif ord(ch) < 0x20: result.append(f"\\u{ord(ch):04x}")`.

### F3.3 — Tool loop has no progress signal to coordinator (P1)
**File:** `ai-stack/local-agents/agent_executor.py`, `execute_task()`
**Impact:** Long-running tool loops (5+ steps, each 30–60s) produce no intermediate output. Coordinator has no heartbeat to distinguish "working" from "hung". After 300s the whole task is killed regardless of progress.
**Fix:** Emit a heartbeat event every N tool calls; coordinator extends timeout on each heartbeat.

### F3.4 — Agent loop processes tools serially — no parallelism (P2)
**File:** `ai-stack/local-agents/agent_executor.py`
**Impact:** All tool calls are sequential even when independent. Multi-tool tasks (e.g., query_aidb + get_hint + get_working_memory in PRE-FLIGHT) run one-at-a-time.
**Fix:** Detect independent tool calls (no data dependency between them) and `asyncio.gather()`.

---

## Critical Findings — ROLE 4: AI/Agentic Research Scientist

### F4.1 — No structured output enforcement for tool calls (P0)
**Impact:** Tool call extraction uses `rfind('{"function"')` — fragile text parsing. llama.cpp supports grammar-constrained generation (`grammar` field in payload). For tool-calling turns, a GBNF grammar enforcing the JSON schema of valid tool calls would eliminate parse failures entirely.
**Fix:** Generate per-session GBNF grammar from registered tool schemas; inject into `build_llama_payload()` for tool-calling steps only.

### F4.2 — PRE-FLIGHT RESEARCH block runs even for trivial tasks (P2)
**File:** `ai-stack/local-agents/agent_executor.py`, `BEHAVIORAL CONTRACT` system prompt
**Impact:** Every agentic task starts with `get_hint + query_aidb + get_working_memory` — adds 90–180s to every task including those that don't need institutional context. No classification gate.
**Fix:** Add task-complexity classifier; skip PRE-FLIGHT for low-complexity tasks (single file edit, factual lookup). Only run for tasks classified as research/synthesis/multi-step.

### F4.3 — No episodic memory across aq-chat sessions (P2)
**Impact:** Each aq-chat session starts cold. Prior conversation context, user preferences, and in-progress work state are not preserved between CLI invocations. Users must re-establish context every session.
**Fix:** Implement lightweight session persistence — store last N turns in coordinator working memory, hydrate on next session start.

### F4.4 — Feedback loop deficit (P0 — systemic) 
**Impact:** Review findings, quality signals, and critique patterns are not consistently written to AIDB collections. Each new agent dispatch re-derives knowledge that has already been established. The training pipeline captures telemetry but not expert critique knowledge.
**Design:** Close the loop WITHOUT recency bias by:
- Writing all review PRD findings as `skills-patterns` / `best-practices` entries in AIDB after consolidation
- Tagging each entry with `review_phase`, `severity`, and `component` — NOT with timestamp as primary sort key
- Future agents query AIDB before starting, retrieve relevant patterns, but the query is scoped to component + severity, not "latest" — this prevents any single review from dominating future dispatches
- The training ingest pipeline promotes consolidated PRD findings to AIDB after each phase close

---

## Feedback Loop Architecture (addressing user requirement)

```
Phase Review → Consolidated PRD → seed-rag-knowledge.py →
  AIDB collections (skills-patterns, best-practices, error-solutions)
       ↓
Future agent dispatch → query_aidb (by component + severity) →
  Agent prompt enriched with relevant historical patterns
       ↓
Agent produces review → new findings discovered →
  Loop: NEW findings weighted equally with historical ones
  (not recency-weighted — tagged by severity not timestamp)
```

Key invariant: agents query AIDB by TOPIC (e.g., "switchboard streaming") not by RECENCY. A 6-month-old best-practice is as valid as a 1-day-old finding if both are tagged `component=switchboard`. This preserves cognitive diversity across sessions.

---

## Severity Matrix

| Finding | Role | Severity | File | Impact |
|---------|------|----------|------|--------|
| F2.1 — proxy bypasses build_llama_payload | Inference | P0 | switchboard.py:2726 | Wrong payloads to llama.cpp on every production request |
| F2.2 — No llama.cpp circuit breaker | Inference | P0 | switchboard.py:2358 | Cascading failures when llama.cpp crashes |
| F2.3 — local-tool-calling exceeds n_ctx | Inference | P0 | switchboard.py:394 | Silent context overflow on moderately long sessions |
| F3.1 — collective_memory_search wrong backend | Coordination | P0 | ai_coordination.py:838 | Memory searches always return wrong content |
| F1.2 — Coordinator path is black box | CLI/UX | P0 | aq-chat | 30-300s silent wait on every agentic turn |
| F1.1 — Substring routing misclassification | CLI/UX | P0 | chat_intent.py | Agentic commands silently downgraded to fast-path |
| F4.1 — No structured output enforcement | AI Research | P0 | agent_executor.py | Fragile tool call extraction; parse fails on control chars |
| F4.4 — Feedback loop deficit | AI Research | P0 | systemic | Expert knowledge not persisting across phases |
| F2.4 — enable_thinking not verified | Inference | P1 | switchboard.py | Context fill risk if callers omit field |
| F3.2 — _sanitize_json misses control chars | Coordination | P1 | tool_registry.py | Silent task termination on control char emission |
| F3.3 — No heartbeat from tool loop | Coordination | P1 | agent_executor.py | 300s hard kill regardless of progress |
| F1.3 — KeyboardInterrupt orphans subprocess | CLI/UX | P1 | aq-chat | llama.cpp slot held for 210s after Ctrl-C |
| F4.2 — PRE-FLIGHT on trivial tasks | AI Research | P2 | agent_executor.py | +90-180s latency on simple tasks |
| F4.3 — No cross-session episodic memory | AI Research | P2 | coordinator | Users re-establish context every session |
| F3.4 — Serial tool calls (no parallelism) | Coordination | P2 | agent_executor.py | 3× longer PRE-FLIGHT phase than necessary |
| F1.4 — No cold-start indicator | CLI/UX | P2 | aq-chat | Silent 15-30s hang on first message |

---

## Architecture Recommendations

1. **Switchboard SSOT enforcement**: All local proxy paths must route through `build_llama_payload()`. This is a one-time refactor of `proxy()` that eliminates an entire class of configuration drift bugs.

2. **Grammar-constrained tool calling**: Generate GBNF grammar from tool registry schemas at session start; inject for tool-calling turns only. Eliminates text parsing fragility entirely.

3. **Coordinator streaming**: Wire `sse_request=True` from aq-chat to coordinator. This is already implemented server-side — only the client needs updating.

4. **AIDB feedback loop as first-class concern**: Add a `post_phase_rag_seed()` step to the commit discipline (CLAUDE.md Rule 8a+). After every phase close, expert findings are seeded to AIDB before the next phase begins.

5. **Context overflow guard**: Switchboard `proxy()` should check total token count against `n_ctx - 512` before forwarding. Reject with a useful error rather than silently truncating.

## What's Working Well

- **Architecture fundamentals**: aq-chat → intent → coordinator/fast-path → switchboard → llama.cpp is the right design. The seam-level bugs don't invalidate the architecture.
- **Two-phase token budget (512/1200)**: Correct and working. Phase 159 fix holds.
- **run_id hoist** (Phase 175, ded880bd): Correctly eliminates the streaming closure NameError.
- **PRE-FLIGHT RESEARCH block**: The pattern is correct even if the trigger conditions need refinement. Agents having institutional knowledge before acting is right.
- **Training data pipeline**: tool_result events now captured (Phase 174), quality scoring calibrated (Phase 173). Direction is correct.
- **AppArmor + systemd isolation**: Security posture is strong. Services are properly sandboxed.

## Open Questions

1. Should `local-tool-calling` profile be split into `local-tool-calling-short` (8k ctx, current) and `local-tool-calling-long` (future, larger context model)?
2. Grammar-constrained generation requires GBNF schema generation from tool registry. Is this worth the added complexity vs. a more robust JSON extractor?
3. Should the coordinator delegate endpoint return a task-id immediately and let aq-chat poll/stream, rather than blocking the HTTP connection for 300s?
