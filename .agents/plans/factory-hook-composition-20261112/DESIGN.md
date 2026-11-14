# Factory hook composition — bounded revision

**Status:** DRAFT — requires independent design acceptance; **not PLAN_READY**.
**Authority:** Narrow extension proposal to frozen
`software-dev-factory-rollout/DESIGN.md` §4.2.  That plan's default foreign-manager
refusal remains the shipped behavior until an implementing code PR and its acceptance
evidence land together.  This document authorizes neither installation nor a docs-only
PR.

## 1. Decision and scope

The smallest safe MVP is a receipt-owned composition for one ordinary worktree only:
an on-disk `.git` directory, local `.githooks/pre-commit`, and a prewarmed,
content-addressed `pre-commit` manager cache.  It preserves the native hook bytes and
first-failure behavior.  It does **not** make arbitrary hook managers composable.

This is minimal-code rung 2: extend the existing factory gate installer/status model;
reuse Git, Python stdlib durability primitives, and the already-installed manager.
No dependency, daemon, or generic hook router is introduced. Completion requires one
additional receipt-owned `reference-transaction` hook (§8); any existing foreign hook
at that path refuses composition. This is an explicit scope extension requiring review,
not an assertion that pre-commit alone can prove a commit completed.

Out of scope: Husky, lefthook, arbitrary `core.hooksPath`, selective suppression of
opaque native commands, automatic repair, network during commit, and linked worktrees.
The existing `retrofit_metadata_conflict()` refusal for a `.git` file or `commondir`
continues unchanged.  A future linked-worktree design must separately prove common-dir
ownership, sibling discovery, idempotence, conflict handling, rollback, and tests;
this MVP deliberately does not discover or mutate siblings.

## 2. Entry points and unchanged defaults

`init`, ordinary `retrofit`, and ordinary `doctor/readiness` retain §4.2's YAML/foreign
manager conflict and exit behavior.  A proposed explicit flow is:

1. `prewarm` materializes a pinned manager environment/cache, without touching hooks.
2. `retrofit --compose-pre-commit --dry-run --json` inventories and emits a canonical
   preview hash.
3. The user confirms that exact hash; the mutating command locks, re-inventories, and
   refuses on any difference before its first target mutation.
4. `doctor/readiness` recognizes composition **only** after it verifies an owned,
   committed receipt and every bound digest.  An unreceipted YAML remains a conflict.

There is no implicit upgrade path.  A bad, stale, or ambiguous receipt is a blocking
`COMPOSITION_RECEIPT_INVALID` state, not a best-effort repair or fallback.

## 3. Eligibility and read-only doctor

Before preview or apply, require all of the following:

| Item | Required proof | Otherwise |
|---|---|---|
| Git topology | physical non-symlink `.git` directory; resolved common dir is that directory | existing linked/redirected-metadata refusal |
| Hook targets | regular executable `.githooks/pre-commit`, no symlink; `core.hooksPath=.githooks`; reference hook absent or already receipt-owned | refusal |
| Manager | normal `.pre-commit-config.yaml`, pinned executable and verified immutable cache | refusal/prewarm required |
| Ownership | receipt, wrapper, native backup, and semantic inventory all hash-valid | conflict; no mutation |
| Semantics | no duplicate classified check is owned by two stages | refusal |

The read-only doctor must first look for the composition receipt.  A valid receipt
changes its answer from the generic YAML conflict to `COMPOSITION_ACTIVE`; it then
validates the receipt's wrapper, native, YAML, manager-cache, factory-bundle, and
semantic-inventory digests.  It performs no manager command, lock acquisition, status
refresh, config write, index refresh, mtime update, or evidence creation.  Thus it
validates factory-owned composition rather than treating YAML alone as a conflict.

The receipt is a schema-versioned, canonical JSON record containing repository identity,
`core.hooksPath`, wrapper/native/backup and reference-observer modes and digests, YAML digest, manager binary
and resolved-config digests, cache manifest digest, factory bundle/config digest,
semantic inventory and approved classification/approval-record digests, prewarm input-lock
digest, sandbox-policy digest, preview hash, and durable-journal generation. Mutable
metadata paths are repository-relative and opened without following symlinks. The only
external paths are digest-bound cache generations and enumerated immutable runtime
closures under preflight-approved roots; arbitrary absolute paths refuse.

## 4. Immutable offline manager cache

