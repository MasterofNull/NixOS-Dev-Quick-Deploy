# PRD — AQ-OS Refoundation Cycle 0: Make the System's Decisions Trustworthy

**Status:** DRAFT / `REQUEST_REVISION`; direction proposed, plan not ratified, implementation not authorized  
**Owner:** hyperd, represented by the AQ-OS owner meta-prompt  
**Prepared:** 2026-07-10  
**Companion artifacts:** `.agents/plans/aqos-refoundation-cycle0/CONSOLIDATED-PLAN.md`,
`STATE-CONTRACT.md`, `EVIDENCE-ALGEBRA.md`, `CURRENT-AUTHORITY-INVENTORY.md`,
`C0.2-SURFACE-INVENTORY.md`, `THREAT-REGISTER.md`, `DECISION-LOG.md`,
`REFERENCE-AND-MIGRATION-COMPARISON.md`, and `EVIDENCE-MANIFEST.md`
**Provenance:** Codex orchestration plus three same-family expert workstreams; these inputs do not
constitute independent model-diverse quorum.

## 1. Product definition

AQ-OS is a **local-first NixOS control plane for bounded, replayable, evidence-driven agent work that
safely improves local AI capability while preserving explicit operator authority**.

Its intended use is not merely to serve a local model or coordinate several chat agents. It is meant
to let one operator run a private, hardware-aware software and knowledge factory in which local and
remote agents can plan, execute, review, learn, and recover without hiding authority, evidence,
resource cost, or risk. The dashboard, CLI, APIs, QA harness, memory, and learning loop are different
views and actuators over that one managed system.

### Non-goals

- An AGI persona, autonomous authority, or general-purpose chatbot.
- A collection of clever scripts whose file presence is treated as integration.
- A dashboard that synthesizes confidence from disconnected or stale authorities.
- Exactly-once claims; the target is at-least-once delivery with idempotent effects.
- Premature microservices, fleet claims, multi-node NATS, SPIRE deployment, a new SPA, or a new model.
- A big-bang rewrite. Existing proven assets migrate through measured strangler steps.
- Postgres or any other clean-sheet dependency in Cycle 0. Cycle 0 establishes the evidence needed
  to ratify Cycle 1 choices.

## 2. Trajectory and current status

The system evolved from a NixOS quick-deploy repository into a broad local AI harness through more
than 175 delivery phases. It now includes declarative deployment, local and remote inference lanes,
a hybrid coordinator, switchboard, AIDB/Qdrant/Redis/Postgres, workflow and delegation machinery,
security controls, a dashboard, a large QA corpus, institutional memory, and a closed learning loop.

That trajectory created genuine assets, but it also optimized for feature arrival before architectural
convergence. The present system is **functionally substantial but not yet trustworthy as a managed
operating system**:

- `verified_source`: NixOS, secrets handling, service identities, rollback, AppArmor, local-first
  inference, switchboard routing, brokered memory, QA, and the closed learning loop are valuable
  foundations to preserve.
- `verified_source`: the coordinator, scripts, registries, telemetry files, Markdown artifacts,
  dashboard collectors, Redis, Qdrant, and JSON/JSONL files can represent overlapping lifecycle or
  evidence state.
- `verified_live`: `aq-collab-round collect` set this round to `CONSENSUS_LOCKED` with `ABSTAIN: 3`,
  empty contributions, no aggregate path/hash, a still-running local lane, and no Antigravity output.
- `verified_live`: concurrent QA runs produced different totals and overwrote one shared `latest`
  artifact. Point-in-time totals belong in dated evidence records, not this durable PRD; a surviving
  mutable snapshot proves broad availability, not immutable certification of its invoking run.
- `verified_source`: current Phase-0 checks frequently validate presence, registration, or endpoint
  wiring. Those are useful conformance checks but do not establish effectiveness, durability, safety,
  or operator outcomes.
- `verified_source`: effectiveness reporting can pass some composites with `no_data`, substitute a
  proxy for absent evidence, and disagree with a separately synthesized dashboard scorecard.
- `inferred`: adding a durable event store, typed SPA, new broker, or more services before repairing
  these semantics would create another authority rather than a coherent system.

### Core critique

