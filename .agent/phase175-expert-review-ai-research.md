---
doc_type: prd
id: phase175-expert-review-ai-research
title: "Expert Review: Local Inference Stack vs State of the Art — Agent Design Patterns"
status: active
owner: claude-sonnet-4-6
phase: "175"
priority: high
created_at: "2026-06-17"
---

# Expert Review: Local Inference Stack vs State of the Art

**System under review:** NixOS-Dev-Quick-Deploy — local Qwen3-35B agent stack  
**Reviewer:** Senior AI/Agentic Systems Researcher (Claude Sonnet 4.6)  
**Files read:**
- `ai-stack/local-agents/agent_executor.py` (1931 lines — complete)
- `ai-stack/local-agents/builtin_tools/ai_coordination.py` (1470 lines — complete)
- `scripts/ai/aq-agent-loop` (418 lines — complete)
- `.agent/LOCAL-AGENT.md` (564 lines — complete)
- `ai-stack/agents/runtimes/local_agent_runtime.py` (1394 lines — signatures + first 200 lines)
- `ai-stack/local-agents/training_ingest.py` (657 lines — signatures)
- `.agent/PROJECT-AGENTIC-MIND-STANDARDIZATION-PRD.md` (245 lines — complete)

---

## 1. Agent Loop Architecture vs State of the Art

### 1.1 ReAct Implementation

**Pattern:** The system implements a modified ReAct (Reason + Act, Yao et al. 2022) loop. The core `_execute_with_tools()` method in `agent_executor.py` executes the classic observe → reason → act cycle. However, the implementation deviates from the ReAct paper in a meaningful way: **thought traces are incidental, not structural**.

**What it does:** The loop captures "prose before the JSON tool call" as `prose_before` and emits it as `agent_thinking` events to telemetry. This is a side-effect of Qwen3's generation pattern — the model sometimes writes prose before the JSON — not an intentional thought-elicitation mechanism.

**What canonical ReAct requires:** A `Thought:` prefix in the prompt that elicits an explicit reasoning trace *before* each action. The thought trace is structurally part of the prompt turn, not incidental prose. Without this, the model defaults to single-turn JSON emission with no observable reasoning, which makes debugging loops nearly impossible and prevents the model from building multi-hop reasoning chains.

**Gap severity: HIGH.** On a constrained 3500-token input budget, a `Thought:` trace costs ~50-100 tokens per step but dramatically improves trajectory quality for multi-step tasks. Given `enable_thinking=false` is mandatory, explicit prompt-level thought elicitation is the *only* mechanism available for structured reasoning.

**Recommendation:** Add `"Thought: [your reasoning here]\nAction:"` as a required prefix in `_get_system_prompt()` for AgentType.AGENT. Parse the thought trace separately from the action JSON. This costs ~60 tokens/step and recovers lost reasoning quality.

### 1.2 ReWOO / Plan-then-Execute

**Pattern:** ReWOO (Xu et al. 2023) eliminates redundant tool calls by producing a full plan with evidence slots *before* any tool execution. The system has zero implementation of this pattern.

**Current behavior:** The loop is purely reactive — each step calls the LLM, which decides the next tool based only on the last N message pairs. For a 12-step task, this means 12 LLM calls (12 × 900 seconds prefill risk at 10 tok/s) when a 2-call plan-then-execute approach could achieve the same result in 2 calls plus parallel tool dispatch.

**Hardware impact:** On Renoir APU at 10 tok/s prefill, a 3000-token context (12000 chars at the current budget) costs **300 seconds of prefill time per LLM call**. A 12-step task risks 3600 seconds of prefill alone. ReWOO would reduce this to 2 LLM calls (plan + synthesis) with parallel tool dispatch in between.

**Gap severity: CRITICAL for multi-step tasks.** The `LLAMA_CHUNK_TIMEOUT` is set to `max(900.0, timeout * 2)` — already indicating awareness of this problem. ReWOO is the architectural solution.

**Recommendation:** For tasks with `complexity > 0.6`, run a planning pass first: one LLM call with prompt `"Produce an ordered list of tool calls needed to complete: {objective}. Format: PLAN:\n1. tool_name(arg=value)\n2..."`. Execute the plan with collected tool results, then synthesize once. This maps to the existing `AgentType.PLANNER` that is currently unused in `execute_task()`.

### 1.3 Reflexion

**Pattern:** Reflexion (Shinn et al. 2023) adds a self-evaluation step after each task attempt: the agent critiques its own output and improves on the next attempt. The system has no implementation of this pattern.

**What exists:** The stagnation guards (exploration stagnation, observation stagnation, file-not-found stagnation) are **reactive circuit breakers**, not reflective evaluators. They abort on failure but do not produce diagnostic critique that guides the next attempt.

