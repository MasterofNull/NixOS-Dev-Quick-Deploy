# Foundation B2 PRD: workflow-run shadow state vertical

**Lifecycle:** DRAFT / DESIGN ONLY / NOT AUTHORIZED

**Parent decision candidate:** `WORKFLOW-SHADOW-ADR.md`

**Program position:** Foundation B2, first state vertical

**Owner gates:** Q1 and exact Q2 ratification remain open

## 1. Problem

Workflow/run/task state is currently split across coordinator JSON mutations, a standalone executor,
a synchronization script, separate graph-run JSON, and an unwired Postgres checkpoint facility. The
Foundation A owner decision names the hybrid coordinator as the target transition authority, keeps
legacy JSON live for the first shadow vertical, and permits Postgres outbox/CAS only as a measured
shadow hypothesis. It does not converge writers or authorize database activity.

We need a first experiment that establishes whether a privacy-minimized Postgres CAS plus
transactional outbox can reproduce a bounded subset of coordinator workflow transitions without
becoming a dependency of the operating system, API, execution, or recovery path.

## 2. Outcome

After separate owner ratification and implementation authorization, the system will be able to shadow
exactly coordinator-managed `run.start`, manual phase transitions, and terminal completion. The legacy
JSON commit remains the user-visible result. A successful legacy commit produces at most one bounded
shadow transaction. Independent validators quantify parity, lag, duplicates, gaps, terminal conflicts,
privacy violations, resource use, crash behavior, replay determinism, and disable/restore behavior.

The outcome is evidence for a later architecture decision, not a state cutover.

## 3. Users and jobs

- **Owner/architect:** decide whether the hypothesis deserves expansion, replacement, or retirement.
- **Operator/SRE:** see whether the shadow is disabled, healthy, lagging, divergent, or parked without
  inspecting raw workflow content.
- **Coordinator maintainer:** add a bounded observer after live commits without changing existing API
  semantics or recovery.
- **Security reviewer:** prove that shadow persistence cannot leak prompt, note, output, secret, path,
  environment, or tool data.
- **QA/reviewer:** replay deterministic fixtures and adversarial failures without a live traffic
  cutover.

## 4. Scope

### In scope

- Closed schemas and golden vectors for the shadow event, snapshot, outbox record, health projection,
  and typed failure reasons.
- A pure allowlist serializer and canonical digest function.
- A coordinator-owned post-legacy-commit adapter for the three transition classes.
- Separately named Postgres shadow snapshot, immutable transactional outbox and mutable
  delivery-control tables.
- Expected-revision CAS, idempotent exact replay, conflicting replay rejection, and terminal uniqueness.
- A pure read-only lifecycle projector/validator, plus a separately permissioned delivery worker that
  alone mutates outbox delivery metadata and never feeds live state.
- Feature/activation guard, bounded circuit breaker, retention and disk controls.
- Focused unit/integration/crash/replay/privacy/resource tests.
- Phase-0 `aq-qa` contract and one existing dashboard surface showing aggregate health.
- Evidence bundle and explicit later cutover/rejection decision gate.

### Out of scope

- Reading Postgres for execution, recovery, API responses, operator actions, or live routing.
- Live traffic cutover, dual-write authority, a new lifecycle service, or a generic repository state
  spine.
- Retiring any legacy writer in this slice.
- Forks, consensus, arbiter, runtime-mode, isolation, generic trajectory-event, automatic executor,
  orchestration-graph, checkpointer, backtrack, execution-pattern, or DLQ mutations.
- Persisting objectives, prompts, notes, outputs, tool content, agent messages, secrets, paths,
  environments, or arbitrary JSON extensions.
- Reusing or changing existing `workflow_checkpoints` or Redis structures.
- A dashboard database browser, raw identifiers, per-workflow metrics, or high-cardinality labels.
- DDL at runtime, destructive migration, history fabrication, or automatic gap repair.
- Deciding Q1/Q2, declaring Foundation A convergence, or authorizing Foundation C/Products D-G.

## 5. Functional requirements

### FR-1 — Legacy commit receipt

The current temporary-file replacement is atomic for reader visibility but does not by itself prove
crash durability. Under the coordinator lock, the live writer must allocate the next monotonic receipt
revision, persist its cursor/identity with the legacy mutation, flush and `fsync` the temporary file,
rename it, and `fsync` the parent directory. Only then may it expose an immutable receipt. The receipt
contains the transition classification, workflow identifier, committed allowlisted state, canonical
live digest, occurrence time, expected revision and revision. Failure before file and parent-directory
durability produces no shadow call.

