---
title: "Phase 175-A: Immediate Correctness Fixes — Implementation Evidence"
doc_type: plan
id: phase175a-implementation
parent_prd: phase175-PRD-CONSOLIDATED
phase: "Phase 175-A"
date: 2026-06-17
status: complete
files_changed:
  - scripts/ai/lib/chat_intent.py
  - ai-stack/local-agents/builtin_tools/ai_coordination.py
  - ai-stack/local-agents/agent_executor.py
  - ai-stack/agents/runtimes/local_agent_runtime.py
  - scripts/ai/aq-chat
  - scripts/testing/test-aq-chat-local-tool-profile.py
---

# Phase 175-A: Implementation Evidence

8 no-rebuild correctness fixes. See `.agent/phase175-PLAN-CONSOLIDATED.md` for full spec.

## A1 — Routing substring over-matching (chat_intent.py)
- Removed question-prefix substrings ("what is", "explain ", etc.) from `_CONVERSATIONAL_INTENTS`
- Short affirmatives now require ≤ 3-word utterance (word-count gate)
- Added `_SYSTEM_CONTEXT_KEYWORDS` override for live-system queries
- Result: "what are the open issues?" → agentic ✓; "ok" → conversational ✓

## A2 — collective_memory_search_handler wrong backend (ai_coordination.py:838)
- Was calling AIDB pgvector `/vector/search` for collection="knowledge"
- "knowledge" is a Qdrant collection (in `_QDRANT_COLLECTIONS` since Phase 175)
- Fixed: replaced with `_query_qdrant_direct(query, "knowledge", limit)`

## A3 — Context pruner pair integrity (agent_executor.py)
- Fallback prune (6 < len ≤ 8) now validates messages[2:4] are (assistant, tool) pair
- Skips prune if pair check fails to prevent dangling role:tool

## A4 — Shell injection blocklist (local_agent_runtime.py:90)
- Added `$` to `_ARG_BLOCKLIST_CHARS` to block `$()` and `${}` substitution

## A5 — Malformed ISO timestamp (agent_executor.py:466)
- `datetime.now(timezone.utc).isoformat()+"Z"` → `strftime("%Y-%m-%dT%H:%M:%S.%f")+"Z"`
- Fixes "+00:00Z" double-suffix on agent-run-events.jsonl timestamps

## A6 — CoT elicitation prefix (agent_executor.py)
- Added "Think step by step... Thought: ..." to user task message
- Compensates for enable_thinking=false removing Qwen3 internal scratchpad

## A7 — Coordinator streaming to aq-chat (aq-chat)
- `_build_coordinator_delegate_payload` now sets `streaming_mode=True`
- Coordinator call changed from blocking `httpx.post()` to `httpx.stream()`
- SSE events parsed and forwarded token-by-token to terminal
- Async 202 dispatch and error paths preserved
- Pre-commit test updated to validate streaming pattern

## A8 — KeyboardInterrupt orphan (aq-chat)
- Handler now clears `interrupt_event` and prints "Cancelled." before continuing
- Prevents interrupt state from leaking into next prompt turn