**Gap severity: MEDIUM.** Given the 300-second timeout constraint, full Reflexion loops are expensive. However, a lightweight variant — a single synthesis call asking "Rate the quality of this result 1-5 and list what was missed" — could be run after `TaskStatus.COMPLETED` and before writing to telemetry. This trains the feedback loop with quality-annotated pairs rather than flat pass/fail signals.

### 1.4 Tree of Thoughts

**Pattern:** ToT (Yao et al. 2023) is relevant for planning tasks where multiple approaches need evaluation. Given the hardware constraints (1-3 tok/s generation), full ToT is impractical. The `AgentType.PLANNER` type could benefit from a 2-branch ToT at planning time only, but this is low priority vs ReWOO.

**Assessment:** ToT is not worth pursuing on current hardware. Skip.

### 1.5 Grammar-Constrained Generation (Structured Output)

**Pattern:** llama.cpp supports GBNF grammar files and JSON schema-constrained generation (`grammar` parameter in the API). This would guarantee valid JSON tool-call format on every token, eliminating the parsing fallbacks currently in `parse_tool_call_from_llama()`.

**Current state:** The codebase has **zero use of llama.cpp's grammar mode**. Instead, `agent_executor.py` implements:
- `response.rfind('{"function"')` — heuristic JSON extraction
- Embedded newline detection and stripping
- Truncated tool call detection (`response.lstrip().startswith('{"function"')`)
- Multiple retry paths for malformed tool calls

**Gap severity: HIGH.** Every malformed tool call is a wasted LLM call (512-1200 tokens = 512-1200 seconds at 1 tok/s). Grammar-constrained generation would eliminate this class of failure entirely. llama.cpp exposes this via `grammar` in the request body. The llm_config SSOT (`shared/llm_config.py`) is the correct place to add this.

**Recommendation:** Add a GBNF grammar file for the tool call format `{"function": "<name>", "arguments": {...}}` to the repository. Inject `grammar=<gbnf_content>` in `build_llama_payload()` when `tool_call=True`. This eliminates the parser, all its fallbacks, and makes tool calling deterministic.

---

## 2. Tool Design & Ecosystem

### 2.1 Tool Count and Categories

The system has **20 registered AI coordination tools** (`register_ai_coordination_tools` log line) plus file/shell/git tools. Total: ~29 tools in full manifest, 8 in self-improvement manifest.

**Comparison to state of the art:**

| Category | System | Modern Standard | Gap |
|----------|--------|----------------|-----|
| File I/O | `read_file`, `write_file`, `edit_file`, `list_files`, `search_files` | MCP filesystem server (equivalent) | None — well-designed |
| Shell | `run_command` (SAFE_COMMANDS whitelist) | Code interpreter sandbox (E2B, Modal) | No sandboxed code execution |
| Web | `web_research_fetch` (coordinator proxy) | Tavily, Brave Search, Playwright | No real-time search; scraping only |
| Memory | `store_memory`, `get_working_memory`, `query_aidb`, `collective_memory_search` | MemGPT/Letta memory tiers | Strong — ahead of baseline |
| Delegation | `delegate_to_remote`, `delegate_to_aider`, `run_opencode` | A2A protocol tasks | Functional but no A2A compliance |
| Orchestration | `discover_objectives`, `execute_workflow`, `mesh_discovery` | LangGraph, CrewAI | Custom implementation, no graph execution |
| Code execution | `run_command` (whitelisted) | Jupyter kernel, E2B sandbox | **Critical gap** |
| Structured data | None | SQL, Pandas, DuckDB tools | Missing entirely |
| Observability | `harness_health`, `get_unified_stack_health` | OpenTelemetry GenAI | Partial — no span correlation |

### 2.2 Tool Call Format Alignment

**Current format:**
```json
{"function": "<tool_name>", "arguments": {"param": "value"}}
```

**OpenAI/Anthropic standard:**
```json
{"type": "function", "function": {"name": "<tool_name>", "parameters": {...}}}
```

The system uses a non-standard format that is **Qwen3-specific** (the `{"function": ...}` wrapper). The `local_agent_runtime.py` uses the standard `{"type": "function", "function": ...}` schema for tool *definitions* but dispatches through a custom format in `agent_executor.py`. This creates a schism: tool definitions are OpenAI-schema-compatible, but tool call parsing is model-specific.

**Gap severity: MEDIUM.** This creates a vendor lock to Qwen3's generation pattern. When the model is swapped, parsing code needs updating. The fix is grammar-constrained generation (see §1.5) which forces a canonical format regardless of model.

