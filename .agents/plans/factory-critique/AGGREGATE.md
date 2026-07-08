# Factory Critique — Aggregate / Roadmap (4/4 landed — RATIFIED)

Last Updated: 2026-07-07

## Contributors
- **claude** ✅ · **codex/gpt-5.5** ✅ · **antigravity[Gemini]** ✅ (via the IDE OAuth inbox — the
  no-key lane WORKED end-to-end) · **local[Qwen]** ✅ (re-dispatch `s1r0ds`, 3722s, 12 tool calls —
  never skipped; hit its known design-task boundary and produced only scaffolding, salvaged into
  local.md. Its substantive alignment is captured in F1/F2/F3, which local co-authored in those rounds).

## Unanimous verdict (3/3 landed)
**"Promising direction, not yet a foundation."** (codex's phrasing; claude + antigravity agree.) The
core is a useful prototype but **too ad-hoc** — too dependent on scripts, conventions, implicit
files, and operator discipline. "The system currently looks more deterministic than it is." Promote
the workflow into **explicit, testable primitives** before more features depend on it.

## EXTRAORDINARY convergence — all 3 independent teams ranked the SAME top 3
1. **Durable, typed round STATE MACHINE.** Replace open/status/collect + conventions with an explicit
   durable state model (`CREATED→DISPATCHED→CONTRIBUTING→COLLECTED→CONFLICTS→CONSENSUS_LOCKED→
   ASSIGNED→IMPLEMENTING→VALIDATING→CLOSED`), JSON schema for round manifest + typed contributions +
   verdicts, **idempotent** commands (rerun never duplicates), quorum + timeout policy (late local
   still admissible; consensus not "whatever landed"), explicit **conflict objects** (not prose), and
   tests for missing/late/duplicate/malformed/dispatch-failure/recovery-after-death.
2. **Local model-stacking + a measured SLOT SCHEDULER.** "Never skip local" is the right POLICY but a
   wrong scheduler. Resident 4B/8B (classification, JSON/tool-call validation, schema repair, short
   critiques, risk scoring) + 35B **session-mode only** (architecture, multi-file planning, dissent
   reviews). Queue classes (interactive/validation/background/batch) with **MLFQ + aging** (no
   starvation); GBNF on post-filter schemas + grammar cache by schema+zero_trust hash; prefix/KV
   reuse; **back-pressure** (typed "local delayed", never silently let consensus move on).
3. **Traceable execution (OTel) + algorithmic consensus.** Spans per agent-turn/tool-call (tokens,
   latency, tool failures) → Grafana/Jaeger; typed **voting protocol** for reproducibility.

## Complementary depth (unique per team — all fold in)
- **codex — the CapabilityLease contract (deepest insight):** unify the 5 ad-hoc capability-selection
  layers (Nix/service/skills/manifest/lease/hot-swap/RAG/security/zero-trust) into ONE canonical
  `CapabilityLease` (id, version, source, owner, permissions, io-schema, trust-tier, zero-trust
  behavior, cost-class, observability hooks, revocation). **Deny-by-default** admission for external
  plugins/MCP; monotonic least-privilege; property tests (stripped-can't-reacquire, caller-false-
  can't-downgrade, stale-lease-can't-revive). Also: signed task **envelope + heartbeat + output
  contract** for the antigravity node (a watched folder alone is fragile); a required **role roster +
  coverage matrix** for "each agent picks its expert team" (else it's "untestable theater");
  acceptance **METRICS** (repair −90%, landing rate, p50/p95, slot occupancy, tok/s by tier, % rounds
  local contributes before lock, 35B time on high-value vs trivial).
- **antigravity — event-driven + rollback:** a **State+Event Broker** (SQLite/Redis) instead of
  filesystem polling; **signed capability tokens** per task; **automatic rollback** via git stash /
  worktree isolation snapshot BEFORE write-access execution → instant reversion on validation fail;
  **idempotency keys** per dispatch; provenance trails (hardware, model tag, tokens, latency).
- **claude — reproducibility + learning:** freeform→typed contributions; **testing the orchestration
  itself** (golden ROUNDS, not just golden tasks); a **learning loop** (accepted-work → better
  routing); provenance = model+version+params, not just "agent".

## Unified reading list (papers/systems the teams named)
Durable orchestration: **Temporal, Durable Task, Ray Workflows, Prefect, Airflow, LangGraph, AutoGen,
CrewAI, MetaGPT**. Inference cascades/routing: **FrugalGPT, RouteLLM, Hybrid-LLM**. Consensus:
**Mixture-of-Agents (Wang), Multi-Agent Debate (Du), self-consistency**. Constrained decoding:
**GBNF, Outlines, XGrammar, Grammar-Constrained Decoding (Geng)**. Planning: **ReWOO, Reflexion,
ReAct, LLMCompiler**. Capability security: **object-capability, macaroons, SPIFFE/SPIRE, TUF/Sigstore,
Zanzibar**. Observability: **OpenTelemetry semantic conventions**. Scheduling: **MLFQ + aging**.

## Roadmap decision — promote the core to explicit primitives (next slices)
- **Slice F1 — Round state machine + typed contract:** `round.json` state + JSON schema for
  contributions/verdicts/conflicts; idempotent open/collect/aggregate; quorum+timeout (late-local
  admissible); consensus as a typed object. [Temporal/LangGraph/MetaGPT lessons; test the lifecycle.]
- **Slice F2 — Local model-stacking + slot scheduler (== Slice 3, now with a scheduler):** resident
  small + 35B session-mode; MLFQ+aging queue classes; GBNF + grammar cache; back-pressure; metrics.
- **Slice F3 — CapabilityLease contract + OTel + signed A2A envelope:** one lease abstraction (deny-by-
  default, monotonic least-privilege, revocation) subsuming the Phase-0 zero_trust; OTel spans; signed
  task envelope + heartbeat for the antigravity node; automatic-rollback (worktree snapshot).

## Status
**4/4 landed — RATIFIED.** claude + codex + antigravity unanimous ("too ad-hoc → promote to explicit
primitives"), identical top-3 (F1/F2/F3). local[Qwen] folded (thin — design-boundary; its real design
input lands in the F1/F2/F3 rounds it co-authored). These 3 slices become the foundation-hardening
epic; the Slice-2/3 zero-trust work folds into F2/F3 (zero_trust = a CapabilityLease).
