# Foundation B2-D0 design packet

**Slice:** B2-D0 — first workflow shadow vertical decision package

**State:** PREPARED FOR REVIEW / NOT AUTHORIZED

**Implementation:** none

**Owner decisions:** Q1 and Q2 remain required and undecided by this packet

## 1. Review subject

The exact subject is these three new documentation files only:

1. `.agents/plans/aqos-foundation-b2/WORKFLOW-SHADOW-ADR.md`
2. `.agents/plans/aqos-foundation-b2/WORKFLOW-SHADOW-PRD.md`
3. `.agents/plans/aqos-foundation-b2/B2-D0-DESIGN-PACKET.md`

The orchestrator must bind a review to fresh SHA-256 digests after this packet is complete. A content
change after review invalidates the verdict.

## 2. Design assertion under review

The packet proposes exactly one Q2 hypothesis:

> `workflow-sessions.json`, committed by the hybrid coordinator, remains the sole live authority. Only
> coordinator-managed `run.start`, manual phase transitions, and terminal completion are observed.
> The current rename is not treated as crash durability: receipt order is allocated with the locked
> legacy mutation, file plus parent-directory `fsync` must complete, and a bounded per-workflow FIFO is
> enqueued under that lock before one-in-flight ordered shadow delivery begins.
> After that durable commit, a bounded privacy-minimized Postgres transaction performs
> expected-revision CAS and appends an immutable transactional-outbox event. A delivery worker owns
> only mutable delivery metadata; the lifecycle projector is pure and read-only. No live execution,
> recovery, API, or cutover path reads Postgres. A shadow failure parks/disables shadow observation
> without changing the live result.

Review approval means the hypothesis is sufficiently specified for owner adjudication. It does not
ratify Q1/Q2 and does not authorize DDL, connections, writes, code, deployment, or live traffic.

## 3. Evidence baseline

Reviewers should verify the proposal against:

- `config/system-state-authorities.yaml`, row `workflow-run-task`: owner-adjudicated target, observed
  split-brain writers, rollback boundary and `Cycle 1 NOT_AUTHORIZED` declaration.
- `.agents/plans/UNIFIED-PROGRAM-PLAN.md`: Foundation B2 is gated by Q8 row adjudication and exact Q2
  ratification. The row is now owner-adjudicated; this packet addresses the still-open Q2 design gate.
- `.agents/plans/unified-program/OWNER-DECISION-SHEET.md`: Q2 requires the exact first hypothesis after
  Q8 and before writes.
- `.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md`: legacy authority, one CAS/outbox/replay
  vertical and evidence-before-expansion.
- `.agent/PROJECT-LOCAL-AI-FACTORY-REFERENCE-ARCHITECTURE-PRD.md`: Cycle 1B invariants and open owner
  decisions.
- `ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_session_handlers.py`: coordinator legacy
  writer and relevant handlers; its current rename gives atomic visibility but lacks the file and
  parent-directory `fsync` required by this design's crash-durable receipt boundary.
- `ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_executor.py`: standalone same-file writer.
- `scripts/ai/sync-workflow-sessions.py`: third same-file writer.
- `ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_checkpointer.py`: existing but separate and
  unwired Postgres checkpoint/backtrack objects that this proposal excludes.

## 4. Frozen boundary

### Included

- design of closed privacy-safe contracts;
- legacy-first one-way observation after file and parent-directory durability;
- Postgres shadow snapshot CAS plus transactional outbox;
- transactionally allocated persistent receipt order, lock-bound FIFO enqueue, one-in-flight delivery,
  and exact replay/gap/stale/conflict branches across concurrency/restart;
- stable opaque allowlisted phase tokens with no raw/model-derived phase text;
- isolated mutable delivery control plus pure read-only lifecycle projection/replay validation;
- parking, disablement, evidence and rollback;
- fixed resource/latency/cardinality budgets;
- `aq-qa`, dashboard and live-test delivery requirements;
- later sliced candidate inventory.

### Excluded

- all repository modifications other than these three documents;
- Q1/Q2 adjudication or implementation authorization;
- database schema creation, migration or connections;
- runtime hooks, traffic, shadow writes or live reads;
- writer retirement or a convergence-state change;
- Postgres recovery, API reads or cutover;
- reuse/change of `workflow_checkpoints`, Redis DLQ or graph-run JSON;
- any workflow mutation outside the three named transition classes;
- a generic lifecycle store or repository-wide state-spine commitment.

## 5. Proposed later candidate inventory

This is a planning ceiling, not an active file lease. Exact paths and predecessor hashes must be frozen
again per slice after Q1/Q2 ratification.

### B2-C1 — pure contracts (maximum 10 files)

- new closed schemas for event, snapshot, immutable outbox, delivery control and health;
- new pure mapper/canonicalizer and reviewed phase-token registry;
- pure monotonic receipt allocation, ordered-delivery and replay decision model;
- golden valid/adversarial vectors;
- focused pure tests;
- one Phase-0 registration/update;
- slice authorization/evidence documents as required.

No Postgres import, network call, runtime handler edit, dashboard edit or new service is permitted.

### B2-M1 — migration boundary (maximum 8 files)

