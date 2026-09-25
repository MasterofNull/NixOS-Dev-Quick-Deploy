---
title: "Foundation C — C6a: Authority-transport `authorize_launch` op + single-use launch-token consume (on the C6-S launch socket; SAME-epoch.lock total ordering vs apply_bump; exactly-once issue→consume; op-specific TEG SO_PEERCRED peer check)"
slice: "C6a (fans out from C6-S in parallel with C6c — attaches the launch op + single-use ledger to the frozen launch socket)"
status: "PREPARED_ONLY — authorizes NOTHING (no build, no freeze, no activation, no epoch bump, no provider traffic, no flag flip). Design + authorization note only."
revision: 2
kind: "design-only"
implementation_authorization: "NONE"
activation_authorization: "NONE"
base_head: "f1f409ef97f73fb6ae152a297ba0c0367e30bf22"
parent_decomposition: ".agents/plans/aqos-foundation-c/C6-DECOMPOSITION-20260924.md (factory/c6-decomposition-v2) §3 — C6a slice spec; §0.4 Service Coverage Contract; §8 build order; §0.3 rev5 §3.3 serialization proof retained as C6a's design basis"
frozen_predecessor_socket: ".agents/plans/aqos-foundation-c/C6-S-DESIGN-AND-AUTHORIZATION.md (factory/c6s-design-v2, rev2) — the frozen two-socket topology (mechanism B): launch.sock + aq-revocation-launch-clients group, control-socket byte-parity, deny-all launch stub, serve_multi(). C6a attaches its op to this frozen surface and MUST satisfy C6-S §7 item 8 (BINDING forward-condition — the op-specific TEG SO_PEERCRED peer check)."
frozen_predecessor_recovery: ".agents/plans/aqos-foundation-c/C6d-DESIGN-AND-AUTHORIZATION.md (factory/c6d-design-v2, rev2) — recover-before-listen barrier + StateDir/Type=notify model + apply_bump/build_env_handler signatures. C6a's launch-ledger recovery composes ON TOP of C6d's recover() and must not contradict it."
closes_finding: "CODEX-C6-REV5-BINDING-REVIEW-20260924.md Finding 1 (HIGH) — authorize_launch was not implementable from the frozen inventory (transport recognized only read-epoch/bump), AND the launch token was NOT specified single-use (no atomic consume op, no ledger state transition, no verifier, no duplicate-consume serialization)."
authoring_role: "architect (design/planning only)"
owner_activation_needed: "NO — default-safe; the op builds dormant. It is reachable only over the C6-S launch socket, which has NO admissible client until C6b adds the TEG to aq-revocation-launch-clients; and the op-specific TEG SO_PEERCRED peer check fails closed until the TEG principal identity is provisioned (C6b). No epoch bump, no flag, no key, no owner act."
build_order: "C6d → C6-S → {C6a ∥ C6c} → [AMEND-C4] → C4 → C6b → C6e (decomposition §8). C6a fans out from C6-S in parallel with C6c; its only consumer is the TEG (C6b). C6a is NOT part of the C4 kill-lever (decomposition §0.3, §7.2 item 3)."
---

# Foundation C — C6a: `authorize_launch` op + single-use launch-token consume

## 0. What this slice is, and why it is not the kill-lever

C6a is the slice that fans out from **C6-S** (in parallel with C6c) and closes **rev5 Finding 1
(HIGH)**. It adds the `authorize_launch` **operation** on the **launch socket C6-S froze**, backs it
with a `revocation_epoch.authorize_launch()` that runs under the **same exclusive `epoch.lock` as
`apply_bump`** (rev5 §3.3 serialization proof — the retained sound core, decomposition §0.3), and —
the part rev5 left undefined — specifies the **atomic single-use launch-token ledger**: an
`issue → consume` state machine with an `O_CREAT|O_EXCL|O_NOFOLLOW` test-and-set consume, a verifier,
and duplicate-consume serialization, so two provider-start attempts can never reuse one token.

C6a is **NOT part of the operator kill-lever.** The decomposition (§0.3, §7.2 item 3) is explicit: the
C6 intervention lever C4 depends on is **C6d + C6-S + C6c** (the durable, reachable, owner-authorized
epoch-bump path). C6a shares the authority's lock/state machinery but its **only consumer is the TEG
(C6b)** — a launch-authorization op with no live consumer is not part of the kill-lever. C6a therefore
does not unblock C4 and is not on that critical path.

**This is design-only and PREPARED_ONLY.** It authorizes no implementation, no freeze, no build, no
activation, no epoch bump, no flag flip. The baseline at `f1f409ef` is dormant (sole owner key
`revoked`, gate env absent, authority `enable = false;`); C6a does not change that. C6a **builds
default-OFF**, and the op is doubly-inert until later slices: it is reachable only over the C6-S launch
socket, which has **no admissible client** until the TEG joins `aq-revocation-launch-clients` in C6b,
and the op-specific TEG peer check (§2.3) **fails closed** until the TEG principal identity is
provisioned (C6b). Gate-ON is C6b/C6e's concern, HARD-gated behind C4 in force.

---

## 1. Current anchored baseline (verified against `f1f409ef`)

Every SHA-256 below was computed at `f1f409ef97f73fb6ae152a297ba0c0367e30bf22`. Every file:line
citation was verified against HEAD in this worktree (`command git show f1f409ef:<path>`); the working
tree equals the anchor for every source path cited (only sibling design docs differ). C6a builds
**on top of C6d and C6-S**: the SHA-256 values below are the `f1f409ef` base bytes those two slices
also anchor to; the freeze reproduces them and additionally binds C6a's candidate hashes *after*
C6d + C6-S have landed (their edits to these same files are the frozen predecessor surface C6a
extends, not a conflict — §2.4 states the exact composition).

