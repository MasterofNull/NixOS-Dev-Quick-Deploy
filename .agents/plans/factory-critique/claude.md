# claude — Foundation Critique of the Flat-Collaborative Factory Core

## Is it too ad-hoc? — YES, in specific, fixable ways
1. **No round STATE.** A round is a directory + markdown files + a thin script + the orchestrator's
   memory. There is no durable, typed round state (open→fanned→collecting→aggregated→ratified→
   assigned→implementing→validated). Interrupt it and state is scattered across files/logs/registry
   → not resumable, not observable as a whole.
2. **Freeform contributions.** `<agent>.md` is prose. Aggregation is therefore MANUAL orchestrator
   reasoning — not reproducible, not automatable, not verifiable. A typed contribution schema
   (verdict enum, required_changes[], risks[], tests[], anchors[]) would let aggregation be
   mechanical + auditable.
3. **Consensus is judgment, not protocol.** "3/3 APPROVE-WITH-CHANGES" is my prose call. We HAVE a
   real consensus engine (`aq-collaborate`/QualityConsensus, VoteType) but `aq-collab-round` doesn't
   use it. No quorum rule, no explicit conflict-resolution algorithm.
4. **Capability auto-selection = independent brittle heuristics.** Keyword hot-swap, intent bundles,
   complexity tiers are separate string-match rules with no unified policy, no learning, no test.
5. **Single-slot fan-out is unscheduled.** We fan a round out to local + others, but local is ONE
   gen slot — the "fan-out" to local actually serializes with no queue/priority/back-pressure.

## Where to improve (prioritized) + what's MISSING (papers/systems)
- **Formalize the round as a durable, typed state machine.** Study **LangGraph** (stateful agent
  graphs), **MetaGPT** (SOPs encode role outputs + handoffs — directly the software-factory), and
  **Temporal / durable execution** (resumability, retries, sagas). Replace file-scatter + my memory
  with a `round.json` state + typed contribution schema.
- **Aggregation/consensus as an algorithm.** Study **Mixture-of-Agents** (Wang et al. — layered
  fan-out + aggregate, a PAPER for exactly our pattern), **Multiagent Debate** (Du et al.),
  **self-consistency** (Wang et al.), LLM-as-judge. Adopt VoteType + a defined merge.
- **Local reliability + stacking (Slice-3, biggest throughput win).** Study **FrugalGPT** (LLM
  cascade: cheap model first, escalate — literally model-stacking), **LLMCompiler** (DAG/parallel
  function calls — relevant to fan-out + single slot), **RouteLLM/Hybrid-LLM** (difficulty routing),
  constrained decoding: **GBNF**, **Outlines**, **XGrammar**, "Grammar-Constrained Decoding" (Geng).
- **Planner/executor discipline.** **ReWOO** (plan-then-execute decouples planning from tool calls →
  fewer tokens/turns — fits our APU), **Reflexion** (self-critique), **ReAct** (already partial).
- **Observability as a STANDARD.** Map audit/PULSE/matrix to **OpenTelemetry** semantics — a span
  per agent turn, tool calls as child spans, attributes = model/role/leased-bundle/zero_trust. Then
  "no black boxes" is standard + tool-able (Jaeger/Grafana), not bespoke.
- **Serving efficiency.** continuous batching (**vLLM/Orca**), speculative decoding — but VRAM-bound
  on the 4GB APU, so the realistic win is stacking + scheduling, not batching the 35B.

## What the core MUST include for highest operability/productivity
Determinism + idempotency (started: reaper, prompt-ext) · **resumability** (durable round state) ·
**typed contributions + automated aggregation** · **a slot scheduler** (priority queue: interactive
> consensus > background; task-class→model; VRAM-budget guard) · **cost/tokenomics accounting**
(per-round budget, cascade) · **OTel traces** · **testing the orchestration itself** (golden rounds,
not just golden tasks) · **provenance** (model+version+params per contribution, not just "agent") ·
**a learning loop** (which agent/role/model produced ACCEPTED work → improve routing).

## Local-agent stacking/scheduling (the utilization fix)
Resident **phi-4-mini or 4B** (fast lane: classification, JSON-repair, tool-args, validation) +
**8B** (bounded reasoning) always warm; **35B** loaded on-demand for planning SESSIONS (batched,
active.gguf swap). A **scheduler** in front of the single gen slot: priority queue + task-class→model
routing + VRAM pool-manager (unload before load). **GBNF on the fast lane** = the biggest reliability
win. Measure first (Slice-3.1 golden suite). Never skip local — but stop single-slotting the 35B on
trivial work.

## Top 3 changes (ranked)
1. **Durable, typed round state machine** (schema + `round.json` + typed contributions) — kills the
   ad-hoc-ness; enables automated aggregation, resumability, real observability. [LangGraph/MetaGPT/Temporal]
2. **Local model-stacking + slot scheduler** (Slice-3) — biggest utilization + throughput win.
   [FrugalGPT cascade / constrained decoding / VRAM pool-manager]
3. **OTel-mapped observability + algorithmic consensus** — standard spans + typed votes; makes
   visibility/control tool-able and aggregation reproducible. [Mixture-of-Agents / multiagent-debate]
