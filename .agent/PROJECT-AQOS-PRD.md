# PRD — AQ-OS v1: From Ad-Hoc Harness to AI Operating System

**Status**: DRAFT for multi-agent ratification (target: 4/4 consensus round `aqos-v1`)
**Owner**: claude-fable-5 (orchestrator) · **Date**: 2026-07-09
**Companion plan**: `.agents/plans/aqos-v1/PLAN.md` · **Handoff**: `.agents/plans/aqos-v1/DELEGATION.md`
**Supersedes nothing** — builds on ratified F1 (round state machine), F2 (scheduler), F3 (CapabilityLease+OTel+signed A2A) and the epic `.agents/plans/epic-flat-collaborative-factory.md`.

---

## 1. Intent & Product Definition

**What this system is**: a local-first AI agent operating system — orchestrating remote frontier agents (Claude, Codex, Gemini/Antigravity) and local inference (Qwen on constrained hardware) through recursive self-improvement loops, with the explicit mission of *training and refining local models while leveraging remote capability*.

**What it must become**: a coherent product a competent engineer could install, understand, operate, and extend in a day — not a collection of 175+ accreted phases. "One of the best AI harness/OS platforms" is measured by: install-to-first-delegation time, operator situational awareness, agent task success rate, local-model improvement velocity, and mean-time-to-diagnose any failure.

**Users** (in priority order):
1. **The operator** (today: hyperd) — needs total visibility and intervention capability.
2. **The agents themselves** — the system's primary "API consumers"; every surface must be agent-legible.
3. **Future adopters** — the productization audience; nothing may require tribal knowledge.

## 2. Current-State Assessment (measured 2026-07-09)

**Scale**: 1,163 Python files (~317K LOC, non-archive), 472 shell scripts, 196 entries in `scripts/ai/` (131 `aq-*` CLIs, 6 `delegate-to-*`), 410 markdown docs, 109 Nix files, 107 files in `config/`, 42 `ai-*` systemd units, 21 dashboard route modules, 49 hybrid-coordinator "extensions", 419+ ad-hoc test scripts.

**Strengths to preserve (do NOT regress)**:
- NixOS declarative foundation + SOPS secrets + AppArmor confinement — rare and genuinely differentiating.
- Closed learning loop (capture→correct→HITL→ingest→train→eval) — live and guarded; this IS the product's soul.
- Activation Gate / Definition-of-Done culture (Rule 15) — dormant-feature prevention.
- Multi-agent A2A with no-API-key OAuth lanes; never-skip-local discipline.
- Hardware-honest engineering (token budgets derived from measured tok/s; modal task profiles).
- Institutional memory: promoted bug patterns, issues backlog, RAG-seeded fixes.

**Structural deficits (the "ad-hoc feel" has specific causes)**:

| # | Deficit | Evidence |
|---|---------|----------|
| D1 | **No kernel/userland boundary** — 317K LOC with no enforced core-vs-plugin split; hybrid-coordinator is a god-service (112+ files, 49 extensions) | coordinator dir listing |
| D2 | **CLI sprawl** — 131 `aq-*` binaries with no shared entrypoint, inconsistent flags, discoverability via grep | `scripts/ai/` count; usability-parity rounds exist because of this |
| D3 | **File-based A2A state** — PULSE.log, RESUME.json, inbox dirs, stream .txt files; no atomicity, no schema, clobber incidents recorded in issues-backlog | RESUME-clobber issue; stale delegation-registry rows reconciled 2026-07-09 |
| D4 | **Config sprawl without schemas** — 107 config files (JSON/YAML/sh/Nix) with hand-maintained `_meta` conventions; switchboard reads at startup only (restart-to-apply); most have no validation | this cycle's switchboard deferral is a live example |
| D5 | **Instruction-file drift risk** — 5 agent .md files manually synchronized by Rule 16 discipline instead of compiled from one source | fable-parity cycle needed a script to guarantee byte-identical sections |
| D6 | **Duplicated payload logic** — build_llama_payload SSOT + dispatch.py inline fallback + historical run_direct heredoc; 3 copies of behavioral prompt text now exist | dispatch-chain facts in memory |
| D7 | **Test corpus, not test suite** — 419 one-off scripts in `scripts/testing/` vs. structured harness_qa; no CI executing them on every change; no hermetic test env | tier0 gate ≠ regression suite |
| D8 | **Observability is fragmented** — health-spider + aq-report + PULSE + telemetry dirs + dashboard collectors overlap; no end-to-end trace joining intent→delegation→payload→model→commit | F3 OTel ratified but unimplemented |
| D9 | **Dormant-feature debt** — F2.5 scheduler/backpressure/model_tier built+tested but unwired; single-slot dispatch still serialized | issues-backlog HIGH |
| D10 | **Frontend is artisanal** — vanilla JS + vendored d3/chart.js against 21 route modules; no typed API client, no component system, no design system; "blank `--`" parity is fought manually | dashboard perf memory file |
| D11 | **Registry fragility** — PID-based delegation tracking (at-least-once, stale rows), no idempotency keys, no exactly-once semantics | 3 stale Codex rows reconciled this week |
| D12 | **Docs as archaeology** — 410 md files, phase-numbered history mixed with living reference; onboarding path exists (aq-prime) but canon vs. sediment is unlabeled | archive/ pattern helps but is partial |

