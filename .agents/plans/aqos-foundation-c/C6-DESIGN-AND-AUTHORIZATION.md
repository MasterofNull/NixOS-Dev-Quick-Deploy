---
title: "Foundation C C6: Authenticated Epoch Authority + F2.5 Scheduler Revocation Gate"
slice: "C6"
status: "PREPARED_ONLY — REVISION 3 (re-anchored after C2-SCI + C6-P0 landed; both blockers resolved); independent binding re-review and single-use owner activation required"
revision: 3
kind: "design-only"
implementation_authorization: "NONE"
activation_authorization: "NONE"
base_head: "e7bf91deb4693a6667cd3c3ed10b0988b4143ef6"
predecessors:
  - "C2 lease verification and executor epoch fence"
  - "F2.5 live slot_queue acquire/release through dispatch.py"
successors:
  - "C4 network confinement"
  - "C3a-2 delegated-effect broker"
---

# Foundation C — C6: Authenticated Epoch Authority + Scheduler Revocation Gate

> **Amendment (2026-08-06, from the C6-P0 rev3 binding review):** the two schemas
> `config/schemas/revocation-epoch-bump.schema.json` and
> `config/schemas/scheduler-lease-context.schema.json` — listed as absent/NEW in §1 and §4
> below — are now **created by C6-P0 rev3** (`C6-P0-TRUST-ANCHORS-REV3-20260806.md`). At C6-main
> freeze these become **verify-only / no-create anchors** here (do not re-create; reproduce their
> C6-P0-provided hashes), and C6-P0 must land before the C6-main re-freeze. This closes the
> schema-ownership collision the binding review flagged; §§1/4 rows below are read subject to this
> amendment.

## Revision 3 — re-anchor after C2-SCI + C6-P0 landed (both blockers RESOLVED, 2026-08-07)

Between rev2 and now, C6's two freeze blockers were CLOSED by landed, independently-reviewed work
(`C6-RECONCILIATION-POST-C2SCI-20260807.md`). rev3 changes ONLY the §1 baseline anchors + the absent/NEW
reservation list to the current truth; the §2 epoch-authority + §3 scheduler-gate semantics and the R1–R6
answers are UNCHANGED and stand.

**Q-C6-1 (the C2 scheduler-lease-context issuer + signed ingress) — RESOLVED.** Built as C2-SCI (design
rev4 `c934db23`, binding + confirmatory review PASS, freeze `C2-SCHEDULER-CONTEXT-ISSUER-FREEZE-20260807.md`,
owner-activated, built B1–B4 default-OFF, all 5 subslices reviewed PASS). NAMING RECONCILE: rev2 §1 reserved
`scripts/ai/lib/scheduler_lease_context.py`; the issuer was actually built as the SEPARATE confined service
`scripts/ai/lib/scheduler_context_issuer.py` (+ `scheduler_context_transport.py`, `nix/modules/services/
c2-scheduler-context-issuer.nix`) and the signed ingress as `dispatch.py::verify_ingress_scheduler_context`
(INERT today, flag-gated `CAPABILITY_SCHEDULER_CONTEXT_ISSUER`). C6 main CONSUMES these — it does NOT
re-create the issuer.

**Q-C6-2 (owner key allowlist + P0 hardening) — RESOLVED.** C6-P0 rev3 BUILT (`config/aqos/
c6-owner-public-keys.json`, `config/schemas/revocation-epoch-bump.schema.json`, `config/schemas/
scheduler-lease-context.schema.json` — verify-only anchors per the amendment above).