`prewarm` is a separately invoked, explicitly network-permitted operation. Its input
lock is canonical JSON schema `prewarm-inputs/v1`: manager executable/store-closure
hashes and version; Git and sandbox executable/closure hashes; platform/architecture;
YAML bytes and fully resolved hook IDs, immutable upstream object IDs, additional
package versions and artifact SHA256s; interpreter/toolchain closure hashes; classifier
catalog digest; builder version; fixed locale/timezone/PATH; and the explicit build-env
allowlist. Floating refs, unverified downloads, unpinned transitive packages, ambient
HOME/user configuration, and unsupported non-hermetic builders refuse. Credentials
may fetch artifacts but are never input/output manifest content. Identical locked
inputs select the same generation key; reproducibility means an identical verified
manifest on rebuild, not merely reusing a directory named after the inputs. A divergent
rebuild is quarantined, never published under that key.

The output `cache-manifest/v1` enumerates EVERY directory, regular file, and permitted
symlink in the generation and its external runtime closure: normalized relative path,
type, mode, uid/gid ownership policy, size and SHA256 for files, literal target for
symlinks, and referenced immutable store-closure digest. Sorted canonical manifest plus
input-lock digest defines the full output digest. Reject unlisted entries, devices,
FIFOs, sockets, setuid/setgid files, hardlinks escaping the generation, traversal, and
symlinks except those resolving wholly within the generation or enumerated immutable
store closure. No writable/shared parent, foreign owner, group/other writable ancestor,
or caller-selected absolute cache path is eligible. Factory metadata is owner-only;
content generations are owner-controlled and mounted read-only during every stage.
Publish via temporary sibling, full verification, file/directory fsync and atomic rename;
never mutate a published generation. Prewarm failure leaves hooks untouched.

Offline is enforced, not an environment convention. The already-installed `bwrap`
executable and its digest are preflight inputs; inability to create an unprivileged
network/mount namespace is `OFFLINE_BOUNDARY_UNAVAILABLE`, with no privileged fallback.
Each native, manager and factory stage, including its descendants, runs separately in a
new network namespace with no host networking or usable loopback, read-only cache and
runtime closures, isolated HOME/tmp, and only catalog-listed repository/index/evidence
write paths. No host /run, user runtime dir, resolver/proxy sockets, host /proc, inherited
network/socket descriptors or namespace handles are exposed. Close all descriptors
except explicit stdio pipes; scrub proxy/agent variables and drop namespace escape
privileges. Expose repository mounts through an enumerated regular-file/directory view:
never bind the whole host root or a directory containing a host socket. Reject sockets,
unlisted nested mounts and escaping symlinks anywhere in an exposed host subtree at
preflight; mounts absent from the policy are invisible. A host-backed writable directory
qualifies only under the trusted-owner/no-concurrent-tampering assumption stated below;
if this cannot be established, refuse rather than promise socket isolation. The
implementing acceptance must demonstrate a socket planted in every exposed subtree is
rejected before stage execution. The sandbox uses its own restricted
proc mount and drops capabilities. Host-accessible Unix sockets are not an alternate
transport. A catalog that needs such access is ineligible. The control-only reference
hook (§8) performs no checks and no network operations; it cannot run a stage outside
this boundary. Network is permitted only in the explicitly separate prewarm process.

Before EVERY stage the outer wrapper verifies receipt, complete tree and closure
manifest, ownership and sandbox policy; inside the namespace it verifies the same
read-only mounted inputs before exec. The manager uses the fixed cache with a read-only
mount: lazy installation cannot succeed. Missing/changed inputs fail before any stage,
never trigger a download. A stage that attempts installation or needs unlisted writes
fails with its real exit status. Concurrent tampering is outside the trusted-owner
threat model, but writable source drift must invalidate preflight; implementation must
prove mount/verification ordering before acceptance.

The implementing PR must demonstrate DNS and TCP denial in EACH of the three stages,
including child processes: a controlled host DNS responder and TCP listener see zero
traffic while namespace probes attempt explicit DNS UDP/TCP to that responder, libc
name resolution, and TCP to both host and public-address fixtures. Test fixtures verify
the responders/listeners are reachable from an unsandboxed positive control, with short
timeouts; a failed internet service is not proof of denial. Also probe a host Unix-socket
proxy, inherited socket FD, and namespace-creation failure. No test depends on public
internet availability. These probes are acceptance tests, not recurring network work in
every normal commit.

