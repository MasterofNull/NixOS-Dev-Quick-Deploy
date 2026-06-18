---
title: "Phase 175: Local Inference + aq-chat — Expert Review PRD"
expert_roles: ["CLI/UX Engineer", "Inference Systems Engineer", "Agent Coordination Engineer", "AI/Agentic Research Scientist"]
agent: gemini
phase: "Phase 2 — Independent PRD Draft"
date: 2026-06-17
status: draft
---

### Executive Summary

The NixOS local AI inference stack (Qwen3-35B + llama.cpp + Hybrid Coordinator) establishes a powerful, hardware-constrained AI mesh. The tight integration between the orchestrator, switchboard proxy, and the Qwen3 endpoint provides an efficient local-first ecosystem. 

However, critical gaps exist across the system. The user experience suffers from cold-start latency due to reasoning-token stripping, payload construction lacks strict enforcement of penalties for tool-calling, the agent executor relies on brittle hardcoded truncation for context management, and the system fails to utilize state-of-the-art structured output grammar features. Addressing these will elevate the stack from a functional pipeline to a highly resilient and transparent AI platform.

### Critical Findings (ROLE 1 — CLI/UX)

- **Severity P1 — Cold-Start UX Latency**: `ai-stack/switchboard/switchboard.py` (`_emit_reasoning_summary_events`) strips `<think>` tokens from the output and emits them as telemetry. For profiles where thinking is enabled, this results in significant Time-To-First-Token (TTFT) latency in `scripts/ai/aq-chat`, as the user sees nothing while the model generates internal thoughts. **Impact:** Degraded UX; users may terminate the process assuming it has frozen.
- **Severity P2 — Opaque Fallback Messages**: `scripts/ai/aq-chat` does not gracefully map underlying circuit breaker errors (e.g., `CircuitBreakerOpenError`) to actionable CLI instructions. **Impact:** Users are left debugging switchboard logs instead of understanding inference capacity issues.
- **Severity P2 — Intent Misclassification Path**: `scripts/ai/chat_intent.py` classifications might skip agentic tools silently. L0 Llama direct paths lack visibility into why a tool-calling profile wasn't selected.

### Critical Findings (ROLE 2 — Inference Systems)

- **Severity P1 — Streaming Buffer Fragmentation**: `ai-stack/switchboard/switchboard.py` strips `<think>` tags using a regex (`_THINK_BLOCK_RE.finditer`). If a stream chunk splits the tag (e.g., `</thi` and `nk>`), the regex will fail to strip it properly in a live streaming context, bleeding raw reasoning tags into the UI. **Impact:** Corrupted streaming output and broken tool-parsing.
- **Severity P1 — Tool-Calling Penalties**: `LOCAL-AGENT.md` explicitly mandates `frequency_penalty: 0.0` for structured outputs to prevent early EOS, but `ai-stack/mcp-servers/shared/llm_config.py` does not strictly enforce this override when building the llama payload for tool-calling profiles. **Impact:** Occasional truncated JSON generation due to cumulative penalties.
- **Severity P2 — Circuit Breaker Isolation**: While `LOCAL_CIRCUIT_BREAKERS` exist, falling back to direct `llama.cpp` (bypassing switchboard) entirely disables rate-limiting and thermal protection.

### Critical Findings (ROLE 3 — Agent Coordination)

