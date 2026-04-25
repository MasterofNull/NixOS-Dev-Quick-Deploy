# Phase 8 — Architecture Assessment: Cutting-Edge AI Harness Patterns

Assessment date: 2026-04-24
Status: active

## Summary

Assessment of the NixOS-Dev-Quick-Deploy AI harness against 2026 industry best practices
for production AI agent infrastructure.

## Strengths (Already Implemented)

| Pattern | Implementation | Status |
|---------|---------------|--------|
| Progressive disclosure / context budgeting | `_progressive_disclosure`, token budgets per tier | ✓ Production |
| Hybrid RAG (dense + keyword) | Qdrant + PostgreSQL FTS via `route_handler.py` | ✓ Production |
| Semantic caching | Quality-gated response cache, 88% hit rate | ✓ Production |
| Tool security auditing | `ToolSecurityAuditor` with policy hash + cache | ✓ Production |
| Hint injection system | Contextual bandit + diversity controls | ✓ Production |
| PRSI self-improvement loop | Phases 0–7 complete, eval-gated promotions | ✓ Production |
| Circuit breakers | Per-backend breakers in hybrid coordinator | ✓ Production |
| Eval framework | Holdout packs, contamination guards, canary suite | ✓ Production |
| Memory recall | `recall_agent_memory` wired, 11.7% recall share (rising) | ✓ Active |
| Reasoning patterns | ReAct, ToT, Reflexion per task phase | ✓ Planned |

## Gaps Identified and Actions Taken

### Gap 1 — Qwen3 Thinking Mode Not Utilized (FIXED: commit 543537e)

**Industry pattern**: Qwen3 natively supports `/no_think` (fast non-CoT mode) and
`/think` (chain-of-thought budget). Production deployments route simple tasks via
no-think for 3-5x latency reduction.

**Impact**: Delegate agent was generating full CoT reasoning (~2000+ tokens) before
the actual response, causing 5+ minute completions for simple tasks.

**Fix**: Agent subprocess now prepends `/no_think` by default. Callers set
`thinking_mode: "on"` in the request payload for complex reasoning tasks.

### Gap 2 — Stop Sequences Missing (FIXED: commit 543537e)

**Industry pattern**: All LLM inference calls in production use explicit stop sequences
to prevent runaway generation past the EOS token.

**Fix**: Added `stop: ["<|im_end|>", "<|endoftext|>"]` to all delegate inference calls.

### Gap 3 — Delegate max_tokens=4096 (FIXED: commit 8d4178b)

**Fix**: Default changed to 768 (matches `continue-local` profile `maxOutputTokens`).
Callers override via `max_tokens` param.

### Gap 4 — Delegate Profile Mismatch (FIXED: commit 543537e, reverted partial in follow-up)

**Issue**: Delegate used `continue-local` (maxInputTokens=1200) instead of
`local-agent` (maxInputTokens=3500, hint injection enabled, proper agentic prompt).

**Initial fix**: `_profile_for_role()` routed coordinator role to `local-agent`.

**Regression**: `local-agent` carries a ~2000-char system prompt (ports, routing,
commit format) vs `continue-local` ~150 chars. For simple delegate tasks like
"reply with only: DELEGATE_OK", the heavier profile caused >300s prefill, negating
the timeout fix entirely.

**Final fix**: Reverted coordinator role back to `continue-local`. Coder role keeps
`local-tool-calling` (function-calling grammar needed). Lightweight profile keeps
delegate completions within the 90-180s budget.

### Gap 5 — Delegate Timeout 60s (FIXED: commit a36e715)

**Fix**: Default raised 60s → 180s. Was causing 75% failure rate.

## Remaining Structural Improvements (Prioritized)

### P1: Async Task Queue for Delegate (Phase 8.6) — FIXED

**Pattern**: Google ADK, LangGraph, and AutoGEN use async work queues (Redis Streams,
asyncio Queue) for agent dispatch. The current `_spawn_local_agent` blocks the HTTP
handler for the full inference duration.

**Impact**: Single slow delegate call blocks the aiohttp event loop worker.
**Fix**: `async_mode=true` in request body triggers `asyncio.create_task()` dispatch.
Returns `{"task_id": "...", "status": "pending", "poll_url": "..."}` (HTTP 202)
immediately. Caller polls `GET /control/ai-coordinator/delegate/status/{task_id}`.
Module-level `_DELEGATE_TASK_REGISTRY` holds state (TTL 600s, lazy cleanup).
Synchronous mode (default) unchanged for backwards compat.
Memory auto-consolidation (8.8) runs in the async background task on success.