## 5. Exactly-once semantics

The wrapper's fixed order is a cache/integrity preflight, then native, manager, factory.
Every stage preserves its normal first non-zero exit code; no later stage runs.  The
native script's original bytes and executable mode are stored verbatim and restored by
rollback.  It is executed whole: the factory never edits it or selectively skips a
command.

| Precedence | Owner | Unit executed once | Duplicate policy |
|---|---|---|---|
| 1 | native | complete preserved native script | opaque native has no safe selective dedup |
| 2 | manager | each resolved manager hook identity | conflict with native/factory classification refuses |
| 3 | factory | each known factory gate semantic ID | conflict with either earlier owner refuses |

The classification authority is a repository-maintained `hook-classifications/v1`
canonical JSON catalog, changed only in a code PR approved by an independent reviewer
and the repository owner/authorized maintainer. The approval record names exact catalog
SHA256, reviewers and code subject; the factory release pins that approved digest.
Operator confirmation approves installation only; it cannot add semantic claims or
approve its own catalog. No runtime inference, skip list or self-declared classification.
An unapproved catalog/version, stale approval, unknown field/schema, unclassified byte
change or duplicate semantic ID is `UNSUPPORTED_SEMANTIC_OWNERSHIP` and refuses.

Each entry binds stage/hook ID; script and transitive helper/interpreter digests; modes;
resolved manager entry, args and dependency closure; complete semantic IDs; allowed
reads/writes; offline compatibility; and an invocation profile with executable path,
argv vector, cwd, stdin policy and named environment values/sources. Receipt and preview
bind catalog schema/version/digest, approval-record digest, exact matched entries and
semantic inventory. Mutable helpers/config are included in preflight hashing, not
silently trusted through an unchanged top-level script. Catalog replacement requires a
new approved release and fresh preview/confirmation, never in-place reinterpretation.

Invocation profile `native-relocated/v1` is deliberately narrow: exec the preserved
backup by absolute path with its original shebang/interpreter and executable mode,
no additional argv, stdin as inherited from Git, cwd the canonical repository root.
Its `$0` is consequently the BACKUP path. Only scripts independently reviewed and tested
to tolerate this relocation qualify. `$0`-sensitive scripts or relative-sibling loads
qualify only when the entry enumerates their exact relocated helper layout and proves
identical behavior; otherwise refuse, without rewriting bytes or spoofing `$0`.
Relative paths from cwd resolve against the repository root. Snapshot native vs composed
invocations in fixtures that inspect `$0`, sibling resolution, cwd, argv, stdin and env.
Preserved bytes alone are never advertised as preserved invocation behavior.

The manager profile pins an exec argv vector for the installed version's pre-commit
stage, config and cache; factory similarly pins its gate argv. Use direct exec, never
shell interpolation. Pre-commit takes no hook arguments. Stages receive only catalog
allowlisted Git-provided repository/index/editor variables validated against this repo,
fixed PATH/locale/timezone, isolated HOME/tmp and explicit stage cache settings. Dynamic
Git values are recorded as invocation provenance, not secret values in the receipt.
Unknown required env or a tool relying on ambient env refuses eligibility. Per-stage
sandbox/env adaptations are reviewed compatibility constraints, not a claim to preserve
all ambient native behavior. The wrapper does not overwrite the caller's environment.

## 6. Lock, journal, recovery, and rollback

For a supported topology the Git common directory is the local `.git` directory.  Apply,
recovery, and rollback take one exclusive factory-owned lock there before **inventory**
and retain it through backup, target mutation, receipt publication, and rollback.  A
future topology may use the same common-gitdir lock protocol only after the linked
worktree requirements in §1 are designed and proven.

The journal records every before/after digest, mode, receipt generation, and phase:
`prepared`, `applying`, `committed`, `rolling_back`, or `recovered`.  Each update writes
a temporary file, fsyncs the file, atomically renames it, and fsyncs the containing
directory.  Native backup publication and receipt publication use the same durability
sequence.  The journal is retained/archived after a completed transaction; it is not
silently deleted.

