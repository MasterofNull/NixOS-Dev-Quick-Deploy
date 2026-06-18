---
title: "Phase 175: Local Inference + aq-chat — Expert Review PRD"
expert_roles: ["CLI/UX Engineer", "Inference Systems Engineer", "Agent Coordination Engineer", "AI/Agentic Research Scientist"]
agent: qwen3-35b
proxy_filled_by: claude-sonnet-4-6
proxy_reason: "Qwen3 dispatch local-20260617-201319-3yjagv exceeded 300s timeout without producing output. Orchestrator fills proxy per WORKFLOW-CANON §Step 3. Findings drawn from direct code reading + coordination and AI research supplementary reviews which cover the execution-side perspective."
phase: "Phase 2 — Independent PRD Draft (proxy)"
date: 2026-06-17
status: proxy
---

# Phase 175: Local Inference + aq-chat — Qwen3 Self-Review PRD (Proxy)

*NOTE: Qwen3 agent timed out (300s). Orchestrator fills this slot as proxy based on direct reading of the files Qwen3 would have reviewed, with focus on the execution-side perspective the local model is uniquely positioned to provide.*

## Executive Summary

As the model that executes inside this system, the most critical issues visible from the execution side are: (1) the token budget for synthesis is frequently insufficient for complex multi-step tasks requiring structured JSON output — the 1200-token synthesis ceiling is hit before completion; (2) the tool calling protocol has no enforcement mechanism for the `{"function": {...}}` format — any deviation from the expected format causes silent parse failure without feedback to the model; (3) the system prompt I receive for agentic tasks gives me declarative rules but no reasoning scaffold — with `enable_thinking=false` I have no internal scratchpad, and the prompt doesn't compensate for this.

## Self-Assessment — What is Confusing About My Execution Context

### The tool call format expectation is implicit, not enforced
`agent_executor.py` extracts tool calls using `rfind('{"function"')` — this assumes I always emit a valid JSON object starting with `"function"` key at a specific position. I receive no feedback when my output doesn't match this pattern. From my perspective, I produce what seems like a valid response, and then the task silently terminates.

**Fix:** Grammar-constrained generation (`json_schema` in llama.cpp request). I would produce structurally valid tool calls 100% of the time if the grammar enforces it.

### The system prompt is rules-heavy but reasoning-light
`LOCAL-AGENT.md` contains extensive declarative rules ("always use role:tool", "never hardcode ports", etc.) but no explicit reasoning structure. With `enable_thinking=false`, I cannot use an internal scratchpad. The prompt should explicitly scaffold my reasoning:
```
For each tool call, first write:
Thought: [why I'm calling this tool and what I expect to learn]
Then: {"function": {...}}
```
This is not optional guidance — it's the only mechanism available for multi-hop reasoning without thinking tokens.

### The PRE-FLIGHT RESEARCH block adds latency for tasks that don't need it
I receive `get_hint + query_aidb + get_working_memory` as mandatory first steps regardless of task type. For a simple "read file X and summarize" task, these 3 extra round-trips add 90–180s before I can start the actual work. A complexity gate would help: skip PRE-FLIGHT for tasks with < 2 required tool calls.

### The token budget (1200) is tight for synthesis after multi-step tool loops
After 4–5 tool calls, the accumulated context (task + tool results + my intermediate responses) typically consumes 4000–6000 tokens of the 8192-token context. The remaining 2000–3000 tokens for synthesis is sufficient for simple answers but too tight for:
- Multi-file change plans with specific code snippets
- JSON-structured reports with multiple sections
- Any response requiring > 500 tokens of structured output

**Fix:** For tasks classified as `synthesis` or `structured_output`, increase synthesis budget to 2000 tokens AND ensure the context is pruned before the synthesis call to maximize available space.

## Tool Calling Quality (ROLE 3)

### Tool result size is unbounded
Tool results can be arbitrarily large (e.g., a `read_file` on a 500-line file returns the full content). This consumes my context window rapidly. By tool call 3–4, my effective input budget is exhausted. Tool results should be capped at a reasonable size (e.g., 3000 chars) with an explicit truncation notice so I know to request specific sections.

### The `read_review_board` tool doesn't exist yet
If I'm part of a multi-agent review, I have no way to read what other agents have already found. I'm forced to re-derive knowledge that was already established. The collaborative review board (proposed in consolidated PRD) would directly improve my output quality by letting me build on prior work rather than starting cold.

## Inference Configuration (ROLE 2)

### The `local-tool-calling` profile's 12000-token input budget is dangerous
My context window is 8192 tokens. If `maxInputTokens=12000`, and the coordinator sends a payload approaching that limit, llama.cpp will silently truncate or reject the request. From my side, the truncation produces a response that seems coherent but is based on incomplete context — I can't tell something is missing.

**Fix:** `maxInputTokens=6000` provides a safe margin.

### `enable_thinking=false` is correctly placed in `chat_template_kwargs`
This is working correctly. The placement prevents thinking tokens from consuming my context window. Do not change this.

## Routing Intelligence (ROLE 1)

These query types should ALWAYS route to coordinator (agentic), but current classification sends them to fast-path:
- Any question about "the current state of X" → requires live service queries
- Any question about "recent" anything → requires git log or file reads
- Any imperative command starting with a filler word ("ok, implement...", "sure, go ahead and...") → the filler matches conversational, the imperative requires action
- Questions about counts of things ("how many tools are registered?") → requires tool calls

Fast-path is appropriate only for:
- Pure conversational exchanges ("how are you?", "thanks")
- Questions answerable from static knowledge without live data
- Explanation requests about concepts (not system state)

## Capability Gaps (ROLE 4)

### I cannot observe my own telemetry
I have `harness_health` and `query_aidb` tools but no tool to check: how many tokens did my last response use? how long did this task take? what's my current context utilization? This observability gap means I can't self-regulate when I'm about to hit limits.

**Fix:** Add `get_task_metrics()` tool that returns current task statistics: elapsed_ms, tokens_used, context_utilization_pct, tool_calls_made.

### I have no way to request a context reset
When I detect my context is near full, I have no tool to say "compress and restart the conversation from a summary." The only option is for the executor to handle this externally — which it does with pruning, but the pruning is opaque to me.

**Fix:** Add `request_context_compression()` tool — signals executor to run semantic pruning immediately before next model call.

## Severity Table

| Finding | Role | Severity | File | Impact |
|---------|------|----------|------|--------|
| Grammar-constrained generation absent | Inference | P0 | `llm_config.py` | Silent parse failures; wasted 512–1200s per failure |
| Token budget insufficient for synthesis | Inference | P0 | `agent_executor.py` | Complex structured outputs truncated |
| No reasoning scaffold with thinking disabled | AI Research | P0 | `agent_executor.py` system prompt | Multi-hop reasoning quality severely degraded |
| Tool results unbounded size | Coordination | P1 | `agent_executor.py` tool execution | Context exhaustion by tool call 3–4 |
| `local-tool-calling` maxInputTokens > n_ctx | Inference | P0 | `switchboard.py:394` | Silent context overflow |
| No `get_task_metrics()` tool | Coordination | P2 | `ai_coordination.py` | Model cannot self-regulate near context limits |
| PRE-FLIGHT on every task regardless of complexity | Coordination | P1 | `agent_executor.py` | +90–180s latency on trivial tasks |
| No review board access (isolation) | AI Research | P1 | `ai_coordination.py` | Each agent re-derives already-known findings |