**§1 re-anchor (rev3 — verify these at C6-main freeze):**
| path | rev2 hash | rev3 (current) | note |
|---|---|---|---|
| `scripts/ai/lib/capability_lease.py` | `a6f92392…` | `611f1af8…` | ALA rev4 added `verify_authoritative`/`sign_ed25519` |
| `ai-stack/switchboard/capability_lease_gate.py` | `3e92d2fe…` | `970d10f7…` | enforce-verify + C2-SCI B3 flag-gated blocks |
| `scripts/ai/lib/slot_scheduler.py` | `ea3b5b9a…` | `ea3b5b9a…` | UNCHANGED |
| `scripts/ai/lib/slot_queue.py` | `e4e7e9b1…` | `e4e7e9b1…` | UNCHANGED — C6 main edits it (the fence) |
| `scripts/ai/lib/dispatch.py` | `1b083b10…` | `77ba0c25…` | C2-SCI B3 added `verify_ingress_scheduler_context` (the Q-C6-1 ingress) |
| `scripts/ai/delegate-to-local` | `b5d2c5cb…` | `b5d2c5cb…` | UNCHANGED |
| `scripts/ai/aq-event` | `5deba81b…` | `5deba81b…` | UNCHANGED |
| `config/env-contract.yaml` | `62450e1f…` | `74c10eb2…` | added CAPABILITY_ASYMMETRIC_LEASE + CAPABILITY_SCHEDULER_CONTEXT_ISSUER |
| `dashboard/backend/api/routes/aistack.py` | `5e736402…` | `aa855d61…` | added ala + c2_scheduler_context_issuer sections |
| `assets/dashboard.js` | `ea88c43e…` | `9c892841…` | added ALA + C2-SCI rows |
| `scripts/testing/harness_qa/phases/phase0.py` | `5e6f2208…` | `5e6f2208…` | UNCHANGED |
| `nix/modules/services/default.nix` | `a36d0b21…` | `f772a1eb…` | ALA + auto-wake + c2-sci imports |

**Absent/NEW reconciliation:** `revocation-epoch-bump.schema.json`, `scheduler-lease-context.schema.json`
(C6-P0), and `scheduler-lease-gate-decision.schema.json` (C2-SCI B2) are now BUILT → verify-only anchors,
NOT re-created by C6 main. `scheduler_lease_context.py` is SUPERSEDED by the built C2-SCI issuer (above).
C6 main's genuinely-still-absent NEW files (confirmed absent at current HEAD): `scripts/ai/aq-epoch-bump`,
`scripts/ai/lib/revocation_epoch.py`, `nix/modules/services/revocation-epoch-authority.nix`,
`scripts/testing/{test-revocation-epoch.py,test-scheduler-lease-gate.py,test-c6-service-coverage.py}`,
`scripts/testing/fixtures/revocation-epoch-golden.json` + the `slot_queue.py` EDIT (verified-context fence
+ durable reservation digest + epoch-bump revocation drop, flag `CAPABILITY_SCHEDULER_LEASE_GATE`, wiring
the built `verify_ingress_scheduler_context` into the live dispatch→slot_queue path).

**Path:** this rev3 → fresh independent BINDING re-review (rev1 had the codex depth-review; rev2/rev3 have
no PASS) → hash-bound freeze (reproduce the rev3 anchors) → single-use owner build-activation → default-OFF
build → independent code review → commit → owner flag/enable → C4.

## 0. Revision, authority, and decision

This revision responds to every blocking item in
`C6-CODEX-DEPTH-REVIEW-20260801.md`; that review remains binding history. The
prior rev1 hash (`89b2b65d…`) is superseded and **must not be frozen, built,
or activated**. This packet is design only and remains PREPARED_ONLY.

C6 is the intervention lever between C2/C3b executor fences and the live F2.5
queue: an authenticated owner request advances one durable epoch, and a
verified, audience-bound dispatch context is checked before `slot_queue.acquire`
can reserve work and while a reservation is held. It does not replace existing
executor checks, grant a lease, reissue a lease, create a provider request, or
enable any flag.

The design makes these binding choices:

1. **One epoch authority:** a dedicated local `aq-revocation-epoch-authority`
   service owns the epoch state and is the sole writer. `AQ_LEASE_POLICY_EPOCH`
   is removed from all enforcement resolution; no environment override exists.
2. **One authenticated bump protocol:** `aq-epoch-bump` is only a UDS client.
   It submits a closed, Ed25519 owner-signed bump request to the authority
   service. `aq-event` is an audit projection only and never authorizes a bump.
3. **The real scheduler seam:** `dispatch.py` verifies a scheduler-audience
   context at trusted ingress and passes the resulting immutable context to
   `slot_queue.acquire/release`; `slot_scheduler.wait_for_slot` remains a
   stateless `/slots` helper and is not represented as a queue or revocation
   authority.

