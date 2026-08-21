---
doc_type: research
title: Harness parity research roadmap — prioritized targets for updating our loops/context/payload
status: draft
owner: hyperd
date: 2026-08-20
companion: .agent/research/deepseek-harness-parity-2026-08.md
---

# Which harnesses to parity-check next (prioritized for OUR pain points)

We already did DeepSeek Harness. We ARE Claude Code (its patterns are our baseline) and already use
Antigravity. So this list ranks the *remaining* harnesses by **what they'd teach us on the specific
areas we're weak/uncertain on** — local-model reliability, agent loop, context engineering, and
payload/tool-call engineering — not by raw popularity.

## The single biggest cross-harness signal
Multiple top harnesses independently converge on **code-as-action / programmatic tool calling**
(model writes code that calls tools instead of emitting JSON): DeepSeek's **PTC**, HuggingFace
**smolagents** (`CodeAgent`), and **OpenHands/CodeAct**. Three independent teams choosing this is
strong evidence it's more reliable than JSON tool-calls for many models — **directly the problem we
spent this whole cycle fighting.** This raises PTC from "interesting" to "priority spike."

The second cross-harness signal: for small/local context budgets, the winners **don't ship a wide tool
schema** — they use a **compact repo map + diff-based edit formats** (Aider) so the window isn't spent
before the task starts. That's exactly our read_file-gate + assembler + verbatim-diff territory,
already battle-tested by Aider across many models.

## TIER 1 — read + parity-check first (directly hit our pain points)

| Harness | Why it's top priority | What to extract | Our area |
|---|---|---|---|
| **Aider** (git-native) | The reference for edit reliability + tiny context budgets on weak/local models. Publishes per-model **edit-format leaderboards** (whole-file vs diff vs udiff) and a **repo map** (ranked, token-budgeted codebase summary). | Their edit-format A/B data (which format each model lands reliably); the repo-map ranking algorithm; git-per-change discipline. | payload, context, loops |
| **smolagents** (HuggingFace) | The clean reference for **code-as-action** tool calling (`CodeAgent` writes Python). Small, readable. HF has benchmarks showing code-agents beat JSON tool-calls on multi-step tasks. | The code-action executor + sandbox; how they constrain/parse code tool calls; the JSON-vs-code benchmark methodology (reuse for our PTC A/B). | payload (PTC), loops |
| **Pi** (Mario Zechner, minimal) | "Strips the harness to task, tools, loop, verification." The cleanest reference loop to diff our `agent_executor` against. DeepSeek even ships an `llm-pi-ai` adapter. | The minimal correct loop + **verification** step (they treat verify as structural, we bolt it on); what they consider essential vs our accreted guards. | loops, workflows |
| **LocalHarness** | Our exact use case: model-agnostic, YAML-defined agents, **deny-first permissions**, runs on llama.cpp/Ollama/vLLM. Small enough to fully read. | Deny-first permission model (vs our capability-lease); YAML agent definition ergonomics; OpenAI-compat endpoint abstraction. | local, workflows |

## TIER 2 — read next (loop/context/interface depth)

| Harness | Why | What to extract | Our area |
|---|---|---|---|
| **OpenHands** (ex-OpenDevin) | Mature research harness; **CodeAct** paradigm (code-as-action again) + **event-stream** architecture (maps to dsh's session-event spine + our aq-event). | Event-stream loop; CodeAct executor; long-horizon context handling. | loops, context |
| **SWE-agent** (Princeton) | The foundational **Agent-Computer Interface (ACI)** research: *how tool/interface design changes agent success* — literally why our tool-calling failed. | ACI design principles (concise, guardrailed tool surfaces); their finding that interface > model for many failures. | payload, loops |
| **OpenCode** | 2026 default open harness; 75+ providers, **LSP auto-loading**, parallel multi-session. We already run opencode (and hit a crash). | Provider-abstraction layer (remote-lane parity); LSP-as-context; multi-session concurrency. | remote, context |
| **Cline / Roo Code** | Permission-gated tool use; **Roo's dedicated context-management** features (custom modes, condensing). | Context-condensing UX + heavy-prompt budgeting lessons (when the system prompt crowds out work — we hit this exactly). | context, payload |

## TIER 3 — skim for one specific idea each
- **Goose (Block)** — extensions-as-installable (a lighter plugin model than dsh's microkernel; a middle ground for us).
- **Kimi CLI** — swarm-style multi-agent coordination (our consensus/multi-lane angle).
- **Continue.dev** — we already run it; IDE-agnostic context/ingress patterns.
- **Zed agentic** — Rust, low-latency tool round-trips (latency lessons for our APU).

## Models (separate from harnesses — for the swap decision)
The current strong OPEN tool-calling models the field cites: **Qwen 3.6 Plus** (owner's "Qwen 37B"
candidate), **DeepSeek V4**, **Kimi K2.6**, **GLM 5.1**. Evaluate on OUR harness AFTER the PTC + edit-
feedback work, so a swap is measured against a fixed baseline (per the config-first lesson this cycle).

## Recommended sequence (do NOT boil the ocean)
1. **Aider edit-formats + repo map** and **smolagents code-action** — these two directly inform the two
   highest-value changes already on our board (PTC A/B; edit reliability). Parity-check both like we did
   DeepSeek.
2. **Pi** + **SWE-agent ACI** — to refactor our loop to a clean task→tools→loop→verify shape with hook
   seams (the one thing worth taking from dsh).
3. **LocalHarness** + **OpenHands CodeAct** — local permission ergonomics + event-stream/CodeAct.
4. Then TIER 2/3 for targeted ideas, and the model-swap eval last.

Each parity check produces: a dimension table (loop/context/payload/tools/security) + a ranked
"adopt / skip / already-have" list, same format as the DeepSeek doc. Estimated: ~1 focused research
pass per harness.
