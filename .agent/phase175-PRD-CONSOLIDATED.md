---
title: "Phase 175: Local Inference + aq-chat — Consolidated Expert Review PRD"
consolidator: claude-sonnet-4-6
source_drafts:
  - .agent/phase175-PRD-claude.md         # Claude: all 4 expert roles
  - .agent/phase175-PRD-gemini.md         # Gemini: all 4 expert roles
  - .agent/phase175-expert-review-cli-ux.md           # Supplementary: CLI/UX depth
  - .agent/phase175-expert-review-inference.md        # Supplementary: Inference depth
  - .agent/phase175-expert-review-agent-coordination.md  # Supplementary: Coordination depth
  - .agent/phase175-expert-review-ai-research.md      # Supplementary: AI Research depth
  - .agent/phase175-PRD-qwen3.md          # Qwen3: PENDING (timed out — proxy fill below)
phase: "Phase 3 — Consolidated PRD"
date: 2026-06-17
status: complete
---

# Phase 175: Local Inference + aq-chat — Consolidated Expert Review PRD

---

## Qwen3 Proxy Note

Qwen3 dispatch was initiated (task `local-20260617-201319-3yjagv`) but exceeded the 300s timeout without producing output. Per WORKFLOW-CANON proxy rules, orchestrator fills this slot below, drawing on findings from the supplementary agent coordination and AI research reviews which cover the execution-side perspective Qwen3 would have provided. The proxy PRD is at `.agent/phase175-PRD-qwen3.md` (written by orchestrator).

---

## Consolidation Notes — Cross-Agent Agreement and Divergence

### Points of Consensus (All Agents)

1. **Grammar-constrained generation is the highest-leverage single change.** Claude (F4.1), Gemini (ROLE 4), AI Research (Severity 10), Inference (SEV-1 context overflow link) all independently name it. llama.cpp's `json_schema` field eliminates the entire class of tool-call parse failures at near-zero runtime cost.

2. **The main proxy bypasses `build_llama_payload()` SSOT** — every production request flows through `proxy()` without touching the SSOT. Every agent identified this independently. Token usage telemetry is always estimated; `frequency_penalty`, `repeat_penalty`, `stream_options.include_usage` never applied.

3. **No circuit breaker for llama.cpp** while remote providers have one. When llama.cpp crashes, cascading retries block the path for up to 3600s.

4. **`local-tool-calling` token budget exceeds `n_ctx=8192`** — `maxInputTokens=12000` + `maxOutputTokens=2048` = 14048 against 8192. Silent overflow on any moderately long session.

5. **`collective_memory_search_handler` routes to the wrong backend** — calls pgvector for a Qdrant collection, silently returning wrong content on every invocation.

6. **Coordinator path is a UX black box** — 30–300s with no streaming output. Server-side SSE exists; aq-chat never enables it.

7. **Two divergent agent runtimes** (`agent_executor.py` via `aq-agent-loop` vs `local_agent_runtime.py` via coordinator) diverge independently. Behavior parity cannot be maintained this way.

### Divergence 1 — Routing Classification Severity

- **Claude + CLI/UX expert**: Substring matching (`"what is"`, `"explain "`, `"how does"`) is the P0 failure mode — legitimate agentic queries incorrectly fast-pathed to no-tools path.
- **Gemini**: Frames this as P2, noting most misclassifications recover gracefully; focuses more on the streaming UX gap.

**Consolidator assessment**: Claude/CLI-UX are correct. The table in the CLI/UX review shows 7 specific query patterns that require tools but are sent to fast-path. These produce subtly wrong responses (model plans without executing) that users may not notice. Classify as P0.

### Divergence 2 — Context Truncation Strategy

- **Gemini**: Current hardcoded `chars > 24768` dropping indices 2+3 can corrupt conversation structure — a dangling `role:tool` result without its preceding `role:assistant` call breaks the conversation graph.
- **Claude**: Identifies this as P1; proposes semantic pruning.
- **AI Research**: Proposes relevance-scored pruning with embedding similarity.

**Consolidator assessment**: Gemini's structural corruption finding is the most critical — a P0 correctness bug. The semantic/relevance-scored pruning (AI Research) is the right long-term direction but is Phase C scope. Phase A fix: preserve tool call/result pairs when pruning (Gemini's structural fix). Phase C: relevance-scored summarization.

### Divergence 3 — Qwen3 chain-of-thought