Any missing authority service, unreadable/malformed epoch, failed context
verification, unavailable public key, replay, stale lease, or ambiguous state is
a typed deny. There is no bootstrap-to-zero, environment fallback, direct epoch
file write, advisory success, or auto-reissue path.

## 1. Current anchored baseline

| Existing path | SHA-256 | C6 role |
|---|---|---|
| `scripts/ai/lib/capability_lease.py` | `a6f923924071618b9e0628e3c93c640bdbeae348e4fee792b0cc5da151997f8f` | Existing signature/freshness primitive; not a scheduler context issuer. |
| `ai-stack/switchboard/capability_lease_gate.py` | `3e92d2fe97a1ea8b18fef82848f11f502de5171bab6b297f810ffd021997e424` | Existing enforcement reader to be re-anchored to C6's authoritative reader. |
| `scripts/ai/lib/slot_scheduler.py` | `ea3b5b9a20137f27f1ec92868aeeb37c0ee16eb744728cb457453d32f7102945` | Read-only `/slots` poll helper; excluded from queue-gate enforcement. |
| `scripts/ai/lib/slot_queue.py` | `e4e7e9b158bec0aa316efb1760de6b83c54d2044b5bbd2b9c394286295a5aa96` | Actual acquire/release reservation seam. |
| `scripts/ai/lib/dispatch.py` | `1b083b1025877385cb4e295234edd23a61a85aae554393fb87792c732e01dd92` | Trusted ingress-to-queue propagation seam. |
| `scripts/ai/delegate-to-local` | `b5d2c5cb6e1018dba42351cc986b951dca25261f66694c995f068fa09254e1c4` | Existing untrusted caller CLI; excluded from accepting a raw lease/context. |
| `scripts/ai/aq-event` | `5deba81b5b044e6ff6cdff9da9359a043052c96decb40e2b57530e5a5f3334d4` | Audit projection only; excluded from bump authorization. |
| `config/env-contract.yaml` | `62450e1f6e84f9c473b2bf838e1121d6db3e40227480c1845d5b24c54686be4f` | Documents default-OFF gate and fixed authority socket/path. |
| `dashboard/backend/api/routes/aistack.py` | `5e736402eb51bf7522902fd4803cd9dac099ce197ec15df4bfec6ec5a1e6d2fd` | C6 state projection source. |
| `assets/dashboard.js` | `ea88c43e2509fd9d5a1c1dbf408c87a48538cd96a33fee2c42ad79f1c347c0be` | C6 dashboard consumer. |
| `scripts/testing/harness_qa/phases/phase0.py` | `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1` | C6 integration AQ-QA registration. |
| `nix/modules/services/default.nix` | `a36d0b21013ff3352c91443c4a6ca39c4e81a3c992d6b8e1dd871aba2c38d32b` | Imports the new authority module. |

The following paths are confirmed **absent** at the base HEAD and are reserved
only for this C6 candidate: `scripts/ai/aq-epoch-bump`,
`scripts/ai/lib/revocation_epoch.py`,
`scripts/ai/lib/scheduler_lease_context.py`,
`config/schemas/revocation-epoch-bump.schema.json`,
`config/schemas/scheduler-lease-context.schema.json`,
`config/schemas/scheduler-lease-gate-decision.schema.json`,
`scripts/testing/fixtures/revocation-epoch-golden.json`,
`scripts/testing/test-revocation-epoch.py`,
`scripts/testing/test-scheduler-lease-gate.py`,
`scripts/testing/test-c6-service-coverage.py`, and
`nix/modules/services/revocation-epoch-authority.nix`.

The final freeze must reproduce every listed hash/absence, bind the revised
packet hash, reject all other changed paths, and stop on HEAD drift.

## 2. Durable authenticated epoch authority

### 2.1 Authority boundary and request schema

`aq-revocation-epoch-authority` is a socket-activated, dedicated unprivileged
local service. Its StateDirectory contains `epoch`, a stable lock inode, a
durable replay ledger, and append-only bounded audit receipts. Its control UDS
is mode `0660`, group-restricted, and additionally validates `SO_PEERCRED`;
transport membership is never sufficient authority.