### FR-2 — Pure privacy-minimized mapping

A pure mapper must build a closed shadow event from the receipt. It must start from an empty mapping,
copy only declared scalars/enums, reject unknown status/action/transition values, bound strings and
integers, and prove forbidden canary values do not appear in serialized bytes, logs, errors, metrics,
or dashboard responses. It must map a fixed coordinator/blueprint phase identifier through a reviewed
allowlist to a stable opaque domain-separated token/digest. Raw phase identifiers and
model-derived/free-form phase names or descriptions are rejected and never persisted or used as metric
labels, including in hashed form.

### FR-3 — Expected-revision transaction

Receipt order is allocated, not inferred: while holding the legacy coordinator lock, the writer reads
the session's durable cursor (zero when absent), assigns `revision = cursor + 1`, and persists the new
cursor with the same crash-durable JSON mutation. For `run.start`, the Postgres writer inserts a
snapshot at revision 1 only when no row exists (`expected_revision=0`). For later transitions, one
transaction conditionally updates the snapshot where the stored revision equals `expected_revision`,
then inserts the unique immutable outbox event. Affected row count other than one enters the explicit
replay/conflict decision tree in FR-4. After directory `fsync` and before releasing the legacy lock,
the coordinator appends the receipt to a bounded per-workflow FIFO. A single in-flight transaction per
workflow preserves commit order after the lock; unrelated workflows may proceed concurrently. Queue
overflow parks instead of reordering or blocking live work. Neither half of the database transaction
may commit alone.

### FR-4 — Idempotency and terminal uniqueness

With the workflow row locked or CAS-tested, the transaction takes one branch: absent row plus start
revision inserts; stored revision equal to expected advances; stored revision and event identity equal
to the receipt is exact replay and returns idempotent success without new event/delivery rows; stored
revision below expected is a gap; stored revision above expected is stale; equal revision with a
different event/digest is a collision; and any nonidentical post-terminal receipt is a terminal
conflict. Gap, stale, collision and terminal-conflict branches roll back and park. On restart the next
revision is recovered from the durable legacy cursor, never from process memory or a shadow read. A
lost intermediate receipt becomes a visible gap; the latest persisted receipt identity may be retried
exactly after restart, while runtime never renumbers or fabricates unavailable history.

### FR-5 — Live-path independence

Database import, pool creation, schema checks, transaction attempts, projector reads, and dashboard
reads must not be required for a live workflow response. After the legacy commit, the adapter receives
a fixed deadline. Timeout/failure returns a shadow-only disposition and preserves the live HTTP result,
status, body, and recovery behavior.

### FR-6 — Shadow projection and replay

A delivery worker reads immutable committed outbox events, owns the only mutable delivery-control
records (lease epoch, attempt count, next-attempt time, disposition and typed error), and cannot update
event payloads, snapshots, or live state. It invokes a pure deterministic lifecycle projector that is
read-only over lifecycle sources and computes an in-memory validation view plus immutable evidence
digest. Restarting from any declared event boundary must reproduce the same digest. Gaps and duplicates
are reported; neither worker nor projector can repair live/shadow lifecycle rows. Delivery metadata is
operational queue state, explicitly not workflow lifecycle authority.

### FR-7 — Parking and activation

The path defaults disabled. Activation is bound to reviewed schema/code/config hashes and expires.
Integrity, privacy, terminal, CAS, disk, queue, connection, or lag breaches park further writes with a
typed low-cardinality reason. Re-enable requires operator authorization after evidence review; it is
not an automatic retry loop.

### FR-8 — Evidence retention

The evidence bundle records build/config/schema digests, migration identity, activation identity,
test vectors, counts, latency/resource histograms, parity results, injected-failure outcomes,
declared replay boundary/projector digest, delivery disposition, disable reason, and review verdict. It
excludes raw workflow content; the read-only projector does not mutate a lifecycle checkpoint.

## 6. Conceptual schemas

Implementation schemas must be Draft 2020-12, closed at every object boundary, use canonical JSON for
digests, and publish compatibility rules. Names below are conceptual until Q2 and a schema slice freeze
them.

### `aq.workflow-shadow-event.v1`

