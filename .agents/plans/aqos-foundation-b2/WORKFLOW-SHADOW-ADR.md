# ADR candidate: first workflow state shadow vertical

**Status:** PROPOSED / NOT RATIFIED / NO WRITES AUTHORIZED

**Decision owners:** Q1 and Q2 owner (`hyperd`)

**Target authority row:** `workflow-run-task` in `config/system-state-authorities.yaml`

**Prepared:** 2026-07-18

**Applies only to:** Foundation B2 design; it does not authorize implementation, DDL, traffic cutover, or a new lifecycle store

## 1. Decision requested

Ratify one deliberately narrow state-spine experiment:

1. The hybrid coordinator and its `workflow-sessions.json` durable commit remain the sole live
   authority for this vertical. The current temporary-file replacement is atomic for visibility but
   is not yet a crash-durability guarantee; the vertical requires file and parent-directory `fsync`
   before a live commit receipt may exist.
2. Only three coordinator-managed transition classes participate:
   `run.start`, manual phase transition, and terminal completion (`completed` or `failed`).
3. Only after the legacy JSON commit succeeds, the coordinator may attempt a bounded,
   privacy-minimized Postgres transaction. That transaction applies an expected-revision compare and
   swap (CAS) to a shadow snapshot and appends the corresponding transactional-outbox record.
4. Postgres is never read to decide execution, recovery, HTTP/API responses, phase position, or live
   success. It is read only by isolated shadow validators and outbox projectors.
5. Any timeout, unavailable database, CAS conflict, duplicate-nonidentical event, integrity failure,
   or parity mismatch parks and disables the shadow path. It never changes, delays beyond the frozen
   bound, rolls back, or relabels the already-committed live result.

This is the exact Q2 hypothesis to accept or reject. It is not a decision that this document can make.
Q1 parent-architecture ratification and Q2 ratification of this exact hypothesis are both required
before any schema, migration, connection, runtime hook, or shadow write is introduced.

## 2. Context and evidence

The `workflow-run-task` inventory row is owner-adjudicated but still truthfully reports
`SPLIT_BRAIN`. The coordinator handlers replace `workflow-sessions.json` under a process-local lock,
while the standalone executor and `sync-workflow-sessions.py` can also write the same file. Replacement
currently prevents readers from seeing a partially written file, but without flushing the temporary
file before rename and the containing directory after rename it does not prove persistence across a
power loss or kernel crash. The existing `workflow_checkpointer.py` creates and upserts a different
Postgres checkpoint shape and catches database failures; it is not wired as live recovery authority and
is not a basis for claiming Postgres authority.

The unified program places one shadow workflow vertical in Foundation B2 and requires an exact
per-authority hypothesis before writes. The synthesis and reference architecture require legacy
authority, CAS, outbox/replay, crash evidence, terminal uniqueness, resource budgets, integrity,
restore, and rollback. This ADR narrows those requirements to a testable first vertical without
silently adopting a repository-wide relational spine.

## 3. Authority and topology

### 3.1 Live topology (unchanged)

```text
HTTP command
  -> hybrid coordinator validates transition
  -> coordinator process lock
  -> allocate next receipt revision inside the locked legacy state
  -> write temporary file + fsync(file)
  -> atomic rename + fsync(parent directory)         DURABLE LIVE COMMIT / RESPONSE TRUTH
  -> enqueue receipt on bounded per-workflow FIFO while lock is still held
  -> release lock
  -> one-in-flight-per-workflow shadow delivery
```

All live readers continue to rebuild their view from `workflow-sessions.json`. The existing API,
executor, recovery behavior, and operator actions must not consult a shadow table.

### 3.2 Shadow topology (candidate)

```text
successful durable live commit receipt
  -> privacy-minimizing event builder
  -> Postgres transaction
       1. expected-revision CAS shadow snapshot
       2. append unique outbox event
       3. commit together
  -> delivery worker leases immutable outbox rows and owns delivery metadata
  -> pure lifecycle projector reads events without mutating lifecycle sources
  -> parity, lag, integrity and parked-state telemetry only
```

The shadow writer is a coordinator-owned adapter, not a lifecycle authority. The delivery worker is
the sole writer of mutable delivery metadata (lease/attempt/disposition) and cannot modify event bytes,
shadow snapshots, or live workflow state. The deterministic lifecycle projector and validator are
read-only with respect to all lifecycle sources; they compute an in-memory view and immutable evidence
digest. Dashboard and `aq-qa` consume bounded aggregate health, never raw objectives, notes, prompts,
outputs, phase identifiers, or outbox payloads.

## 4. Exact transition boundary

