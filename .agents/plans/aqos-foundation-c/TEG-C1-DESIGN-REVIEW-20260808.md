---
doc_type: plan
id: teg-c1-design-review-20260808
title: TEG C1 Independent Architecture Security SRE Review
slice: C6-B3R-C1
date: 2026-08-08
reviewer: codex-subagent-tracker-am2-rebase-audit
role: independent flagship architecture/security/SRE reviewer
head: 0579c5796730c443bca31612efa8e4aa6ce784b3
verdict: REQUEST_REVISION
status: draft
parent_prd: trusted-execution-gateway
---

# TEG C1 independent architecture/security/SRE review

## Frozen subject

The reviewed bytes and repository anchor matched exactly:

| Subject | SHA-256 |
|---|---|
| `.agent/PROJECT-TRUSTED-EXECUTION-GATEWAY-PRD.md` | `e7497f09eb5c812909f22c4a83cfdfb9c60ceb97f75735c96ff1d43383b66778` |
| `.agents/plans/aqos-foundation-c/TEG-C1-DESIGN-PACKET-20260808.md` | `69ab382d14e24c49b5c07e255092b837024af5d4c97f15e1ec75b8f46dc12aae` |
| accepted reconciliation `.agents/plans/aqos-foundation-c/C6-B3-LIVE-SEAM-RECONCILIATION-20260808.md` | `0523b4c275d5abf13178eaae6d72603f12325e88a73f2d95a03d37e3b7116ea4` |
| repository HEAD | `0579c5796730c443bca31612efa8e4aa6ce784b3` |

This was a static design review under the explicit no-test/no-runtime boundary. No implementation or
activation evidence is credited.

## What is sound

The subjects make the correct high-level correction: one broker-neutral TEG, one durable lifecycle
writer, no caller-supplied authority object, a dedicated service identity, private authority surfaces,
default-OFF rollout, and no promotion of `dispatch.py`, switchboard, or an unbuilt `aq-dispatchd` into an
authority. They also preserve independent acceptance, hermetic fake-provider coverage, separate canary
authorization, low-cardinality telemetry, and the mandatory aq-qa/dashboard pairing.

Those choices close the core same-UID authority-confusion problem identified by the rejected C6-B3
commit. The current packet is nevertheless not yet safe to freeze for implementation because it weakens
or leaves ambiguous several load-bearing details from the accepted reconciliation.

## Blocking findings

### R1 — lifecycle and token ordering drift from the accepted reconciliation

The PRD lifecycle omits `revoked` while its monitoring contract reports revoked counts and its epoch rule
says an advance revokes unlaunched permits (`PRD:33-49,78`). The design packet repeats the omission
(`DESIGN:22-27`). The accepted reconciliation explicitly permits `queued|held -> revoked` and requires a
durable revoked record before releasing a held slot (`RECONCILIATION:67-81,94-101`).

The subjects also collapse token creation and token consumption: they say token consumption atomically
commits `held -> launch_authorized` (`PRD:45`, `DESIGN:26`). The accepted ordering instead creates the
one-use token and commits `held -> launch_authorized`, after which the adapter consumes the token once and
CASes `launch_authorized -> running`. Those are different crash and replay boundaries.

Required revision: restore one normative transition table including `revoked`; define actor, expected
revision/fence, durable evidence, and slot-release behavior for every transition; and retain the accepted
create/commit/consume/run ordering. State explicitly that `launch_authorized` is the execution-start
linearization point and that an epoch bump afterward is reported as already-starting/running, never
claimed as prevented.

### R2 — crash-after-linearization truth is underspecified

The PRD says an uncertain pre-launch operation remains non-running, while a failed post-consume launch is
recorded `failed` (`PRD:41,45`). A crash after the durable `launch_authorized` commit or token consumption
but before the adapter records `running` cannot prove that provider I/O did or did not begin. Recording
ordinary `failed`, retrying, or inferring from a PID would each be false or unsafe.

Required revision: freeze the recovery state for every crash point. A durable `launch_authorized` record
with uncertain provider start must remain explicitly indeterminate/possibly-started, must never be
relaunched automatically, and must not be reported as prevented, running, completed, or ordinary failed
without evidence. If a new terminal state is introduced, amend the reconciliation and closed schemas
together; otherwise define a bounded parked `launch_authorized` reconciliation state and its operator
resolution contract.

### R3 — public identity, idempotency, and cancellation authority are not closed

Public peers are correctly untrusted, but an arbitrary caller-provided idempotency key currently returns
the original durable record (`PRD:27,41`). Without binding the key to the canonical envelope digest and a
gateway-owned namespace, a same-UID caller can collide with another request, suppress work, or use the
response as a record oracle. The lifecycle also permits cancellation without naming who may authorize it.