### P2: OpenAI-Compatible Tool Calling in Delegate (Phase 8.7)

**Pattern**: llama.cpp supports `tools: [...]` in the OpenAI-compatible API.
Wiring MCP tool definitions into the delegate agent enables multi-step execution
with proper function-call tracking.

**Current state**: Agent does single-shot completion with no tool access.
**Fix**: Pass a curated tool schema (harness CLIs as functions) to the delegate
inference call. Parse `tool_calls` in the response and dispatch via MCP bridge.
**Effort**: High — requires function-call schema for each MCP tool

### P3: Memory Auto-Consolidation (Phase 8.8)

**Pattern**: Successful agent completions should auto-store structured memories
(task type, outcome, key context) for future recall.

**Current state**: Memory recall works (11.7% share, rising) but memories must be
manually stored. The `_store_memory` function exists but isn't called on delegate success.

**Fix**: After `_spawn_local_agent` returns `ok=True`, call `_store_memory` with a
structured summary of the task and result.
**Effort**: Low — 30 min

### P4: Streaming Inference for Delegate (Phase 8.9)

**Pattern**: Stream inference results to the caller to reduce perceived latency.
The caller can display partial results while generation continues.

**Current state**: Delegate uses `stream: False`, full round-trip blocks.
**Fix**: Enable `stream: True` in agent subprocess, pipe SSE to caller via
`web.StreamResponse`.
**Effort**: Medium — 2 hours

### P5: Parallel Retrieval + Inference Pipeline (Phase 8.10)

**Pattern**: While waiting for LLM inference, pre-fetch and pre-process retrieval
results. Return the best available combination within a deadline.

**Current state**: `/query` is sequential — retrieval then generation.
**Fix**: `asyncio.gather()` for parallel qdrant retrieval + cache check, then feed
results to inference only if both succeed within budget.
**Effort**: Medium — 2 hours

### P6: Thinking Budget Routing (Phase 8.11)

**Pattern**: Route to thinking mode based on task complexity signal:
- Simple factual / short-answer → `/no_think` (90-120s → target 30-60s)
- Multi-step reasoning / code → `/think budget=1024` (better quality)
- Complex architecture decisions → `/think budget=4096`

**Current state**: No thinking mode routing; all tasks use no-think default.
**Fix**: Add complexity classifier in `_ai_coordinator_route_by_complexity()` that
sets `thinking_mode` and `thinking_budget_tokens`.
**Effort**: Low-Medium — 1 hour

## Industry Pattern Reference (2026)

| Pattern | Reference | Our Status |
|---------|-----------|------------|
| Structured output (JSON schema) | OpenAI response_format, Anthropic tool_use | Partial — hints/plans use JSON, delegate does not |
| Thinking mode routing | Qwen3, DeepSeek-R1, Claude extended thinking | **Gap** — now no-think default added |
| Stop sequences | Universal best practice | **Fixed** in commit 543537e |
| Async agent dispatch | LangGraph, AutoGEN, Google ADK | **Gap** — P1 above |
| Tool calling in agents | OpenAI tools API, MCP | **Gap** — P2 above |
| Retrieval-augmented generation | LlamaIndex, LangChain RAG | ✓ Production |
| Semantic/contextual caching | GPTCache, semantic-cache | ✓ Production |
| Memory as a service | MemGPT, Letta, mem0 | Partial — recall works, consolidation missing |
| Multi-agent supervisor | CrewAI, LangGraph supervisor | Partial — PRSI + hybrid coordinator |
| Eval + self-improvement | DSPy, OPRO | ✓ Production (Phases 0-7) |
| Continuous batching | vLLM, SGLang | **Gap** — llama.cpp single-slot |
| Model routing by capability | RouteLLM | Partial — local/remote, not task-type |

## Next Session Targets

1. Phase 8.6: Async delegate task pool (unblock event loop)
2. Phase 8.8: Memory auto-consolidation on delegate success
3. Phase 8.11: Thinking budget routing by complexity
4. Phase 8 validation: run delegate smoke gate after nixos-rebuild with all fixes

## Validation Checklist

After all Phase 8 fixes are deployed:
- [ ] `ai_coordinator_delegate` smoke: success rate ≥ 90% in 7d window
- [ ] Delegate response time: p50 ≤ 120s, p95 ≤ 180s
- [ ] Memory recall share ≥ 15%
- [ ] route_search >10s outlier rate ≤ 1%
- [ ] aq-qa 0: 39/39 pass
