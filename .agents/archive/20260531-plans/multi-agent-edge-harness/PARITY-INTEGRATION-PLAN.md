# Parity Integration Plan — MAEAH v0.3 Supplement
> Date: 2026-05-21  
> Scope: Incorporate external parity findings into the current system-improvement cycle without blocking Claude's active coordinator refactor.

## Operating constraint

The coordinator refactor line is past R2.9 and current commits have moved into Phase 60 memory/RAG work. This plan therefore treats runtime implementation as allowed only after the active Phase 60 dirty tree is validated and ownership is clear. Planning/security-gate documentation may proceed independently.

## Phase 0 — Refactor stabilization gate

**Status: CLEARED FOR PLANNING, NOT CLEAN FOR IMPLEMENTATION (2026-05-21)** — Refactor baseline is past R2.9 and current `aq-qa 0` is green at 66 PASS / 0 FAIL / 3 SKIP. Current working tree still contains follow-on Phase 60 implementation changes plus parity docs. Treat runtime implementation as pending validation until those changes are reviewed, tested, and committed or handed off.

## PA-Item → Phase 60-63 Cross-Reference

| PA Item | Description | Maps to PRD Phase | Status |
|---------|-------------|-------------------|--------|
| PA-1 | Bitemporal memory schema + supersession tests | Phase 60.1–60.4 | **COMPLETE** — bitemporal event_time+valid_at (9844d3e0), superseder `_superseded_ids` ledger + `is_superseded()` bitemporal (commit 0fc32d28) |
| PA-2 | Tool sandbox policy schema + registry lint | Phase 62 (nsjail, AM-C3) | **COMPLETE** — nsjail+safety-rails.yaml (f61ef4b1); S2 tool-auth enforcement middleware (e1987d06); S2.5 `/admin/v1/policy/tool-deny-stats` live (post-rebuild) |
| PA-3 | Agent identity/delegation review gate | Phase 62 safety rails (`config/safety-rails.yaml`) | **PARTIAL** — static no-recursive-delegation rail + Ed25519 A2A cards; runtime bounded delegation envelope enforcement remains |
| PA-4 | MCP/A2A governance profile | Ed25519 Agent Cards (MAEAH Phase D) + Phase 62 | **PARTIAL** — A2A Ed25519 signing (6e1d8072) + static security contract; MCP runtime tool-boundary profile enforcement remains |
| PA-5 | Memory poisoning + retrieval benchmark additions | Phase 60.3–60.7 (RAGAS metrics) | **COMPLETE** — RAGAS eval_runner: answer relevance (embed cosine), context precision, faithfulness (Qwen judge); eval_results Postgres table; `/eval/trend` (commits 0fc32d28, 5a98b394) |
| PA-6 | Trace schema: prompt version, route, tool sequence | Phase 60 (prompt_version_id) + Phase 63 path view | **PARTIAL** — OTel trace_collector gen_ai.* attrs (0e1be322); prompt_version_id + full path view still pending |
| PA-7 | Semantic task descriptor + scheduler pressure tests | Phase 61 CLM + MLFQ pressure integration | **COMPLETE** — CLM Hot→Warm→Cold (53c724e0); MLFQ `apply_clm_pressure()` wired; thermal gate coupling (AM-G3) via IPM→scheduler |
| PA-8 | Edge persistence classification + rollback drill | Phase 63 impermanence + `/persist` mounts | **COMPLETE** — impermanence module in flake+options+host-class (b80723b2); enable-flag guarded; `/persist` FS required before activation |

## Slice Queue → PRD Mapping

| Slice | PRD Equivalent | Owner |
|-------|---------------|-------|
| S1 sandbox policy schema | Phase 62.3–62.4 (nsjail policy + safety-rails.yaml) | Codex + Claude |
| S2 identity/delegation gate | Phase 62 + MAEAH Phase D (Ed25519 done) | Gemini + Claude |
| S3 bitemporal memory | Phase 60.1–60.4 — **ACTIVE / pending validation** | Claude/Codex review |
| S4 observability path view | Phase 60.5 (RAGAS) + Phase 63 trace extension | Claude/Codex |
| S5 persistence/rollback map | Phase 63.4–63.5 (impermanence + rollback drill) | Codex + Claude |