On the next mutating command, the lock holder first recovers a non-terminal journal.
It may finish a fully verified post-state or restore only locations whose current digest
is exactly the recorded factory after-state.  If a path is neither recorded before nor
after state, recovery stops with `COMPOSITION_RECOVERY_CONFLICT`, retaining evidence and
making no speculative write.  Concurrent processes block or fail before inventory; they
never interleave receipts or rollback.

Explicit rollback takes the same lock and requires the receipt, wrapper, backup, and
current target to match their recorded ownership digests.  It restores the original
native bytes/mode atomically, archives factory metadata, and leaves manager cache
generations intact.  Any user drift, missing backup, or uncertainty refuses rollback;
rollback is intentionally not a cleanup tool.

## 7. Preview and confirmation

Dry-run is observationally zero-write, including no lock/journal/receipt/cache creation,
no mtime changes, no Git config or index/status refresh, and no manager invocation.  It
opens the candidate files safely and hashes a canonical inventory: file content/mode and
stat identity, config origin/value, receipt state, manager/cache manifest, semantic
inventory, factory bundle, and Git topology.  The preview hash is over that inventory.

Confirmation acquires the lock, recomputes the full inventory, and compares the preview
hash before any target mutation.  A mismatch (including cache or config drift) exits
without changing hooks.  This closes the preview-to-confirm TOCTOU window rather than
assuming a displayed plan remains current.

## 8. Real commit-traversal evidence

A pre-commit success is only a pending attempt. Parent/tree coincidence is NEVER
completion. This MVP also installs a receipt-owned `reference-transaction` observer,
using the same apply/rollback journal and preview for both hook targets. A foreign
reference hook, unsupported Git invocation shape or unavailable process-identity proof
refuses eligibility. The observer is not a generic router. Scope is ordinary, attached,
single-parent `git commit`; unborn/detached HEAD, merge/amend/rebase and other ref writers
receive no composed completion evidence. Non-commit ref operations remain permitted
without minting evidence. Git-version-specific transaction shapes must have fixtures;
unknown shapes cannot consume an attempt.

1. On pre-commit entry, identify the nearest real Git ancestor using kernel process
   ancestry, pinned `/proc/<pid>/exe` digest, boot ID and process start time (PID alone or
   an environment nonce is insufficient). Record attached branch/ref and old OID.
   Create owner-only `attempt/v1` with a cryptographically random 256-bit nonce, process
   identity, receipt/input/invocation digests, final validated index tree, and a monotonic
   deadline ten minutes AFTER successful checks. Check the Git process identity is still
   live. One attempt per Git process; repeated pre-commit entry invalidates rather than
   reuses it. No stage receives the control-state directory as a writable sandbox mount.
2. Under an exclusive evidence lock, the reference hook's `prepared` callback must match
   that SAME nearest Git process, live nonce and unexpired attempt. Validate the complete
   transaction's old/new/ref tuples: exactly the recorded branch transition, with only
   tested HEAD-alias bookkeeping allowed. Read the actual new commit object and require
   its sole parent equals old OID and its tree equals the checked tree; bind actual new
   OID, exact normalized tuple vector and all digests. Atomically change `pending` to
   `reserved` using one canonical state-file replacement with file+directory fsync.
   No second reservation is allowed. A missing attempt never borrows a previous one.
3. A matching `committed` callback, still from that process and before expiry, verifies
   the actual ref now resolves to the reserved new OID. Atomically replace the SAME
   state record with terminal `consumed` containing completion plus old/new/ref/nonce,
   tuple vector, process identity and digests. Thus consumption and completion are one
   durable transition, not two files whose crash ordering permits reuse. Subsequent
   callbacks are idempotent reads and cannot mint another completion.
4. `aborted`, mismatched tuples, process death, expiry, reboot or verification error
   terminally invalidate the attempt; a prepared-hook refusal also invalidates locally
   because Git need not send an aborted callback after hook rejection. There is no
   recovery promotion of pending/reserved state by searching later commits. On a crash
   after Git updates the ref but before durable consumption, report missing evidence;
   never invent successful traversal. A completion records a committed ref transition,
   not success of later notification hooks or the outer command's exit status.