- **AI Research**: No explicit chain-of-thought elicitation exists; `enable_thinking=false` removes the internal scratchpad; explicit `"Think step by step:"` prefix is the recovery.
- **Gemini**: Notes that suppressing thinking globally is correct for latency; proposes profile-specific reasoning via ReAct/Reflexion for `research` profile.

**Consolidator assessment**: Both are correct and non-contradictory. Phase A: add explicit CoT elicitation prefix to agent task prompt (6 tokens). Phase B: profile-specific reasoning modes for research/synthesis tasks.

### Divergence 4 — Fallback Policy

- **Gemini**: `local_agent_runtime.py` falls back directly to llama.cpp when switchboard is unreachable, bypassing all telemetry and circuit breakers. This is a correctness concern.
- **Agent Coordination expert**: Identifies zombie subprocess risk and shell injection at `local_agent_runtime.py:90`.

**Consolidator assessment**: Both findings are correct. The fallback bypass is P1 (correctness degradation, not crash); the shell injection is P0 (security).

---

## Critical Findings — Consolidated Severity Matrix

### P0 — Blocking / Security

| # | Finding | Agent Source | File:Line | Impact |
|---|---------|-------------|-----------|--------|
| P0-1 | Main proxy bypasses `build_llama_payload()` SSOT | All agents | `switchboard.py:2726` | Wrong payloads on every production request; telemetry estimated not actual |
| P0-2 | No circuit breaker for llama.cpp | Claude/Inference | `switchboard.py:2358` | Cascading failure when llama.cpp crashes; remote has breakers, local doesn't |
| P0-3 | `local-tool-calling` maxInputTokens=12000 > n_ctx=8192 | Claude/Inference | `switchboard.py:394` | Silent context overflow on moderately long sessions |
| P0-4 | `collective_memory_search_handler` wrong backend | Coordination/Claude | `ai_coordination.py:838` | Every memory search silently returns wrong content |
| P0-5 | Coordinator path has no streaming to aq-chat | Claude/CLI-UX | `aq-chat` + `ai_coordinator_handlers.py` | 30–300s black box; SSE exists server-side, never wired to client |
| P0-6 | Routing substring match over-fires on agentic queries | CLI-UX/Claude | `chat_intent.py` | "what is", "explain", "how does" → fast-path; user gets plan not execution |
| P0-7 | Grammar-constrained generation absent | All agents | `llm_config.py` + `agent_executor.py` | Parse failures; at 1 tok/s each retry costs 512–1200 seconds |
| P0-8 | Shell injection vector in `local_agent_runtime.py` | Coordination | `local_agent_runtime.py:90` | `$()` in subprocess args — code injection if any tool result contains backtick/dollar |
| P0-9 | Context truncation drops indices 2+3 → dangling tool results | Gemini | `agent_executor.py` | Corrupt conversation graph; model sees tool result without preceding assistant call |

### P1 — Significant Degradation

| # | Finding | Agent Source | File:Line | Impact |
|---|---------|-------------|-----------|--------|
| P1-1 | Streaming regex fragmentation for `<think>` tags | Gemini | `switchboard.py:53` | Chunk-split think tags bleed into UI output |
| P1-2 | Fallback in `local_agent_runtime.py` bypasses switchboard telemetry | Gemini/Coordination | `local_agent_runtime.py` | Silent loss of circuit breaker + hint injection + telemetry on fallback |
| P1-3 | Zombie subprocess on coordinator timeout | Coordination | `ai_coordinator_handlers.py:1373` | Orphaned process holds llama.cpp slot up to 210s after Ctrl-C or timeout |
| P1-4 | `_emit_agent_event` malformed ISO timestamp `+00:00Z` | Coordination | `agent_executor.py:466` | Every event in `agent-run-events.jsonl` has corrupt timestamp; strict parsers reject |
| P1-5 | `_sanitize_json` misses `\x08` and control chars < 0x20 | Coordination | `tool_registry.py:606` | Tool call silently terminated; raw JSON returned as final answer |
| P1-6 | Registry memory leak on coordinator restart | Coordination | `ai_coordinator_handlers.py:1659` | In-memory registry lost on restart; running tasks orphaned |
| P1-7 | `enable_thinking` not verified in proxy path | Claude | `switchboard.py` proxy | Context fill risk if caller omits field; thinking tokens exhaust 8192 context |
| P1-8 | Two divergent runtimes | AI Research/Claude | `agent_executor.py` vs `local_agent_runtime.py` | Behavior parity impossible; prompts, tool counts, token budgets diverge |
| P1-9 | No explicit CoT elicitation with `enable_thinking=false` | AI Research | `agent_executor.py` system prompt | Multi-hop reasoning quality degraded without structured reasoning scaffold |
| P1-10 | `injectHints` code/doc mismatch on 2 profiles | Inference | `switchboard.py:294,390` | Context injection may be inactive for profiles it's documented as active |
| P1-11 | Inactivity timeout is dead code; 1-hour hang possible | Inference | `switchboard.py:56,2933` | Resource leak on hung streams |

