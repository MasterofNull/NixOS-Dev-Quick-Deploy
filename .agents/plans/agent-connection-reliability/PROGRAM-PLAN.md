# Agent Connection Reliability — Program Plan

Status: **C0 ACCEPTED/COMMITTED (`4e3d96d3`) — C0.5 NEXT; NO LIVE ROUTE AUTHORITY**
Parent: `.agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md`
Date: 2026-07-16

## Sequence

### C0 — Contract and failure characterization

Land only closed request/ack/status/event schemas, adapter interface types, reason taxonomy, policy,
and hermetic fixtures. Characterize caller-death, zero-output, shell-metacharacter, PID namespace,
duplicate submission, quota-window, broker-unavailable, and daemon-restart cases. No daemon, wrapper,
Nix, traffic, or lifecycle-store mutation.

Exit: all current wrapper defects reproduce as fixtures; schemas reject unknown/unbounded data;
dashboard contract-health projection exists from pure fixtures.

Completion state: implemented under `auth-agent-connection-reliability-c0-am1-20260716`, independently
accepted by Antigravity against exact hashes, and committed as `4e3d96d3`. Focused contract, Agent
Ops, local-reliability, and Tier0 suites passed. Receipt:
`.agents/plans/agent-connection-reliability/antigravity-c0-acceptance.md`. C1 remains unimplemented
and unauthorized.

### C0.5 — Review receipts and recursive-feedback contract

Before C1 implementation, define closed, bounded review-round receipt and learning-candidate
contracts for every later slice. Bind subject hashes, same-baseline pass IDs, dynamic required roster,
role/model lineage, per-criterion evidence, verdicts, unavailable/parked reasons,
revision/supersession, and feedback disposition. Add only pure Agent Ops review/feedback health; do
not add a lifecycle store or claim live orchestration.

Exit: hermetic fixtures prove missing lanes are not converted to abstention, self-review cannot count
as flagship acceptance, reviewer-authored changes create new hashes requiring independent re-review,
and every accepted finding resolves to a regression/eval candidate or typed non-propagation reason.

### C1 — Socket-activated broker with fake adapter

Implement `aq-dispatchd` and thin client over `AF_UNIX`, systemd socket/service declarations, strict
peer/admission validation, transactional existing-registry writer, idempotency, fencing, CAS,
heartbeat, bounded evidence, and fake-provider adapter. Ship Phase-0, Tier0 registration, Agent Ops TUI,
and web dashboard health together. Existing wrappers remain unchanged and no real provider activates.

Exit: accepted fake tasks survive client/sandbox death and daemon restart; duplicate requests execute
once; cancellation affects only owned fake work; live dashboard and `aq-qa` pass.

C1 fixtures also cover same-baseline reasoning admission, cheapest eligible implementer selection,
independent flagship receipts, and distinct local coding/logic/embedded modalities. The fake adapter
emits typed feedback candidates without directly mutating prompts, policy, tools, or routing.

### C2 — Claude canary adapter

Use Claude as the first remote canary because its current failure is reproduced and measurable.
Install adapter dormant, validate model-tier resolution, protected input transport, provider error
capture, quota classification, and flagship quota reservation. Activate only one explicit canary task
class through a single manifest switch; legacy Claude wrapper remains available only for read/status
until full cutover.

Exit: repeated headless review canaries survive caller death, expose progress/terminal evidence, and
produce no stale running or zero-byte unexplained exits during soak.

### C3 — Codex, local, and Antigravity adapters

Add one adapter at a time under separate activation:

1. Codex process/cgroup adapter and approval-safe headless profile.
2. Local switchboard/inference adapter with aq-chat parity and contention-aware phase budgets.
3. Antigravity inbox/collector adapter with pending/archive lifecycle receipts.

Each adapter must pass caller-death, duplicate, cancellation, privacy, dashboard, and live-canary gates
before the next begins. Retired Gemini remains fail closed.

The local activation separately certifies agentic coding/tools, bounded logic/direct generation, and
embedded retrieval against measured hardware/model profiles and shared authority/evidence contracts.
Failure in one modality cannot silently disable, promote, or reroute another.

### C4 — Park/resume and collaboration-round integration

Implement RSI R8 failure classification, durable parked state on the existing lifecycle spine,
earliest-resume scheduler, intended-lane preservation, idempotent resume, quota reservations, and
late review folding. No silent local fallback.

Exit: simulated long `Retry-After` survives daemon/session restart, resumes exactly once, and closes a
required-lane collaboration round with visible parked latency.

C4 also closes recursive propagation: findings are deduplicated, attached to issues and reproducible
evals, routed to affected shared/flagship/implementer/local/embedded consumers, and promoted only
after shadow evaluation, independent flagship acceptance, canary/soak, and rollback capture.

### C5 — Atomic universal cutover and legacy removal preparation

After all adapters pass independent flagship acceptance, drain legacy tasks under the admission lock
and flip one versioned manifest to broker-only. Legacy writer/launch branches become unreachable and
are removed only in a later archive-reviewed cleanup slice.

Exit: static and dynamic gates prove every supported route traverses the broker; a seven-day soak has
zero manual repairs, duplicate executions, dark tasks, or unexplained terminal states.

## Immediate next slice: C0.5

Proposed inventory must be separately reviewed before activation. Expected categories:

- strict review-receipt and learning-candidate schemas/policy under `config/`;
- pure validation, quorum/separation, feedback-disposition, and projection logic;
- golden same-baseline, partial-roster, self-review, revision, local-modality, and propagation fixtures;
- pure Agent Ops review/feedback contract-health projection;
- PRD/plan status only.

C0.5 must not edit delegation wrappers, Nix services, live registry data, provider configurations,
credentials, network routes, prompts, model artifacts, training data, or inference weights.

## Relationship to existing programs

- Agent Ops M2B is paused and absorbed into C1/C5; its CAS, durable-write, exec-before-attach, and
  monitoring invariants remain mandatory.
- Local Delegation Reliability R0 remains an input contract; live R1–R4 adoption occurs only through
  the local adapter in C3.
- RSI R8 becomes C4 rather than a separate queue implementation.
- The archived dispatch refactor supplies local configuration lessons but not the execution boundary.
- Owner Q8/state-spine selection remains independent and unauthorized.

`RECORD: C0 implementation used its activated hash-bound grant. This plan authorizes no live traffic or C1–C5 work.`