| Existing path | SHA-256 (`f1f409ef`) | C6a role |
|---|---|---|
| `scripts/ai/lib/revocation_epoch_transport.py` | `066b30c326898d6ef8e4ab085cf82ce131bb9812b08a61993de86b0812a6be28` | **EDIT.** Replace **C6-S's deny-all launch-socket stub** with a real launch handler that dispatches `authorize_launch` and `consume_launch`. Today (`f1f409ef`) `handler()` (`:282`) recognizes only `{"op":"read-epoch"}` (`:283`) and `{"bump":{...}}` (`:290`→`apply_bump` at `:296`) — the exact Finding-1 defect (no launch op is reachable). C6a adds a **new** `build_launch_handler()` (sibling of `build_env_handler()` at `:246`) whose `handler(request, peer_creds)` dispatches `authorize_launch`/`consume_launch`; the launch listener that C6-S's `serve_multi()` binds gets **this** handler instead of the stub. The **control** handler `build_env_handler()` (`:246`) and its `apply_bump` call site (`:296`) are UNCHANGED — control-socket byte-parity (C6-S §7 item 5) holds. `serve()` (`:128`) and C6-S's `serve_multi()` are NOT modified — C6a only supplies the launch listener's handler. The handler already receives `peer_creds` (passed by the accept loop at `:177`, threaded to `handler()`'s second arg at `:282`), so the op-specific TEG `SO_PEERCRED` check (§2.3) reads them directly — no transport-loop change needed. |
| `scripts/ai/lib/revocation_epoch.py` | `d6c3a3b60a04fde15b5fe9a619f6fc290110776bbdefc35c6de21dcd594a75e6` | **EDIT.** Add `authorize_launch()` and `consume_launch()`, each under `_acquire_epoch_lock` (`:549`, `fcntl.flock LOCK_EX` on `epoch.lock` at `:553`) — the **same** exclusive lock `apply_bump` (`:609`, acquire at `:642`, release at `:690`) holds — and the single-use launch-authorization ledger (`issue → consume`/`expired`) built from the same `O_CREAT|O_EXCL|O_NOFOLLOW` + `fsync(file)` + `fsync(dir)` test-and-set primitive as `DurableReplayLedger.check_and_record` (`:505`/`:507`). Both are **total functions** (never raise — mirrors `apply_bump`'s contract, `:616-618`). `apply_bump`, `verify_bump` (`:432`), `read_epoch` (`:206`), `_write_epoch_atomic` (`:564`), and `DurableReplayLedger` (`:474`) signatures are **unchanged** (C6d §1 precondition preserved). |
| `nix/modules/services/revocation-epoch-authority.nix` | `b539e5de6dd89eb4fd93ed2119055ad9440897b1c408a98f6c23d9ded0db0172` | **EDIT.** Add the launch-ledger StateDirectory subtree (`launch-ledger/issued/`, `launch-ledger/consumed/`, `launch-ledger/expired/`, each `0700 aq-revocation-epoch-authority`) as `systemd.tmpfiles.rules` alongside the existing `ledger/` rule (`:125`) and C6d's `journal/`,`by-request-id/`,`by-idempotency-key/` rules, under `statePath` (`/var/lib/aq-revocation-epoch-authority`, `:84`). Add a documented `AQ_REVOCATION_LAUNCH_TEG_UID` env reference to the unit `Environment` (`:146-152`), **empty by default** (fail-closed — §2.3); C6b provisions it. **No new socket** (C6-S declared `launch.sock`); **reuse C6d's recover-before-`listen()` ordering** (`Type=notify`, readiness after recovery — §5). `enable = false;`, control socket, `aq-revocation-epoch-clients`/`aq-revocation-launch-clients` membership, and hardening (`NoNewPrivileges`/`ProtectSystem="strict"`/`RestrictAddressFamilies=["AF_UNIX"]`, `:159`/`:161`/`:166`) all UNCHANGED. |
| `config/env-contract.yaml` | *(binds landed shape)* | **EDIT.** Document `AQ_REVOCATION_LAUNCH_TEG_UID` (default **empty** — no admissible peer until C6b) alongside the existing `AQ_REVOCATION_EPOCH_SOCKET_PATH` (`:1339`) and the `AQ_REVOCATION_LAUNCH_SOCKET_PATH`/`_CLIENT_GROUP` references C6-S adds. This is a principal-identity reference, **not** a capability flag (C6a introduces no capability flag). |
| `scripts/testing/test-revocation-epoch.py` | `40cf094c73b3298698097e1d0988ca8fd187df1772b1b9beb4aa3c26a0ac59df` | **EXTEND** (494 lines today) with the serialization, single-use exactly-once, ≤250 ms expiry, epoch-supersession, binding-mismatch, TEG-peer-check, and crash-recovery vectors (§3.5, §4, §5). |
| `dashboard/backend/api/routes/aistack.py` | *(binds landed shape)* | **EDIT.** Add a compact live-backed `result["revocation_launch_authorization"]` section, modelled on the ALA section (`result["ala"]` at `:2104`, `ala_flag` at `:2091`) / C2-SCI section (`result["c2_scheduler_context_issuer"]` at `:2133`). States: `op_present\|op_absent`, `ledger_durable` (bool), `teg_peer_check_enforced` (bool). No hard-coded healthy state, no `--` placeholder; rendered inside the existing Foundation-C authority health block — no new card. |
| `assets/dashboard.js` | *(binds landed shape)* | **EDIT (minimal, folded).** Read `revocation_launch_authorization` and render the op-present/ledger-durable/TEG-peer-check rows inside the existing Foundation-C authority health block (no new card). |
| `scripts/testing/test-c6a-authorize-launch-service-coverage.py` | *(NEW)* | **NEW.** Cross-surface Service-Coverage test mirroring `scripts/testing/test-c2-sci-service-coverage.py` (§8). |
| `nix/modules/services/default.nix` | `7873bff56d33f7d798bafa4cc1ecceebdb10975d1ae62c83e48fdcafe94e0ecc` | **NO EDIT.** Already imports `./revocation-epoch-authority.nix` at **line 26** — the authority (and therefore the launch op C6a attaches to it) is already wired into the system. C6a binds this landed import (Service-Coverage row 2); it adds **no new module**. |
| `config/validation-check-registry.json` | *(binds landed shape)* | **EDIT.** Register the new `c6a-authorize-launch-coverage` behavioral check (§8), modelled on `c2-sci-service-coverage` (`:1398`) / `ala-service-coverage` (`:1376`). |
| `scripts/testing/harness_qa/phases/phase0.py` | *(binds landed shape)* | **EDIT.** Add the authority-op integration probe via `results.extend(...)`, modelled on `_check_intent_classifier_coverage` (`:1325`, check id `0.10.10`). Allocate the **next-free id `0.10.53`** (§8). |
| `scripts/ai/_aq-qa-bash` | *(binds landed shape)* | **EDIT.** Mirror the same `0.10.53` check id in the bash harness, modelled on the `0.10.10` `_check` line (`:1635`), per the dual-harness check-id contract. |
| `scripts/ai/lib/revocation_epoch_transport.py` (C6-S deny-all stub) | *(bound via C6-S freeze)* | **CITED, replaced.** C6-S §1/§3 ship the launch listener with a **deny-all stub handler** ("a well-formed request over it yields a typed deny … until C6a lands", C6-S §6). C6a is the slice that replaces that stub — this is the frozen forward-condition C6a fulfills. |

**Landed reality that C6a changes (verified, `f1f409ef`).**

- The authority transport `handler()` (`revocation_epoch_transport.py:282-296`) dispatches **only**
  `read-epoch` (`:283`) and `bump` (`:290`→`apply_bump` at `:296`). **There is no `authorize_launch`
  op, no launch handler, and no launch-token ledger anywhere in the landed code** — the exact
  Finding-1 defect ("a TEG request cannot reach the proposed `revocation_epoch.authorize_launch`").
- `apply_bump` (`revocation_epoch.py:609`) runs its whole transaction under one exclusive
  `epoch.lock` — `_acquire_epoch_lock` (`:642`, `flock LOCK_EX` at `:553`) → `read_epoch` (`:648`
  region) → expected-epoch compare → `ledger.check_and_record` → `_write_epoch_atomic` (`:564`) →
  release in `finally` (`:690`). This is the lock `authorize_launch` will share for total ordering
  (§4).
- The single-use durable primitive already in the module is `DurableReplayLedger.check_and_record`
  (`:505`): a single `os.O_WRONLY | os.O_CREAT | os.O_EXCL | O_NOFOLLOW` create (`:507`) +
  `fsync(file)` + `fsync(dir)` — "exactly one of two [racers] wins" (`:478`). C6a's launch-token
  consume reuses this exact test-and-set shape (§3.4).
- The launch **token** in rev5 §3.3 carried `{task/context/gateway binding, ≤250 ms expiry}` but rev5
  "defines no atomic consume operation, ledger state transition, verifier, or duplicate-consumption
  serialization" (Finding 1) — "two provider-start attempts can therefore reuse the same returned
  token." C6a defines all of it (§3).

The final freeze must reproduce every listed base hash, confirm the launch-ledger StateDirs and the
`AQ_REVOCATION_LAUNCH_TEG_UID` reference are **absent at the base**, bind the revised candidate
hashes, reject all other changed paths, and stop on HEAD drift.

---

## 2. The `authorize_launch` op + the BINDING op-specific TEG peer check

### 2.1 Two ops on the C6-S launch socket

C6a replaces C6-S's deny-all launch stub with a launch handler dispatching exactly two ops on
`launch.sock` (the control socket keeps `read-epoch`/`bump` only, byte-for-byte — §2.4):

| Op | Direction | Under `epoch.lock`? | Purpose |
|---|---|---|---|
| `authorize_launch` | TEG → authority | **Yes** (§4) | **Issue** a single-use launch token bound to `{context_digest, task_id, task_revision, epoch=current, gateway_instance}`; the authority mints `nonce`, `issued_at`, `deadline`; writes the durable `issued/<nonce>` record; returns the token. |
| `consume_launch` | TEG → authority | **Yes** (§4) | **Consume** the token exactly once (atomic `issued → consumed` test-and-set + verifier); a launch proceeds **iff** this returns `ok`. |

Both ops are un-signed (rev5 §3.2 — the token is minted by the authority under its lock, not
owner-signed). Neither mutates the epoch; both READ it under the lock (§4). Neither is reachable while
the launch socket has no admissible client (until C6b) or while the TEG peer check is unresolved (§2.3).

### 2.2 Request / response shapes (typed-deny discipline, never raise, never `0`)

- `authorize_launch` request: `{"op":"authorize_launch", "context_digest":<hex>, "task_id":<str>,
  "task_revision":<int>, "gateway_instance":<str>}`. Response on success:
  `{"ok":true, "token":{"nonce":<hex-256>, "context_digest", "task_id", "task_revision",
  "epoch":<current>, "gateway_instance", "issued_at":<iso>, "deadline_ms":<≤250>}}`. On any
  fault: `{"ok":false, "reason":DENY_*, "detail":..., "token":null}`.
- `consume_launch` request: `{"op":"consume_launch", "nonce":<hex>, "context_digest", "task_id",
  "task_revision", "epoch", "gateway_instance"}`. Response: `{"ok":true, "receipt":{...}}` on the
  single winning consume, else `{"ok":false, "reason":DENY_*, ...}`.
- New typed denials joining the existing `DENY_*` family (`revocation_epoch.py:303`+): the malformed
  guards `DENY_LAUNCH_MALFORMED`; the peer-check `DENY_NOT_TEG_PEER` (§2.3); the consume verifier
  `DENY_LAUNCH_UNKNOWN` (no `issued/<nonce>`), `DENY_LAUNCH_ALREADY_CONSUMED` (the `O_EXCL` loser,
  §3.4), `DENY_LAUNCH_EXPIRED` (deadline elapsed, §3.3), `DENY_LAUNCH_EPOCH_SUPERSEDED` (a bump
  advanced the epoch after issuance, §4), `DENY_LAUNCH_BINDING_MISMATCH` (wrong
  context/task/revision/gateway/epoch, §3.2); plus the inherited `DENY_LOCK_UNAVAILABLE` (`:305`) on
  a failed lock acquire. Every deny is fail-closed: it mutates no epoch, releases no other token's
  state, and never returns `0` or a fabricated success.

### 2.3 The BINDING op-specific TEG `SO_PEERCRED` peer check (inherited MUST from C6-S §7 item 8)

**This design cites the C6-S freeze and satisfies its BINDING forward-condition.** C6-S §2.3 / §7 item
8 established: because `authorize_launch` is **un-signed** and the **authority-user is itself a
member of `aq-revocation-launch-clients`** (a chgrp-only role so `serve()`/`serve_multi()` can
`chown`-to-group the launch inode — C6-S §2.2 item 3), the kernel `0660` group boundary excludes
ALA/C2-SCI/owner but does **NOT** exclude the authority's own UID. A self-launch surface via the
authority UID would become live the moment C6a attaches a reachable op — so C6-S made it a **MUST**,
not a recommendation, that **C6a implement an operation-specific `SO_PEERCRED` peer check on
`authorize_launch` verifying the connecting peer's uid is the TEG principal** before honoring the
request. (Wording corrected to **uid-only** — the mechanism in item 2 below has never compared gid;
consistent with C6-S §7.8's own uid-only formulation of this MUST.)

**C6a satisfies this MUST as follows:**

1. **Applied to BOTH launch ops.** The check runs at the top of `build_launch_handler()`'s
   `handler(request, peer_creds)` — before any dispatch — for **`authorize_launch` AND
   `consume_launch`** (a launch that could not be *authorized* by a non-TEG peer must equally not be
   *consumed* by one). `peer_creds` is `(pid, uid, gid)` from `get_peer_credentials()`
   (`revocation_epoch_transport.py:69`), already threaded to the handler's second argument by the
   accept loop (`:177`); C6a reads it directly — no transport-loop edit.
2. **Verifies uid is the TEG principal, not merely "any launch-group member."** The check is
   **uid-only** (there is no gid comparison anywhere in this mechanism — see the corrected wording
   above). The expected TEG identity is resolved from `AQ_REVOCATION_LAUNCH_TEG_UID` (the unit
   `Environment` reference C6a documents, provisioned by C6b's `dispatch-gateway.nix`). The check
   requires `peer_creds is not None AND peer_creds[1] == <resolved TEG uid>`; anything else —
   including the **authority-user's own UID** (the chgrp-role launch-group member) and a `None`
   peer-creds read — returns `DENY_NOT_TEG_PEER`. This closes the residual self-launch gap C6-S
   flagged: the authority-user is in the launch group but is **not** the TEG, so it is denied.
3. **Fail-closed until C6b.** At C6a build time the TEG principal does not yet exist, so
   `AQ_REVOCATION_LAUNCH_TEG_UID` is **empty/unresolvable** (env-contract default empty). An
   unresolved expected-uid makes the equality check deny **every** peer — the op is inert even if a
   process reached the socket. C6b (which adds the TEG to `aq-revocation-launch-clients` and
   provisions the TEG uid) is what makes the op reachable-by-the-TEG-only. This is why C6a "builds
   dormant" and needs no owner activation.
4. **`SO_PEERCRED` remains the authoritative check for THIS op only.** For the control socket,
   C6-S/§2.4 keep `SO_PEERCRED` log-only (`transport:163-171` untouched). C6a elevates it to
   authoritative **only inside the launch handler**, for the two un-signed launch ops, exactly as
   C6-S's forward-condition requires — it does not change the control-socket posture.
5. **BINDING forward-condition for C6b — the TEG uid MUST be distinct from the authority-user uid.**
   The check in item 2 admits a peer **iff** `peer_creds[1] == resolved TEG uid`. That closes the
   self-launch surface **only if** the uid C6b provisions into `AQ_REVOCATION_LAUNCH_TEG_UID` is
   **different from** the uid of the `aq-revocation-epoch-authority` service user. If C6b were ever to
   provision the TEG identity as (or aliased to) the authority-user's own uid, the equality check would
   admit the authority-user — the exact self-launch surface this peer check exists to close reopens.
   C6a therefore records this as a **MUST C6b inherits**: the TEG MUST run as its own distinct
   principal, and C6b's freeze must verify `AQ_REVOCATION_LAUNCH_TEG_UID != <aq-revocation-epoch-authority uid>`
   before that value is provisioned live.

A C6a build that omits this peer check does not satisfy C6-S's freeze forward-condition and must be
revised before it may build on C6-S (C6-S §7 item 8). A C6b build that provisions
`AQ_REVOCATION_LAUNCH_TEG_UID` equal to the authority-user's uid does not satisfy the forward-condition
in item 5 above and must be revised before C6b may activate the TEG peer.

### 2.4 Control-socket byte-parity + `serve()`/`serve_multi()` untouched (inherited from C6-S)

C6a honors every C6-S transport invariant: it edits **only** the launch handler (replacing the
deny-all stub with `build_launch_handler()`); it does **not** touch `build_env_handler()` (`:246`,
read-epoch/bump), `apply_bump`'s call site (`:296`), `read_frame()` framing (`:86`), `serve()`
(`:128`, C6-S left byte-for-byte unchanged), or C6-S's new `serve_multi()`. A control-socket client
observes identical bytes on the wire (C6-S §7 item 5 control-socket byte-parity). The launch
listener's handler is the only thing that changes from "deny-all" to "the two launch ops," and only
when the authority is enabled and the TEG peer resolves.

---

## 3. The single-use launch token (fields, ≤250 ms deadline, atomic consume, exactly-once)

This section defines everything rev5 Finding 1 found undefined: the token fields (already in rev5
§3.3, restated for completeness), **and** the atomic consume op + ledger state transition + verifier +
duplicate-consume serialization that make the token single-use.

### 3.1 Token fields (bound at issuance, under `epoch.lock`)

`{nonce, context_digest, task_id, task_revision, epoch, gateway_instance, issued_at, deadline_ms}`:

- `nonce` — 256-bit authority-minted random (`secrets.token_hex(32)`), the ledger key; collision-free,
  so one `issued/<nonce>` record per token.
- `context_digest` — the digest the TEG presents for the scheduler context being launched (binds the
  exact context/inode the launch is for — the "wrong-inode/wrong-context deny" of the freeze criteria).
- `task_id`, `task_revision` — bind the exact task + its revision (wrong-task / stale-revision deny).
- `epoch` — set to `read_epoch()` **under the lock** at issuance (§4). The revocation binding: a
  bump after issuance advances the live epoch, so consume's `epoch` re-check denies a superseded token.
- `gateway_instance` — binds the issuing TEG instance (wrong-gateway deny).
- `issued_at` — authority clock at issuance (`datetime.now(timezone.utc)`).
- `deadline_ms` — **≤ 250 ms** (decomposition §3 / rev5 §3.3). Consume is valid only while
  `now ≤ issued_at + deadline_ms`; else `DENY_LAUNCH_EXPIRED`.

The token is a **capability with an expiry and a binding, not a standing grant** (decomposition §0.2).

### 3.2 The verifier (evaluated at consume, before the atomic transition)

`consume_launch` verifies, in order (each a typed deny, never raise):
1. **peer is the TEG** (§2.3) — else `DENY_NOT_TEG_PEER`.
2. **`issued/<nonce>` exists** — else `DENY_LAUNCH_UNKNOWN` (no such token, or already reaped).
3. **binding matches** — the presented `{context_digest, task_id, task_revision, gateway_instance,
   epoch}` equals the stored `issued/<nonce>` record — else `DENY_LAUNCH_BINDING_MISMATCH`
   (wrong-context/wrong-inode, wrong-task, stale-revision, wrong-gateway, wrong-epoch).
4. **not expired** — `now ≤ issued_at + deadline_ms` — else `DENY_LAUNCH_EXPIRED`.
5. **not superseded** — `read_epoch()` (under the lock) `== token.epoch` — else
   `DENY_LAUNCH_EPOCH_SUPERSEDED` (a bump/revocation advanced the epoch after issuance; §4).
6. **atomic single-use transition** — §3.4. Only if all of 1-5 pass.

### 3.3 The ledger state machine

Launch-ledger StateDirectory under `statePath` (`/var/lib/aq-revocation-epoch-authority`):
`launch-ledger/issued/<nonce>` (the issued record), `launch-ledger/consumed/<nonce>` (the consume
tombstone), `launch-ledger/expired/<nonce>` (the terminal-expired tombstone, §5). States and the only
transitions:

```
   (none) --authorize_launch--> issued --consume_launch(atomic,verified)--> consumed  (terminal, success)
                                   |
                                   +--deadline elapsed / crash-survived (recover)------> expired  (terminal, unconsumable)
```

`issued → consumed` is the exactly-once success path; `issued → expired` is the fail-closed path (a
token that is never consumed within its ≤250 ms deadline, or that survives a crash — §5). There is **no
`consumed → *` and no `expired → *`**: both are terminal. A token is launchable **iff** a single
`consume_launch` performs the `issued → consumed` transition and returns `ok`.

### 3.4 The atomic consume (`issued → consumed`) — the duplicate-consume serialization

The transition is a single `O_CREAT|O_EXCL|O_NOFOLLOW` create of `launch-ledger/consumed/<nonce>`
(+ `fsync(file)` + `fsync(dir)`) — the **identical** test-and-set primitive as
`DurableReplayLedger.check_and_record` (`revocation_epoch.py:505`/`:507`): a single atomic kernel
syscall in which **exactly one** of any number of concurrent creators wins and every other gets
`EEXIST`. Sequence, all under `epoch.lock`:
1. verifier steps 1-5 (§3.2) pass;
2. `O_EXCL`-create `consumed/<nonce>` recording the consume receipt;
   - **success (file created)** → this is the sole winning consume → return `{"ok":true, "receipt":…}`;
     the launch may proceed **exactly once**;
   - **`EEXIST`** → a prior consume already claimed this token → `DENY_LAUNCH_ALREADY_CONSUMED`; no
     launch, no epoch mutation, no second receipt.
3. best-effort audit projection (mirrors `_append_audit_receipt` at `:586` — a projection failure
   marks the event, never the transaction; the `consumed/<nonce>` tombstone is authoritative).

### 3.5 Exactly-once proof

**At most once.** The `issued → consumed` transition is the `O_EXCL` create at §3.4 step 2. `O_EXCL` is
atomic and idempotent-preventing: for any `nonce`, at most one create ever succeeds; all others fault
`EEXIST → DENY_LAUNCH_ALREADY_CONSUMED`. A launch proceeds **iff** consume returns `ok` (§3.3), so at
most one provider start per token — even under two simultaneous provider-start attempts. Two layers
enforce this: **(a)** both `consume_launch` calls hold the same exclusive `epoch.lock` (§4), so they are
serialized in-process — the second sees `consumed/<nonce>` already present at its own verifier step 2/§3.4
and denies; **(b)** the `O_EXCL` create is the durable, cross-process, **cross-restart** guarantee — even
if two authority processes ever raced (they cannot, given the single unit + the lock), the kernel admits
exactly one. Belt (lock) and suspenders (`O_EXCL`) — matching the module's own single-use discipline.

**Not after revocation, not after deadline.** Even a first-and-only consume is refused if the epoch
advanced after issuance (`DENY_LAUNCH_EPOCH_SUPERSEDED`, §3.2 step 5 / §4) or the ≤250 ms deadline
elapsed (`DENY_LAUNCH_EXPIRED`, step 4). So the transition is not merely "≤ once" but "≤ once **and**
only while the launch is still live and un-revoked."

**At least the legitimate once.** A single well-formed `consume_launch` from the TEG, with matching
binding, within deadline, at the unchanged epoch, performs the `issued → consumed` create and returns
`ok`. The token is thus consumable exactly once by its legitimate holder and never again — the precise
single-use guarantee rev5 Finding 1 required.

---

## 4. Same-`epoch.lock` total-ordering proof vs `apply_bump`

**Claim (rev5 §3.3, retained sound core — Finding 1 confirmed this ordering "is sound").**
`authorize_launch` and `apply_bump` are **totally ordered** because both acquire the **same** single
exclusive `epoch.lock`. C6a implements it as follows and reproduces the proof at freeze:

- `apply_bump` acquires `epoch.lock` via `_acquire_epoch_lock` (`revocation_epoch.py:642`,
  `fcntl.flock(fd, LOCK_EX)` on the `epoch.lock` inode at `:553`), does its whole read→CAS→write
  transaction, and releases in `finally` (`:690`).
- C6a's `authorize_launch()` acquires the **same** `_acquire_epoch_lock(epoch_path_p)` (same lock
  inode — `epoch.lock` beside `epoch`), then: `read_epoch()` → bind `token.epoch = current` → durably
  write `issued/<nonce>` → release. `consume_launch()` likewise re-reads `read_epoch()` under the same
  lock for the supersession check (§3.2 step 5).

**Because both hold `LOCK_EX` on one inode, exactly one holds it at a time.** Therefore:
- **A bump committed *before* issuance is read-and-denied.** If `apply_bump` commits and advances the
  epoch first, it releases the lock; `authorize_launch` then acquires it, `read_epoch()` returns the
  **new** epoch, and the token binds `epoch = new`. Any launch whose bound context targeted the old
  epoch fails the binding check (§3.2 step 3, wrong-epoch), and any already-issued old-epoch token
  fails consume's supersession check (step 5). The revocation is honored — no launch is authorized
  against a superseded epoch. (rev5 §3.3: "a bump committed before issuance is read and denied.")
- **A bump *after* issuance is ordered strictly after the declared launch point.** If
  `authorize_launch` acquires the lock first, it reads `current`, writes `issued/<nonce>` bound to
  `epoch = current`, and releases — the **declared launch point** is this under-lock issuance commit. A
  bump arriving now must wait for the lock, so it is serialized strictly **after** issuance. When it
  commits, it advances the epoch; the outstanding token's later `consume_launch` re-reads the epoch
  under the lock, sees it advanced, and denies `DENY_LAUNCH_EPOCH_SUPERSEDED` — the post-issuance bump
  revokes the not-yet-consumed launch. (rev5 §3.3: "a bump after issuance is ordered after the declared
  launch point.")
- **No unordered bump between the under-lock read and the token-issuance commit.** The `read_epoch()`
  and the `issued/<nonce>` durable write happen **within one uninterrupted `epoch.lock` hold**, so no
  `apply_bump` can interleave between them (it would need the lock, which `authorize_launch` holds).
  There is no window in which the epoch changes after `authorize_launch` reads it but before it commits
  the token. (rev5 §3.3: "no unordered bump between the under-lock read and token-issuance commit.")

The freeze reproduces this proof against the landed `apply_bump` lock (`:642`/`:553`/`:690`) and the
new `authorize_launch`/`consume_launch` lock acquisitions, and the extended `test-revocation-epoch.py`
asserts the three orderings above with an interleaved bump/authorize/consume harness (§8 probe).

---

## 5. Launch-ledger recovery composed with C6d's recover-before-listen

C6a adds durable state (`launch-ledger/`), so its crash-consistency **must compose with C6d's
recover-before-listen barrier** (C6d §3.3/§3.4) and must not contradict it (C6d's `recover()`,
journal, two uniqueness indexes, `Type=notify`, and readiness semantics are all untouched by C6a).

### 5.1 The composition rule

C6d changed the transport `__main__` (`revocation_epoch_transport.py:301-309`) to
**acquire `epoch.lock` → `revocation_epoch.recover()` → release → serve** (via C6-S's `serve_multi()`),
with `sd_notify(READY=1)` only after recovery. **C6a adds a second recovery pass —
`recover_launch_ledger()` — that runs in the SAME under-lock recovery phase, after C6d's `recover()`
and before either socket binds.** Concretely the barrier becomes:
`acquire epoch.lock → recover() [C6d journal] → recover_launch_ledger() [C6a launch ledger] → release
→ serve_multi() binds control+launch → listen(both) → sd_notify(READY=1) → accept`. Both passes share
the one lock and the one recovery phase; **no socket accepts before both complete** (C6d §3.4
preserved — the launch socket in particular must not accept an `authorize_launch`/`consume_launch`
against an unreconciled launch ledger). This does not alter C6d's `__main__` shape beyond adding one
sibling call in the recovery phase; it adds no param to `apply_bump`/`recover()`.

### 5.2 The deterministic issued-but-not-consumed-across-a-crash resolution

**The case the task requires defined:** a token was `issued/<nonce>` but the authority crashed before
any `consume_launch`. Deterministic resolution — **fail-closed, no auto-launch, no auto-bump.**

**The correctness argument rests on the unconditional under-lock-before-accept sweep, NOT on a
recovery-timing claim.** An earlier revision of this section justified expiring surviving `issued`
records by asserting "no crash-plus-restart of a systemd unit completes in under 250 ms" — i.e. that
the elapsed time alone proves every surviving token's deadline has already passed. That timing claim
is **not safe to hang correctness on**: a warm restart of an already-code-cached `Type=notify` Python
unit (default `RestartSec` on the order of 100 ms, with `sd_notify(READY=1)` gated only on the small
recovery pass) can plausibly complete in well under 250 ms, so "elapsed time > deadline" is not
guaranteed at every recovery. **The design does not need that guarantee, and never did:**
`recover_launch_ledger()`, described below, transitions **every** surviving `issued`-without-`consumed`
record to terminal `expired` **unconditionally** — it does not read the clock, does not recheck
`issued_at + deadline_ms`, and does not branch on elapsed time. An unconditional sweep can only ever
**deny** a launch (move a record to a state from which no consume can ever succeed); it can never
*authorize* one, and it never expires a token that recovery leaves in a state where it remains
legitimately consumable, because recovery — not the deadline check — is what decides the outcome for
every surviving `issued` record before any socket accepts. Fail-closed correctness therefore follows
from the sweep being unconditional and running strictly before accept, independent of how fast or slow
the crash-to-restart interval was.

**The ≤ 250 ms deadline is a live-path freshness bound, not a recovery-safety assumption.** On the live
(non-crash) path, `deadline_ms ≤ 250` bounds how long a legitimately-issued, not-yet-consumed token
stays consumable — that is its only job (§3.1/§3.2 step 4, `DENY_LAUNCH_EXPIRED`). It plays **no role**
in why recovery is safe; recovery is safe because the sweep is unconditional, not because the deadline
happened to have elapsed by the time recovery runs.

**Build requirement (BINDING).** The implementation of `recover_launch_ledger()` MUST expire every
surviving `issued/<nonce>` with no `consumed/<nonce>` **unconditionally** — the transition to
`launch-ledger/expired/<nonce>` MUST NOT be conditioned on re-checking `issued_at + deadline_ms`,
current wall-clock time, or any other elapsed-time computation. A build that guards the sweep behind an
elapsed-time recheck (e.g. "only expire if `now > issued_at + deadline_ms`") reintroduces exactly the
timing dependency this section rejects and does not satisfy this design.

`recover_launch_ledger()`, under `epoch.lock`, sweeps `launch-ledger/issued/`:
- For every `issued/<nonce>` with **no** `consumed/<nonce>`: the record is **unconditionally**
  transitioned to terminal `launch-ledger/expired/<nonce>` (`O_EXCL`-create `expired/<nonce>` +
  `fsync`; then `unlink` `issued/<nonce>` + `fsync(dir)`) — no clock read, no deadline recheck. The
  token is thereby made **unconsumable by construction** (any subsequent `consume_launch` for that
  nonce denies `DENY_LAUNCH_UNKNOWN`, since `issued/<nonce>` no longer exists — §3.2 step 2).
  Operator-visible (an expired-across-crash count), never a silent launch, never `0`.
  - **Independent second layer:** even setting the unconditional sweep aside, the launch ledger binds
    `token.epoch`, and a crash+restart that spanned any revocation would also fail consume's
    supersession check (§3.2 step 5). The resolution does **not depend** on this second layer — the
    unconditional sweep alone is sufficient and is what the build requirement above binds.
- For every `issued/<nonce>` **with** a `consumed/<nonce>` present (a crash after the atomic consume
  but before the best-effort audit projection, §3.4 step 3): the consume already durably won; the
  transition is complete. `recover()` reconciles the audit projection best-effort and leaves the
  terminal `consumed` state — **exactly-once preserved** (no re-launch, no re-consume).
- A `consumed/<nonce>` or `expired/<nonce>` with **no** `issued/<nonce>` (issued unlinked after the
  terminal tombstone) is already terminal — left as-is.

**Determinism.** Every crash interleaving of the `issue → {consume | expire}` machine maps to exactly
one terminal outcome (`consumed` once, or `expired`), decided **unconditionally**, before the socket
accepts. No issued-but-not-consumed token ever survives a crash into a live, consumable launch
authorization — the fail-closed guarantee holds regardless of how quickly the unit restarted. This
mirrors C6d's "each crash point uniquely determines the outcome" discipline (C6d §5) for the launch
ledger, and reuses C6d's `O_EXCL` + `fsync(file)`+`fsync(dir)` durability-barrier ordering.

### 5.3 No contradiction with C6d

C6a does not touch `recover()`, the journal, the two uniqueness indexes, `Type=notify`, or C6d's
readiness semantics — it adds a **sibling** launch-ledger recovery pass inside the same barrier, and a
sibling StateDirectory subtree. C6d's `apply_bump`/`build_env_handler` signatures and its
`__main__`-only transport-edit surface are preserved (C6a's transport edit is the launch handler,
already anticipated by C6-S's stub-replacement forward-condition — not a change to C6d's `__main__`
recovery wiring; C6a only inserts the `recover_launch_ledger()` call beside C6d's `recover()`).

**BINDING freeze-time verification requirement (composition with C6d's frozen `__main__` region).**
§5.1 discloses that C6a's `recover_launch_ledger()` insertion lands **inside** C6d's declared
`EDIT (__main__ only)` region (`revocation_epoch_transport.py:301-309`) — the same block C6d's own
freeze declared as its frozen edit surface. C6a and C6d therefore both touch that one `__main__` block,
and the freeze MUST NOT accept this on design prose alone. At freeze/land time, the freeze MUST verify,
against C6d's **landed** `__main__` recovery sequence (not this design's description of it), that
C6a's insertion is **purely additive**:
- it adds exactly one sibling call — `recover_launch_ledger()` — inside the single `epoch.lock` hold,
  strictly after C6d's `recover()` returns and strictly before `serve_multi()` binds or `listen()`s
  either socket;
- it does not alter C6d's `recover()` body, the journal, the two uniqueness indexes
  (by-request-id/by-idempotency-key), `Type=notify`, or the `sd_notify(READY=1)`-after-recovery
  readiness gate;
- it does not alter the `apply_bump` or `build_env_handler` signatures C6d's §1 precondition binds.

This is a landing-order condition, checked against C6d's landed code at C6a's freeze, referencing C6d's
own edit-surface claim — not a restatement of design intent. A C6a freeze that cannot reproduce this
purely-additive diff against C6d's landed `__main__` does not satisfy this requirement and must be
revised before C6a may freeze.

---

## 6. How this closes rev5 Finding 1 (all facets)

| Finding 1 facet | Landed / rev5 gap | C6a closure |
|---|---|---|
| **`authorize_launch` not reachable from the frozen inventory** | The landed transport handler recognizes only `read-epoch`/`bump` (`transport:283`/`:290`); rev5 did not make that file an EDIT surface, so a TEG request could never reach `revocation_epoch.authorize_launch`. | §1/§2.1: C6a **edits** `revocation_epoch_transport.py` to add `build_launch_handler()` dispatching `authorize_launch`/`consume_launch` on the **C6-S launch socket** (replacing C6-S's deny-all stub). The op is now reachable — over the launch socket only, by the TEG only (§2.3). |
| **Token not specified single-use — no atomic consume op** | rev5 §3.3 created an issuance ledger entry and said the token "must be consumed" but defined **no** atomic consume operation. | §2.1/§3.4: a distinct `consume_launch` op performs an atomic `issued → consumed` `O_EXCL` test-and-set. |
| **No ledger state transition** | rev5 defined no ledger state machine. | §3.3: `issued → consumed` (success terminal) / `issued → expired` (fail-closed terminal), both terminal, one launchable transition. |
| **No verifier** | rev5 defined no consume-time verifier. | §3.2: a six-step verifier (TEG peer, existence, binding, expiry, epoch-supersession, then the atomic transition). |
| **No duplicate-consumption serialization — two starts can reuse one token** | rev5: "Two provider-start attempts can therefore reuse the same returned token." | §3.4/§3.5: the `O_EXCL` create serializes duplicate consumes (loser → `DENY_LAUNCH_ALREADY_CONSUMED`), and both consumes hold the same `epoch.lock` — exactly-once proven (§3.5). |
| **Shared-lock ordering (the sound part) must be preserved** | rev5 §3.3's one-lock ordering was confirmed sound but needed the reachable op to realize it. | §4: `authorize_launch`/`consume_launch` acquire the **same** `epoch.lock` as `apply_bump` (`:642`/`:553`) — the three orderings (bump-before read-and-denied; bump-after ordered-after; no unordered bump between read and issuance) reproduced and test-asserted. |
| **≤250 ms expiry + task/context/gateway binding** | rev5 provided these fields but "not single-use enforcement." | §3.1/§3.2: fields retained AND made enforceable — binding-mismatch and expiry are consume-time denials, on top of the single-use `O_EXCL`. |

---

## 7. Exclusions

C6a touches **only** the files in §1. Explicitly excluded (each is a later slice or out of scope):

- The **launch socket / `aq-revocation-launch-clients` group / control-socket byte-parity /
  `serve_multi()`** topology — **C6-S** (frozen; C6a attaches its op to it and cites its freeze, but
  declares, moves, or re-modes **no** socket or group, and does **not** modify `serve()`/`serve_multi()`).
- The **deterministic journal recovery / `recover()` / two-index shape / `Type=notify`** — **C6d**
  (C6a composes on top; §5 — it adds only a sibling launch-ledger recovery pass, changing none of C6d's).
- The **TEG principal joining `aq-revocation-launch-clients`**, `dispatch_gateway.py` /
  `dispatch-gateway.nix`, in-principal provider execution, and **provisioning
  `AQ_REVOCATION_LAUNCH_TEG_UID`** — **C6b** (C6a defines the peer-check *mechanism* and reads the
  reference; it does not add the TEG member or set the uid — until C6b, the op is unreachable and the
  check fails closed).
- The offline owner-key **submission path** / `aq-epoch-bump` verb reconciliation — **C6c** (on the
  C6-S control-socket owner-bump path, which C6a never touches).
- Any owner public-key allowlist change or **epoch bump** — **P-F4** (C6c activation), not C6a. C6a
  neither signs nor submits a bump; it only *reads* the epoch under the lock.
- `slot_queue` / `dispatch.py` scheduler-gate fence, `CAPABILITY_SCHEDULER_LEASE_GATE` gate-flip —
  later C6 (C6b/C6e). C6a introduces **no capability flag**; the op's dormancy comes from the launch
  socket having no admissible client + the fail-closed peer check, not from a gate.
- TEG egress confinement / C4 gate — **C6e / C4**.
- The auto-revert guard (decomposition §0.2 — no C6 slice modifies it).
- Provider invocation, network, DDL, deployment, activation, flag flips.

Any need to touch an excluded path is a **stop condition** requiring a new reviewed design, not
expansion of C6a.

---

## 8. Service-Coverage inventory (decomposition §0.4)

C6a adds a **new public consumer surface** (the `authorize_launch`/`consume_launch` ops) → per §0.4 it
ships a **new** `test-<slice>-service-coverage.py` AND registers a dual-harness integration probe that
exercises **issue → consume → duplicate-deny** (an integration exercise, **not** unit-only — review
Finding 3):

- **env-contract** (row 1) — **NEW reference, no flag.** `AQ_REVOCATION_LAUNCH_TEG_UID` (default
  **empty** — no admissible peer until C6b) added to `config/env-contract.yaml` alongside the existing
  `AQ_REVOCATION_EPOCH_SOCKET_PATH` (`:1339`) and C6-S's launch socket/group references. A
  principal-identity reference, **not** a capability flag — C6a introduces **no** capability flag, so
  the "new flags default `"0"`" rule has nothing to gate.
- **Nix service + import** (row 2) — **bound to the landed import.** `revocation-epoch-authority.nix`
  is already imported at `default.nix:26`; C6a edits that module (launch-ledger StateDirs + the TEG-uid
  env ref) but adds **no new module** and does not touch the import. The module stays `enable = false;`,
  `RestrictAddressFamilies = ["AF_UNIX"]` (`:166`), `NoNewPrivileges`/`ProtectSystem="strict"`
  (`:159`/`:161`) unchanged; the launch op uses the dedicated `aq-revocation-launch-clients` socket
  (C6-S) + the op-specific TEG peer check (§2.3).
- **Durable primitive** (row 3) — **present.** The launch-token consume is an
  `O_CREAT|O_EXCL|O_NOFOLLOW` + `fsync(file)`+`fsync(dir)` test-and-set (§3.4), the same primitive as
  `DurableReplayLedger.check_and_record` (`revocation_epoch.py:505`/`:507`); the coverage test and the
  extended `test-revocation-epoch.py` assert it.
- **Flag-gated call path** (row 4) — **gate-OFF byte-parity holds.** C6a adds no capability flag; the
  op's inertness comes from (a) the authority `enable = false;`, (b) the launch socket having no
  admissible client until C6b, and (c) the fail-closed TEG peer check. When the authority is enabled
  but pre-C6b, every launch request denies (`DENY_NOT_TEG_PEER`), and every `read-epoch`/`bump` trace
  on the control socket is byte-for-byte unchanged (§2.4).
- **Dashboard API + UI** (rows 5, 6) — **minimal, folded, live-backed; no new card.** `aistack.py`
  adds `result["revocation_launch_authorization"]` (modelled on `result["ala"]` at `:2104` /
  `result["c2_scheduler_context_issuer"]` at `:2133`): `op_present\|op_absent` (probed from whether the
  launch handler dispatches the ops, not hard-coded), `ledger_durable` (the launch-ledger StateDirs
  present + `0700`), `teg_peer_check_enforced` (the op-specific check is wired). No hard-coded healthy
  state, no `--` placeholder. `assets/dashboard.js` renders these rows **inside the existing
  Foundation-C authority health block** — no new card (a separate card would duplicate the block
  without a new operator action).
- **Crypto/service tests exist** (row 7) — `test-revocation-epoch.py` EXTENDED (§3.5/§4/§5 vectors);
  the new `test-c6a-authorize-launch-service-coverage.py` is the cross-surface coverage.
- **Integration-check registration** (row 8, NEW, required) — register **`c6a-authorize-launch-coverage`**
  in `config/validation-check-registry.json` (modelled on the `c2-sci-service-coverage` entry at
  `:1398`: `id`, `description`, `trigger_paths` = [`scripts/ai/lib/revocation_epoch.py`,
  `scripts/ai/lib/revocation_epoch_transport.py`, `nix/modules/services/revocation-epoch-authority.nix`,
  `config/env-contract.yaml`, `dashboard/backend/api/routes/aistack.py`, `assets/dashboard.js`,
  `scripts/testing/test-revocation-epoch.py`, `scripts/testing/test-c6a-authorize-launch-service-coverage.py`],
  `command`, `tier:"behavioral"`, `timeout_seconds`, `enabled:true`), **AND** wire the authority-op
  integration probe in **BOTH** harnesses per the dual-harness check-id contract:
  - `scripts/testing/harness_qa/phases/phase0.py` — a new `_check_c6a_authorize_launch_coverage(ctx)`
    returning `CheckResult`, added via `results.extend(...)`, modelled on
    `_check_intent_classifier_coverage` (`:1325`, id `0.10.10`). Allocate the **next-free id
    `0.10.53`**. **Verified at `f1f409ef` the current max id is `0.10.50` in BOTH `phase0.py` and
    `_aq-qa-bash`; the sibling C6d design reserves `0.10.51` and C6-S reserves `0.10.52`, so C6a takes
    `0.10.53`** to avoid a collision when all three land.
  - `scripts/ai/_aq-qa-bash` — the mirror
    `_check 1 "0.10.53" "revocation authorize-launch + single-use consume" …` line, modelled on the
    `0.10.10` entry (`:1635`), per the dual-harness contract.
  - **The probe asserts** (an integration exercise, not just static parsing / unit tests): an
    **`authorize_launch`** issue yields a bound token (correct fields, `epoch = current`,
    `deadline_ms ≤ 250`); a **`consume_launch`** of that token succeeds **exactly once**; a **second**
    `consume_launch` of the same token yields `DENY_LAUNCH_ALREADY_CONSUMED` (the duplicate-deny — the
    core exactly-once assertion); a launch op from a **non-TEG peer** yields `DENY_NOT_TEG_PEER`; an
    expired token (past its ≤250 ms deadline) yields `DENY_LAUNCH_EXPIRED`; a token whose epoch was
    bumped after issuance yields `DENY_LAUNCH_EPOCH_SUPERSEDED`; and the op is reachable **only** over
    the C6-S launch socket (a launch request on the control socket is not dispatched there).

---

## 9. Freeze, authorization, and activation

**Freeze criteria (all must hold):**
1. **Same-lock total ordering reproduced** against `apply_bump` (`revocation_epoch.py:642`/`:553`/
   `:690`): `authorize_launch`/`consume_launch` acquire the same exclusive `epoch.lock`; the three §4
   orderings hold (bump-before read-and-denied; bump-after ordered-after; no unordered bump between the
   under-lock read and token-issuance commit).
2. **Single-use exactly-once** (§3.5): the `issued → consumed` `O_EXCL` transition admits at most one
   consume; a duplicate consume denies `DENY_LAUNCH_ALREADY_CONSUMED`; a legitimate single consume
   within deadline at the unchanged epoch succeeds once.
3. **≤250 ms deadline** enforced (`DENY_LAUNCH_EXPIRED`); **binding** enforced
   (wrong-context/inode, wrong-task, stale-revision, wrong-gateway, wrong-epoch →
   `DENY_LAUNCH_BINDING_MISMATCH`); **epoch supersession** enforced (`DENY_LAUNCH_EPOCH_SUPERSEDED`).
4. **BINDING op-specific TEG `SO_PEERCRED` peer check, uid-only** (§2.3, satisfying C6-S §7 item 8):
   both launch ops verify `peer_creds[1] == resolved TEG uid` (uid-only — no gid comparison); the
   authority-user (chgrp-role launch-group member) and any non-TEG peer and a `None` peer-creds read
   all deny `DENY_NOT_TEG_PEER`; unresolved TEG uid (pre-C6b) denies every peer. This freeze **cites
   the C6-S freeze** and this criterion is the condition C6-S imposed on C6a. **Forward-condition C6b
   inherits** (§2.3 item 5): `AQ_REVOCATION_LAUNCH_TEG_UID` MUST be provisioned distinct from the
   `aq-revocation-epoch-authority` service-user uid — C6b's own freeze must verify this before the TEG
   peer is live, or the self-launch surface this check exists to close reopens.
5. **`authorize_launch`/`consume_launch` reachable over the C6-S launch socket ONLY**; the control
   socket keeps `read-epoch`/`bump` byte-for-byte (§2.4 control-socket byte-parity).
6. **Composes with C6d** (§5, and the BINDING freeze-time verification requirement in §5.3): the
   recovery argument rests on `recover_launch_ledger()` **unconditionally** transitioning every
   surviving `issued`-without-`consumed` record to terminal `expired` — never conditioned on an
   elapsed-time recheck — running under `epoch.lock` in the same recovery phase, after C6d's
   `recover()` and before either socket accepts; the ≤250 ms deadline is a live-path freshness bound
   only, not a recovery-safety assumption. An issued-but-not-consumed token across a crash is thereby
   resolved to terminal `expired` (unconsumable) — never a live launch. The freeze MUST additionally
   verify, against C6d's **landed** `__main__` (not this design's prose), that the
   `recover_launch_ledger()` insertion is purely additive: it adds one sibling call inside the single
   lock hold and does not alter C6d's `recover()`, journal, two uniqueness indexes, `Type=notify`,
   readiness gate, or the `apply_bump`/`build_env_handler` signatures.
7. **Gate-OFF byte-parity — scoped to C6a's own edit** (§8 row 4): the authority ships
   `enable = false;`; when enabled but pre-C6b, every launch request denies and every control-socket
   `read-epoch`/`bump` trace is byte-for-byte identical. `CAPABILITY_SCHEDULER_LEASE_GATE` is out of
   scope (§7).
8. The **`c6a-authorize-launch-coverage` integration check is GREEN in both harnesses** (phase0
   `0.10.53` + bash mirror), exercising issue→consume→duplicate-deny (§8).
9. The freeze binds the exact candidate hashes, reproduces the §1 base hashes, confirms the
   launch-ledger StateDirs and `AQ_REVOCATION_LAUNCH_TEG_UID` are **absent at the base**, rejects all
   other changed paths, and stops on HEAD drift. It also binds the **retained rev5 §3.3 serialization
   proof** (decomposition §0.3) as C6a's design basis.

**Authorization / activation note — C6a needs NO owner activation.** C6a is **default-safe**: the op
**builds dormant**. It is reachable only over the C6-S launch socket, which has **no admissible client
until C6b** adds the TEG to `aq-revocation-launch-clients`; and even then the op-specific TEG peer
check (§2.3) **fails closed** until `AQ_REVOCATION_LAUNCH_TEG_UID` is provisioned (C6b). C6a performs
**no epoch bump** (it only *reads* the epoch under the lock — the bump is offline-owner-signed and C6a
neither signs nor submits one), flips **no flag** (introduces no capability flag), provisions **no
key**, and opens **no network** (AF_UNIX only, inherited). Enabling the authority unit and adding the
TEG member are separate, later acts C6a neither performs nor depends on. There is **no owner
activation act tied to C6a.** The baseline stays dormant. (Gate-ON of the scheduler seam is C6b/C6e's
concern, HARD-gated behind C4 in force + the auto-revert guard armed — decomposition §3, §6, §8.)

**Dependencies / order.** Requires **C6d** (recover-before-listen + StateDir machinery — §5) and
**C6-S** (the launch socket + `aq-revocation-launch-clients` group + deny-all stub it replaces + the
`serve_multi()` it attaches to + the BINDING peer-check forward-condition it satisfies — §2). **Fans
out from C6-S in parallel with C6c.** Its only consumer is the TEG (**C6b**). C6a is **NOT** part of
the C4 kill-lever (decomposition §0.3, §7.2 item 3) and does not unblock C4.

---

**RECORD: PREPARED_ONLY revision 2. No implementation, freeze, activation, epoch bump, provider
traffic, deployment, restart, network authority, or flag flip is granted by this document. C6a is the
`authorize_launch` + single-use launch-token slice of `C6-DECOMPOSITION-20260924.md` (§3, §8); it
requires its own independent binding review → hash-bound freeze → default-OFF build, per the
decomposition's per-slice contract. This document closes rev5 (`f68ccf91`) Finding 1 (HIGH) at design
level: it makes `authorize_launch` reachable on the C6-S launch socket, defines the atomic single-use
launch-token ledger (`issue → consume`/`expired`, `O_EXCL` test-and-set consume, verifier,
duplicate-consume serialization — exactly-once proven §3.5), reproduces the retained rev5 §3.3
same-`epoch.lock` total-ordering proof vs `apply_bump` (§4), satisfies C6-S §7 item 8's BINDING
op-specific TEG `SO_PEERCRED` peer check (§2.3, uid-only), and composes its launch-ledger recovery with
C6d's recover-before-listen barrier — an issued-but-not-consumed token across a crash resolves
deterministically to terminal `expired` via an **unconditional** sweep, never a live launch, and never
on a recovery-timing assumption (§5.2). It contradicts neither C6-S's frozen transport surface
(`serve()`/`serve_multi()` untouched, control-socket byte-parity, deny-all stub replaced) nor C6d's
`__main__`-only / `apply_bump` / `recover()` model, and binds a BINDING freeze-time verification
requirement that the `recover_launch_ledger()` insertion into C6d's landed `__main__` region is purely
additive (§5.3). The rev5 §3.3 serialization proof it builds on is the retained design basis
(decomposition §0.3).

**Revision 2 (this revision) applies the focused fixes from
`CODEX-C6A-DESIGN-BINDING-REVIEW-20260924.md` (disposition FREEZE-ELIGIBLE, NO HIGH, rev5 Finding 1
CLOSED) against rev1 (`9066e259`, `factory/c6a-design`): **F1 (MEDIUM)** reframes §5.2's recovery
argument off the ≤250 ms recovery-timing claim onto the unconditional under-lock-before-accept sweep,
and adds a BINDING build requirement that the expiry sweep never conditions on elapsed time; **F2
(MEDIUM)** adds a BINDING freeze-time verification requirement in §5.3 that the
`recover_launch_ledger()` insertion into C6d's frozen `__main__` region is purely additive against
C6d's *landed* code; **F3 (LOW)** corrects §2.3's "uid/gid" prose to uid-only, matching the mechanism
and C6-S §7.8; **F4 (LOW)** records a new BINDING forward-condition C6b inherits (§2.3 item 5, §9 item
4) — the TEG uid MUST be provisioned distinct from the authority-user uid; **F6 (informational)**
corrects the `ledger/` tmpfiles anchor from `:126` to `:125` (§1). **F5** (single-use is per-token, not
per-binding) required no change per the review and is unchanged.**