### P2 — Quality / Maintainability

| # | Finding | Agent Source | File:Line | Impact |
|---|---------|-------------|-----------|--------|
| P2-1 | No per-session episodic memory across aq-chat invocations | Claude/AI Research | coordinator memory | Users re-establish context every session |
| P2-2 | PRE-FLIGHT RESEARCH block runs on every task regardless of complexity | Claude | `agent_executor.py` | +90–180s latency on trivial tasks |
| P2-3 | Serial tool calls — no async parallelism for independent calls | Claude | `agent_executor.py` | PRE-FLIGHT 3 calls take 3× longer than necessary |
| P2-4 | `stream_options.include_usage` missing from stream override | Inference | `switchboard.py:2834` | Usage chunk never arrives; fallback estimator runs on every local stream |
| P2-5 | Lane reservation logic is a stub (`pass`) | Inference | `switchboard.py:2869` | High-priority reservation semantics not implemented |
| P2-6 | Budget state file I/O is synchronous in async handler | Inference | `switchboard.py:2420,2438` | Blocks event loop during budget reads/writes |
| P2-7 | No feedback loop seeding — expert findings don't persist to AIDB | Claude | systemic | Each phase re-derives knowledge; institutional learning not accumulating |
| P2-8 | No collaborative review board — agents review in isolation | Claude/user | systemic | Agents can't build on each other's findings during review |

---

## Collaborative Review Board Protocol (New Design)

*Addressing user requirement: "agentic memories or agentic discussion boards/comms can be places we can temporarily place recent discoveries so that agents have easy access to the recent and other agent findings — a true collaborative approach."*

### Design

```
Phase Review Session:
  Orchestrator creates review board key: f"phase{N}-review-board"

  Per-agent flow:
    1. Agent queries working_memory for review board key → reads prior findings
    2. Agent reads codebase / runs analysis
    3. Agent writes each finding to working_memory with:
         {"board": f"phase{N}-review-board",
          "component": "switchboard|coordinator|aq-chat|...",
          "severity": "P0|P1|P2",
          "finding": "...",
          "agent": "gemini|claude|qwen3|...",
          "file_line": "switchboard.py:2726"}
    4. Next agent picks up step 1 → sees all prior findings → avoids duplication,
       can explicitly agree/disagree (adds "agrees_with": ["prior-agent-finding-id"])

  Post-phase:
    Orchestrator consolidates review board → PRD
    Consolidated findings seeded to AIDB (skills-patterns, best-practices)
    AIDB entries tagged by: component + severity (NOT timestamp as primary sort)

  Future agent dispatch:
    query_aidb(f"switchboard {task_component}", collection="skills-patterns")
    → Returns relevant historical patterns
    → Injected into system prompt
    NOT weighted by recency — weighted by component match + severity
```

### Anti-Recency-Bias Invariant

AIDB seeding uses **topic-first indexing**: the vector embedding encodes the FINDING CONTENT (component, behavior, root cause), not the phase number or date. A 6-month-old finding about `switchboard payload construction` scores equally with a 1-day-old finding on the same topic. Recency does not increase a finding's retrieval weight.

Agents are instructed: "Query AIDB for historical patterns on [component]. These are equally weighted regardless of when they were discovered. Novel findings not in AIDB are just as valid as historical ones."

### Implementation Files

| Component | Change | Phase |
|-----------|--------|-------|
| `ai-stack/local-agents/builtin_tools/ai_coordination.py` | Add `post_review_finding(board_key, component, severity, finding, file_line)` tool | C |
| `ai-stack/local-agents/builtin_tools/ai_coordination.py` | Add `read_review_board(board_key)` tool | C |
| `scripts/data/seed-rag-knowledge.py` | Add `--from-prd` flag: extract findings from PRD YAML + seed to AIDB | C |
| `.agent/WORKFLOW-CANON.md` | Add Step 2a: review board query before any multi-agent review | C |
| `scripts/ai/delegate-to-gemini` + `delegate-to-local` | Add `--review-board KEY` flag that injects board read at start | C |