Required: schema version, event ID, vertical ID, workflow ID, expected revision, revision, transition
kind, status, opaque allowlisted phase token/index, action, terminal flag, live commit digest,
occurred-at timestamp, writer identity/version. No extension bag and no raw/model-derived phase text.

### `aq.workflow-shadow-snapshot.v1`

Required: workflow ID, revision, last event ID, allowlisted state, terminal flag, live commit digest,
created/updated timestamps. The database row also carries integrity constraints; it does not contain
the source JSON document.

### `aq.workflow-shadow-outbox.v1`

Required: outbox ID/event ID, workflow ID, revision, canonical event bytes or JSONB constrained to the
event schema, and transaction timestamp. Event rows are immutable after insertion.

### `aq.workflow-shadow-delivery-control.v1`

Required: event ID, lease/fencing epoch, bounded attempt count, next-attempt time, closed disposition,
last typed delivery error and timestamps. This mutable record is owned only by the delivery worker,
contains no lifecycle payload, and cannot authorize or modify workflow state.

### `aq.workflow-shadow-health.v1`

Required low-cardinality fields: enabled state, health state, schema version, last successful write age
bucket, lag bucket, total transitions by kind/status, CAS conflicts, duplicates, gaps, terminal
conflicts, privacy failures, parked reason, disk budget state, and evidence freshness. Workflow IDs,
event IDs, phase tokens/raw phase IDs, prompts, and free-form errors are prohibited from metric
labels/dashboard payloads.

### Typed errors

At minimum: `disabled`, `deadline_exceeded`, `database_unavailable`, `schema_unready`, `schema_invalid`,
`privacy_rejected`, `cas_mismatch`, `revision_gap`, `event_collision`, `terminal_conflict`,
`transaction_failed`, `projection_gap`, `integrity_failed`, `disk_budget_exceeded`, and `parked`.

## 7. State and transaction model

```text
disabled --authorized activation--> observing
observing --successful transaction--> observing
observing --invariant/budget failure--> parked
parked --reviewed operator reactivation--> observing
observing|parked --authorization expiry/rollback--> disabled
```

The live state machine is not changed. Shadow `observing/parked/disabled` is operational state only.
No state transition in this machine is allowed to modify a workflow's live status.

The expected-revision source for the first transition is zero. Thereafter it is the cursor allocated
and persisted with the prior legacy mutation under the coordinator lock. It survives restart and is
never sourced from the shadow database. A missing or ambiguous predecessor is a gap and parks; it is
not guessed, renumbered, or reconstructed by a live handler.

## 8. Writer and reader topology

| Component/principal | Allowed operations | Forbidden operations |
|---|---|---|
| coordinator live writer | existing legacy JSON mutations | read shadow for decisions; runtime DDL |
| coordinator shadow adapter | allowlist mapping; bounded transaction via least-privilege writer | live mutation; shadow reads as state authority; repair/backfill |
| migration principal | apply exact reviewed forward/disable migration | runtime use; live JSON access |
| delivery worker | read immutable outbox; mutate delivery-control rows only | modify event/snapshot/live state; project a competing lifecycle store |
| lifecycle projector | pure ordered-event projection and digest; read lifecycle sources only | write lifecycle or delivery state; call live handlers |
| validator/QA | compare independent legacy observation and shadow evidence | mutate either authority |
| dashboard/metrics adapter | read aggregate health projection | raw event/workflow access; free-form labels |
| API/executor/recovery | existing legacy reads | any Postgres shadow read |

Database permissions and import boundaries must make the forbidden edges testable, not merely
conventional.

## 9. Non-functional budgets

These are proposed freeze values requiring Q2 owner ratification; implementation may tighten but not
relax them without re-review.

| Budget | Proposed ceiling / policy |
|---|---|
| post-commit shadow deadline | 100 ms p99 local attempt; hard cancellation at 250 ms |
| live response overhead | p95 <= 10 ms when healthy; <= 250 ms absolute on a shadow timeout |
| database pool | maximum 2 shadow-writer connections, 1 delivery-worker connection and 1 read-only projector/validator connection |
| in-process pending work | maximum 64 receipts; overflow parks instead of blocking live work |
| event size | <= 2 KiB canonical bytes |
| adapter RSS increment | <= 64 MiB steady-state, <= 96 MiB peak in stress test |
| projector RSS increment | <= 128 MiB steady-state |
| database disk | <= 256 MiB during the bounded trial; park at 80%, disable at 95% |
| retention | 7 days or 100,000 events, whichever comes first; no runtime destructive purge |
| projection lag | warn above 5 s or 100 events; park above 60 s or 1,000 events |
| parity | 100% for accepted trial transitions; any unexplained mismatch parks |
| terminal conflicts/privacy canaries | zero tolerated |
| trial scale | max 10,000 workflows / 100,000 included transitions before owner evidence review |