The authority accepts only `aq.revocation-epoch-bump/1` documents validated by
the new closed schema. Required fields are `schema_version`, `request_id`,
`idempotency_key`, `issued_at`, `expires_at`, `actor_key_id`,
`expected_epoch`, `reason_code`, `scope`, and `signature`. `scope` is exactly
`fleet`; reason codes are a bounded enum; no free-form reason, secret, prompt,
path, or arbitrary payload is accepted. The Ed25519 signature covers a
domain-separated canonical payload and is checked against the tracked,
key-id-selected owner public-key allowlist. The service rejects unknown/revoked
keys, malformed signatures, wrong audience, expired/future-invalid windows,
duplicate request IDs, duplicate idempotency keys with different digests, and
an `expected_epoch` unequal to durable state.

The command cannot synthesize owner authority. `aq-epoch-bump` reads a signed
request from an explicit file descriptor or stdin, sends it once, and returns
only a redacted typed receipt. It has neither epoch write permission nor a
private owner key. `aq-event` receives the post-commit receipt through a
restricted internal projector; a CLI `--agent owner` event is explicitly not
an epoch operation and cannot affect enforcement state.

### 2.2 Single durable transaction and reader contract

The service opens a fixed state root without following symlinks and uses a
stable `epoch.lock`. Under exclusive lock it opens `epoch` with no-follow
semantics, requires a regular file, owner/mode policy, UTF-8, and one strict
non-negative decimal integer. It compares `expected_epoch`, creates a
same-directory temporary regular file with fixed ownership/mode, writes
`new_epoch = old_epoch + 1`, fsyncs it, atomically replaces `epoch`, and fsyncs
the directory. It atomically records the idempotency/replay receipt before
releasing the lock. Only after that durable commit may it publish the bounded
audit event with `{receipt_id, request_digest, old_epoch, new_epoch,
actor_key_id, committed_at}`. If projection fails, the receipt is
`committed_audit_pending`, never a claim that no bump occurred; its idempotent
reconciler can publish only the already-durable receipt.

All enforcement readers use `revocation_epoch.resolve_current_epoch()` with the
fixed authority state path supplied by Nix, no environment precedence and no
absent-file default. Reads use the same no-follow regular-file validation and
return a typed unavailable result, never `0`, on replacement race, malformed
content, symlink, permission, or I/O error. C2, the scheduler gate, and future
C3b readers deny on unavailable. A process holding a stale value must reread
before every admission/reservation and on each held-reservation revocation tick;
it may not cache an epoch across those fences.

## 3. Verified ingress and the live queue seam

### 3.1 Scheduler lease context

A raw lease, environment value, CLI flag, JSON field, or a caller-created
`--lease` argument is never accepted by `delegate-to-local` or `dispatch.py`.
The new closed `aq.scheduler-lease-context/1` is a domain-separated signed
handoff produced only by the authenticated C2 admission issuer. Its required
signed bindings are: `context_id`, `lease_id`, `grant_digest`, `task_id`,
`audience="aq-f2.5-slot-queue"`, authenticated caller principal, dispatch
mode, allowed action class, issued/expiry times, revocation epoch, policy
revision, and signature/key id. It is single-use: `slot_queue` durably records
its context digest before a reservation and refuses replay or digest conflict.

`dispatch.py` obtains this context only through a new authenticated local
ingress adapter (not the shell caller), verifies signature, audience,
principal/task/mode binding, freshness, and the authoritative epoch, then
passes an immutable verified object to `slot_queue.acquire`. The adapter itself
is within the exact C6 inventory below; if C2 cannot produce this signed
audience-bound handoff at the frozen base, C6 stops for a separately reviewed
C2 handoff slice. No unsigned compatibility path is permitted merely to make
the gate usable.

### 3.2 Reservation and revocation behavior