---

## Architecture Recommendations

### 1. Switchboard SSOT Enforcement (P0-1, P0-3)
All `proxy()` local paths must route through `build_llama_payload()`. Minimum viable fix:
inject `chat_template_kwargs.enable_thinking=false`, `stream_options.include_usage=true`, 
`frequency_penalty=0.0` as a pre-flight guard on every local request. Full refactor routes 
through the SSOT.

### 2. Grammar-Constrained Tool Calling (P0-7)
Add `json_schema` field to `build_llama_payload()` when `task_type="tool_call"`. 
Generate schema from `ToolRegistry.get_all_schemas()` at session start. Eliminates entire 
class of parse failures; at 1 tok/s every prevented retry is 512–1200s saved.

### 3. Coordinator Streaming to aq-chat (P0-5)
`aq-chat` already has an SSE handler for fast-path. Add `streaming_mode=True` to coordinator 
delegate payload; switch coordinator call from `httpx.post()` to `httpx.stream()`. Server-side 
SSE is already implemented. This is a 2-file change.

### 4. Routing Classification Fix (P0-6)
Bound conversational phrase matching: match only when the phrase constitutes the entire 
utterance (token count ≤ 3), not as a substring. Add "requires context from files" classifier: 
questions about "the current state", "recent commits", "open issues" require tools regardless 
of surface phrase.

### 5. Unified Agent Runtime (P1-8)
Create `ai-stack/local-agents/base_runtime.py` with the shared execution core. Both 
`agent_executor.py` and `local_agent_runtime.py` become thin wrappers that instantiate 
`AgentRuntime` with their respective entry point config. Single source for: prompts, tool 
registry, token budget, context pruning, telemetry.

### 6. Conversation-Preserving Context Pruning (P0-9)
Replace hardcoded index dropping with a pair-aware pruner: always remove tool calls and 
their corresponding tool results together. Never leave a dangling `role:tool` without its 
preceding `role:assistant` call. Phase C: compress evicted pairs to a summary string.

---

## What's Working Well

- **Architecture fundamentals correct**: aq-chat → intent → coordinator/fast-path → switchboard → llama.cpp is the right design. Issues are seam-level, not structural.
- **`enable_thinking` placement**: `chat_template_kwargs.enable_thinking=false` correctly placed per Qwen3 requirements. Not a top-level field.
- **`role:"tool"` compliance**: `agent_executor.py` correctly uses `role:"tool"` not `role:"function"`. Qwen3 silent-drop bug is mitigated.
- **Two-phase token budget (512/1200)**: Phase 159 fix holds correctly.
- **AppArmor + systemd isolation**: Security posture is strong. Services are properly sandboxed.
- **Memory architecture**: `store_memory` + `get_working_memory` + AIDB Qdrant (14 collections, 8220+ vectors) is ahead of many production agent systems.
- **run_id hoist** (Phase 175, ded880bd): Correctly eliminates the streaming closure NameError.
- **PRE-FLIGHT RESEARCH pattern**: Direction is correct — agents having institutional context before acting. Trigger conditions need refinement, not the pattern itself.

---

## Open Questions (Require User Input)

1. **Coordinator delegate response model**: Should aq-chat block on the HTTP connection for 300s (current), or should coordinator return a task-id immediately and aq-chat poll/stream? The second model is more robust but requires a new polling loop in aq-chat.

2. **Grammar enforcement scope**: Full JSON schema from ToolRegistry (maximum correctness, more complex) or a relaxed generic JSON grammar (simpler, catches most failures)? Recommend: generic JSON grammar first, per-tool schema as Phase C enhancement.

3. **Qwen3 chain-of-thought mode**: Global `"Think step by step:"` prefix on ALL agent tasks (simpler), or profile-specific CoT elicitation (research/synthesis profiles only)? Recommend: global for Phase A, profile-specific for Phase B.

4. **Runtime unification timeline**: Unifying the two runtimes is high-value but medium-risk refactor. Should this block Phase A fixes or proceed in parallel?

5. **Review board persistence**: Should the review board live in coordinator working memory (session-scoped, lost on restart) or be written to a tracked file in `.agent/review-boards/`? Recommend: coordinator memory during session + file archive at consolidation.