Required revision: make TEG assign the canonical task identity; bind idempotency to a domain-separated
canonical envelope digest plus gateway namespace/revision; reject same-key/different-envelope reuse; return
only a redacted correlation receipt; and define a separately authenticated cancellation authority. Public
socket reachability, caller-selected fields, and `SO_PEERCRED` must never authorize cancellation or record
disclosure.

### R4 — private UDS identity and authority-response integrity need an end-to-end rule

Dedicated principals and private groups are necessary routing controls, but the subjects do not state how
TEG proves that it connected to the intended ALA, C2, and epoch services or how it rejects a replaced
socket. They also alternate between one principal and “principal(s)” (`PRD:25`; `DESIGN:31`). Group
membership alone is explicitly non-authoritative.

Required revision: freeze exactly one TEG service principal, distinct public/private socket paths and
groups, expected server principal/credential checks as transport binding, symlink-safe socket handling,
and cryptographic verification of every returned lease/context/epoch fact. Remove the owner and all agent
identities from private groups. Tests must cover socket replacement, wrong peer, stale/inactive key,
malformed signed response, and private-socket access by the public submitter.

### R5 — durable CAS and fencing mechanics are not sufficiently specified

“Durable CAS record” and “stable lock” (`PRD:33`; `DESIGN:22`) do not freeze the mechanics needed to
survive concurrent writers, symlink attacks, partial writes, or restart. The accepted reconciliation
already requires `O_EXCL`, durable directory fsync, ordered CAS, and orphan/revoked handling
(`RECONCILIATION:73-81`).

Required revision: carry those requirements forward and add no-pre-lock truncation, stable lock inode,
`O_NOFOLLOW`/regular-file/owner checks, same-directory atomic replacement, file and parent-directory
fsync, bounded record size, corruption fail-stop, monotonic persistent fencing-epoch allocation, and a
crash matrix for every write/fsync/CAS boundary. A stale process must be unable to publish after restart.

### R6 — resource and denial-of-service budgets are deferred too late

“Bounded” queue, records, retention, timeouts, and concurrency plus a future measured baseline
(`PRD:80`) are not enforceable design limits. The public socket is intentionally untrusted, so an
unbounded pre-activation implementation can exhaust memory, disk, descriptors, tasks, or authority calls.

Required revision: before implementation authorization, freeze numeric ceilings for envelope and record
bytes, outstanding/per-state tasks, queue depth, request and authority timeouts, connections, file
descriptors, worker concurrency, retention/compaction, retry/reconciliation attempts, journal rate, and
systemd `MemoryMax`/`TasksMax`/CPU/IO constraints. Specify admission backpressure and disk-full behavior;
both must deny or park without losing lifecycle truth.

### R7 — authority SSOT and complete Service Coverage inventory are missing

TEG creates a new sole lifecycle authority but neither future inventory includes
`config/system-state-authorities.yaml`. The listed implementation paths also omit the environment-contract
entry, aq-qa phase and registration surfaces, dashboard backend/frontend surfaces, Agent Ops projection,
and the schema/config registration needed to make the new service observable (`PRD:55-70`;
`DESIGN:33-48`). Deferring these unnamed paths conflicts with the canonical Service Coverage rule and the
accepted reconciliation’s atomic runtime/Nix/Phase-0/dashboard/fake-provider release
(`RECONCILIATION:103-113`).

Required revision: add an adjudicated TEG lifecycle/permit authority row and freeze the complete later
release inventory, including `config/env-contract.yaml`, service/module registration, protocol/schema
registration, integration-path aq-qa phase plus `phases/__init__.py`/`ALL_PHASES`, dashboard API and live
panel, Agent Ops projection, and their tests. Missing or stale telemetry must render `unknown/unavailable`,
not zero, healthy, or `--`. Runtime, Nix, coverage, and consumer wiring must be one atomic release unit.

### R8 — prerequisite and overlap gates are prose-only

The design depends on “accepted ALA-to-C2 repair” without exact accepted subject/reviewer hashes
(`DESIGN:5-7`), while the current ALA-C2 records are still prepared-only. Therefore no TEG implementation
authorization can yet be valid. Conditional edits to `scripts/ai/lib/dispatch.py` and
`nix/modules/services/switchboard.nix` also overlap previously frozen/committed contracts and require
explicit supersession or re-pinning, not only a later inventory (`PRD:66-70`; `DESIGN:42-48`).

Required revision: bind the exact independently accepted ALA-C2 implementation manifest and verdict;
otherwise retain a hard stop. For every conditional predecessor, name the prior freeze/manifest,
supersession or re-pin rule, exact no-touch hash, and overlap/CAS stop condition. No implementation packet
may be prepared from an uncommitted or merely design-PASS dependency.