- forward/disable migration for separately named shadow objects;
- least-privilege migration/writer/reader grant declarations;
- isolated migration/privilege/rollback tests;
- deployment documentation/evidence.

No runtime activation, existing table mutation, destructive down migration or live data backfill.

### B2-W1 — disabled runtime adapter (maximum 10 files)

- crash-durable legacy save/receipt cursor and three exact post-commit hook sites;
- bounded transaction adapter and circuit breaker;
- configuration/env-contract additions if required;
- focused unit/integration/fault tests.

Activation remains false. No handler may read shadow state, and no excluded mutation receives a hook.

### B2-P1/O1 — observability and verification (maximum 12 files)

- delivery-control worker plus pure read-only lifecycle projector and deterministic replay tests;
- aggregate low-cardinality metrics/health route or existing projection integration;
- Phase-0 integration checks;
- existing dashboard surface/card/badge;
- browser/API/accessibility/security tests and evidence builder.

The dashboard cannot expose raw event payloads or imply Postgres authority.

### B2-T1 — trial activation

No code delta is assumed. A hash-bound, expiring owner activation freezes migrations, runtime,
configuration, trial ceiling, evidence destination, abort thresholds and rollback commands. A later
owner decision—not trial uptime—chooses expand, replace, retire or prepare cutover.

## 6. Acceptance criteria for this D0 design

A reviewer may issue `PASS` only if all are true:

1. The exact legacy-live/Postgres-shadow hypothesis is unambiguous and appears consistently in all
   three documents.
2. The design observes only coordinator-managed start, manual phase transitions and terminal
   completion, with excluded mutations explicitly named.
3. Current atomic visibility is distinguished from crash durability; file and parent-directory `fsync`
   precede every receipt/shadow attempt, and no shadow read can affect execution, recovery, API results
   or cutover.
4. Receipt order is allocated/persisted with the locked legacy transaction and survives restart;
   per-workflow FIFO enqueue occurs before lock release and one-in-flight delivery prevents overtaking;
   snapshot CAS and immutable outbox append share one transaction; exact replay, restart gap, stale,
   collision and terminal branches are specified.
5. Privacy minimization is allowlist-based and prohibits prompt/note/output/tool/secret/path/env data
   plus raw/model-derived phase text and high-cardinality telemetry labels; phases use stable opaque
   allowlisted tokens only.
6. Failure behavior parks/disables shadow work without changing the live result, and rollback preserves
   legacy authority and evidence.
7. Migration/runtime/delivery-worker/read-only-projector principals, immutable event ownership, mutable
   delivery-metadata authority and the non-reuse of current checkpoint objects are explicit without
   creating a second lifecycle writer.
8. Numeric time, connection, queue, event, RSS, disk, retention, lag, parity and trial budgets are
   proposed for owner freeze.
9. Threat matrix covers pre-save ordering, DB dependency, concurrency, duplication, terminal conflict,
   partial transaction, privacy, tamper/replay, outage, memory/disk, privileges and false authority.
10. Service coverage requires instrumentation, non-health-only Phase-0 `aq-qa`, dashboard state and live
    failure/resource tests in the same delivery sequence.
11. Later work is sliced and bounded; no candidate inventory is represented as a lease.
12. Q1/Q2 remain explicit owner gates, and neither reviewer approval nor broad preauthorization is
    treated as ratification.

## 7. Mandatory reviewer challenges

The independent architecture/security/SRE/concurrency review must attempt to disprove:

- that a database import, pool or timeout can alter live startup/response behavior;
- that an acknowledged rename can be lost because file or parent-directory durability was skipped;
- that concurrent/restarted coordinator transitions can allocate duplicate or regressed receipt order;
- that exact retry can be confused with a gap, stale receipt or nonidentical collision;
- that a crash can leave snapshot without outbox or outbox without snapshot;
- that terminal replay/races can create two outcomes;
- that a forbidden canary can reach any durable bytes or operational surface;
- that raw/model-derived phase text can reach shadow bytes, hashes, logs, metrics or the dashboard;
- that the delivery worker or projector can mutate workflow lifecycle state;
- that gaps can be silently synthesized, repaired or overlooked;
- that the existing checkpoint tables can be confused with B2 authority;
- that resource/retention controls require destructive runtime privileges;
- that a dashboard or API consumer could treat shadow state as live truth;
- that Q1/Q2 could be inferred rather than explicitly recorded.

## 8. Review output contract

The reviewer must identify model/role, exact subject hashes, evidence inspected, each acceptance
criterion result, findings with file/section references, and one final line:

`VERDICT: PASS|FAIL|REQUEST_REVISION — <one-line reason>`

Only an independent final `PASS` may support later owner adjudication. The author cannot accept this
packet. A `PASS` still authorizes no implementation.

## 9. Next gate

1. Orchestrator records exact hashes and requests independent design review.
2. Author resolves any requested revisions; changed hashes require re-review.
3. Owner explicitly decides Q1 and this exact Q2 hypothesis, names the migration owner, and freezes or
   amends the proposed resource envelope.
4. Only then may a separate B2-C1 pure-contract authorization be prepared and independently reviewed.

Until step 3 is complete: **Foundation B2 implementation remains NOT AUTHORIZED.**
