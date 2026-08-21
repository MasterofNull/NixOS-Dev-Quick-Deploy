---
doc_type: research
title: Maturity gap analysis — observability, extensibility, interop, benchmarking
status: draft
owner: hyperd
date: 2026-08-20
companion: .agent/research/deepseek-harness-parity-2026-08.md
---

# What we're missing to mature faster (observability / extensibility / interop / benchmarking)

Framing: the gaps below are graded by **how much they accelerate every OTHER improvement**, and each
is backed by *concrete pain from this session* — which is the strongest evidence they're real. The
two force-multipliers (record/replay benchmarking + structured OTel observability) are "dev-velocity
infrastructure": we were slow this whole cycle precisely because we lacked them.

## 1. OBSERVABILITY  — biggest weak spot, standard exists

**Have:** dashboard, health-spider, PULSE.log, RESUME.json, steps.jsonl, per-task heartbeat/progress
JSON, dogfood-ledger, aq-event (append-only), aq-report/aq-top/aq-insights, telemetry dir.
**Gap vs the 2026 standard (OpenTelemetry GenAI Semantic Conventions):**
- Not schema-standard. Our signals are **fragmented across ~6 ad-hoc files** — no unified, typed,
  per-run event stream (llm_call / tool_call / tool_result / intervention / edit_attempt / edit_landed
  spans). OTel GenAI semconv defines exactly these; adopting it = free interop with Langfuse/OpenLLMetry
  and instant trace views.
- **No token / cost / latency metering per task/lane** — the owner's "prove capability empirically"
  goal needs this and we don't emit it.
- **No trace/span view** of the turn/step lifecycle; **no first-token / prefill visibility**
  (logged this session as a gap and still open).
**This session's proof:** I diagnosed wedge-vs-slow, narrate-vs-act, and edit-mismatch by *grepping
scattered logs* — slow, error-prone archaeology. A typed event stream makes each failure mode a
one-line query.
**Recommendation (HIGH):** adopt **OTel GenAI semconv** as our agent-run event schema; wire `aq-event`
as the OTel-shaped spine and emit spans from the agent loop + tool pipeline; add a token/cost/latency
meter (mirror dsh's `token-meter`). Point it at a local Langfuse/OTel collector for trace UI. Pays back
on all future debugging.

## 2. BENCHMARKING  — the single biggest velocity multiplier for the work we're doing NOW

**Have:** bench-local-agent, aq-qa, tier0, the dogfood runner (built ad-hoc this session),
.agents/bench, capability-envelope notes, VF PRD (golden-task bank planned).
**Gap vs the field (Terminal-Bench, replayability, lucky-pass guards):**
- **No record/replay of LLM interactions.** We re-run 30-minute LIVE tasks for every A/B. The field
  standard is *"one command reconstructs any reported score."*
- **No standard benchmark.** **Terminal-Bench** (89 hand-crafted end-to-end terminal tasks) is a near-
  perfect fit (we're terminal/CLI-native) and lets us compare to the field; we only measure our own
  ad-hoc dogfood.
- **No systematic A/B-config harness** (grammar on/off, edit-format whole/diff, PTC on/off, model A/B
  as swappable variants with metrics) — we env-flag by hand.
- **No semantic-correctness scoring** — we score "edit landed," not "edit correct." The field calls
  this the **lucky-pass problem** (~20% of SWE-Bench "solved" are semantically wrong).
- **No capability timeseries** (rate/tokens/latency per cycle) to *show the curve* the owner wants.
**This session's proof:** I re-ran dogfood-01 live ~8 times to A/B grammar/budget/format (hours that
replay would make seconds); dogfood-01's "landed" diff was *incorrect* (missing `re` import) = lucky
pass in the flesh.
**Recommendation (HIGH — do this next, before more model/format work):**
1. **Record/replay layer** for llama.cpp/remote calls (capture prompt→stream; replay deterministically)
   — instantly speeds up the PTC / edit-format / 37B-swap decisions already in flight.
2. **Terminal-Bench harness** + a small **golden-task bank** (reuse our dogfood queue as seed).
3. **A/B-config runner** (one command, N configs, metrics table — Aider-leaderboard style).
4. **Semantic-correctness gate** (compile/test/lint the diff, not just "it changed the file").

## 3. EXTENSIBILITY  — structural, medium-high

**Have:** NixOS modules, MCP servers, 65 skills (markdown, mostly UNVALIDATED per our inventory),
profile + env flags, delegate-* lanes.
**Gap:**
- **Loop is monolithic** — every guard this session (re-read, no-action, edit-feedback, write-region)
  was an inline `agent_executor` edit. No **hook seams** (pre-step / tool-pre / tool-post /
  request-error / turn-stopping) to mount behaviors beside the loop.
- Skills are **docs, not executable/validated plugins**; tool surface not fully **MCP-native**.
- Config changes require rebuild, not runtime swap (fine for prod, slow for experimentation).
**Recommendation (MEDIUM-HIGH):** build a small **loop hook-seam pipeline** and refactor the 4
interventions into mountable hooks (the one dsh idea worth taking, no microkernel). Make skills
validated + loadable; converge the tool surface onto MCP so external tools/agents plug in.

## 4. INTEROP  — medium, unlocks the model-swap decision

**Have:** delegate-{claude,codex,gemini,local}, Agent tool, aq-collab-round, MCP servers, antigravity
inbox, OAuth-only, Foundation-C signed-A2A.
**Gap:**
- **No clean model-adapter seam** — we are llama.cpp-direct + `build_llama_payload`. Swapping
  models/backends (vLLM, Ollama, remote, **the Qwen 37B the owner is weighing**) is surgery, not config.
- **No OpenAI-compatible endpoint** exposing OUR local model + coordinator — so external harnesses
  (Aider, LocalHarness) can't use our stack, and we can't point them at us for benchmarking.
- MCP partial; **A2A / ACP** (Agent Client Protocol) not fully spoken.
**Recommendation (MEDIUM):**
1. **Model-adapter seam** in `llm_config` (uniform swap across llama.cpp/vLLM/Ollama/remote/37B) —
   directly de-risks and speeds the model-swap decision.
2. Expose an **OpenAI-compatible endpoint** (switchboard likely already close) — two-way interop +
   lets us benchmark our stack with off-the-shelf harnesses.
3. Fully speak MCP; evaluate A2A/ACP for cross-agent interop.

## Bottom line — what matures us fastest (ranked)
1. **Record/replay + A/B benchmark harness** (BENCHMARKING). Force-multiplier: makes every config/
   format/model decision we're actively making instant, deterministic, and auditable. Also catches
   lucky-pass. **Do first.**
2. **OTel-GenAI structured observability + token metering** (OBSERVABILITY). Makes failure diagnosis
   one-query and gives the empirical capability numbers the owner wants. **Do second (pairs with #1).**
3. **Loop hook-seams** (EXTENSIBILITY) — clean home for the growing set of interventions.
4. **Model-adapter seam + OpenAI-compat endpoint** (INTEROP) — unlocks the 37B swap + external
   benchmarking.

The meta-point: #1 and #2 are *how we build everything else faster*. This session was slow because we
hand-rolled a dogfood runner and grepped logs; building the replay-benchmark + OTel-observability spine
now converts that grind into fast, auditable iteration for every future harness update.