### R9 — rollback and observability need truthful transition semantics

“Disable the consumer gate and preserve evidence” (`PRD:82`) does not say what happens to submitted,
queued, held, launch-authorized, or running work, nor who may fence the old writer. Monitoring lists useful
fields but omits freshness, projector/API unavailable states, and the post-linearization uncertainty from
R2.

Required revision: freeze rollback ordering: stop admission, durably advance the gateway fence, revoke
unlaunched reservations, preserve/park possibly-started and running work without retry, drain or cancel
only through named authority, and keep the TEG path fail-closed—never bypass to direct dispatch. Add
freshness/revision timestamps and explicit gateway/authority/projector/dashboard unavailable states, with
bounded reason vocabulary and no identifiers or sensitive data in labels.

## Re-review boundary

A revision may remain contract-only. It must update both subjects (and the accepted reconciliation if a
new lifecycle state is chosen), bind the accepted ALA-C2 evidence, provide a complete future inventory and
numeric budgets, and receive a new independent exact-hash review. No implementation authorization,
C6-B4 build, flag flip, socket/service start, provider traffic, canary, or deployment is warranted by this
review.

VERDICT: REQUEST_REVISION — restore the accepted revoked/token/CAS ordering; define truthful crash uncertainty, idempotency/cancellation and private-UDS authority; freeze durable-write mechanics, numeric budgets, authority/Service-Coverage inventory, exact ALA-C2/overlap prerequisites, and fail-closed rollback/telemetry semantics

---

## Revision R1 exact-byte re-review

### Revised subject

Re-reviewed independently at unchanged HEAD `0579c5796730c443bca31612efa8e4aa6ce784b3`:

| Subject | Revised SHA-256 |
|---|---|
| `.agent/PROJECT-TRUSTED-EXECUTION-GATEWAY-PRD.md` | `ca855c967d1874a6f0ff3c16d48525ea8353981b557e0da81617f4ef16b9316c` |
| `.agents/plans/aqos-foundation-c/TEG-C1-DESIGN-PACKET-20260808.md` | `54b8e0705530548f5365963ea06801a50e097d359a290228094545ec410fdd87` |

The earlier review above is preserved as historical `REQUEST_REVISION` evidence. This section supersedes
only its terminal adjudication for the revised bytes. No tests or runtime evidence were authorized or
credited.

### R1-R9 correction matrix

| Prior finding | Result | Evidence |
|---|---|---|
| R1 lifecycle/token ordering | PASS | `revoked` restored; token creation precedes durable `held -> launch_authorized`; adapter then consumes and CASes to `running`; post-linearization epoch is possibly-started. |
| R2 crash uncertainty | PASS WITH residual below | `launch_authorized` remains parked, non-retriable, and non-success until authenticated evidence reconciles it. |
| R3 identity/idempotency/cancellation | PASS WITH residual below | gateway task identity, domain-separated digest, same-key/different-digest rejection, and named cancellation authority are present. |
| R4 private UDS authority | REQUEST_REVISION | public-group membership creates deny-all and epoch-result authentication contradicts the no-key epoch authority. |
| R5 durable CAS/fencing | PASS | stable lock, exclusive markers, no-follow/owner checks, atomic replace, file+directory fsync, persistent revision/fence, and crash rows are mandatory. |
| R6 numeric budgets | REQUEST_REVISION | logical record limits landed, but process/transport/systemd ceilings remain absent. |
| R7 authority/Service Coverage inventory | REQUEST_REVISION | authority ledger is included, but the claimed exact inventory contains invalid and unresolved path placeholders. |
| R8 exact prerequisite/overlap gates | PASS | exact prepared ALA-C2 hashes are truthfully non-accepted; implementation is stopped pending final accepted manifest/verdict; conditional predecessors require supersession/re-pin and overlap preflight. |
| R9 rollback/telemetry | REQUEST_REVISION | unavailable telemetry is explicit, but fence advance strands old-fence running receipts and launch-authorized cancellation truth is incomplete. |

### Remaining blocking corrections

#### RR1 — the public submitter group excludes every stated caller

The PRD and packet define `aq-teg-submitters` as the public socket group and then exclude the owner and
unconfined agent accounts from **both** public and private groups. No alternate public submission principal
or proxy is selected. This recreates a flag-on deny-all route: the agents/wrappers that originate work
cannot reach the untrusted submission socket. The accepted reconciliation excludes owner/agents only from
the private authority-client surface, not from untrusted public submission.