The largest deficit is not missing capability. It is **semantic integrity**: the system cannot yet
reliably answer which state is authoritative, why it reached that state, whether the evidence is
current and attributable, and what an operator may safely authorize next. Cycle 0 therefore repairs
the ability to decide before it implements the clean-sheet architecture.

## 3. Current authority map

```text
Operator / agents
  ├─ aq-* CLIs and direct scripts
  ├─ dashboard routes and caches
  └─ Markdown, inbox, PULSE, PENDING, RESUME, registry and telemetry artifacts
                   │
                   ▼
Hybrid coordinator / extensions
  ├─ workflow, delegation, policy, scheduling and learning
  ├─ duplicated/direct payload and fallback paths
  └─ file, Redis, Qdrant, Postgres and dashboard projections
                   │
                   ▼
Switchboard execution gateway ──► llama.cpp / remote provider lanes
```

| Concern | Current competing representations | Failure to eliminate | Intended authority after migration |
|---|---|---|---|
| Planning consensus | `round.json`, proposal files, aggregate, lane/registry status | Status can become consensus without evidence | Durable decision/review objects; files are hashed projections |
| Delegation lifecycle | PID registry, heartbeat, stream/output files, PULSE | Liveness or stale state can masquerade as completion | Durable run/task/attempt transitions |
| Session recovery | PENDING, RESUME, PULSE, HANDOFF | Concurrent writers and projections diverge | Durable intent/run state with single-writer projections |
| Runtime workflow | Coordinator objects, checkpointers, FSMs, telemetry | Multiple lifecycle concepts lack one revision sequence | One control-plane run/task/event authority |
| QA/effectiveness | latest JSON, result logs, report, dashboard | Missing, stale, conflicting, or overwritten evidence can look green | Immutable evidence/eval records plus atomic named pointers |
| Model routing | Coordinator policy, switchboard profiles, direct callers | Payload, fallback, and policy drift | Control plane owns policy; switchboard owns execution |
| Learning | capture/correction/HITL queues, scorer, golden data, promotion | Reward corruption and backlog amplification | Lineage-bound eval/artifact/policy decisions |
| Memory | hot/warm Markdown, AIDB, Qdrant, brokered stores | Projection freshness and authority are unclear | Durable source records; semantic stores are projections |
| Configuration | Nix, env contract, JSON/YAML, code defaults | Duplicate defaults and startup/runtime divergence | Nix substrate plus versioned application contracts |
| Operator truth | CLI output, API, report and dashboard synthesis | Different consumers derive different answers | One public API and serialized scorecard semantics |

`CURRENT-AUTHORITY-INVENTORY.md` provides the source-anchored current writer/reader/bypass/recovery
inventory for the ten broad domains and confirms all ten are presently `SPLIT_BRAIN`; the deployed Nix
configuration chain is the one mostly-`SINGLE` subpath. C0.3 converts that research snapshot into a
schema-validated registry, adjudicates target ownership and attaches rollback/retirement deadlines.

## 4. Clean-sheet intent architecture

If recreating the intent from scratch, use the smallest deployable shape that can preserve evidence
and recover from process death:

```text
aq CLI / operator console
          │ one versioned API
          ▼
Modular control-plane application
  intent · workflow · policy · review · evidence · capability registry
          │ transactional state and outbox
          ▼
Postgres ──► idempotent workers/projections
  │             ├─ Redis: ephemeral queue/cache/wakeup only
  │             ├─ Qdrant: lineage-bound semantic projection
  │             └─ local CAS: immutable prompts/logs/patches/eval artifacts
  ▼
Switchboard ──► local llama.cpp by default; explicit remote providers when permitted

NixOS declares packages, identities, secrets, ports, persistence, resource controls,
sandboxing, activation, backup and rollback.
```

This keeps the existing four-plane model as an operator explanation—experience, control, inference,
and data—without granting each plane independent workflow truth. The initial target should be a
modular monolith, not a microservice fleet. Postgres plus transactional outbox is the leading Cycle 1
hypothesis because the existing host already runs Postgres, but restore cost, write amplification,
schema ownership, failure modes, and APU/RAM/disk impact must be measured in C0.3.

## 5. Canonical object model