## 3. From-Scratch Design Principles

If rebuilding today, these are the axioms (each maps to workstreams in §5):

1. **Kernel/userland split.** A small, stable, schema-typed core (contracts, event bus, registries, policy engine, scheduler) — everything else is a versioned plugin (capability) loaded through one interface. The coordinator's 49 extensions become userland.
2. **Contracts before code.** Every config, payload, event, A2A message, and API response has a versioned JSON Schema / pydantic model in ONE `contracts/` tree. Generated projections (docs, TS types, agent cards). Nothing parses untyped dicts.
3. **One event log as spine.** Append-only, signed event stream (Redis Streams now; NATS when multi-node) is the A2A medium and audit log. PULSE.log/RESUME.json become *projections* of the log (kept for git/human legibility), never the primary store.
4. **One CLI.** `aq <noun> <verb>` with plugin subcommands, shared context injection, generated completions/help. The 131 binaries become subcommands with deprecation shims.
5. **Compile the canon.** One `canon/` source compiles to CLAUDE.md, CODEX.md, GEMINI.md, LOCAL-AGENT.md, WORKFLOW-CANON.md, switchboard cards, and payload prompt blocks. Rule 16 becomes a build step, not a discipline. (Fable-parity contract = first migrated content.)
6. **Trace everything end-to-end.** One trace id from operator intent through routing, payload, model call, tool calls, commit. OTel + structured events; dashboards query traces, not scraped text.
7. **Eval-gated promotion.** Models, prompts, profiles, and routing policies promote only through golden-set evals with recorded scorecards. Shadow/canary lanes before default lanes. (Extends the existing closed loop from "training data" to "everything configurable".)
8. **Zero-trust agents.** CapabilityLease (F3) enforced at the bus: an agent holds signed, expiring, least-privilege leases for tools/paths/budgets. Registry of who-may-do-what replaces convention.
9. **Degrade modally, never silently.** Every component declares its degraded modes and kill switch (modal-state HARD rule generalized). Health = the composed modal state, not a boolean.
10. **Product discipline.** Semver releases of the flake, migration scripts, changelogs, install profiles (APU-class / GPU-class / multi-node), docs site compiled from canon. "Works on hyperd's machine" is a bug class.

## 4. Target Architecture (four planes)

```
┌─ EXPERIENCE PLANE ─ Web console (typed SPA) · aq CLI · TUI · notifications
├─ CONTROL PLANE ─── Kernel: contracts · event bus · policy/leases · scheduler
│                    Registries: agents · models · prompts · skills · tasks · runs
├─ INFERENCE PLANE ─ Switchboard (hot-reload profiles) · local llama.cpp · remote lanes
│                    Eval service · training pipeline · model registry/promotion
└─ DATA PLANE ────── Postgres (system of record: events, runs, evals, costs)
                     Qdrant (vectors) · Redis (ephemeral/streams) · object store (artifacts)
                     Retention · backup/DR · lineage
```