Retention enforcement must use a separately reviewed archival/partition policy. The runtime writer is
not granted deletion to satisfy the disk budget.

## 10. Telemetry and dashboard delivery gate

The slice is incomplete unless all three ship together:

1. **Instrumentation:** counters/histograms/gauges for attempts, accepted transactions, typed failures,
   latency, lag, revision gaps, terminal conflicts, privacy failures, circuit state, disk budget and
   evidence freshness. Labels are closed and low cardinality.
2. **Phase-0 `aq-qa`:** at least one integration-path check proves legacy authority with shadow
   disabled/unavailable, one proves atomic CAS+outbox behavior, and one validates the aggregate health
   contract. A `/health`-only check is insufficient.
3. **Dashboard:** an existing system-state/program surface displays `DISABLED`, `OBSERVING`, `PARKED`,
   or `STALE`; parity, lag, failures, last evidence age, schema/config digest health and the statement
   `legacy JSON authoritative`. Blank fields are failures.

Alerting thresholds follow the budgets above. Error detail and identifiers remain in access-controlled
evidence, not Prometheus labels or the operator summary.

## 11. Threat and failure matrix

| Threat/failure | Required control | Acceptance evidence |
|---|---|---|
| shadow invoked before legacy durability | file `fsync`, rename and parent-directory `fsync` precede receipt | faults at each save boundary produce zero premature DB calls; crash-reopen retains acknowledged state |
| Postgres becomes accidental live dependency | one-way adapter; no live read imports/edges | DB absent/slow/corrupt and live responses remain equivalent within bound |
| duplicate/reordered revision under concurrency/restart | cursor allocation plus FIFO enqueue under coordinator lock; one in-flight delivery per workflow | concurrent transitions receive and deliver unique order; restart continues from durable cursor or exposes a gap |
| stale/concurrent shadow writer | explicit exact-replay/gap/stale/collision CAS branches | deterministic race accepts one; exact retry is idempotent; nonidentical contender parks |
| duplicate delivery | unique event/revision constraints and canonical event ID | exact replay adds zero rows and returns idempotent result |
| conflicting terminal | terminal constraint and transition guard | completed-vs-failed race commits at most one terminal |
| partial snapshot/outbox commit | single database transaction | crash/fault between statements leaves neither half |
| prompt/note/secret disclosure | empty-object allowlist mapper plus canary scan | forbidden values absent from DB, logs, metrics, errors and dashboard |
| event tampering/corruption | canonical digest and validation before projection | mutated row rejected; projector stops and reports integrity failure |
| replay reorders/gaps events | per-workflow revision order and checkpoint digest | shuffled/gapped fixtures never silently converge |
| delivery worker becomes lifecycle writer | separate delivery-control authority and DB grants; pure read-only projector | privilege tests reject snapshot/event/live mutations from worker/projector |
| raw/model-derived phase disclosure | reviewed fixed-ID to opaque-token allowlist; reject all other phase text | raw and model-derived phase canaries absent from DB/log/metric/dashboard bytes |
| database outage/restart | deadline, circuit breaker, no live retry storm | bounded calls, parked state, no live result change |
| queue/memory exhaustion | fixed queue/RSS/event ceilings | overload parks at cap; no unbounded tasks or payload growth |
| disk exhaustion | measured disk thresholds and least-privilege writer | warning/park/disable transitions; live path continues |
| runtime schema mutation | separate migration principal; no runtime DDL | privilege test rejects CREATE/ALTER/DROP/TRUNCATE |
| malicious/high-cardinality IDs | bounded schema; no IDs in metric labels | cardinality contract and adversarial IDs pass/fail predictably |
| operator mistakes shadow for authority | explicit UI/API authority label | every health view states `legacy JSON authoritative` |
| false recovery claim | Postgres excluded from recovery | restart test recovers exactly as before with shadow unavailable |