| Object | Required semantics |
|---|---|
| Intent | Owner objective, constraints, risk, revision and separate direction/plan/authorization decisions |
| Run | Intent link, actor identity, environment, trace, budget, monotonic revision and terminal outcome |
| Task | Parent, dependencies, contract, assignee capability, attempt, idempotency key, deadline and budget |
| Event | Immutable ID, aggregate/type/revision, producer, observed/recorded time, schema, causation/correlation and payload hash |
| Artifact | Raw-byte content hash, type, size, producer, lineage, privacy, retention, storage location and atomic named pointer |
| Review | Exact subject hash/revision, reviewer identity/lineage, verdict, evidence, required changes, expiry and supersession |
| Capability | Name/version, owner, contracts, permissions, dependencies, resource envelope, probes, kill switch and retirement |
| Lease | Principal, capability/version, actions/resources, budget, issuer, expiry and revocation revision; checked at both effect boundaries |
| Eval | Dataset/scorer/model/prompt/profile versions, isolation evidence, case results, trust state, absence reason and promotion decision |
| Policy decision | Input and policy revisions, allow/deny/review/degrade result, obligations, actor, evidence and expiry |
| Evidence manifest | Claim, producer assurance, collection command, environment, immutable artifacts, freshness, assessment and lineage |
| Projection checkpoint | Projection/version, last authoritative revision, rebuild status and hash; never grants authority |

### Lifecycle and relationship requirements

| Object | Owner / legal lifecycle | Revision and relationship rules |
|---|---|---|
| Intent | owner: operator; `DRAFT → DIRECTION_RATIFIED | REJECTED | CANCELLED`; ratified may become `SUPERSEDED` | One intent has many plan revisions and runs; supersession atomically supersedes plan ratifications and suspends authorizations |
| Run | owner: control plane; `QUEUED → RUNNING → SUCCEEDED | FAILED | CANCELLED | BLOCKED`; terminal outcomes are immutable | Belongs to one intent/authorization; has many tasks/events/artifacts; retries create attempts, not rewritten outcomes |
| Task | owner: workflow module; `PENDING → READY → RUNNING → SUCCEEDED | FAILED | CANCELLED | BLOCKED` | One run has many tasks; dependency revisions and idempotency key are immutable per attempt |
| Review | owner: review module; `REQUESTED → SUBMITTED → ACCEPTED | REJECTED | SUPERSEDED | EXPIRED` | Targets exactly one subject revision/hash; producer-lineage independence is evaluated before eligibility |
| Artifact | owner: producing task; `STAGED → VERIFIED → ACTIVE | QUARANTINED → RETIRED`, with `PURGED` as audited terminal metadata | Bytes are immutable; names are pointers; one artifact may support many evidence records but has one privacy/retention domain |
| Capability | owner: admission authority; `CANDIDATE → ADMITTED → ENABLED ↔ DEGRADED → DISABLED → RETIRING → RETIRED` | Version changes create a new capability revision; enabled instances require current policy and probes |
| Lease | owner: policy authority; `ISSUED → ACTIVE → EXPIRED | REVOKED | CONSUMED`; terminal records never reactivate | Belongs to one principal and capability revision; reauthorization creates a new lease |
| Eval | owner: eval authority; `COLLECTING → VALIDATING → PASSED | FAILED | UNKNOWN | INVALID | UNTRUSTED` | Binds exact dataset/scorer/model/prompt/profile/environment revisions; promotion is a separate policy decision |
| Policy decision | owner: policy engine/operator; `PENDING → ALLOW | DENY | REQUIRE_REVIEW | DEGRADE → EXPIRED | SUPERSEDED` | Binds exact input/policy revisions; changed inputs require a new decision |
| Event | owner: aggregate writer; append-only, no mutable lifecycle | Each aggregate revision is monotonic; source+ID is unique; causal/correlation links do not grant authority |
| Evidence manifest | owner: collector; `STAGED → VERIFIED | INVALID → SUPERSEDED | EXPIRED` | Binds claims to immutable artifacts; changing any input creates a new manifest revision |
| Projection checkpoint | owner: projection worker; `BUILDING → CURRENT | STALE | FAILED → REBUILDING` | References one authoritative revision; deletion/rebuild cannot affect authoritative state |