### 2.3 Tool Result Handling

**Strength:** Tool results are capped at 3000 chars (~750 tokens), sanitized via `context_sanitizer` for prompt injection, and written to a `role: "tool"` message — all correct per Qwen3's chat template.

**Gap:** Tool results lack **structured metadata**. A result from `query_aidb` returns `{"success": true, "results": [...]}` with no reliability score, no provenance tracking, and no confidence interval. The model receives raw JSON and must parse it. Modern tool systems (Anthropic tool_use, OpenAI function calling v2) attach `tool_use_id` for correlation and permit structured result schemas with typed fields.

**Gap severity: LOW.** The current approach works but makes it harder to build quality metrics on top.

### 2.4 Missing Tool Categories

**Code execution sandbox:** The biggest missing tool. `run_command` is whitelisted-shell-only. For programming tasks, the model cannot execute arbitrary Python to test its own edits without either using the whitelist (which may not cover the script) or calling `validate_before_commit`. An E2B-style sandbox (or even a local `python3 -c` execution tool with output capture) would be transformative for implementation tasks.

**Structured data query:** No SQL, no Pandas, no DuckDB. Tasks involving the 8,220+ AIDB vectors or training data analysis require writing Python scripts and running them via `run_command`. A `query_dataframe(sql)` tool backed by DuckDB would be immediately useful.

---

## 3. Memory Architecture

### 3.1 Current Memory System Audit

The system implements a more sophisticated memory architecture than most open-source agent frameworks:

| Tier | Implementation | Standard |
|------|---------------|---------|
| Working memory | 8192-token context (pinned+sliding) | MemGPT working context |
| Episodic memory | coordinator `/memory/store` type=episodic | MemGPT archival memory |
| Semantic memory | AIDB Qdrant collections (14 collections, 8220+ vectors) | MemGPT archival + retrieval |
| Procedural memory | `store_memory(type=procedural)` | Partially implemented |
| Prune checkpoints | `_store_prune_checkpoint()` → semantic memory on context eviction | Novel, strong pattern |

**Overall assessment:** The three-tier memory (working/episodic/semantic) is architecturally sound and ahead of most agent frameworks. The prune checkpoint mechanism that saves evicted context to working memory before dropping is particularly strong — this is equivalent to MemGPT's "move to archival" transition.

### 3.2 Episodic Memory — Critical Gap

**Problem:** `query_context_handler` (the `query_context` tool) hits `/memory/recall` with `memory_types: ["episodic", "semantic"]` but there is **no per-task session history**. The coordinator's memory store is a shared flat namespace. An agent running task A cannot query "what did the last agent working on coordinator changes find?" because there is no session-scoped episodic index.

**MemGPT comparison:** MemGPT (Packer et al. 2023, now Letta) maintains per-conversation message history in archival memory with automatic summarization. This system has per-session PULSE.log files and RESUME.json, but these are file-based and not queryable through the agent's memory tools.

**Gap severity: HIGH.** Multi-session task continuity currently depends on the operator writing PULSE.log and RESUME.json faithfully. An agent that fails mid-task leaves no queryable episodic record. The fix is to auto-index task completion events (already emitted as `agent_complete` to `agent-run-events.jsonl`) into episodic memory with session_id tags.

### 3.3 Working Memory — Pinned+Sliding Strategy

**Assessment:** The `pinned[:4] + sliding[-4:]` strategy in `_execute_with_tools()` is well-reasoned for Qwen3's SWA (sliding window attention) behavior. Pinning the system+user+first_call+first_result ensures the model never loses the task objective and initial discovery context.