Required correction: name the actual public client principal or permit owner/agent membership in
`aq-teg-submitters`, explicitly stating that this grants transport reachability only. Keep them excluded
from every private authority/cancellation group. Freeze the exact membership test proving public submit
succeeds while all private surfaces deny.

#### RR2 — the epoch authentication requirement cannot be satisfied by the frozen dependency

Both revised subjects require cryptographic signatures on every authority result. The current
revocation-epoch authority intentionally holds no private key and its `read-epoch` response is the closed
unsigned `{ok, epoch}` shape. It authenticates owner-signed **bump requests**, not read responses. Yet the
epoch module and service are frozen no-touch. Therefore the proposed TEG cannot both cryptographically
verify the epoch result and preserve the frozen authority; implementation would stop or silently weaken
the reviewed rule.

Required correction: define separate trust rules per authority. ALA leases and C2 contexts remain
signature-verified. For epoch reads, either (a) explicitly accept the canonical authority service identity
as authenticated local transport using safe parent/socket ownership plus expected server UID from
`SO_PEERCRED`, with schema/exact-current-epoch checks, or (b) authorize a separate amendment that adds an
authenticated response without giving the authority forge-equivalent owner signing power. Also name TEG's
membership in the existing `aq-revocation-epoch-clients` transport group. Clarify path checks as
`S_ISSOCK` for UDS nodes and regular-file checks only for records/markers; an AF_UNIX socket is not a
regular file and cannot be validated by the stated regular-file rule.

#### RR3 — “complete exact inventory” still contains invalid/nonexistent placeholders

`scripts/testing/harness_qa/phases/phase-teg.py` is not a valid importable Python module name, and
`scripts/testing/harness_qa/runner.py` does not exist. `ALL_PHASES` is owned by
`scripts/testing/harness_qa/phases/__init__.py`. “`assets/dashboard.js` or its selected canonical panel
asset” and “canonical registration/ALL_PHASES owner” are alternatives, not exact paths. The inventory also
does not name focused tests for the aq-qa and dashboard/API projections.

Required correction: replace every placeholder/alternative with one verified path (for example an
importable `phase_teg.py` or integration into the selected existing phase), name the actual registration
owner, and list the exact dashboard/API/Agent-Ops test surfaces. The later authorization may bind future
predecessor hashes, but the design cannot call an unresolved menu an atomic exact inventory.

#### RR4 — resource limits are only partially enforceable

The revision adds useful logical limits for records, queue states, sizes, freshness, and retention, but it
still lacks the prior required ceilings for concurrent public connections, open descriptors, worker/adapter
instances, authority-call concurrency, per-request/lock/authority timeouts, retry counts, journal rate, and
systemd `MemoryMax`, `TasksMax`, CPU, and IO controls. “One active launch per adapter instance” is not a
global bound when adapter-instance count is unbounded.

Required correction: give numeric maximums for those dimensions before implementation authorization and
bind each to its enforcement layer (schema/parser, listener, worker pool, lifecycle owner, or Nix unit).
Define reject/backpressure behavior and metrics for every ceiling.

#### RR5 — rollback fencing and post-linearization cancellation can lose lifecycle truth

Rollback advances the gateway fence while `launch_authorized` and running work remain possibly active.
Without a narrowly defined old-fence terminal-receipt path or fence-transfer protocol, the sole CAS writer
must reject those tasks' later authenticated completion/cancellation receipts as stale, stranding records
forever. Conversely, the broad lifecycle transition `launch_authorized -> failed|cancelled` could publish a
terminal state while provider work actually started unless evidence proves non-start or whole-tree
termination. The authoritative clock used for expiry/freshness across restart or wall-clock rollback also
remains unspecified.

Required correction: freeze rollback receipt reconciliation for pre-fence work, including who may accept
an old-fence terminal receipt, how it is bound without reviving launch authority, and its bounded parked
fallback. Permit `launch_authorized -> failed|cancelled` only with authenticated proof of non-start or
verified whole-process-tree termination. Name monotonic versus wall-clock sources and fail-closed clock
rollback behavior. In `config/system-state-authorities.yaml`, freeze a concrete TEG row ID, transition and
rollback owners, and selected target authority rather than only saying the file will be edited.

### Re-review boundary

The next revision remains design-only. It must correct RR1-RR5 in both subjects, preserve the exact
ALA-C2 implementation stop, and receive another independent exact-hash review. No implementation
authorization, C6-B4 implementation, live service/socket/provider action, flag flip, canary, deployment,
staging, or commit is warranted.

VERDICT: REQUEST_REVISION — fix public-submitter deny-all membership, define feasible per-authority UDS/epoch authentication, replace invalid Service-Coverage placeholders with exact paths/tests, add numeric process/systemd ceilings, and close rollback-fence/launch-cancellation/clock/authority-row truth