State names are contract hypotheses for Cycle 0 review. Exact commands, actors, transitions and cascades
for planning decisions are specified in `STATE-CONTRACT.md`; runtime-object lifecycles remain
`research_required` until C0.3 verifies current writers and Cycle 1 ratifies their authority.

### Planning and authorization state contract

`direction_ratified`, `plan_ratified`, and `implementation_authorized` are distinct decisions bound to
immutable subject hashes:

| Decision | States | Critical invariant |
|---|---|---|
| Direction | `PENDING`, `RATIFIED`, `REJECTED`, `SUPERSEDED`, `CORRUPT`, `CANCELLED` | Requires eligible proposal quorum and no unresolved critical change |
| Plan | `BLOCKED_ON_DIRECTION`, `PENDING_REVIEW`, `RATIFIED`, `REJECTED`, `SUPERSEDED`, `CORRUPT` | Reviews target the exact plan hash and current ratified direction |
| Authorization | `BLOCKED`, `AUTHORIZED`, `SUSPENDED`, `REVOKED`, `EXPIRED`, `CONSUMED` | Requires both ratifications, signed dependencies, current evidence, and explicit operator/policy action |

Artifact mutation changes the subject hash, supersedes dependent decisions, and blocks or suspends
authorization. Human override is a distinct attributed decision and must never be rewritten as model
consensus.

## 6. Clean-sheet parity matrix

| # | Requirement | Current equivalent/evidence | Gap | Decision | Success metric |
|---:|---|---|---|---|---|
| 1 | Modular control plane | Coordinator plus many extensions/scripts `[verified_source: PROJECT-AQOS-PRD §2]` | Unenforced boundaries and god-service growth | Refactor | Forbidden-import tests pass; lifecycle survives restart |
| 2 | Durable state plus transactional outbox | Files, registries, JSONL, Redis and Markdown `[verified_source: E-002/E-003]` | No atomic lifecycle/evidence replay | Replace authority | Crash/replay is identical; restore drill passes |
| 3 | Redis is ephemeral | Existing cache/coordination and proposed stream spine `[verified_source: PROJECT-AQOS-PRD §3-4]` | Risk of promoting delivery state to truth | Refactor | Redis loss cannot lose committed workflow state |
| 4 | Qdrant is a semantic projection | Existing AIDB/Qdrant/RAG `[verified_source: canonical-kernel declaration; ai-stack role wiring; quality remains research_required]` | Weak lineage, freshness and quality semantics | Keep/refactor | Every vector links to source/version/freshness; rebuild reconciles |
| 5 | Content-addressed artifact storage | Mutable spools, logs, datasets and result files `[verified_source: full-system analysis E-004]` | Incomplete lineage, retention, atomicity and GC | Replace authority | Accepted evidence is hash-addressed; pointer/GC/recovery tests pass |
| 6 | One versioned contract package | Env contract plus scattered schemas/dicts `[verified_source: PROJECT-AQOS-PRD D4-D6]` | Drift and manual projections | Refactor | Critical objects share one schema; generated projections drift-fail CI |
| 7 | At-least-once plus idempotent effects | PID/heartbeat registry and unsigned JSONL `[verified_source: scripts/ai/lib/event_log.py; delegation monitor; issues backlog]` | Stale rows, weak producer identity, duplicate risk | Replace | Duplicate/reordered delivery causes one effect and monotonic revision |
| 8 | One generation gateway | Switchboard plus coordinator/direct payloads `[verified_source: full-system analysis A1]` | Routing/payload/fallback split-brain | Refactor | Every call has gateway request ID; alternate callers blocked/retired |
| 9 | Admitted capability modules | Skills, intake, extensions and partial leases `[verified_source: canonical-kernel declaration]` | Admission, budgets, controls and retirement are inconsistent | Refactor | Every enabled capability has owner, lease, budget, probe and kill switch |
| 10 | One API; CLI and console as clients | Many `aq-*` entrypoints and dashboard routes `[verified_source: PROJECT-AQOS-PRD §2]` | Behavioral and semantic duplication | Consolidate | Generated client contracts pass; shim use reaches retirement threshold |
| 11 | NixOS is the substrate | NixOS, SOPS, identities, AppArmor and rollback `[verified_source: canonical-kernel declaration]` | Strong asset; declaration/runtime drift remains | Keep | Clean activation/rollback; no undeclared port/service/secret |
| 12 | Stable observability semantics | QA, report, spider, dashboard and telemetry `[verified_source: scripts/ai/aq-report; dashboard/backend/api/routes/aistack.py; full-system analysis E-004]` | Availability conflated with effectiveness; absence can pass | Replace semantics | Full trace coverage; typed absence blocks; immutable run evidence |