---

**Goal:** Do not stack new architecture changes onto unstable runtime structure.

Required before runtime implementation of parity amendments:

- active agent/collaboration check-in completed;
- coordinator refactor live endpoints pass;
- `aq-qa 0` and tier0 pre-commit pass, or failures are explicitly classified;
- dirty tree ownership is clear;
- no active Claude/Gemini file ownership conflict.


## Cross-surface change contract

Every accepted module, feature, service, route, or agent capability change in this cycle must update the surfaces that make the change understandable and operable. A slice is not complete unless one of these outcomes is recorded in its validation evidence:

1. **Connected documentation updated** — PRD/plan/runbook/architecture docs that describe the changed system piece are updated in the same slice.
2. **Command Center visibility updated** — new or changed tests, measured metrics, health states, validation gates, drift signals, or agent/service operational states are exposed through the AI Command Center dashboard or its backend API when they are relevant to an operator.
3. **Explicit non-applicability recorded** — if a docs or dashboard update is not appropriate, the handoff must say why.

This contract exists to prevent hidden capability drift: system behavior, validation evidence, and operator visibility must evolve together.

Enforcement surface: `scripts/governance/check-cross-surface-contract.py` and `docs/architecture/cross-surface-change-contract.md`.

## Phase 1 — Security and governance contracts

**Implements:** PA-2, PA-3, PA-4, PA-9.

Deliverables:

1. Tool sandbox policy schema and registry lint.
2. Agent identity/delegation contract for signed cards and review gates.
3. MCP/A2A governance profile contract: roots, auth, sampling, duties.
4. Static tests proving privileged/admin/tool routes fail closed without required policy metadata.

Why first: these are prerequisite controls for autonomous code generation, multi-agent delegation, and broader tool creation.

## Phase 2 — Memory and RAG correctness

**Implements:** PA-1, PA-5.

Deliverables:

1. Bitemporal memory schema extension plan and migration strategy.
2. Supersession/default-recall behavior tests.
3. Memory poisoning and stale coordination recall tests.
4. Retrieval quality benchmark additions: context precision, support coverage, and deterministic expected contexts.

Why second: the team is relying on agentic memory to preserve long-cycle intent. Incorrect memory is more dangerous than missing memory.

## Phase 3 — Observability and eval parity

**Implements:** PA-6.

Deliverables:

1. Trace schema amendment for prompt version, route decision, tool sequence, sandbox decision, memory recall IDs, and review verdict.
2. `aq-report` path view: prompt → route → memory → tools → response → review.
3. Shared eval/production span contract.

Why third: scheduler and autonomous SWE changes need traceability before they become debuggable at scale.

## Phase 4 — Scheduler/resource pressure, deployment gates, and edge state

**Implements:** PA-7, PA-8, PA-10.

Deliverables:

1. Semantic task/resource descriptor added to scheduler planning docs.
2. Pressure-policy acceptance tests for thermal/RAM demotion.
3. Edge persistence classification doc for AIDB, Qdrant, model catalog, traces, scratchpads, and model files.
4. Rollback drill that verifies durable state remains coherent.

Why fourth: these improve system survivability under local model pressure without overreaching into eBPF, distributed mesh, or new databases.

## Phase 5 — Optional future tracks

Only open after Phases 1–4 are stable and accepted:

- OpenHands-style resolver mode in isolated PR-only workflow.
- Dashboard/agentic UI widgets for actionable system operations.
- Multimodal RAG for PDFs/images/audio/video.
- NATS/gRPC mesh and chaos testing for multi-node deployments.
- Federated learning, PQC identity, audio-native agents, neuromorphic/embodied/cryptoeconomic tracks.

## Current reconciliation — 2026-05-23

Recent committed work changed the Phase 1/62 status:

- `MAEAH-SECURITY-CONTRACT-GATES.md` and `scripts/testing/test-security-contract-gates.py` pin the static security/governance contract.
- `config/safety-rails.yaml`, `evidence_safety_handlers.py`, local shell sandbox tests, and nsjail environment wiring provide the first runtime safety-rail layer.
- `docs/architecture/cross-surface-change-contract.md` and tier0 now require connected docs/handoff/planning or dashboard visibility for runtime/service/module changes.
- Local-agent `ToolDefinition` now has effective sandbox/security metadata defaults plus `scripts/testing/test-tool-registry-security-metadata.py`; the Command Center harness overview exposes `policies.tool_registry_security`.
- Dashboard visual QA tooling now has a local `scripts/ai/aq-screenshot` entrypoint, Home Manager Playwright/system-Chromium no-download contract, and `scripts/testing/test-aq-screenshot-contract.sh` guardrail for operator-visibility validation.
- Runtime auth/profile baseline now resolves middleware `auth_context`, validates `X-Harness-Auth-Profile`, and exposes `policies.runtime_auth_profiles` in Command Center.

- Command Center visibility has expanded for parity-cycle operations: agent ops drift/override state, promoted lessons, active hints, memory statistics, trace summary/drift, fleet/budget/reasoning profile cards, ports registry, and health aggregate are now visible through dashboard cards and guarded API routes.
- Managed-service discipline is part of the acceptance criteria: dashboard validation must confirm `command-center-dashboard-api.service` is active and serving `127.0.0.1:8889`; ad-hoc `uvicorn` on `0.0.0.0:8889` is considered degraded state, not a valid workaround.

PA-1, PA-2, PA-5, PA-7, PA-8 are fully complete as of 2026-05-23. PA-3 and PA-4 have static contracts committed; runtime bounded delegation envelopes and MCP tool-boundary profile enforcement remain. PA-6 (trace schema path view) is partially complete via OTel attrs; prompt_version_id and full path view still pending.

All agent configs (CLAUDE.md, GEMINI.md, CODEX.md, LOCAL-AGENT.md) now share identical canonical sections (Behavioral Rules, Architecture Constraints, Service Ports, File Placement, On-Demand Context). aq-insights end-to-end validated (local model producing real harness analysis). Dashboard `section-local-insights` card live. aq-qa 93/93 PASS · tier0 17/17 PASS.

## Slice queue after refactor lands

| Slice | Owner suggestion | Files expected | Validation |
|---|---|---|---|
| S1 security contract gates | Codex + Claude review | `MAEAH-SECURITY-CONTRACT-GATES.md`, acceptance criteria corrections | DONE: `scripts/testing/test-security-contract-gates.py` + tier0 history |
| S2 sandbox policy schema | Codex + Claude review | docs/config schema + governance lint tests | PARTIAL+: nsjail/safety rails + local-agent registry metadata lint/dashboard summary present; runtime auth/profile baseline added, deeper MCP tool-boundary enforcement remains |
| S3 identity/delegation review gate | Gemini design + Codex/Claude review | A2A/agent card docs, review gate contract | static contract tests |
| S4 bitemporal retrieval traceability pack | Codex + memory/local model | memory envelope docs, retrieval plan schema, eval fixtures | memory/RAG benchmark additions |
| S5 observability path view | Claude/Codex | trace docs, aq-report plan | trace schema tests |
| S6 deployment/pressure/chaos gates | Codex + edge/ops agent | deployment gate docs, pressure state contract, chaos matrix | dry-run gate, rollback drill dry run |
| S7 persistence/impermanence map | Codex + edge/ops agent | persistence manifest, impermanence dry-run criteria | reboot/rollback evidence plan |

## Explicit non-actions for this cycle

- No host eBPF scheduling.
- No Postgres/Qdrant replacement with SurrealDB.
- No NATS/gRPC distributed mesh until single-node governance is complete.
- No autonomous resolver that writes PRs until sandbox and identity gates exist.
- No frontier tracks unless promoted to a dedicated PRD.