**Gap:** The strategy uses a **fixed character budget** (12,000 chars ≈ 3,000 tokens) as the prune trigger, but does not track *semantic importance* of message pairs. A highly informative tool result at step 3 that gets pruned at step 7 (because it's now in the "middle" range) is lost forever (only a 120-char summary is stored as prune checkpoint). Modern context management systems (e.g., LangChain's `ConversationSummaryBufferMemory`, MemGPT's importance scoring) use relevance to the *current* objective to decide what to keep.

**Recommendation:** Score each tool result message by semantic similarity to the task objective (single embedding call via llama-embed:8081) before pruning. Keep the top-K most relevant messages regardless of recency. This costs ~1 embedding call per pruned step but preserves critical findings.

### 3.4 Embedding Model Assessment

The system uses BGE-M3 (BAAI/bge-m3) at port 8081 for embeddings. This is a **strong choice** — BGE-M3 is a state-of-the-art multi-lingual, multi-granularity embedding model that handles both retrieval and reranking. The 0.45 score threshold (options.nix) is appropriately calibrated for sparse collections.

**Gap:** BGE-M3 is used for storage (seed-rag-knowledge.py) but is not used *within the agent loop* for relevance-scored context management (see §3.3). The embedding infrastructure exists; the usage pattern needs extension.

---

## 4. Multi-Agent Patterns

### 4.1 Current Architecture Assessment

```
aq-chat → intent classify → coordinator (8003)
                          → local_agent_runtime.py (subprocess)
                            → agent_executor.py (tool-calling loop)
                              → switchboard (8085) → llama.cpp (8080)
```

This is a **single-level supervisor/worker** pattern where the coordinator acts as a fixed supervisor that spawns one worker at a time. The coordinator's role is:
1. Intent classification (route to local vs remote)
2. Profile selection (local-tool-calling, continue-local, remote-*)
3. Task envelope construction (partial — see PRD-148)
4. Result collection

### 4.2 Gaps vs Modern Multi-Agent Patterns

**Supervisor/Worker gap:** The coordinator does not implement a proper **critic/verifier** role. After the local agent completes, there is no automated quality check of the output before returning to the user. The `reviewer` role exists in the role matrix but is never autonomously invoked by the coordinator. The operator must manually delegate review tasks.

**Parallel execution gap:** Every subtask is strictly sequential. The coordinator has no concept of a task graph where independent subtasks can be parallelized. For example, a task like "update documentation + seed RAG + run tests" runs as three sequential agent invocations when it could run as three concurrent workers. LangGraph, AutoGen, and CrewAI all handle parallel node execution.

**Agent specialization gap:** The `_select_tools_for_task()` function in `local_agent_runtime.py` does dynamic tool selection based on task keywords. However, all agent invocations use the same base model (Qwen3-35B) with the same system prompt shape. There is no mechanism for task-class-specific agents with specialized system prompts, context, or tool subsets. For example, a "security reviewer" agent could be given a radically different system prompt, tool access limited to read-only, and a structured output schema for review verdicts — none of this exists.

**A2A Protocol gap:** The `PROJECT-AGENTIC-MIND-STANDARDIZATION-PRD.md` (Phase 148) identifies the need for a canonical task envelope. The current delegation mechanism passes task text as a string with a few metadata fields. The Google A2A protocol (2025) and the emerging OpenAI Agents SDK trace model define **agent identity cards**, **task artifacts**, and **structured handoff protocols** that enable any agent to consume any other agent's output. This system's delegation is bespoke HTTP POST with unstructured text.

**Gap severity: MEDIUM for supervisor/worker; HIGH for parallel execution in complex multi-step scenarios.**

### 4.3 The Two-Runtime Problem

There are **two separate agent runtimes** with partially overlapping capabilities:

1. `ai-stack/local-agents/agent_executor.py` — full tool-calling loop (29 tools, aq-agent-loop)
2. `ai-stack/agents/runtimes/local_agent_runtime.py` — coordinator-spawned runtime (17 tools, http_server.py)

These runtimes have different:
- Tool sets (different tool counts, partially different tools)
- Tool selection strategies (`_refresh_active_tools` in executor vs `_select_tools_for_task` in runtime)
- Context management strategies (pinned+sliding in executor vs no pinning in runtime)
- Token budgets (AGENT_MAX_TOKENS=768 in runtime vs 512/1200 in executor)
- Hot-swap mechanisms (keyword-based in executor vs static in runtime)

**Gap severity: HIGH.** This is a maintenance and behavior-parity risk. The PRD-148 §PR-6 correctly identifies this as a prompt assembly SSOT violation. The two runtimes will diverge over time, producing inconsistent agent behavior depending on whether the task came via `aq-agent-loop` or coordinator spawn. A unified `AgentRuntime` class that both entry points instantiate would eliminate this risk.

---

## 5. Context & Prompt Engineering

### 5.1 System Prompt Quality

The system prompt for AgentType.AGENT is:

```
"You are AQ, an expert coding and systems developer on NixOS. 
You have full tool access: file read/write, shell commands, git operations, 
and harness coordination (get_hint, query_aidb, store_memory, get_working_memory). 
HARNESS-FIRST: before reading any file or writing any code, call 
get_hint + query_aidb(collection='error-solutions') + get_working_memory 
to load institutional knowledge..."
```

**Strengths:** Domain-specific framing ("NixOS"), role clarity, explicit harness-first instruction, tool call format. The `_behavioral_contract` section with concrete rules (READ LIMIT: 4, SURGICAL FINALITY) is well-designed.

**Weaknesses:**

1. **No explicit chain-of-thought elicitation.** With `enable_thinking=false`, the model has no internal scratchpad. The system prompt does not instruct the model to reason before acting. Adding `"Before each tool call, write one sentence explaining WHY you are calling it"` would recover significant reasoning quality at ~20 tokens/step.

2. **Tool descriptions are minimal by design** (`_minimal_tool()` shows only name + required params). This saves context tokens but sacrifices model grounding. The model may not know what `harness_health(phase=0)` actually does without reading a description. The balance between context efficiency and model grounding needs recalibration.

3. **No few-shot examples.** The behavioral contract is declarative ("do X") but provides no demonstrated examples of correct multi-step trajectories. Few-shot examples are particularly effective for small-context models learning tool-calling patterns. Even 1-2 examples of "good" vs "bad" trajectories in the system prompt would improve first-call quality measurably.

4. **Task-type conditional logic is complex.** The `_is_si_task` check to conditionally inject the self-improvement slice, combined with the `task_type` profile system, creates a 3-way conditional prompt: base prompt + optional SI slice + tool format + extensions. A template system (e.g., Jinja2) would make this more maintainable and testable.

### 5.2 Chain-of-Thought Without Thinking Tokens

With `enable_thinking=false` mandatory, chain-of-thought must come from the prompt, not the model's internal reasoning tokens. The current system provides:

1. Behavioral rules (declarative)
2. Step-by-step SI workflow (procedural)
3. Nudge messages injected mid-loop (reactive)

**Missing:** A zero-shot CoT trigger at the task level. Appending `"Let's approach this systematically:"` to the user message (the simplest CoT elicitor from Wei et al. 2022) or `"Think step by step before calling any tools:"` would cost 6 tokens and potentially improve multi-hop task quality.

**Research note:** For instruction-tuned models like Qwen3, "step-by-step" elicitors in the user turn are more effective than in the system prompt, because the model was trained to respond to user-turn CoT triggers during RLHF.

### 5.3 Task Decomposition Architecture

The current decomposition pipeline:
```
User request → aq-chat intent classify → coordinator route → single agent task
```

There is **no task decomposition layer**. The entire user request is handed to the agent as one objective. Complex tasks (e.g., "implement X, write tests, update docs, seed RAG, commit") are expected to be decomposed *inside* the agent loop via sequential tool calls. This is inefficient — it requires the model to maintain multi-task state across a long loop with context pruning.

**Modern pattern:** A dedicated `TaskDecomposer` agent (one lightweight LLM call at 512 tokens) that takes a complex objective and produces 2-5 subtasks with dependencies. The coordinator then executes this plan, spawning agents for each subtask. This is the core of LangGraph, AutoGen's GroupChat, and CrewAI's crew planning.

---

## 6. Observability & Learning Loop

### 6.1 Telemetry Infrastructure Assessment

**Strong positives:**
- Three-surface telemetry: `hybrid-events.jsonl` (training signal), progress sidecar (dashboard), steps JSONL (streaming tail)
- Structured events: `agent_step_start`, `agent_tool_intent`, `agent_tool_result`, `agent_thinking`, `agent_synthesis_start`, `agent_complete`, `agent_failed`, `agent_stall`
- Token usage tracking per call
- Per-task sequence numbers for event correlation

**This is ahead of most open-source agent frameworks** in telemetry density. The `agent_thinking` event (prose before JSON) gives partial observability into model reasoning that most systems discard.

### 6.2 Training Pipeline Assessment

`training_ingest.py` collects `agent_step_complete`, `local_inference`, and `tool_result` events from `hybrid-events.jsonl`, scores them via `_quality_score()`, and adds quality-passing pairs to a fine-tuning dataset (JSONL).

**Critical gap: The quality scoring function is keyword-coverage based**, not semantic. From the signatures: `_quality_score(response, query) → float`. Given the MEMORY.md note "training_ingest quality score too harsh for structured outputs" and the fix to set `is_structured` base to 0.50, this is a known limitation.

**State of the art comparison:**
- **RAGAS** (Es et al. 2023) provides faithfulness, answer relevancy, context precision, and context recall metrics using an LLM judge. The system has none of this.
- **TRL's DPO/PPO trainer** would enable fine-tuning on the collected preference data (successful vs failed agent trajectories). The training dataset is being collected but never used for actual model training.
- **AgentBench** (Liu et al. 2023) provides standardized benchmarks for agent capabilities across task types. The golden evals corpus has only 2 cases (per PRD-148).

**Gap severity: HIGH for evaluation; CRITICAL for the training pipeline.** The collected data is currently inert — it feeds into a JSONL file that is used for prompt extensions (gap rules) but not for model adaptation. The infrastructure exists; the training loop is not closed.

### 6.3 Feedback Loop Architecture

```
agent run → telemetry event → training_ingest.py → JSONL dataset
                                                  → prompt_extensions.yaml (gap rules)
```

The second output — `generate_prompt_extensions()` — is genuinely novel: it extracts failure patterns from agent runs and injects them as runtime prompt rules. The `_load_prompt_extensions()` function in `agent_executor.py` loads up to 5 of these rules into every system prompt. This is a form of **automated prompt optimization** without requiring a full RL loop.

**Gap:** The gap rule extraction in `training_ingest.py` uses heuristic pattern matching on failure events. Modern AutoPrompt / PromptBreeder / EvoPrompting approaches use LLM calls to generate and evaluate candidate rule improvements. The current system could be enhanced by having the coordinator's local model draft candidate rules from failed trajectories — a task ideally suited to the "research" task_type profile.

---

## 7. Emerging Packages & Patterns to Consider

### 7.1 Structured Output Enforcement

**llama.cpp JSON schema grammar (immediate):** llama.cpp supports `json_schema` in the API request body as of llama.cpp build `b3780+`. This generates a GBNF grammar from a JSON schema automatically:
```python
payload["json_schema"] = {
    "type": "object",
    "properties": {"function": {"type": "string"}, "arguments": {"type": "object"}},
    "required": ["function", "arguments"]
}
```
This eliminates all JSON parsing fallbacks in `agent_executor.py` at zero cost. The llm_config SSOT is the right place to add this when `tool_call=True`.

**Outlines/Guidance:** For more complex structured output (e.g., enforcing plan schemas, structured review verdicts), the `outlines` library (Willard & Louf 2023) provides regex/JSON-schema-constrained generation that works with llama.cpp via its API. Relevant for implementing structured agent output contracts (PRD-148 §PR-4).

### 7.2 Improved Context Management

**MemGPT/Letta (2024+):** The Letta framework (successor to MemGPT) has open-sourced its memory architecture including the "context compiler" that assembles working memory from multi-tier storage at each turn. The system's pinned+sliding strategy could be replaced with a Letta-style context compiler that scores relevance before inclusion. Letta is MIT-licensed.

**LlamaIndex's ContextChatEngine:** Provides RAG-augmented context management with automatic context injection — similar to the working memory prefetch in `_execute_with_tools()` but with better relevance scoring and chunk management.

### 7.3 Local Fine-tuning Opportunities

The system collects (query, response) pairs with tool call traces. This is precisely the data format needed for **function-calling fine-tuning** using:

- **LLaMA-Factory** (open source) — supports Qwen3 fine-tuning with function-calling datasets in ShareGPT format. The existing JSONL dataset can be converted with a simple script.
- **Unsloth** (already referenced in model name `unsloth/Qwen3.6-35B-A3B-MTP-GGUF`) — the model is already from the Unsloth ecosystem, making fine-tuning on the collected data directly compatible.

Even a LoRA adapter trained on 500-1000 high-quality agent trajectories would meaningfully improve first-pass tool-calling accuracy and reduce the JSON parse failures.

### 7.4 Qwen3-Specific Underutilized Capabilities

1. **MTP (Multi-Token Prediction) speculative decoding:** Already in use (`--spec-type draft-mtp --spec-draft-n-max 2`). Strong choice. Consider tuning `spec-draft-n-max` up to 4 for structured JSON generation where acceptance rate should be high.

2. **Thinking mode with `thinking_budget`:** The `research` and `deep_reasoning` task profiles use this correctly. Gap: the coordinator-spawned runtime (`local_agent_runtime.py`) uses `AGENT_TASK_TYPE=agent` (no thinking) for all tasks. The `AGENT_TASK_TYPE=research` override via env var is documented but not wired into the coordinator's task dispatch logic. Complex coordinator-spawned tasks never benefit from bounded thinking.

3. **Qwen3's native tool calling format:** Qwen3's chat template has a native `<tool_call>` XML tag format that is distinct from the `{"function": ...}` JSON used here. Using the native format with grammar constraints would be more reliable than the current custom JSON format.

### 7.5 OpenTelemetry GenAI Semantic Conventions

The `gen_ai.*` attribute conventions (OpenTelemetry GenAI SIG, 2024-2025) define a standard span schema for LLM observability:
- `gen_ai.system` (e.g., "llama.cpp")
- `gen_ai.operation.name` ("chat", "embeddings")
- `gen_ai.request.model`, `gen_ai.response.model`
- `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
- `gen_ai.tool.name`, `gen_ai.tool.call.id`

The system's telemetry events contain the right data but use custom field names. Adopting the GenAI convention would make the telemetry compatible with any OTel-compatible observability tool (Jaeger, Grafana Tempo, Honeycomb) without translation.

---

## 8. What's Working Well

### 8.1 Genuine Architectural Strengths

**1. Stagnation guard system:** The multi-dimensional stagnation detection in `_execute_with_tools()` is more sophisticated than anything in LangChain, AutoGen, or CrewAI's open-source agent implementations. The distinction between same-result stagnation, file-not-found stagnation, per-tool-failure stagnation, exploration stagnation, and observation stagnation is correct and battle-tested. Most frameworks simply cap tool calls at N — this system makes those caps dynamic and failure-mode-specific.

**2. Prune checkpoint pattern:** Saving evicted context to working memory before pruning (`_store_prune_checkpoint()`) is a novel and correct solution to the context window ceiling problem that most frameworks ignore. MemGPT has a similar mechanism but requires the model to initiate it; this system does it automatically.

**3. Tool hot-swap (A.6 pattern):** Expanding the active tool set mid-loop based on tool result content is an elegant progressive disclosure mechanism. The model starts with a minimal tool surface and gains access to additional tools as its needs become apparent. This is more sophisticated than any standard framework's tool management.

**4. Two-phase token budget:** The `AGENT_TOOL_CALL_MAX_TOKENS` (512) vs `AGENT_TASK_MAX_TOKENS` (1200) distinction correctly models that tool call JSON is short (50-100 tokens) but synthesis may be long. This prevents the majority of synthesis truncation failures that plague simpler implementations.

**5. Telemetry density:** Three concurrent telemetry surfaces (JSONL events, progress sidecar, steps JSONL) providing live streaming observability is genuinely ahead of most frameworks.

**6. Training data pipeline with gap rule extraction:** Automatically converting agent failure patterns into runtime prompt rules via `generate_prompt_extensions()` is a lightweight but effective form of automated prompt optimization that closes the feedback loop without requiring RLHF.

**7. Hardware-aware design throughout:** Every budget decision (context size, GPU layers, KV allocation, token budgets, timeouts) reflects the specific hardware constraints. The thermal gate system, MLFQ scheduler, and CLM compaction guard show awareness of the complete resource picture that most agent frameworks ignore.

---

## 9. Priority Recommendations (Ranked by Severity)

### Severity 10 — Grammar-Constrained Tool Call Generation

**What:** Add `json_schema` parameter to `build_llama_payload()` when tool calling is active.  
**Why:** Eliminates the entire class of JSON parse failures (truncated tool calls, embedded newlines, prose before JSON). Every wasted retry costs 512-1200 seconds on Renoir APU.  
**File:** `ai-stack/mcp-servers/shared/llm_config.py` (add `json_schema` to `build_llama_payload`), `ai-stack/local-agents/agent_executor.py` (remove parse fallbacks).  
**Effort:** 1 day. Zero cost beyond llama.cpp API parameter.

### Severity 9 — Unify the Two Agent Runtimes

**What:** Extract `AgentRuntime` as a shared class; both `agent_executor.py` and `local_agent_runtime.py` instantiate it.  
**Why:** Two diverging runtimes with different tool counts, context strategies, and token budgets mean PRD-148's agent parity goal is structurally impossible. Behavior differs based on entry point.  
**Files:** New `ai-stack/local-agents/agent_runtime.py` (shared core), then thin wrappers.  
**Effort:** 3-5 days.

### Severity 8 — ReWOO / Plan-then-Execute for Complex Tasks

**What:** Add a planning pass for `task.complexity > 0.6`: one LLM call generates a tool execution plan; plan steps are executed with collected results; one synthesis call.  
**Why:** At 10 tok/s prefill and 12000-char context, every iteration of the ReAct loop costs 300s of prefill. A 10-step task risks 3000s in prefill alone. ReWOO reduces this to 2 LLM calls + parallel tool dispatch.  
**Files:** `ai-stack/local-agents/agent_executor.py` (`_execute_with_tools()`), `scripts/ai/aq-agent-loop` (task.complexity routing).  
**Effort:** 3-4 days.

### Severity 7 — Explicit Chain-of-Thought Elicitation

**What:** Add `"Think step by step before calling any tools:"` to the user task message. Add `"Thought: [one sentence why you're calling this tool]\n"` as a required prefix in `TOOL_USE_PROTOCOL`.  
**Why:** With `enable_thinking=false`, the model has no internal reasoning scratchpad. Prompt-level CoT is the only path to structured multi-hop reasoning.  
**File:** `ai-stack/local-agents/agent_executor.py` (`_get_system_prompt()`, `_execute_with_tools()`).  
**Effort:** 2 hours. High return for minimal cost.

### Severity 6 — Per-Session Episodic Memory Indexing

**What:** Auto-index `agent_complete` events into episodic memory with `session_id` and `task_id` tags. Add a `recall_session_history(session_id)` tool.  
**Why:** Task continuity currently depends on PULSE.log/RESUME.json written by the operator. Crashed or interrupted tasks leave no queryable episodic record. The data is already in `agent-run-events.jsonl` — it just needs indexing.  
**Files:** `ai-stack/local-agents/agent_executor.py` (post-completion indexing), coordinator memory handlers.  
**Effort:** 1 day.

### Severity 5 — Relevance-Scored Context Pruning

**What:** Before pruning a message pair, compute embedding similarity to task objective via llama-embed (8081). Keep the top-K most relevant pairs regardless of recency position.  
**Why:** The pinned+sliding strategy preserves recency but not relevance. A critical tool result at step 3 can be lost when step 7 triggers pruning, with only 120 chars saved.  
**Files:** `ai-stack/local-agents/agent_executor.py` (context prune section).  
**Effort:** 1-2 days.

### Severity 4 — AGENT_TASK_TYPE Wiring for Coordinator-Spawned Tasks

**What:** Wire `AGENT_TASK_TYPE=research` injection in the coordinator's task dispatch for complex tasks (complexity > 0.7 or task contains "plan"/"analyze"/"research").  
**Why:** The bounded thinking mode (`thinking_budget=100`) is documented and implemented but never activated by the coordinator. Complex coordinator-spawned tasks get `enable_thinking=false` always.  
**File:** Coordinator task dispatch (http_server.py or whichever spawns local_agent_runtime.py).  
**Effort:** Half a day.

### Severity 3 — Automated Quality Annotation with LLM Judge

**What:** After each `agent_complete` event, run a lightweight quality evaluation call (one Qwen3 call at 256 tokens max): "Rate this response 1-5: task={objective}, response={result[:500]}. Output JSON: {score, reason}". Store score with the training pair.  
**Why:** Current `_quality_score()` is keyword-coverage-based and systematically under-scores structured outputs. LLM judge scoring (as used in RAGAS, MT-Bench) is more accurate and produces better training signal.  
**Files:** `ai-stack/local-agents/training_ingest.py`, `ai-stack/local-agents/agent_executor.py` (post-completion).  
**Effort:** 1-2 days.

### Severity 2 — Golden Eval Corpus Expansion (PRD-148 §PR-2)

**What:** Expand `data/harness-golden-evals.json` from 2 cases to 20+ covering: multi-step implementation, RAG-grounded lookup, self-improvement cycle, delegation, security review, and context overflow recovery.  
**Why:** PRD-148 identifies this as P1. First-pass agent quality cannot be measured without a golden corpus. Fallback recovery masking first-pass failures is the key threat to harness reliability.  
**Files:** `data/harness-golden-evals.json`, `scripts/ai/aq-agent-contract-eval` (new).  
**Effort:** 2-3 days.

### Severity 1 — Local Fine-tuning Pipeline (Medium-term)

**What:** Convert collected training data (JSONL) to ShareGPT format; run a LoRA fine-tuning job using LLaMA-Factory or Unsloth on the top 500 quality-scored agent trajectories.  
**Why:** The training infrastructure exists and is collecting data. Closing the loop with actual model adaptation would measurably improve first-pass tool-calling accuracy and reduce parse failures.  
**Files:** New `scripts/training/convert-to-sharegpt.py`, new `scripts/training/run-lora.sh`.  
**Effort:** 3-5 days (tooling) + GPU time.

---

## Summary

This is a mature, production-grade local agent stack that outperforms most open-source agent frameworks in specific areas: telemetry density, stagnation guard sophistication, memory tier design, and hardware-aware resource management. The three critical gaps are:

1. **Grammar-constrained generation is missing** (Severity 10): Every JSON parse failure burns 512-1200 seconds on this hardware. llama.cpp supports `json_schema` natively; adding it to `build_llama_payload()` eliminates the entire parse-failure class.

2. **Two diverging agent runtimes** (`agent_executor.py` vs `local_agent_runtime.py`) make behavior parity between aq-agent-loop and coordinator-spawned tasks structurally impossible (Severity 9). This is the root cause of the PRD-148 agent parity problem.

3. **No chain-of-thought elicitation with `enable_thinking=false`** (Severity 7): The model has no reasoning scratchpad and the system prompt does not instruct structured pre-action thinking. Adding `"Think step by step"` to the user turn costs 6 tokens and partially recovers this.

The training pipeline collects good data but does not close the loop — the data is not used for model adaptation (Severity 1), and quality scoring is keyword-based rather than LLM-judge-based (Severity 3). ReWOO plan-then-execute would materially improve throughput on the constrained hardware (Severity 8).