“Replace” means replace the authority or semantic contract, not indiscriminately discard working code.

## 7. Ranked parity gaps

Scores use the owner formula: outcome 25%, trust/safety 20%, convergence 20%, measurability 10%,
hardware fit 10%, reversibility 10%, and reverse implementation cost 5%.

| Rank | Gap | Score / 5 | Priority | Stop condition |
|---:|---|---:|---|---|
| 1 | Evidence-bound consensus/review invariants | 4.85 | P0 | Any terminal decision lacks eligible reviews, attribution, hashes or recovery |
| 2 | Truthful evidence/effectiveness algebra | 4.75 | P0 | Missing, stale, invalid, conflicting or unauthorized evidence can pass |
| 3 | Authority, duplicate-path and retirement ledger | 4.55 | P1 | Any writer, reader, bypass, owner or retirement condition is unknown |
| 4 | Durable lifecycle store, outbox and replay | 4.50 | P2 | C0.3 has not ratified authority, restore and resource evidence |
| 5 | Identity, leases and effect-boundary enforcement | 4.40 | P2 | A model can reacquire authority or bypass an enforcement layer |
| 6 | Eval isolation, certification, lineage and promotion | 4.35 | P2 | An untrusted scorer/dataset/run can influence promotion |
| 7 | Resource admission, backpressure and cancellation | 4.20 | P2 | Background work can starve interactive or review capacity |
| 8 | Switchboard-only execution and payload consolidation | 4.10 | P2 | Any unmeasured alternate generation path remains |
| 9 | End-to-end trace/evidence and SLO semantics | 4.00 | P2 | A failed run still requires cross-file/journal archaeology |
| 10 | One API and compatibility retirement | 3.70 | P3 | Shims lack usage evidence, owner, deadline or divergence alarm |
| 11 | Backup/restore, upgrade/rollback and releases | 3.60 | P3 | Recovery and clean installation are not repeatedly exercised |
| 12 | Second continuously tested hardware class | 3.05 | P3 | Portability claims lack current benchmark evidence |

Only the first three gaps belong in Cycle 0.

## 8. Cycle 0 product requirements

### C0.1 — Evidence-bound collaboration decisions

- Quorum derives from eligible contribution objects, not lane status.
- `ABSTAIN`, absence, timeout, failure, proxy output, unknown provenance, self-review, or schema fallback
  has zero approval weight.
- Contributions bind round, decision type, subject revision/hash, dispatch principal, model lineage,
  explicit verdict, evidence and recovery tests.
- Use `APPROVE`, `APPROVE_WITH_CHANGES`, `REJECT`, `ABSTAIN`. The old conditional verdict never
  approves or counts; only fresh `APPROVE` reviews of the amended subject hash can ratify it. An
  eligible reject requires adjudication or a new revision.
- Structured records use `aq-canonical-json-v1` from `STATE-CONTRACT.md` then SHA-256; files use exact raw bytes and SHA-256.
  Hashes establish integrity, not authorship. Attribution assurance is separately recorded as
  `UNVERIFIED`, `ORCHESTRATOR_ATTESTED`, or `CRYPTOGRAPHIC`.
- Amendments are append-only. A late rejection, new critical risk, or subject change suspends any
  authorization until disposition and re-review.
- Invalid state becomes `CORRUPT/BLOCKED`; recovery quarantines evidence, dry-runs reconstruction,
  requires attributed operator acceptance, preserves the invalid revision, and replays invariants.

### C0.2 — Truthful evidence and effectiveness semantics

Represent three orthogonal values:

```text
EvidenceCondition = VALID | MISSING | STALE | INVALID | CONFLICTING | UNAUTHORIZED | INSUFFICIENT_SAMPLE
ClaimAssessment   = PASS | WARN | FAIL | UNKNOWN | NOT_APPLICABLE
GateOutcome       = PASS | DEGRADED | FAIL | BLOCKED
```