Key moves: coordinator decomposes into kernel + capabilities; switchboard gains config hot-reload + becomes the only model gateway; dashboard backend becomes an OpenAPI-first API server; frontend rebuilt as typed SPA consuming generated client.

## 5. Workstreams & Requirements

Each workstream ships under the Activation Gate (integrated + ON + validated + observable + intervenable). Refactor is **strangler-pattern**: new spine grows alongside, traffic migrates lane-by-lane, old paths archived (never deleted). No big-bang rewrite; **Rust refactor remains deferred — Python/Nix stack stands.**

**WS1 — Contracts & Canon Compiler** *(foundation; unblocks D2/D4/D5/D6)*
- R1.1 `contracts/` tree: pydantic/JSON-Schema for events, A2A envelopes, delegation records, payloads, configs, API DTOs; CI-validated; semver per schema.
- R1.2 Canon compiler: `canon/*.md` + data → generated agent instruction files, switchboard cards, prompt blocks (fable-parity contract migrates first). Drift = build failure.
- R1.3 Config loader library: schema-validated, env-overlay, hot-reload signal (SIGHUP/inotify) — adopted first by switchboard (kills restart-to-apply).
- Accept: 0 hand-synced instruction files; switchboard profile edit applies <5s without restart; every config in `config/` parses against a schema in CI.

**WS2 — Event Bus & A2A v2** *(D3, D11; implements F3 transport)*
- R2.1 Append-only signed event log (Redis Streams; envelope = contracts v1; idempotency keys; consumer groups per agent).
- R2.2 PULSE.log/RESUME.json become projections written by a single projector service (agents write events, never files).
- R2.3 Delegation registry v2 on the log: heartbeats, leases, exactly-once state transitions, automatic stale reconciliation.
- R2.4 Antigravity/IDE inbox becomes a bridged consumer (file bridge preserved for OAuth-lane constraint — NO API keys).
- Accept: zero direct writes to PULSE/RESUME by agents; kill -9 any agent → registry reflects truth within 60s without manual reconcile.

**WS3 — Kernel Extraction & Coordinator Decomposition** *(D1, D9)*
- R3.1 Kernel package: policy/leases, scheduler (wire F2.5 scheduler/backpressure/model_tier — closes the dormant HIGH), routing, registries.
- R3.2 Coordinator's 49 extensions re-homed as declared capabilities with manifest (name, contracts consumed/produced, lease requirements, health probe, kill switch).
- R3.3 Capability lifecycle: install/enable/disable/upgrade via `aq capability ...`; deny-by-default intake (existing capability-intake skill becomes the gate).
- Accept: F2.5 live (parallel-safe local dispatch); coordinator main <15 files; every capability listable with owner, state, lease scope.

**WS4 — One CLI** *(D2)*
- R4.1 `aq` single entrypoint (typer/click plugin architecture); nouns: task, agent, model, run, eval, memory, config, capability, round, loop, report.
- R4.2 All 131 binaries become subcommands or deprecated shims printing the new invocation; shared context injection/audit/rate-limit middleware once, not per-script.
- R4.3 Generated shell completions, `aq help` tree, man pages from the same contract metadata.
- Accept: `aq --help` covers 100% of live workflows; new-operator task discovery without grep; shims log usage so removal is data-driven.

**WS5 — Observability & SLOs** *(D8; F3 OTel)*
- R5.1 OTel tracing across CLI → bus → switchboard → model → tools → commit; one trace id per intent.
- R5.2 Metrics SSOT: token spend, cost, latency, success rate, queue depth, APU thermals/RAM — per lane/agent/model; Prometheus-compatible export.
- R5.3 SLOs + error budgets per lane (e.g., local first-token p95, delegation completion rate); alerting = budget burn, not raw thresholds.
- R5.4 Health-spider probes become capability-declared checks; composed modal system state replaces boolean health.
- Accept: any failed run diagnosable from its trace alone (no journalctl spelunking); dashboard renders live SLO burn; blank `--` is structurally impossible (missing metric = declared absent state).