Git's transaction callback states and old/new/ref stdin contract are documented in
[Git hooks](https://git-scm.com/docs/githooks#_reference_transaction); its hook cwd/env
contract also governs invocation fixtures. The observer validates the installed Git
version rather than assuming every version emits the same symbolic-ref bookkeeping.
This is protection against accidental replay/drift, not against the repository owner or
same-UID malicious code able to replace Git, hooks and evidence together.

Read-only doctor accepts only a terminal consumed record, a currently valid receipt
with all matched digests, and traversal proving that EXACT new OID remains reachable
from the recorded branch with the recorded parent/tree. It never accepts a later commit
with merely the same parent/tree. Completion has no reusable authorization power;
pending/reserved expire in ten minutes and on process death, consumed records remain
historical until explicit archive and become inapplicable on receipt drift. Metadata
lives under owner-only `.git/aq-factory/composition/attempts`, separate from tracked
content, with no secret env dumps. Doctor does no cleanup. A mutating maintenance action
may archive invalid/expired records; nonterminal state never resurrects. Direct gate-run
evidence remains distinct and cannot satisfy composed evidence.

## 9. Acceptance matrix and fault injection

| Case | Required result |
|---|---|
| Valid owned receipt + matching inputs | doctor reports active; no writes; composed commit traversal is required |
| YAML without valid receipt | current foreign-manager conflict/refusal unchanged |
| `.git` file, `commondir`, or linked worktree | current refusal unchanged; no sibling discovery |
| Cache absent/altered | confirm refuses before mutation; wrapper fails before every stage |
| Opaque native/manager or duplicate semantic ID | refusal; native is never selectively skipped |
| Preview input changed | confirmation hash mismatch; no target mutation |
| Native, manager, factory failures | same first failing exit; subsequent stage not run |
| Lock contention | one owner proceeds; peer has no inventory/mutation interleaving |
| Kill after each journal phase | restart recovers only exact known state or refuses with retained journal |
| Crash after native replacement/before receipt | recovery restores only verified native state or blocks |
| Direct gate runner evidence | never satisfies composed traversal evidence |
| Actual supported `git commit` | matching prepared/committed transition atomically consumes one attempt; exact OID traversal |
| Pre-commit succeeds, commit-msg aborts, later identical parent/tree commit bypasses checks (test fixture only) | old attempt cannot reserve/complete; doctor reports missing evidence |
| Expiry/PID reuse/reboot/foreign process/duplicate callbacks | no new completion; consumed callback replay is read-only |
| Kill before/after reservation or consumption fsync | never reusable completion; uncertain successful commit reports missing evidence |
| `$0`/sibling/cwd/argv/env profile mismatch or catalog tamper | refuse before installation/execution |
| DNS/TCP/Unix proxy/inherited FD attempt from each stage and child | denied with reachable unsandboxed positive controls |
| Sandbox unsupported or writable manifest/escaping path | fail closed; no unsandboxed fallback |
| Rollback with drift | refusal, no partial restore |

Fault injection must cover fsync/rename errors, SIGKILL at each journal boundary, corrupt
receipt/manifest, changed cache file, concurrent confirm/rollback, and a commit that
fails after pre-commit.  Tests include byte-for-byte native preservation, dry-run
metadata snapshots (including mtimes and Git config), and offline execution with network
disabled.

## 10. Reuse and implementation boundary

Reuse `scripts/ai/lib/factory_gate_install.py`: `retrofit_metadata_conflict()` (around
464–476) for the unchanged topology refusal; `status()` (around 875–908) and
`readiness_preflight()` (around 1077–1148) for receipt-aware doctor integration;
`ensure_evidence_ignored()` for the existing atomic-write pattern, extended with required
directory fsync; and `_execution_evidence_state()` (around 973–1013) solely for the
explicit distinction from composed traversal evidence.  Preserve frozen
`software-dev-factory-rollout/DESIGN.md` §4.2 as the default refusal authority.

The first implementation PR must contain code, tests/fault injection, a receipt schema,
and this design revision together.  It needs independent design acceptance before it can
be marked PLAN_READY.  No document-only delivery is valid.

## 11. Review boundary and remaining implementation details

The three protocol decisions are specified above, pending independent review rather
than claimed accepted. Review must explicitly assess the added reference-hook scope,
kernel process-identity binding, atomic consumed-record crash behavior, catalog authority
and invocation restrictions, and sandbox closure/egress probes. If the installed platform
cannot implement any boundary, keep the current composition refusal; do not weaken it.
Only CLI spellings and cache directory naming remain implementation details, constrained
by the manifest/ownership rules. No hook code, runtime activation or acceptance is
asserted by this design. Ship only with the first implementing code PR.