| Included transition | Live source | Shadow kind | Expected behavior |
|---|---|---|---|
| create coordinator workflow run | `handle_workflow_run_start` after durable JSON commit | `run.start` | allocate/persist revision 1 with `expected_revision=0`, then shadow it |
| manual `pass`, `skip`, `fail`, or state-bearing `note` | `handle_workflow_session_advance` after durable JSON commit | `run.phase_transition` | allocate/persist exactly the next legacy receipt revision under the coordinator lock |
| transition to `completed` or `failed`, including the no-phase terminal branch | same handler after durable JSON commit | `run.terminal` | one terminal revision; identical replay idempotent, conflicting terminal rejected and parked |

The phase action remains part of the privacy-safe enum. Free-form `note` text is excluded. Raw phase
IDs and model-derived/free-form phase text are also excluded. A phase is represented only by a stable
opaque `phase_token` obtained from a reviewed allowlist that maps fixed coordinator/blueprint phase
identifiers to domain-separated digests. A value absent from that allowlist is rejected and parks the
shadow attempt; it is never persisted even as a digest. A manual transition that produces terminal
state emits only `run.terminal`, with the action and allowlisted opaque token included, so one live
commit cannot create two shadow revisions.

Excluded writers and transitions remain evidence, not participants: standalone executor mutations,
`sync-workflow-sessions.py`, forks, consensus/arbiter changes, mode/isolation changes, generic event
ingest, graph-run JSON, workspace teardown, automatic executor phase updates, and all
`workflow_checkpointer.py` checkpoint/backtrack/DLQ behavior.

## 5. Conceptual contract

The later implementation must freeze closed, versioned schemas before code. The minimum event
contract is conceptually:

| Field | Constraint |
|---|---|
| `schema_version` | exact supported version; unknown versions fail closed |
| `event_id` | deterministic digest over vertical ID, workflow ID, revision, transition kind and live-commit digest |
| `workflow_id` | existing opaque session identifier; never objective-derived |
| `expected_revision` / `revision` | monotonic integers allocated and persisted with the legacy mutation under its lock; `revision = expected_revision + 1` |
| `transition_kind` | closed enum: `run.start`, `run.phase_transition`, `run.terminal` |
| `status` | closed enum used by this vertical only |
| `phase_token` / `phase_index` | stable opaque allowlisted token/digest and bounded integer; raw or model-derived phase text is prohibited |
| `action` | closed manual-action enum or null; no note content |
| `live_commit_digest` | digest of canonical, allowlisted live state—not a copy of the live state |
| `occurred_at` | timestamp taken from the committed live record, not database wall-clock ordering |
| `writer` | fixed coordinator adapter identity and code/schema version |

The shadow snapshot stores the allowlisted state plus revision, terminal flag, last event ID, and live
commit digest. The immutable outbox event stores only the event envelope and transaction timestamp.
A separate delivery-control record owns mutable lease epoch, attempt count, next attempt, delivery
disposition, typed error and timestamps. Unique constraints cover `(workflow_id, revision)` and
`event_id`; database permissions and triggers/constraints prevent the delivery worker from changing
the snapshot or immutable event payload.

Prohibited payload fields include objective/query/prompt, phase notes, outputs, tool inputs/results,
agent messages, secrets, paths, environment, isolation details, lesson references, and arbitrary
extension dictionaries. Raw phase IDs, model-generated phase names/descriptions and their hashes are
also prohibited; only a pre-reviewed phase-token mapping output is accepted. Unknown fields are
rejected before a database call.

### 5.1 Receipt ordering and CAS branches

Under the same coordinator lock that mutates legacy state, the live writer reads the session's durable
receipt cursor (zero when absent), allocates `revision = cursor + 1`, embeds the new cursor and the
privacy-safe receipt identity in the JSON mutation, and completes file/parent-directory `fsync`. The
receipt derived from those committed bytes is then appended to a bounded per-workflow FIFO before the
lock is released. One worker permits only one in-flight shadow transaction per workflow. This preserves
the durable commit order even when different workflows run concurrently and prevents two coordinator
transitions from allocating or delivering the same revision. Queue overflow parks the shadow path
instead of blocking or reordering live work.

The Postgres transaction locks or conditionally updates the workflow row and takes exactly one branch:

1. no row plus `(expected_revision=0, revision=1)` -> insert snapshot and immutable event;
2. stored revision equals expected revision -> advance snapshot and insert immutable event atomically;
3. stored revision and event ID/digest equal the receipt revision and identity -> exact replay,
   idempotent success with no new event or delivery-control row;
4. stored revision is lower than `expected_revision` -> detectable gap, rollback and park;
5. stored revision is higher than expected, or equal to receipt revision with different identity ->
   stale/conflicting receipt, rollback and park;