**WS6 — Experience Plane: Console & Dataviz** *(D10)*
- R6.1 OpenAPI-first backend (FastAPI native); generated typed client; SSE/WS for live state.
- R6.2 SPA rebuild (React or Svelte; impeccable/frontend-design skill standards; design tokens; light/dark) — views: Fleet (agents/leases/live runs), Runs (trace waterfall), Evals (scorecards/regressions), Memory (browse/search/lineage), Models (registry/promotion), Cost (budgets/burn), Backlog (issues kanban), Approvals (HITL queue: repairs, intakes, deferrals), Topology (live system graph).
- R6.3 Every mutating view has its CLI twin (`aq` parity) — UI and CLI call the same API.
- Accept: operator can answer "what is every agent doing right now, what did it cost, what's stuck, and why" in <30s from the console; zero vendored-script chart hacks.

**WS7 — Data Plane & Memory Architecture**
- R7.1 Postgres as system-of-record (events archive, runs, evals, costs, decisions); Alembic migrations; nightly backup + restore drill; retention policies per table.
- R7.2 Memory service v2: episodic (runs/events), semantic (Qdrant RAG), procedural (skills/patterns), identity (canon) — one query API with provenance + confidence + freshness on every result; MemoryBroker consolidates the current scattered stores.
- R7.3 Data lineage: training samples traceable to originating runs; PII/secret scan on ingest; lifecycle (hot→warm→cold→archive) automated.
- Accept: restore-from-backup drill documented and passing; every RAG answer cites source + age; training set fully lineage-traceable.

**WS8 — RSI Loop Industrialization** *(builds on live closed loop)*
- R8.1 Eval service: golden task sets per capability (coding, tool-use, structured output, NixOS domain); versioned datasets; scorecards per model/prompt/profile; regression gates in CI.
- R8.2 Prompt/profile registry: versioned, A/B-able, promoted via eval + shadow traffic; rollback one command.
- R8.3 Training pipeline as declared DAG (capture→curate→correct→HITL→train→eval→promote) with per-stage observability and kill switches; fine-tuning artifacts in model registry with provenance.
- R8.4 Local-model improvement flywheel gets a KPI dashboard: capability envelope over time (the promoted measure: bounded single-edit ✅ → multi-edit ❌ boundary must visibly move).
- Accept: any prompt/model change shows its eval delta before default-lane promotion; local capability envelope re-measured weekly, trend visible.

**WS9 — Security & Supply Chain**
- R9.1 Threat model doc (STRIDE over the four planes; agentic OWASP top-10 mapping made testable).
- R9.2 CapabilityLease enforcement at bus + tool layer (least privilege, expiry, budget caps); egress allowlists per capability; audit events for every privileged action.
- R9.3 Supply chain: flake input pinning policy, skill/plugin signing (extend existing sign-skill-registry), SBOM generation, intake quarantine (existing skills become the enforced path).
- R9.4 Secret lifecycle: SOPS rotation runbook + expiry alerts; secret-in-repo scanning in CI (the known HARD rule, mechanized).
- R9.5 Incident response: runbooks per failure class, `aq incident` capture command, post-incident → promoted-bug-pattern pipeline.
- Accept: red-team exercise (prompt-injection → exfil attempt) blocked at lease/egress layer with audit trail; CI fails on unsigned capability or unpinned input.

**WS10 — Release Engineering & Product Polish**
- R10.1 CI pipeline (self-hosted runner acceptable): schema validation, unit+integration suites (hermetic Nix devShell + ephemeral services), eval regressions, security scans — on every PR; tier0 gate becomes CI's local mirror.
- R10.2 Test consolidation: 419 ad-hoc scripts triaged into pytest suites / harness_qa phases / archived fixtures; coverage floor enforced.
- R10.3 Semver releases of the flake; CHANGELOG; migration scripts; install profiles (apu/gpu/multi-node); upgrade drill.
- R10.4 Docs site compiled from canon + contracts (living reference), with phase history explicitly labeled as archaeology; quickstart: install→first-delegation <1 hour.
- Accept: green CI required to merge; clean-machine install succeeds from docs alone; release v1.0 tagged with upgrade path from current state.

## 6. What Was Missing (gaps beyond the request)

The request covered monitoring, viz, UI, storage, A2A, CLI, DB, security, RSI, routing. These additional dimensions are folded into the workstreams above:

1. **Agent identity & authorization** — leases/zero-trust (WS9), not just "security checks".
2. **Eval-gated promotion as the universal change mechanism** — for prompts/configs/routing, not only models (WS8).
3. **Cost & token accounting with budgets/quotas per lane** and burn alerts (WS5) — you cannot manage what you cannot meter.
4. **Data lifecycle**: retention, PII governance, backup/restore *drills*, disaster recovery (WS7).
5. **Versioning & migration discipline** for schemas/configs/APIs/prompts + deprecation policy (WS1/WS10).
6. **Idempotency/exactly-once semantics** in registries and queues — the current stale-row class of bugs (WS2).
7. **Hermetic testing** — ephemeral service fixtures via Nix, not tests against the live stack (WS10).
8. **Threat model + incident response** as artifacts, not vibes (WS9).
9. **Docs compilation & drift-proofing** — canon as build input (WS1); Rule 16 mechanized.
10. **Capacity planning** — APU thermal/RAM/tok-s trending to predict when local lanes saturate (WS5).
11. **HITL as product surface** — one approvals queue UI for repairs/intakes/deferrals instead of scattered CLIs (WS6).
12. **Multi-node path** — bus choice (Redis→NATS) and registry design must not assume one host (WS2/WS3), even if v1 ships single-node.
13. **Upgrade/release engineering** — semver, changelog, migration drills (WS10).
14. **Operator ergonomics telemetry** — measure the operator's own friction (time-to-diagnose, prompts-per-task) as a first-class KPI (WS5/WS6).

## 7. Non-Goals & Constraints

- **No Rust rewrite** (deferred indefinitely — explicit standing order). No language migration; structure over syntax.
- **No cloud dependency** for core function; remote lanes remain optional accelerators. NO API keys — OAuth/IDE lanes only (HARD).
- **Hardware floor unchanged**: Renoir APU ceilings (GPU layers 12, 27GB RAM, thinking budgets) are physics; WS designs must fit them.
- **Never-skip-local stands**: every round engages Qwen; its failures feed WS8.
- **Archive, never delete** during all refactors.

## 8. Migration Strategy

Strangler pattern in five beats, each independently valuable and activation-gated:
1. WS1 contracts+canon (pure addition, zero runtime risk) →
2. WS2 bus with projections (old files keep working as read surfaces) →
3. WS3 kernel + F2.5 wiring (closes the standing HIGH) →
4. WS4-6 experience+observability on the new spine →
5. WS7-10 data/RSI/security/release hardening.
Old paths retire only after two clean cycles on the new path (data-driven via shim/usage telemetry).

## 9. Success Metrics (v1.0 exit)

| Metric | Now | Target |
|--------|-----|--------|
| Install→first-delegation (clean machine) | undefined/tribal | <1 hour, docs-only |
| Mean time to diagnose failed run | journalctl+grep, ~minutes-hours | <2 min from trace |
| Hand-synced canonical files | 5 | 0 (compiled) |
| CLI entrypoints | 131 | 1 (+shims) |
| Configs schema-validated in CI | ~0% | 100% |
| Delegation registry stale rows/week | recurring | 0 (self-healing) |
| Eval-gated changes (prompts/models/routing) | models only (partial) | 100% |
| Dormant shipped features | ≥1 (F2.5) | 0 |
| Local capability envelope | single-edit ceiling | multi-edit measured weekly, trending up |

## 10. Risks

- **Refactor stall risk**: mitigated by strangler beats each shipping standalone value + activation gate.
- **Single-operator review bottleneck**: HITL queue (WS6) + batch approvals mitigate; delegation matrix spreads implementation across all four agents.
- **Local-lane slowness blocking rounds**: async fan-out with open aggregation (existing pattern) stays mandatory.
- **Scope gravity**: one workstream per dev cycle max in-flight for WS1-3; parallelism only after the spine exists.

---
*Ratification: dispatch round `aqos-v1` (see DELEGATION.md) — each agent critiques, scores 1-10 per workstream, proposes amendments; consensus ≥3/4 ratifies; local (Qwen) contribution mandatory regardless of latency.*
