# Antigravity Autonomous Bridge A0 — Claim-Bound Inbox Supervisor

Status: **OWNER-DIRECTED IMPLEMENTATION SLICE**
Date: 2026-07-29
Parent: `.agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md`
Slice claim: `antigravity-autonomous-bridge-a0`

## Objective

Remove the manual-poke dependency from the existing Antigravity IDE inbox lane without
claiming that the future universal `aq-dispatchd` broker already exists. A0 makes one
inbox dispatch attempt a deterministic, receipt-backed state transition suitable for a
host-owned timer in A1.

## Root cause

The current wake prompt tells Antigravity to read and complete a task but never tells it
to atomically claim the task. `wake` records only a nudge, `complete` accepts missing
claims and missing output, and status cannot distinguish pending, claimed, parked, or
completed work. Therefore a successful CLI return is not attributable processing, a
failed or ignored nudge has no bounded retry/parking transition, and the operator must
manually notice and retrigger the lane.

## Exact implementation ceiling

1. `scripts/ai/aq-antigravity-inbox`
2. `scripts/testing/test-antigravity-claim-receipt.py`
3. `scripts/testing/test-antigravity-inbox.py`
4. `.agents/plans/antigravity-autonomous-bridge/A0-DESIGN-PACKET.md`

No dashboard, Phase-0, Nix, provider routing, registry, deployment, staging, or commit
changes are permitted in A0.

## Required behavior

### Agent protocol

Each drop must contain exactly one bounded output declaration in the existing
human-readable form:

```text
Respond by writing only:
`<repo-relative-output-path>`
```

The helper parses and validates that declaration before admission. Absolute paths,
traversal, symlinks, multiple declarations, and missing declarations fail closed.

The fixed wake prompt requires this exact lifecycle:

1. request metadata-only next-task selection (never task content);
2. atomically `claim <basename> --actor ide-watch --json`;
3. read task content only from the claimed marker, perform only the advisory task, and
   write only the claim receipt's declared output;
4. `complete .claimed-<task-id> --output <declared-output> --json`.

Task content is never interpolated into subprocess argv.

### Completion integrity

Normal completion fails closed unless:

- the latest claim receipt is bound to the current drop generation/content hash;
- the claimed marker is the consumed source and its bytes still match the claim hash;
- no terminal or recovery record already exists for the generation;
- `--output` exactly matches the claim-bound declared output;
- the declared output exists, is a non-symlink regular repo-contained file, and can be
  hashed.

Explicit owner recovery may bypass a check only with a named recovery flag, constrained
`--recovery-actor owner-manual`, and a non-empty reason of at most 240 characters.
Every bypass is recorded as recovery evidence and cannot count as independent review
proof. Prepared `source_name` is an exact basename derived from task ID and recovery
mode; prepared archive paths resolve to the exact dated archive directory and
generation-derived basename. Authority and containment validation precede every
filesystem read, link, or unlink.

### Single-shot supervision

Add `dispatch-once`, designed for a host timer:

- select the oldest eligible non-parked pending task;
- if it is already claimed, report `claimed` without another wake;
- issue a fixed-argv wake attempt when eligible;
- suppress retry during a bounded retry interval;
- after the configured attempt ceiling, append one idempotent `parked` record and return
  a typed parked result;
- never convert wake success into claim or completion;
- never execute task content or claim on behalf of the IDE.

The eligibility decision and wake reservation are serialized under one stable
supervisor lock. The lock is released before invoking `antigravity chat`, because the
prompted IDE must acquire the same lock to claim. After the subprocess returns, the
supervisor reacquires the lock and finalizes the reserved wake only if the generation
and reservation still match. Concurrent dispatchers may observe the reservation but
must not issue a duplicate wake. Only current-generation, non-passive supervisor wake
reservations/attempts count.
The public `wake` command cannot impersonate the internal supervisor actor or consume
its attempt budget.
Parked tasks cannot be returned by `next` or claimed without an explicit future resume
transition, and cannot starve later eligible tasks. Machine mode emits exactly one JSON
document. Positive bounded retry, timeout, and attempt arguments are mandatory.

The later A1 timer repeatedly calls this command; A0 contains no resident loop.

### Receipt concurrency and projection

Receipt updates serialize on stable no-follow lock inodes, reject corrupt evidence, and
use durable non-clobbering atomic replacement. Inbox members, claimed markers, receipt
files, locks, and temporary files must be non-symlink regular files. Records bind to a
current generation/content hash so a reused basename cannot inherit claim, attempt,
parked, recovery, or terminal state.
Archive identity includes the generation, not only task ID and day, so a new drop may
reuse a basename without colliding with prior evidence.

Completion first persists a prepared terminal record, then performs a non-clobbering
archive move, then persists final terminal evidence. A crash must remain reconcilable
without fabricating completion or overwriting prior archive evidence.
Reconciliation explicitly handles both hard-link crash windows: source+archive present
and archive-only. It verifies generation/content hashes, removes only the verified
duplicate source when both exist, and idempotently finalizes the terminal receipt.
It selects a prepared record only for the current marker generation; when the marker is
absent it validates the prepared timestamp's UTC archive date rather than recomputing
the current date. A clean prepared record must link to a matching attributable claim.
A recovery prepared record must contain and honor constrained owner recovery evidence,
including unclaimed-source and missing-output bypasses.

Status reports bounded counts for pending, claimed, parked, and
claim-required tasks plus the next eligible task. Prompt, output, argv payload values,
paths beyond existing bounded repo-relative evidence, and task IDs never become metric
labels.

## Acceptance tests

Hermetic tests must prove:

- the wake prompt requires claim before work and output-bound completion;
- wake uses a fixed argv and attempts even when no prior IDE process is observed;
- concurrent receipt appends do not lose records;
- concurrent `dispatch-once` calls produce at most one wake/park transition;
- a provider-triggered claim completes while the wake subprocess is still active
  (no supervisor-lock deadlock);
- completion without a claim fails closed;
- completion without output fails closed;
- claimed-marker tamper, stale-generation receipt, output substitution, receipt
  corruption, symlink preplanting, duplicate archive, and completion crash windows fail
  closed;
- prepared completion reconciles both marker+archive and archive-only crash windows;
- task-ID reuse, owner-recovery crash windows, and a completion crash spanning UTC
  midnight reconcile without inheriting or overwriting prior-generation evidence;
- explicit recovery is visible and cannot look clean;
- `dispatch-once` suppresses premature retries;
- the attempt ceiling parks exactly once;
- a claim stops further wake attempts;
- parked work cannot starve or be returned/claimed;
- machine mode emits one parseable JSON document and truthful wake outcome;
- invalid bounds and malformed timestamps fail closed;
- status distinguishes pending, claimed, and parked work;
- the pre-existing inbox regression is aligned to claim/output-bound completion and all
  claim-CAS, traversal, hash-tamper, and liveness tests remain valid.

## A1 adoption gate

A0 does not make the lane continuously autonomous by itself. A1 must declaratively add
the user-service/timer (or the accepted host broker adapter), Phase-0 integration-path
check, Agent Ops TUI/web indicator, and live harmless canary in one Service Coverage
slice. A1 must not edit the currently dirty shared monitoring surfaces until their
active candidates are resolved or an exact non-overlap amendment is independently
accepted.

## Stop conditions

Stop on any fifth file, task-content shell interpolation, synthetic claim, unbounded
retry, caller-owned background loop, completion without attributable evidence, shared
dashboard/Phase-0 edit, live provider-route cutover, staging, commit, or deployment.