When `CAPABILITY_SCHEDULER_LEASE_GATE=0`, C6 imports/calls no verifier and
`slot_queue`/`dispatch` preserve byte-parity for every legacy request. When ON,
only a request arriving through the verified ingress may become lease-bearing.
Before `slot_queue.acquire` mutates persistent queue state, it verifies the
context and current epoch. A stale, unavailable, replayed, mismatched, or
invalid context returns a stable typed denial and creates no slot/held state.

`slot_queue` stores only context digest, lease ID digest, epoch, reservation
state, and bounded receipt ID—not a grant, prompt, path, or signature. On every
queue wake/tick and immediately before dispatch execution, it rereads the epoch
and validates the reservation context. If revoked/unavailable, it atomically
removes queued work; held work is released, marked `revoked-before-execution`,
and never handed to a provider. Work already executing is not falsely claimed
killed: it receives the existing executor fence and a typed C6 observation.

`slot_scheduler.wait_for_slot` is unchanged and never makes authorization
decisions. Its `/slots` result may inform availability only after the `slot_queue`
admission fence; it cannot grant a reservation.

## 4. Exact implementation inventory and exclusions

The only future implementation candidate paths are:

| Operation | Path | Purpose |
|---|---|---|
| NEW | `nix/modules/services/revocation-epoch-authority.nix` | Dedicated state, UDS, fixed reader membership, public-key-only verifier, hardening. |
| EDIT | `nix/modules/services/default.nix` | Import only the new authority module. |
| NEW | `scripts/ai/lib/revocation_epoch.py` | Strict reader, durable bump transaction, typed receipts/reconciliation. |
| NEW | `scripts/ai/aq-epoch-bump` | Unprivileged signed-request client; no epoch writer. |
| EDIT | `ai-stack/switchboard/capability_lease_gate.py` | Replace environment/file fallback resolution with the fixed C6 reader. |
| NEW | `scripts/ai/lib/scheduler_lease_context.py` | Signed context verify, audience/principal binding, replay-safe projection. |
| EDIT | `scripts/ai/lib/slot_queue.py` | Verified context fence, durable reservation digest, queued/held revocation drop. |
| EDIT | `scripts/ai/lib/dispatch.py` | Authenticated ingress adapter and immutable context propagation; no raw CLI lease. |
| EDIT | `config/env-contract.yaml` | `CAPABILITY_SCHEDULER_LEASE_GATE` default `0`; fixed non-overridable authority references. |
| NEW | `config/schemas/revocation-epoch-bump.schema.json` | Closed signed bump request/receipt schema. |
| NEW | `config/schemas/scheduler-lease-context.schema.json` | Closed audience-bound context schema. |
| NEW | `config/schemas/scheduler-lease-gate-decision.schema.json` | Low-cardinality typed admission/drop/audit record. |
| NEW | `scripts/testing/fixtures/revocation-epoch-golden.json` | Valid and negative signed epoch/context/replay/CAS vectors. |
| NEW | `scripts/testing/test-revocation-epoch.py` | Offline authority protocol, CAS, fsync-order seam, replay and recovery tests. |
| NEW | `scripts/testing/test-scheduler-lease-gate.py` | Offline `dispatch`→`slot_queue` admission, queue/held-drop, flag parity tests. |
| EDIT | `dashboard/backend/api/routes/aistack.py` | Live-backed, redacted C6 state projection only. |
| EDIT | `assets/dashboard.js` | C6 epoch/gate/denial/latency display with unavailable state. |
| EDIT | `scripts/testing/harness_qa/phases/phase0.py` | Registered integration AQ-QA check for the actual authority-to-queue path. |
| NEW | `scripts/testing/test-c6-service-coverage.py` | Integration fixture path validating API projection and AQ-QA registration. |

Excluded: `slot_scheduler.py`, `scripts/ai/delegate-to-local`, `scripts/ai/aq-event`,
executor/C3b files, provider invocation, task-registry writer semantics, database
or DDL, C4 networking, C3a-2 delegation, secrets/private keys, unrelated dashboard
cards, deployment, and activation. Any need to touch an excluded path—including a
C2 inability to mint the signed scheduler context—is a stop condition requiring a
new reviewed design rather than expansion.

## 5. Tests, rollback, and Service Coverage