## 12. Validation plan and success metrics

### Contract/golden tests

- Valid start, nonterminal pass/skip/note, fail terminal, completed terminal, no-phase terminal, and
  fixed phase-ID to opaque-token vectors.
- Unknown fields/enums, overlong identifiers, negative/overflow revisions, forbidden content.
- Raw/model-derived phase IDs/names/descriptions rejected before database calls and absent even hashed.
- Canonical serialization/event ID stability across processes and key order.
- Exact replay, conflicting replay, stale revision, gap, post-terminal transition.

### Transaction/crash tests

- Fault before file flush, after file `fsync`, after rename/before directory `fsync`, after durable
  legacy commit/before DB, between CAS and outbox, before DB commit, after DB commit/before
  acknowledgement, coordinator/database restart, pool exhaustion and cancellation.
- Concurrent legacy transitions allocate unique monotonic revisions; restart resumes from the durable
  cursor. Per-workflow delivery cannot overtake. Exact-retry, restart-gap, stale and collision branches
  remain deterministic.
- Prove atomic shadow pair, deterministic replay, terminal uniqueness and live-path equivalence.

### Live and resource tests

- Run the three transition types against a temporary isolated Postgres schema and the running
  coordinator only after deployment authorization.
- Remove/deny Postgres and verify the same live API result and legacy recovery behavior.
- Measure p50/p95/p99 latency, RSS, connections, event bytes, database bytes and projection lag at the
  proposed trial limits.

### Exit metrics

- 100% of included successful legacy commits either have a matching accepted shadow transition or a
  typed, visible parked failure; zero silent drops.
- Zero unexplained parity mismatch, terminal conflict, privacy canary, partial transaction, or live
  response mutation.
- 100% deterministic projector reconstruction across crash/restart fixtures.
- All budgets, focused tests, Phase-0 checks, live smokes, dashboard fields, security checks and Tier-0
  gate pass under an exact independently reviewed candidate hash.

## 13. Rollback and restore drills

Rollback disables shadow activation, cancels bounded pending work, closes the shadow pool, stops the
delivery worker/projector, preserves evidence and restores the shadow-disabled runtime path. The
crash-durable legacy save primitive and monotonic cursor remain part of live JSON correctness; the live
JSON file is not restored from Postgres because it never ceased to be authoritative.

Required drills:

1. Disable before any event and prove no behavioral difference.
2. Disable with pending receipts and prove bounded cancellation/no corrupt transaction.
3. Disable after a CAS conflict/terminal conflict/privacy failure and preserve evidence.
4. Restart coordinator with Postgres absent and recover through the unchanged legacy path.
5. Re-enable only after explicit operator action bound to corrected hashes.

## 14. Delivery slices

- **B2-D0 (this package):** ADR, PRD and frozen design packet; no writes.
- **B2-C1:** schemas, canonical mapper/phase-token registry, receipt-order model, fixtures and pure
  contract tests; no database/network use.
- **B2-M1:** reviewed DDL/migration and privilege tests in an isolated test schema; runtime disabled.
- **B2-W1:** coordinator post-commit adapter, bounded circuit and transaction implementation; activation
  remains off.
- **B2-P1:** delivery-control worker, pure read-only lifecycle projector, replay/integrity evidence and
  aggregate health contract.
- **B2-O1:** Phase-0 checks, dashboard surface, resource/crash drill harness and rollback evidence.
- **B2-T1:** bounded shadow trial only after a fresh owner activation; evidence-review decision follows.

Every slice needs an exact inventory, predecessor hashes, independent review, validation evidence and
an atomic commit. No slice inherits authority merely because this PRD exists.

## 15. Gates and open decisions

Blocking before B2-C1 or any later implementation authorization:

- Q1 parent-architecture ratification or explicit replacement.
- Q2 owner ratification of the exact ADR hypothesis, named migration owner and resource envelope.
- Independent design review over the exact three-document subject.
- Resolution of any reviewer-requested revision and new subject hashes.

Blocking before runtime activation:

- exact schema/code/migration/config candidate and rollback hashes;
- independent security/SRE/concurrency/privacy acceptance;
- temporary Postgres test evidence and least-privilege grants;
- Phase-0/dashboard/service-coverage parity;
- a separately recorded owner activation with expiry and trial ceiling.

No current statement in this PRD asserts that Q1 or Q2 has been decided.