- Non-valid evidence yields `UNKNOWN`, never `PASS`.
- Required fail yields `FAIL`; otherwise required unknown yields `BLOCKED`; otherwise required warning
  yields `DEGRADED`; only all required pass yields `PASS`.
- Zero denominator is `UNKNOWN/NO_DENOMINATOR`; missing is never silently `NOT_APPLICABLE`.
- Availability, contract conformance, effectiveness, and SLO reliability are different claim classes.
- Proxy metrics have their own identity and cannot silently satisfy the original claim.
- Every non-pass required claim emits stable reason codes and operator remediation.
- CLI and dashboard consume the same serialized scorecard. The dashboard does not author another one.
- QA runs produce immutable run-keyed evidence; `latest` is only an atomic pointer containing run ID/hash.

### C0.3 — Authority and retirement ledger

- Inventory every canonical object and all current writers, readers, caches, bypasses and projections.
- For each competing path, select keep/refactor/replace/retire, owner, instrumentation, rollback,
  compatibility ceiling and maximum retirement date.
- A compatibility path must expose use count, divergence, last use, exception owner and expiry.
- Produce the Cycle 1 ADR comparing existing Postgres, Redis, Qdrant, filesystem CAS and modular-monolith
  options by durability, recovery, security, packaging, APU/RAM/disk cost, migration and exit strategy.
- Do not enforce the Cycle 1 architecture inside C0.3; the output is a ratifiable decision package.

## 9. Cycle 0 acceptance

Cycle 0 exits only when all are true:

1. The current false-locked round, all-reject, empty-extraction, self-review, proxy-lineage and late-reject
   fixtures cannot ratify or authorize implementation.
2. Missing/stale/invalid/conflicting evidence and zero denominators cannot produce a pass in CLI, API,
   report, dashboard, or automation.
3. A QA run is immutable, named by run ID/hash, and cannot be overwritten by a concurrent run.
4. The authority ledger covers all declared objects and has no unowned writer, reader, bypass or shim.
5. Every new signal is visible through the same API/CLI/dashboard semantics with operator remediation.
6. Destructive, replay and concurrency tests use isolated temporary stores and cannot touch live
   PULSE/RESUME, registries, QA `latest`, Qdrant, Redis or production Postgres.
7. Resource budgets and rollback tests in the companion plan pass.
8. Independent model-diverse reviewers ratify the exact `PACKAGE-ROOT.json` external hash that binds
   the PRD, plan and every required companion contract.
9. A separate attributed owner action records `implementation_authorized=AUTHORIZED`.

## 10. Success measures

- 100% of planning terminal states have a valid subject hash, evidence manifest and attributed transition.
- 0 false ratifications across the adversarial fixture suite.
- 0 required claims pass with non-valid evidence or zero denominators.
- 100% of scorecard non-pass states expose deterministic reason and remediation codes.
- 100% of QA consumers expose run ID, artifact hash, observed time and freshness.
- 100% of authority-ledger rows truthfully record observed claims/writers and current condition; every
  `SPLIT_BRAIN`, `UNKNOWN`, or `UNOWNED` row has a reviewed target, adjudicator, resolution deadline,
  backup/recovery, telemetry and retirement action before C0.3 ratification.
- No increase in local inference calls, steady-state services, or required background memory during Cycle 0.

## 11. Deliberately deferred

Postgres migration, transactional outbox runtime, capability identity/leases, F2.5 scheduling activation,
eval industrialization, payload consolidation, one-API migration, console rebuild, portability and release
engineering begin only after Cycle 0 evidence ratifies their exact plans.

The full source-pattern comparison, build/adopt hypotheses, six-cycle strangler map and consolidation/
deletion candidate classes are in `REFERENCE-AND-MIGRATION-COMPARISON.md`; source-supported exact
retirement candidate paths are in `CURRENT-AUTHORITY-INVENTORY.md`. C0.3 must still adjudicate targets,
owners and deadlines before Cycle 1 ratification; it may never invent a convenient current singleton.

`VERDICT: REQUEST_REVISION — the product direction and three Cycle 0 slices are evidence-backed, but
model-diverse quorum, exact resource/retention thresholds, and owner authorization remain outstanding.`