Offline vectors must cover: valid owner bump; forged/unknown/revoked key; expired
or future request; wrong audience/scope; idempotent replay and conflicting replay;
two concurrent bumpers; interrupted temp write; malformed, symlinked, wrong-mode,
or unreadable state; event projection failure/reconcile; stale reader; no
environment override; flag-OFF no-import parity; unsigned/raw caller lease refusal;
wrong principal/task/mode/audience; expired/stale context; context replay;
refusal before `slot_queue.acquire`; queued and held revocation drops; and executor
handoff observation without claiming a running process was killed.

The integration AQ-QA path uses a hermetic authority and queue fixture, not a
provider. It proves signed bump → durable epoch/receipt → authenticated dispatch
context → `dispatch.py` → `slot_queue` denial/drop → redacted API projection. It
is registered in `phase0.py`, exercises more than health, and validates honest
unavailable/error states.

The dashboard shows only: authority health (`healthy|degraded|unavailable`), current
epoch or unavailable, scheduler gate configured/effective state, last redacted bump
receipt reference, typed refusal/drop counters, and bounded revocation latency
buckets. It shows no request ID, lease ID, prompt, command, absolute path, signature,
or raw reason. It derives from durable authority/queue receipts, never flags or
hard-coded health. Service code, AQ-QA check, and dashboard projection ship together.

Rollback is forward-safe: disable the scheduler gate only through a separate owner
act; retain durable epoch and receipts; stop new verified scheduler contexts; release
only reservations proved not executing; and preserve any ambiguity as typed
`quarantined`/`unavailable` evidence. Rollback never lowers epoch, deletes audit,
auto-reissues, restores a raw lease path, or claims a running process was stopped
without executor proof.

## 6. Freeze, activation, and explicit blockers

Before freeze, an independent reviewer must verify all base hashes/NEW absences,
the exact C2 issuer identity and public-key revision for scheduler contexts, the
authority service's Nix hardening and state ownership, and all test vectors. The
freeze must bind exact candidate hashes, no-edit anchors, source schema versions,
validation commands, the implementer/reviewer identities, and explicit exclusions.

**Blocking question Q-C6-1 (must close before freeze):** identify the existing C2
component that can issue the `aq.scheduler-lease-context/1` signature for the
authenticated ingress, including its exact key-id/public-key revision and how the
context reaches `dispatch.py` without a caller-controlled channel. The current C2
gate returns admission decisions but does not itself expose that handoff; until a
reviewed issuer/transport is named, C6 may not be frozen or built.

**Blocking question Q-C6-2 (must close before freeze):** name the owner public-key
allowlist source and its immutable revision, and verify the dedicated authority
service can enforce state-file ownership/mode without a switchboard hardening
change. No owner key, Nix service hardening, or credential path may be assumed.

After both blockers are closed: design → independent binding review → hash-bound
freeze → single-use owner activation to build default-OFF → independent code review
→ commit. Enabling the scheduler gate is a later, separate owner act. No review,
freeze, or default-OFF build authorizes an epoch bump, provider traffic, deployment,
or live scheduling cutover.

## 7. Finding closure matrix

| Binding finding | Closure |
|---|---|
| R1 stale environment/non-coherent epoch | §2.2 removes environment override and absent-zero fallback; all readers use fixed durable authority. |
| R2 forgeable `aq-event` bump | §2.1 selects dedicated UDS authority, closed owner-signed protocol, replay/idempotency; event is projection only. |
| R3 wrong `slot_scheduler` seam/no provenance | §3 grounds enforcement in verified ingress → `dispatch.py` → `slot_queue.acquire/release`; raw leases refuse. |
| R4 vague CAS/durability | §2.2 specifies lock, no-follow validation, CAS, temp/fsync/replace/directory fsync, ordered audit, recovery, and reader failure. |
| R5 non-exact inventory/tests | §§1 and 4 bind current hashes/NEW absences, operations, exclusions, schemas, fixtures, and test paths. |
| R6 absent observability/Service Coverage | §5 requires durable live-backed API/UI state and registered integration AQ-QA with honest unavailable states. |

**RECORD: PREPARED_ONLY revision 2. No implementation, activation, staging, commit,
deployment, restart, provider, or network authority is granted.**