- **Severity P1 — Observability Loss on Fallback**: `ai-stack/local-agents/local_agent_runtime.py`'s `_post_completion_with_fallback()` retries the switchboard, then falls back directly to `llama.cpp`. This bypasses `switchboard.py`'s telemetry, circuit breakers, and RAG/hint injections. **Impact:** Silent loss of tracking and context limits.
- **Severity P1 — Brittle Context Truncation**: `ai-stack/local-agents/agent_executor.py` hardcodes pruning logic to drop indices 2+3 when `chars > 24768`. If a single tool result is massive or system prompts expand, this naive index dropping will corrupt the message history structure. **Impact:** The LLM may receive dangling `role: "tool"` responses without the preceding `role: "assistant"` tool call.
- **Severity P0 — Tool Role Compliance**: Confirmed working. `agent_executor.py` correctly appends `role: "tool"` (as required by Qwen3, dropping OpenAI's `function` role).

### Critical Findings (ROLE 4 — AI/Agentic Research)

- **Severity P1 — Missing Grammar-Based Structured Output**: Currently, the system relies on prompt constraints for JSON tool calls. `llama.cpp` supports `json_schema` grammar enforcement. We are exhausting the 512-token budget retrying malformed JSON. **Impact:** High token waste and lower reliability. Implementing grammar restrictions for the `local-tool-calling` profile would guarantee 100% parse success.
- **Severity P2 — Suboptimal Reasoning Profiles**: We suppress `<think>` tokens globally for speed, but `research` and `deep_reasoning` profiles should adopt ReAct/Reflexion patterns, explicitly emitting internal thoughts for complex problems before taking action.
- **Severity P2 — Context Compression vs. Eviction**: Naive dropping of past turns in `agent_executor.py` destroys episodic history. A semantic summarizer (compressing evicted turns into a single "Prior Context" string) would retain history within the same budget.

### Severity Matrix

| Finding | Role | Severity | File:Line | Impact |
|---------|------|----------|-----------|--------|
| Streaming Regex Fragmentation | Inference | P1 | `ai-stack/switchboard/switchboard.py:53` | Leaked `<think>` tags and broken UI streaming. |
| Missing `frequency_penalty: 0.0` | Inference | P1 | `ai-stack/mcp-servers/shared/llm_config.py` | Early EOS and broken JSON. |
| Observability Loss on Fallback | Coordination | P1 | `ai-stack/local-agents/local_agent_runtime.py` | Bypassed telemetry and thermal gates. |
| Brittle Context Truncation | Coordination | P1 | `ai-stack/local-agents/agent_executor.py` | Corrupted conversation history (dangling tool results). |
| Cold-Start UX Latency | UX | P1 | `scripts/ai/aq-chat` | User confusion during hidden reasoning generation. |
| Missing JSON Schema Grammar | Research | P1 | `ai-stack/mcp-servers/shared/llm_config.py` | Token waste on JSON retries. |

### Architecture Recommendations

1. **Stateful Stream Processor**: Replace the regex in `switchboard.py` with a state-machine stream processor that buffers chunks when a `<` is detected until the tag is resolved, ensuring clean stripping of `<think>` blocks without fragmentation.
2. **Grammar Enforcement Integration**: Update `build_llama_payload()` in `llm_config.py` to optionally accept a JSON schema for `local-tool-calling`, utilizing `llama.cpp`'s native grammar engine.
3. **UX Spinner for Reasoning**: Update `switchboard.py` to emit a distinct SSE event (e.g., `event: status\ndata: {"status": "reasoning"}`) when `<think>` is active, allowing `aq-chat` to display a spinner/indicator to the user.
4. **Semantic Pruning Strategy**: Replace the hardcoded `chars > 24768` truncation in `agent_executor.py` with a sliding window that preserves paired tool calls/responses, or summarize evicted messages.

### What's Working Well

- **Model Agnosticism & Parameter Management**: `llm_config.py` successfully acts as an SSOT for payload construction. Setting `enable_thinking: false` cleanly inside `chat_template_kwargs` manages Qwen3 specifics perfectly.
- **AIDB & Hint Integration**: The proxy design correctly injects `X-AI-Route` and hints implicitly, making the local agent context-aware without manual user effort.
- **Strict Role Mapping**: `agent_executor.py` successfully mitigates Qwen3's `role: "function"` dropping bug by correctly mapping to `role: "tool"`.

### Open Questions

1. **Fallback Policy**: Should `local_agent_runtime.py` strictly fail if `switchboard` is unreachable, rather than falling back to `llama.cpp` directly and bypassing all telemetry/thermal protections?
2. **Grammar Constraints**: Should we implement full JSON schema generation dynamically from the `ToolRegistry` for `llama.cpp`, or use a relaxed generic JSON grammar?