6. stored state is terminal and the receipt is not its exact replay -> terminal conflict, rollback and
   park.

If the process crashes after durable legacy commit but before shadow acknowledgement, restart recovers
the monotonic receipt cursor and latest privacy-safe receipt identity from legacy JSON, never from
Postgres as live authority. An exactly retained latest receipt may be retried. The in-memory FIFO is not
claimed durable: if an unavailable intermediate receipt was lost, the next attempted receipt produces
a deterministic revision gap and parks. It is evidence, never a license to infer, renumber, or
synthesize history.

## 6. Required invariants

1. **Legacy-first:** no shadow attempt exists until temporary-file data and the parent-directory rename
   have both been `fsync`ed and a successful durable legacy receipt exists.
2. **No reverse dependency:** live execution and responses have no import-time or runtime dependency
   on Postgres availability or shadow reads.
3. **Atomic shadow pair:** shadow snapshot CAS and outbox append commit or abort together.
4. **Revision monotonicity:** receipt order is allocated/persisted with the locked legacy mutation and
   survives restart; enqueue occurs under that lock and one-in-flight-per-workflow FIFO delivery
   preserves order; only `expected_revision == stored_revision` advances shadow state.
5. **Terminal uniqueness:** a workflow has at most one distinct terminal event; exact replay is
   idempotent, any conflicting replay parks the vertical.
6. **No fabricated repair:** a detected legacy/shadow gap is evidence. Runtime does not synthesize or
   backfill a missing historical transition.
7. **Privacy allowlist:** serialization begins from an empty object and copies only schema fields;
   phases use reviewed opaque tokens, never raw or model-derived phase text.
8. **Bounded impact:** the shadow path has fixed time, queue, connection, memory, and disk budgets and
   cannot exert backpressure on the live path beyond its per-attempt deadline.
9. **Fail-closed shadow / fail-open live:** contract or integrity failures disable shadow writes, but
   preserve the already-valid legacy outcome.
10. **No authority promotion by uptime:** parity evidence can recommend expansion or replacement; it
    cannot make Postgres authoritative without a later owner decision and cutover authorization.

## 7. Migration and database authority

Q2 ratification must name a Foundation B2 migration owner. That owner controls reviewed migration
artifacts and rollback; the coordinator runtime principal must not have `CREATE`, `ALTER`, `DROP`,
`TRUNCATE`, or broad schema privileges. A separate deployment/migration principal applies exact DDL.
The runtime shadow writer receives only the minimum insert/update rights. The delivery worker has a
distinct principal limited to delivery-control rows and immutable-event reads. The lifecycle
projector/validator uses a distinct read-only principal and cannot update delivery metadata.

Existing `workflow_checkpoints`, execution-pattern, backtrack, and Redis DLQ objects are untouched and
must not be renamed, reused, read, or presented as B2 evidence. The later design must use separately
named shadow objects so that experimental evidence cannot be mistaken for recovery state.

## 8. Rollback and disablement

The default state is disabled. The enabled state requires schema health, credentials, a passing
privacy canary, and an unexpired activation record. Any invariant failure atomically opens a local
circuit breaker for further shadow attempts and emits a low-cardinality reason. In-flight Postgres
transactions roll back; no compensating write is made to the legacy file.

Rollback consists of disabling the adapter and delivery worker, stopping projector observation,
retaining immutable validation evidence, revoking runtime database grants if required, and continuing
the coordinator JSON path with its required crash-durable save primitive.
Table deletion, data repair, and legacy writer retirement are explicitly not rollback steps for this
vertical.

## 9. Decision consequences

### If ratified

- B2 may prepare a hash-bound implementation candidate for only this vertical.
- The experiment can measure relational CAS/outbox behavior without risking live authority.
- The split-brain row remains `SPLIT_BRAIN` until physical writer convergence is separately proven.
- Results decide whether to expand, replace, or abandon this state-spine hypothesis.

### If rejected

- No shadow writes occur.
- A replacement per-authority hypothesis must receive its own ADR and Q2 ratification.
- Foundation B2 remains blocked; Foundation B1/B3 work that does not assume state authority may proceed
  under its own gates.

## 10. Ratification gate

No implementation authorization may be prepared as active until the owner explicitly records both:

- **Q1:** ratification (or an explicit replacement) of the parent architecture; and
- **Q2:** ratification of this exact legacy-live/Postgres-shadow workflow hypothesis, including a named
  migration owner and the frozen resource envelope.

Silence, prior broad preauthorization, owner adjudication of the Foundation A target, or a reviewer
`PASS` on these documents does not satisfy either gate.
