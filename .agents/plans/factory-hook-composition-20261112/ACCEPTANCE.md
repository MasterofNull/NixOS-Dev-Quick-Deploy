# Factory hook composition: design acceptance and implementation boundary

## Frozen design provenance

The supplied delegation records independent design acceptance by reviewer lane **local**,
author lane **codex**, run **local-20261113-023101-3i2ut5**: all three prior blockers
RESOLVED, no further revisions. `DESIGN.md` is a byte-exact copy of the recovered design,
SHA256 `4b9d4b3ac52745c826dcb57c81b878de2fb067139206cc9b45292544c122b5ac`.
Its original draft heading is preserved. This records the supplied review provenance;
it does not mint a machine review receipt or accept the implementation.

## Delivered boundary

This is the coherent **refusal-only admission** first sub-slice permitted by the task.
It resumes code from `190ee9757284163190458626e8ac550affba4611` using its patch.
It adds explicit `retrofit --compose-pre-commit` inspection, a bounded no-follow
diagnostic inventory, and early quarantine of composition metadata. All composition
receipts refuse, including structurally valid records, because the runtime verifier
and offline boundary are unavailable. No confirmation hash is issued; the inventory
digest is diagnostic only. Ordinary init, retrofit, update, rollback and doctor cannot
use composition metadata or ordinary gate evidence to bypass that quarantine.

The reserved closed receipt schema describes future structural fields only. It is
not a runtime authorization mechanism. Canonical encoding, digest verification,
repository identity, filesystem ownership, immutable closure validation, and semantic
approval still require the deferred verifier. The tracker contains editorial goals
and dependencies without hand-authored status, activation or acceptance assertions.

## Frozen section 9 matrix

“Admission only” means the operation refuses without mutation; it does not satisfy
the active-protocol result required by the frozen design.

| Frozen case | Evidence in this sub-slice | Remaining acceptance |
|---|---|---|
| Valid owned receipt + matching inputs | All receipts quarantined | Receipt-aware active doctor and actual composed traversal |
| YAML without valid receipt | Both YAML suffixes refuse through library entry points | None for refusal behavior |
| Gitfile, commondir, linked worktree | Gitfile and symlink inventory cannot traverse; commondir diagnostics cannot authorize; snapshots preserved | Full ordinary eligibility classification with real linked-worktree fixtures |
| Cache absent/altered | Admission only; no manager executes | Immutable manifests, preflight and per-stage digest verification |
| Opaque/duplicate semantics | Admission only; native bytes preserved | Independent catalog and duplicate-ID rejection |
| Preview input changed | Diagnostic digest changes; confirmation remains absent | Locked re-inventory and exact confirmation mismatch |
| Native/manager/factory failures | Poison executables never run during admission | Ordered stages and first-failure exit propagation |
| Lock contention | Concurrent confirmation and rollback both refuse unchanged | Exclusive lock with one authorized owner |
| Kill after each journal phase | No journal or mutation exists | SIGKILL recovery at every durable phase |
| Crash after native replacement | Native never replaced | Verified restore or retained blocking journal |
| Direct gate runner evidence | Forged ordinary proof cannot grant readiness | Active doctor rejects direct-run traversal evidence |
| Actual supported commit | Deferred | Exact prepared/committed transition and consumed OID |
| Commit-msg abort then same-tree bypass | Deferred | Old attempt cannot complete on a later commit |
| Expiry/PID reuse/reboot/foreign process/replay | Deferred | Real-process binding and read-only consumed replay |
| Reservation/consumption fsync crashes | Deferred | No reusable or uncertain completion |
| Invocation profile/catalog tamper | Admission only | Approved argv/cwd/env/$0 profile and catalog validation |
| Network/Unix/FD probes in every stage and child | Deferred; no sandbox claim | Reachable unsandboxed controls and denied sandbox probes |
| Unsupported sandbox/unsafe manifest | Unsupported boundary refuses universally; unsafe files cannot authorize | Writable manifests, escaped closures and namespace failure fixtures |
| Rollback drift | Receipt-bearing rollback refuses unchanged | Authorized rollback verifies every bound artifact before restoring |

## Fault injection and limits

Focused fixtures inject EACCES/EIO during metadata inspection and EIO at descriptor
open, fstat and read boundaries. They check descriptor closure, concurrent read drift,
oversize inputs, corrupt/forged receipts, symlinks, FIFOs, directories, poisoned command
execution, and concurrent confirmation/rollback refusal. Target snapshots cover
contents, types, modes, mtime, ctime and Git configuration. Atime is excluded because
ordinary observational reads may update it.

Mutation-primitives tests assert fsync/rename/write are **not invoked**. They do not
claim recovery coverage for fsync/rename failures. SIGKILL, cache corruption, network
positive controls, and commits failing after pre-commit remain deferred until their
corresponding live protocol exists. These tests do not establish full MVP readiness.
Fixtures are retained under `.agents/delegation/outputs/`, never `/tmp`.

Validation passed: Python compilation of both implementation files and the focused
test file; all 16 focused tests; ordinary gate-install and gate-retrofit regression
fixtures (every reported result true); `git diff --check`; and tracker schema plus
projection validation. No Bash files changed. The live `aq-pm-tracker` resolved a
relative plan argument against the main checkout and reported a missing tracker;
using this worktree's absolute plan path passed without changing tracker contents.

```text
Ran 16 tests in 2.247s
OK
PASS test-factory-gate-install.py
PASS test-factory-gate-retrofit.py
PASS: factory-hook-composition-20261112/tracker.json valid + projects
```

Tier0, independent implementation review, commit, landing and runtime activation
are the orchestrator's responsibilities and have not been performed by this delegate.

## Exact next slices

1. Immutable approved prewarm input lock, closure/cache manifests and publication.
2. Fail-closed offline sandbox for every stage and descendant; independent semantic
   catalog and invocation compatibility approval; exactly-once stage composition.
3. Locked canonical preview/confirmation, durable install journal, verified recovery
   and drift-safe rollback; fsync/rename and SIGKILL fault matrix.
4. Receipt verifier, real Git reference-transaction observer, durable one-use attempts,
   receipt-aware doctor and all abort/replay/process-binding fixtures.
5. Full frozen acceptance matrix using real dependencies, independent implementation
   audit, activation evidence and PM projection. No active composition is shipped here.
