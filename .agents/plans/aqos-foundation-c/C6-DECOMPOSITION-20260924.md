---
title: "Foundation C — C6 Decomposition: five individually-freezable slices (C6a–e) + C4↔C6 ordering resolution"
slice: "C6 (decomposition / per-slice charter)"
status: "PREPARED_ONLY — authorizes NOTHING (no build, no freeze, no activation, no epoch bump, no provider traffic, no flag flip)"
kind: "decomposition-plan"
implementation_authorization: "NONE"
activation_authorization: "NONE"
base_head: "f1f409ef97f73fb6ae152a297ba0c0367e30bf22"
supersedes_scope_of: "C6-DESIGN-AND-AUTHORIZATION.md rev5 (factory/c6-rev5 @ f68ccf912f07c4a872f17c1cbe6c469eac444350) — the MONOLITHIC single-freeze scope only; rev5's proven components are RETAINED as the per-slice design basis (see §0.3)"
closes_review: ".agent/collaboration/CODEX-C6-REV5-BINDING-REVIEW-20260924.md (REQUEST_REVISION — 5 HIGH findings)"
authoring_role: "architect (design/planning only)"
---

# Foundation C — C6 Decomposition

## 0. Why this document exists

C6 (the operator epoch-revocation kill-lever + F2.5 scheduler-launch gate) has failed
**five** whole-design binding revisions. Rev5's independent binding re-review
(`CODEX-C6-REV5-BINDING-REVIEW-20260924.md`, subject `f68ccf91`, baseline `f1f409ef`)
returned **REQUEST_REVISION — not freeze-eligible** with five HIGH findings. Crucially, the
review confirmed the two *hardest* design ideas are **SOUND**:

- the **one-lock serialization proof** — `authorize_launch` under the same exclusive
  `epoch.lock` as `apply_bump` totally-orders launch against bump (rev5 §3.3, Finding 1 "the
  shared-lock ordering is sound");
- **in-principal TEG execution** — the provider `urlopen()` running inside the dedicated TEG
  principal so no launch capability crosses back to the caller (rev5 §3.2, Finding 2 "the TEG
  direction is correct").

What keeps failing is not the ideas — it is that the **monolithic** design keeps colliding with
the LANDED code (wrong transport surface, wrong CLI verbs, wrong group memberships) and tries to
freeze **too much at once**. Every one of the five findings is a place where the single-freeze
packet asserted something the anchored tree does not support.

**Owner decision (2026-09-24): re-scope C6 into small, individually-freezable slices.** There is
NO urgency — the live mechanism-test risk is already reverted at `f1f409ef` (PR #333, merge
`785ff50b` / revert `2ef1406e`): the baseline is dormant (gate env removed, sole owner key
`revoked`, authority running but with no admissible signer). This document is the **decomposition +
per-slice charter**. It authorizes nothing; each slice gets its own design → independent binding
review → freeze → default-OFF build, one at a time.

### 0.1 Verified landed-code facts (each finding checked against `f1f409ef`)

The reviewer's five findings are all **factually correct at the anchor**. Verified in this
worktree against `f1f409ef`:

| # | Reviewer claim | Verified landed fact |
|---|---|---|
| 1 | The authority transport recognizes only `read-epoch` / `bump`; `authorize_launch` cannot be reached; single-use token consume is undefined. | `scripts/ai/lib/revocation_epoch_transport.py` `build_env_handler().handler()` accepts **only** `{"op":"read-epoch"}` and `{"bump":{...}}` (lines ~283/290). `serve()` (line ~128) is a generic loop; the handler owns dispatch. No `authorize_launch` op, no launch ledger, no consume verb anywhere. |
| 2 | `aq-revocation-epoch-clients` is NOT TEG-only; ALA + C2-SCI principals also hold it; rev5's claimed c2 line-122 shared-UID removal does not exist. | Members of `aq-revocation-epoch-clients`: `primaryUser` (`revocation-epoch-authority.nix:111`), the **ALA** service principal (`lease-signing-authority.nix:76` — `extraGroups=["aq-lease-signing-clients" "aq-revocation-epoch-clients"]`), the **C2-SCI** issuer principal (`c2-scheduler-context-issuer.nix:114` — `extraGroups=["aq-c2-scheduler-context-clients" "aq-revocation-epoch-clients"]`), and the authority's own user (`:102`, to chgrp the socket). `c2-scheduler-context-issuer.nix:122` is a group **declaration** (`users.groups.aq-revocation-epoch-clients = {};`), NOT a `primaryUser` membership — rev5's claimed "coordination edit removing a shared-UID revocation membership" there is editing nothing. Deleting `authority:111` removes only `primaryUser`; ALA + C2-SCI still reach the socket. `SO_PEERCRED` is log-only today (`serve()` passes it "for LOGGING only"). |
| 3 | The offline owner-key ceremony has no callable submission path; the CLI verb is `build` not `prepare`; `submit` writes 0700 authority state; `bump` uses a host private key + needs the group. | `scripts/ai/aq-epoch-bump` verbs are **`build`** (unsigned request, prints bytes-to-sign — rev5 wrongly calls this `prepare`), **`submit --signed`** (calls `apply_bump` **in-process** against `--epoch-path`/`--ledger-dir`, which are the authority's `0700` StateDirectory the owner UID cannot write), and **`bump`** (one-shot: reads/signs with a **host private-key file** — violates "private key never on host" — then submits `{"bump":request}` over the UDS, requiring `aq-revocation-epoch-clients` membership). After a TEG-only group narrowing, no offline-signed doc has an authorized route to the running authority. |
| 4 | W1 retry / dual-index recovery non-deterministic despite the claimed `aborted→intent` transition. | `apply_bump` (`scripts/ai/lib/revocation_epoch.py:609`) runs under `_acquire_epoch_lock` (`:549`, `fcntl.flock LOCK_EX` on `epoch.lock`) → `_write_epoch_atomic` (`:564`). rev5 §2.2 rewrites the journal to `aborted` but step-2 still does `O_CREAT|O_EXCL` on the same journal pathname (tombstone present) → the identical retry cannot re-create it and cannot "actually bump"; partial dual-index rollback and orphan-index→journal reconciliation are unspecified. |
| 5 | Deferring enforceable TEG network confinement to C4 is not acceptable under rev5's activation order; a URL is not an OS boundary; C4-before-C6 vs C4-blocked-on-C6 contradiction. | rev5 §3.2 scopes TEG egress "to the provider URL(s)" (a routing target, not an OS boundary; AF_INET reachable) and §6 orders the C6 flag-enable **before** C4. `DESIGN-PACKET.md §8` resequence (owner-ratified 2026-07-29) orders **C4 before C6**; `C4-ACTIVATION-READINESS-20260806.md` says C4 freeze is **blocked on** the C6 intervention lever. Contradiction is real; §5 below resolves it. |

### 0.2 Ground rules for every slice (inherited HARD constraints)

- **Design/planning only.** No slice in this document is authorized to build, freeze, activate,
  bump the epoch, emit provider traffic, or flip a flag. Each slice is designed → independently
  binding-reviewed → frozen → built default-OFF, individually.
- **Fail-closed, no standing authority.** Every unavailable/malformed/racing read returns a typed
  deny (never `0`, never fail-open). No capability is a standing grant; the launch token is
  single-use and expiring; the owner key is offline-held and never a host/`/run/secrets` secret.
- **Off-is-inert byte-parity.** With `CAPABILITY_SCHEDULER_LEASE_GATE=0` (the `f1f409ef` default),
  every legacy request keeps its exact current call trace; no new op is reachable.
- **Small enough to freeze.** Each slice closes exactly ONE reviewer finding and edits a bounded,
  enumerated file set with its own acceptance + freeze criteria.
- **Activation safety-net.** The landed dead-man auto-revert guard (`scripts/ai/lib/activation_guard.py`,
  `scripts/ai/aq-activation-guard`, `nix/modules/services/activation-auto-revert-guard.nix`,
  default-OFF) is the safety-net for the eventual gate flip. The revert is **flag-based** (remove
  `CAPABILITY_SCHEDULER_LEASE_GATE` + rebuild), **never** an epoch bump (the bump is
  offline-owner-signed and cannot be auto-run by the sweep). C6-main does not modify the guard.

### 0.3 rev5's proven parts — RETAINED as the per-slice design basis (do not re-derive)

To ensure the five failed revisions' *sound* work is not lost, the following rev5 components are
carried forward as the normative design basis for their slices. Cite rev5 `f68ccf91` when each
slice is designed:

- **The one-lock serialization proof** (rev5 §3.3): `authorize_launch` and `apply_bump` both take
  the authority's single exclusive `epoch.lock`, so they are totally ordered; a token issued
  under-lock at `epoch==E` implies any bump to `E+1` is ordered strictly-before (→ deny, no I/O)
  or strictly-after (→ "already-starting", executor fence). **→ design basis for C6a.**
- **In-principal TEG execution** (rev5 §3.2): the provider `urlopen()` executes inside the TEG
  principal; the caller receives only response *bytes*; no launch capability crosses back.
  **→ design basis for C6b.**
- **The dormant-baseline / P-F4 monotonic-advance reasoning** (rev5 §0.1, §6): the freeze binds the
  rev-4 allowlist (mechtest revoked, no active key); P-F4 is an activation-time public-only
  monotonic advance that does not mutate frozen code bytes. **→ design basis for C6c activation.**
- **The recover-before-listen barrier + two-independent-uniqueness-index shape** (rev5 §2.2):
  correct in intent; C6d fixes the `aborted→intent` reuse and the rollback/reconciliation gaps.
  **→ design basis for C6d.**
- **The authority-unavailable posture** (rev5 §3.5, DESIGN-PACKET §9): deny-closed + LOUD alert,
  never total DoS. **→ cross-cutting basis for all slices.**

---

## 1. Slice C6a — Authority-transport `authorize_launch` + single-use launch-token consume

**Closes reviewer Finding 1 (HIGH).**

**Scope.** Extend the *actual* authority socket handler with a new `authorize_launch` operation
and back it with a `revocation_epoch.authorize_launch()` that runs under the SAME exclusive
`epoch.lock` as `apply_bump` (rev5 §3.3 serialization proof — the retained sound core). Define the
**atomic single-use launch-token ledger transition** rev5 left undefined: `issue → consume`, each
`O_CREAT|O_EXCL|O_NOFOLLOW` + `fsync(file)`+`fsync(dir)`, the token bound to `{nonce,
context_digest, task_id, task_revision, epoch, gateway_instance, issued_at, deadline≤250ms}`, plus
an explicit **consume** operation (verifier + duplicate-consume serialization under the lock) so
two provider-start attempts cannot reuse one token. Add the launch-ledger StateDirectory and the
recovery-before-listen ordering in the authority `ExecStart` (shared machinery with C6d).

**Exact landed files edited.**
- `scripts/ai/lib/revocation_epoch_transport.py` — add the `authorize_launch` op to
  `build_env_handler().handler()` (today only `read-epoch` / `bump`).
- `scripts/ai/lib/revocation_epoch.py` — new `authorize_launch()` under `_acquire_epoch_lock`;
  single-use launch-authorization ledger + `consume()` verb.
- `nix/modules/services/revocation-epoch-authority.nix` — launch-ledger StateDirectory
  (ownership/mode) + recover-before-`listen()` ExecStart ordering.
- EXTEND `scripts/testing/test-revocation-epoch.py` — serialization + single-use + expiry vectors.

**Dependencies / order.** Requires **C6d** (the recover-before-listen barrier + StateDir/ExecStart
machinery it shares). The *consumer* of the token is the TEG (C6b), but C6a defines the consume
**contract**; C6b wires the consumer. → C6a lands after C6d, before C6b.

**Acceptance + freeze criteria.** Serialization proof reproduced against `apply_bump` (one lock,
total order); token is single-use (duplicate consume denies); ≤250 ms deadline enforced;
context/gateway/task-revision binding enforced (wrong-inode/wrong-task/wrong-gateway/wrong-context
deny); `authorize_launch` reachable over the transport; **gate-OFF byte-parity** (op inert/unreachable
when disabled). Freeze binds candidate hashes + the retained rev5 §3.3 proof.

**Owner activation needed?** **No.** Build is default-OFF; the op is inert until gate-ON; no epoch
bump. (Gate-ON activation is C6b/C6e's concern.)

---

## 2. Slice C6b — TEG-exclusive launch authorization + in-principal provider execution

**Closes reviewer Finding 2 (HIGH).**

**Scope.** Make `authorize_launch` reachable **only** by the TEG principal, correctly accounting for
the fact that the ALA (`lease-signing-authority.nix:76`) and C2-SCI
(`c2-scheduler-context-issuer.nix:114`) principals **also** hold `aq-revocation-epoch-clients`
(this **corrects rev5's false claim** that deleting `authority:111` + editing `c2:122` makes the
socket TEG-only). Design and choose between:
- **(A) op-specific authoritative `SO_PEERCRED` check** on `authorize_launch` (peer creds are
  log-only today) admitting only the TEG uid/gid, while `read-epoch`/`bump` stay group-gated; OR
- **(B) a dedicated launch socket + dedicated `aq-revocation-launch-clients` group** that ONLY the
  TEG joins, leaving the existing `aq-revocation-epoch-clients` socket for read-epoch/bump.

**Preserve a least-privileged epoch-READ path** for ALA + C2-SCI (they legitimately `read-epoch`
for their own stale-lease checks). Also lands the **in-principal provider execution** boundary
(rev5 §3.2, retained sound core): the TEG owns `urlopen()` and returns only response *bytes*; no
token/lease/context crosses back to the caller.

**Exact landed files edited.**
- NEW `scripts/ai/lib/dispatch_gateway.py` — TEG adapter: private ALA→C2 clients, the
  `authorize_launch` client + token consume, gateway-owned lifecycle CAS record, in-principal
  provider-execution adapter.
- NEW `nix/modules/services/dispatch-gateway.nix` — dedicated TEG principal, public untrusted
  submission socket, private client memberships, launch-client membership (or launch-group per
  option B), `enable=false`.
- EDIT `nix/modules/services/revocation-epoch-authority.nix` — the op-peer-check (A) or dedicated
  launch socket/group (B). **Do NOT** perform the rev5 c2 line-122 "shared-UID removal" (no such
  membership exists). Removing `primaryUser` from `aq-revocation-epoch-clients` (`:111`) is
  optional and does not by itself achieve TEG-exclusivity — the op-check/launch-group does.
- EDIT `scripts/ai/lib/dispatch.py` — gate-ON lease-bearing path submits envelope to the TEG,
  receives response bytes; gate-OFF byte-parity.
- EDIT `scripts/ai/lib/slot_queue.py` — accept context only from the TEG in-process handoff;
  `held→launch_authorized` recorded as downstream bookkeeping of the C6a fence.
- NEW `scripts/testing/test-dispatch-gateway.py`.

**Dependencies / order.** Requires **C6a** (the `authorize_launch` op + consume contract).
Critical path after C6a.

**Acceptance + freeze criteria.** Proven that the shared owner UID **and** the ALA + C2-SCI
principals cannot obtain a launch token, while all three retain (or, for the shared UID, do not
need) the least-privileged `read-epoch` path; the TEG principal can; caller receives only provider
response bytes (no token/lease/context in reply or telemetry); gate-OFF byte-parity.

**Owner activation needed?** Build default-OFF (`enable=false`). **Gate-ON flag-flip is a later
owner activation**, HARD-gated on C6e's egress resolution + the auto-revert guard armed.

---

## 3. Slice C6c — Callable offline owner-key submission path (the C4 intervention lever)

**Closes reviewer Finding 3 (HIGH) / rev4 Finding 4.**

**Scope.** Reconcile the ACTUAL `aq-epoch-bump` verbs with the offline-key model and inventory a
real, callable **prepare → offline-sign → submit-to-authority** courier path with **no host private
key** and **no owner-UID access to the 0700 authority StateDirectory**. Facts to reconcile
(verified §0.1): the design's `prepare` is really **`build`**; **`submit --signed`** calls
`apply_bump` in-process against the authority's `0700` dirs (owner cannot write); **`bump`** reaches
the socket but signs with a **host** private key. Design decision: add an offline
`submit --signed --socket <path>` path on `aq-epoch-bump` that sends a pre-signed
`{"bump": <signed doc>}` to the running authority over its control socket **without** reading any
host private key and **without** touching the 0700 StateDirectory (the authority applies the
verified bump itself). Decide the owner's socket access relative to C6b's group model — keep an
owner-bump path (read+bump) **separate** from the TEG launch group C6b introduces, so narrowing the
launch surface does not sever the operator kill-lever.

**Exact landed files edited.**
- `scripts/ai/aq-epoch-bump` — add offline `submit --signed --socket` (no host key); correct the
  `build`/`submit`/`bump` reconciliation; the `bump` host-key one-shot is documented as
  NOT the offline model's path.
- `config/env-contract.yaml` — the fixed authority socket reference for owner submission.
- Possibly `nix/modules/services/revocation-epoch-authority.nix` — an owner-bump membership kept
  distinct from the TEG launch surface (coordinated with C6b).

**Dependencies / order.** Requires the authority reachable (C6a/C6d) and a decided group model
(C6b). **This slice completes the C4 freeze prerequisite** (the "C6 intervention lever", §5).

**Acceptance + freeze criteria.** The owner can produce an offline signature and DELIVER it to the
running authority through an authorized path with no host private key and no owner-UID 0700 access;
revoked/unknown/non-monotonic keys deny; the lever is observably `operational` vs
`none(revoked-only)` vs `unavailable` on the dashboard.

**Owner activation needed?** **Yes — P-F4** (owner OFFLINE keygen + public-only monotonic allowlist
advance rev-4→rev-5 adding `owner-2026-09 status:active`, per rev5 §2.3/§6) is an activation-time
owner act. The code build is default-OFF/dormant; until P-F4 the lever is observably
non-operational.

---

## 4. Slice C6d — Deterministic journal recovery (foundation slice)

**Closes reviewer Finding 4 (HIGH) / rev4 Finding 5.**

**Scope.** The recoverable write-ahead intent journal in `revocation_epoch.py` + authority
StateDirectories, fixing the three gaps rev5 left open:
1. **Atomic `aborted → intent` reuse via a new attempt-generation path** so an `O_EXCL` retry can
   actually bump (rev5's tombstone at the same journal pathname blocked the identical retry).
2. **Partial dual-index rollback** — if `by-request-id` reserves but `by-idempotency-key`
   conflicts, roll back the request-id index immediately.
3. **Orphan-index → journal reconciliation algorithm** (not merely iterating non-terminal journal
   entries): indexes whose target journal does not exist must be reconciled.
Two independent `O_EXCL` uniqueness indexes (`by-request-id/`, `by-idempotency-key/`); the a–i
crash matrix (rev5 §2.2); the **recover()-before-listen** barrier enforced in the authority
`ExecStart` (shared with C6a).

**Exact landed files edited.**
- `scripts/ai/lib/revocation_epoch.py` — `recover()` + `aborted→intent` attempt-generation + dual-
  index rollback + orphan reconciliation.
- `nix/modules/services/revocation-epoch-authority.nix` — `journal/`, `by-request-id/`,
  `by-idempotency-key/` StateDirectories + recover-before-`listen()` ExecStart ordering (shared
  with C6a).
- EXTEND `scripts/testing/test-revocation-epoch.py` — the a–i crash-injection matrix.

**Dependencies / order.** **Foundation slice — lands first.** C6a's launch-ledger recovery and the
recover-before-listen barrier + authority StateDir/ExecStart edits build directly on this. Root of
the critical path.

**Acceptance + freeze criteria.** Deterministic W1 reuse (an identical signed request that never
committed actually bumps on retry — never `DENY_REPLAY`); W2 receipt reconstruction; partial-
reservation and orphan-index cases recovered; each of the a–i crash vectors yields exactly-once
idempotent receipt or a typed `quarantined`; recover completes before the socket accepts.

**Owner activation needed?** **No.** Pure durability/recovery hardening of the already-landed epoch
primitive; default-OFF; no bump.

---

## 5. Slice C6e — Interim egress boundary + C4↔C6 ordering resolution

**Closes reviewer Finding 5 (HIGH).**

### 5.1 The C4↔C6 ordering resolution (unambiguous)

The contradiction is between:
- **DESIGN-PACKET §8 resequence (owner-ratified 2026-07-29):** `C4 (network profiles) → … → C6`
  — **C4 before C6.**
- **C4-ACTIVATION-READINESS-20260806 + C6-ACTIVATION-READINESS-20260806:** C4's *freeze* is
  **blocked on the C6 intervention lever** — **C6 (lever) before C4.**
- **rev5 §6:** orders the C6 flag-enable **before** C4 (C4 as successor).

**Resolution — the contradiction dissolves once "C6" is disambiguated into the two scopes the two
documents actually mean:**

1. The **"C6 intervention lever"** that C4's freeze prerequisite names = the *operator epoch-bump
   kill-switch control surface* (authority reachable + a callable owner submission path + a durable
   recoverable epoch). **= C6d + C6a + C6c.** These are **genuine C4 pre-requisites** and land
   **BEFORE C4**. C4 opens network egress and requires the ability to *bump the epoch to revoke an
   over-scoped lease before widening the network* (C4 §4/§8) — that ability is exactly this lever.

2. The **"C6 scheduler-launch seam whose egress needs C4's network profiles"** that the
   DESIGN-PACKET §8 resequence orders after C4 = the *TEG launch fence + in-principal execution +
   the TEG's provider egress*. **= C6b + C6e's egress enforcement.** These may be **built**
   (default-OFF) before C4, but their **activation** (gate-ON, which turns on TEG egress) is
   HARD-gated behind an enforceable OS network boundary.

**Therefore the two "orderings" are both true and non-contradictory:** C6-kill-lever
(C6d+C6a+C6c) **before** C4; C6-TEG-egress-activation (C6b+C6e) **after** C4 (or after an interim
boundary). rev5 §6's "C6 flag-enable before C4" is **superseded** for the TEG-egress activation
specifically; the kill-lever sub-slices satisfy C4's freeze prerequisite without any gate flip.

### 5.2 The egress mechanism decision

A provider URL is a routing target, not an OS boundary (Finding 5). C6e must therefore do ONE of:
- **(Primary, recommended) Make C4 a HARD pre-activation gate for TEG egress.** The TEG service
  stays `enable=false` / gate-OFF until C4's network profile confines it. C6b builds; TEG egress
  activates only once C4 lands.
- **(Fallback, if C4 slips) Freeze an enforceable interim egress boundary** for the TEG principal:
  a dedicated **network namespace + nftables/firewall policy that DENIES every non-provider
  destination** (an OS boundary, declared in `dispatch-gateway.nix`), so the TEG can activate ahead
  of full C4.

**Recommendation:** default to (Primary) with (Fallback) authorized as the escape hatch, since the
auto-revert guard (§0.2) already covers the gate-flip risk and there is no urgency.

**Exact landed files edited.**
- `nix/modules/services/dispatch-gateway.nix` — the C4-gate hook OR the interim netns/nftables
  deny-all-non-provider egress declaration.
- `config/env-contract.yaml` — TEG egress reference.
- This decomposition document is the normative ordering-resolution artifact.

**Dependencies / order.** Requires **C6b** (the TEG principal must exist to confine it). **Gates the
TEG gate-ON activation** (not the build). Coordinates with C4.

**Acceptance + freeze criteria.** No TEG lease-bearing egress activation is possible without either
C4's confining profile in force OR the interim netns/firewall boundary denying every non-provider
destination; the ordering resolution in §5.1 is reflected in the C4 and C6 activation-readiness
docs (a follow-up doc-sync, not code).

**Owner activation needed?** The TEG **gate-ON flag-flip** is the owner activation, guarded by the
auto-revert guard + the §5.2 egress boundary.

---

## 6. Dependency-ordered sequence + critical path

```
            ┌─────────────────────────── C4 freeze prerequisite MET here ───────────────────────────┐
            │                                                                                        │
  C6d  ───▶ C6a  ───▶ C6c  ══(operator epoch-bump kill-lever = "C6 intervention lever")═══▶  [ C4 freeze eligible ]
   │          │
   │          └───▶ C6b  ───▶ C6e  ══(TEG launch fence + egress)══▶  [ C4 lands / interim boundary ]  ──▶ TEG gate-ON activation
   │                                                                                                        (auto-revert guard armed)
   └─ (recovery machinery + authority StateDir/ExecStart barrier: reused by C6a)
```

Dependency-ordered build sequence (each: design → independent binding review → freeze → default-OFF build):

1. **C6d** — deterministic journal recovery (foundation; establishes recover-before-listen +
   StateDirs that C6a reuses). *No owner activation.*
2. **C6a** — `authorize_launch` op + single-use launch-ledger + consume (uses C6d's barrier).
   *No owner activation.*
3. **C6c** — callable offline owner submission path. **Completes the C4 freeze prerequisite.**
   *Owner activation = P-F4 (offline keygen + public-only allowlist rev-5 advance) at its own
   activation time.*
4. **C6b** — TEG-exclusive `authorize_launch` + in-principal execution. *Build default-OFF; gate-ON
   is a later owner act gated by C6e.*
5. **C6e** — interim egress boundary + C4↔C6 ordering resolution; **gates TEG gate-ON activation**.

**Critical paths:**
- **To unblock C4's freeze (the near-term milestone):** `C6d → C6a → C6c`. C6c completing IS the
  event that makes C4 freeze-eligible.
- **To full C6 scheduler-seam activation:** `C6d → C6a → C6b → C6e` (+ C4, or the interim boundary).

C6b and C6c both fan out from C6a and can be designed in parallel once C6a is frozen (C6b needs the
consume contract; C6c needs the group model C6b decides — so if run in parallel, C6c's group
decision must consume C6b's group model as a bounded input, or C6b's group model is fixed first).

---

## 7. Decomposition decisions for the reviewer / owner to confirm

1. **Slice boundaries = the five findings.** C6a↔F1, C6b↔F2, C6c↔F3, C6d↔F4, C6e↔F5. One finding
   per slice; each independently freezable. **Confirm this is the intended granularity** (vs., e.g.,
   folding C6a+C6b into one "launch-fence" slice — rejected here because F1 is transport/serialize
   and F2 is principal/boundary, with different freeze surfaces).

2. **C6d lands first as the foundation slice** (not C6a), because the recover-before-listen barrier
   + authority StateDirectory/ExecStart edits are shared machinery that C6a's launch-ledger
   recovery builds on. **Confirm C6d-first ordering.**

3. **C4↔C6 ordering resolution (§5.1):** "C6" splits into the *intervention lever*
   (C6d+C6a+C6c, **before C4**) and the *TEG egress seam* (C6b+C6e, activation **after C4 / interim
   boundary**). This makes both "C4-before-C6" (DESIGN-PACKET §8) and "C6-lever-before-C4"
   (C4/C6 readiness) simultaneously true and **supersedes rev5 §6's** "C6 flag-enable before C4"
   for TEG-egress activation only. **Confirm this reading** — it is the crux and needs an explicit
   owner/reviewer nod, plus a follow-up sync into the C4 + C6 activation-readiness docs.

4. **Egress mechanism (§5.2):** recommend C4-as-HARD-pre-activation-gate (Primary) with a frozen
   interim netns/nftables deny-all-non-provider boundary (Fallback). **Confirm the Primary/Fallback
   choice** (given no urgency, Primary alone may suffice).

5. **C6b group mechanism (§2):** op-specific authoritative `SO_PEERCRED` check (A) vs a dedicated
   launch socket/group (B). Left as an in-slice design choice; flag if the owner has a preference
   (B is cleaner — it keeps the existing read/bump socket untouched and avoids making a whole
   socket's peer check authoritative).

6. **rev5 corrections carried in:** (a) the CLI verb is `build`, not `prepare`; (b)
   `c2-scheduler-context-issuer.nix:122` has no shared-UID revocation membership to remove; (c)
   removing `primaryUser` from `aq-revocation-epoch-clients` does **not** by itself achieve
   TEG-exclusivity (ALA + C2-SCI remain). **Confirm these corrections are accepted** so the failed
   assertions are not re-introduced.

---

**RECORD: PREPARED_ONLY decomposition. No implementation, freeze, activation, epoch bump, provider
traffic, deployment, or flag flip is authorized. Each slice C6a–e requires its own design →
independent binding review → hash-bound freeze → default-OFF build, one at a time. rev5
(`f68ccf91`) proven components (§0.3) are the retained design basis; its monolithic single-freeze
scope is superseded by this decomposition.**
