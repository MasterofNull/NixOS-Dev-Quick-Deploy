# Agent Parity Review Notes
> Date: 2026-05-21
> Purpose: Capture team review inputs for the external parity amendment package.

## Review request

Agents were asked to inspect:

- `.agents/scratchpad/EXTERNAL-PARITY-CATALOG.md`
- `.agents/scratchpad/SEARCH-LOG.md`
- `.agents/plans/multi-agent-edge-harness/COMBINED-PRD.md`
- `.agents/plans/multi-agent-edge-harness/PLAN-SIGNOFF.md`
- `.agents/plans/multi-agent-edge-harness/SYSTEM-COMPARISON-PLAN.md`

Constraints:

- read-only review;
- no coordinator refactor edits;
- prioritize additions that amend MAEAH without destabilizing active work.

## Codex initial synthesis

Codex recommends the amendment package in `EXTERNAL-PARITY-AMENDMENTS.md` and delivery order in `PARITY-INTEGRATION-PLAN.md`.

### Highest-value additions

1. Bitemporal memory and correction chains.
2. Tool sandbox ladder.
3. Agent identity/delegation and signed review gates.
4. MCP/A2A governance profiles.
5. RAG quality/eval gates before GraphRAG dependency adoption.
6. Traceability path from prompt through tools/memory/review.
7. Scheduler semantic task/resource descriptors.
8. Edge persistence/rollback map.

### Explicit deferrals

OpenHands resolver, NATS/gRPC mesh, SurrealDB, multimodal RAG, audio-native agents, federated learning, PQC, embodied AI, neuromorphic, and cryptoeconomics remain future tracks unless promoted by a dedicated PRD.

## Team review results

All four read-only explorer reviews completed. No reviewer edited files.

### Architecture/runtime reviewer

Consensus: the current PRD already has the main runtime spine. The best additions are adjacent hardening/spec amendments, not refactor-disrupting rewrites.

Top additions:

1. Tool sandbox tiers: subprocess → stronger isolation such as Wasmtime/Firecracker when risk requires it.
2. Bitemporal memory for event-time vs ingestion-time correctness.
3. MCP Roots and remote auth policy.
4. Local-first/CRDT sync contract for small edge metadata only.
5. RAG/eval gates and AIDB retrieval SLOs.
6. Optional NixOS impermanence profile and lightweight local chaos tests.

Explicit deferrals: NATS/gRPC mesh, PQC identity, cryptoeconomic agents, neuromorphic/SNN support, embodied agents, SurrealDB replacement, and speculative planning until the coordinator refactor settles.

### Security/governance reviewer

Consensus: the security concepts are present, but must become enforceable pass/fail gates.

Required corrections and additions:

1. Loopback must not equal privilege; mutating admin/lifecycle operations require explicit auth even on 127.0.0.1.
2. Agent Card signing needs lifecycle rules: canonicalization, expiry, trust store, replay rejection, revocation, and quarantine reasons.
3. A2A → MCP/tool chains need bounded delegation envelopes to prevent confused-deputy escalation.
4. Every MCP tool needs a sandbox profile, roots/resource indicators, egress policy, output caps, and taint semantics.
5. Model/catalog supply-chain gates must cover source, hash, license, trust level, compatible MTP sibling identity, and signed/operator-approved remote catalog updates.
6. Cross-agent memory requires provenance, scope, quarantine, and poisoning tests.
7. Audit needs actor/action/resource/decision/policy/trace/reason fields plus redaction/tamper-evidence.
8. Security-sensitive slices require non-self reviewer sign-off.

Concrete correction applied in this slice: `PHASE-A-ACCEPTANCE-CRITERIA.md` Gate 9 no longer accepts unauthenticated loopback mutation.

### Memory/RAG/eval reviewer

Consensus: avoid “more RAG” as a vague goal. The valuable additions are fact lifecycle, retrieval explainability, reproducible evals, and trace-to-memory causality.

Top additions:

1. Canonical bitemporal memory envelope with valid time, ingestion time, source hash, confidence, evidence refs, agent ID, scope, and schema version.
2. Lightweight provenance-backed KG over existing Postgres/Qdrant; do not replace AIDB.
3. Typed `RetrievalPlan` emitted per query with collections, strategies, filters, candidate limits, and final-k.
4. Stage-level RAG tracing: normalize, expand, vector, lexical, KG, merge, rerank, compress, inject.
5. Versioned RAG eval pack with expected supporting memory/chunk IDs and deterministic evidence checks.
6. Memory/RAG dashboard lane for latency, candidate/final counts, supersession blocks, poisoning/quarantine, and eval trends.
7. Exportable trace-debug bundle with retrieval-only replay.

Best next implementation candidate after refactor stabilization: “Bitemporal retrieval traceability pack.”

### Edge/ops reviewer

Consensus: edge survivability requires enforceable contracts for service hardening, pressure behavior, persistence, chaos, and deploy promotion.

Top additions:

1. MAEAH edge service hardening profile: writable paths, resource ceilings, service identities, network class, and `systemd-analyze security` evidence.
2. Local state sync contract: immutable artifacts, append-only events, mutable CRDT metadata; no KV/full working-memory sync in v1.
3. Deterministic pressure-state machine: normal → elevated → constrained → critical → shed.
4. Persistence/impermanence manifest before tmpfs-root adoption.
5. Lightweight local chaos matrix: kill llama/coordinator, corrupt staged model hash, disk pressure, mock thermal critical, stale Agent Card, queue pressure.
6. Deployment promotion protocol: preflight → switch → converge → canary → promote/rollback evidence.

Priority recommendation: deployment gates, pressure-state machine, persistence contract, chaos suite, edge hardening profile, then CRDT/local-first sync.

## Resulting plan changes

The team inputs are folded into:

- `EXTERNAL-PARITY-AMENDMENTS.md`
- `PARITY-INTEGRATION-PLAN.md`
- `MAEAH-SECURITY-CONTRACT-GATES.md`
- `PHASE-A-ACCEPTANCE-CRITERIA.md` Gate 9 correction
- small v0.3 supplement pointers in `COMBINED-PRD.md`, `PLAN-SIGNOFF.md`, and `SYSTEM-COMPARISON-PLAN.md`
