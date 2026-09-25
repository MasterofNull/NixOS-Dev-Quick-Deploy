---
title: "Foundation C — C6d: Deterministic journal recovery for the revocation-epoch authority (recover-before-listen; crash-safe idempotent epoch-bump journaling)"
slice: "C6d (foundation slice of the C6 decomposition — lands first)"
status: "PREPARED_ONLY — authorizes NOTHING (no build, no freeze, no activation, no epoch bump, no provider traffic, no flag flip). Design + authorization note only."
revision: 1
kind: "design-only"
implementation_authorization: "NONE"
activation_authorization: "NONE"
base_head: "f1f409ef97f73fb6ae152a297ba0c0367e30bf22"
parent_decomposition: ".agents/plans/aqos-foundation-c/C6-DECOMPOSITION-20260924.md (factory/c6-decomposition-v2) §1 — C6d slice spec + §0.4 Service Coverage Contract"
design_basis: "C6-DESIGN-AND-AUTHORIZATION.md rev5 (factory/c6-rev5 @ f68ccf912f07c4a872f17c1cbe6c469eac444350) §2.2 — the recover-before-listen barrier + two-independent-uniqueness-index shape, RETAINED as design basis (decomposition §0.3)"
closes_finding: "CODEX-C6-REV5-BINDING-REVIEW-20260924.md Finding 4 (HIGH) / rev4 Finding 5 — W1 tombstone-blocks-retry, partial dual-index reservation, orphan-index→journal reconciliation, and the undefined startup reconciliation algorithm"
authoring_role: "architect (design/planning only)"
owner_activation_needed: "NO — default-safe durability/recovery hardening; no epoch bump, no flag, no key, no owner act"
build_order: "C6d → C6-S → {C6a ∥ C6c} → [AMEND-C4] → C4 → C6b → C6e (decomposition §8). C6d is the FOUNDATION — it lands first and enables everything else; the recover-before-listen barrier + StateDirs it defines are the shared machinery C6-S, C6a, and C6c reuse."
---

# Foundation C — C6d: Deterministic journal recovery for the revocation-epoch authority

## 0. What this slice is, and why it is first

C6d is the **first, foundation slice** of the freeze-eligible C6 decomposition
(`C6-DECOMPOSITION-20260924.md` §1, §8). It hardens an **already-landed** durability
primitive — it adds **no new public surface**, needs **no owner activation**, and is
**default-safe**. It is the root of the critical path: the `recover()`-before-`listen()`
barrier and the authority StateDirectories it defines are the shared machinery that C6-S
(launch-socket topology), C6a (`authorize_launch` ledger), and C6c (owner submission) all
build on. Nothing downstream can freeze on an unreconciled journal, so C6d lands first.

C6d closes **rev5 Finding 4 (HIGH)** — the last open recovery/durability defect from the
binding re-review (`CODEX-C6-REV5-BINDING-REVIEW-20260924.md`). Finding 4 has four distinct
non-determinism cases (§4 below); this document specifies a single deterministic recovery
algorithm that closes all four, states the exact durability (fsync) ordering, and gives the
crash-consistency argument for each persistence-boundary interleaving.

**This is design-only and PREPARED_ONLY.** It authorizes no implementation, no freeze, no
build, no activation, no epoch bump, no flag flip. The baseline at `f1f409ef` is dormant
(sole owner key `revoked`, gate env absent, authority `enable=false`); C6d does not change
that.

---

## 1. Current anchored baseline (verified against `f1f409ef`)

Every hash below was computed at `f1f409ef97f73fb6ae152a297ba0c0367e30bf22`. Every file:line
citation was verified against HEAD in this worktree.

| Existing path | SHA-256 | C6d role |
|---|---|---|
| `scripts/ai/lib/revocation_epoch.py` | `d6c3a3b60a04fde15b5fe9a619f6fc290110776bbdefc35c6de21dcd594a75e6` | **EDIT.** Holds the primitive C6d replaces: `DurableReplayLedger` (single combined-key marker) + `apply_bump`. C6d adds the write-ahead intent journal, the two independent uniqueness indexes, the `aborted→intent` reuse, and `recover()`. |
| `scripts/ai/lib/revocation_epoch_transport.py` | `066b30c326898d6ef8e4ab085cf82ce131bb9812b08a61993de86b0812a6be28` | **EDIT (`__main__` only).** Its `__main__` (lines 301-309) today does `serve(_sp, build_env_handler())` with **no recovery pass**. C6d makes it run `recover()` to completion before `bind()`/`listen()`, and gates readiness on it. No dispatch/op change (no `authorize_launch` — that is C6a). |
| `nix/modules/services/revocation-epoch-authority.nix` | `b539e5de6dd89eb4fd93ed2119055ad9440897b1c408a98f6c23d9ded0db0172` | **EDIT.** Adds `journal/`, `by-request-id/`, `by-idempotency-key/` StateDirectories (0700, authority-owned) via `systemd.tmpfiles.rules`; adds the recover-before-`listen()` `ExecStart` ordering / readiness. Keeps `enable = false;`, the control socket, and hardening unchanged. |
| `nix/modules/services/default.nix` | `7873bff56d33f7d798bafa4cc1ecceebdb10975d1ae62c83e48fdcafe94e0ecc` | **NO EDIT.** Already imports `./revocation-epoch-authority.nix` at line 26 — the authority is already wired into the system. C6d binds this landed import (Service-Coverage row 2). |
| `scripts/testing/test-revocation-epoch.py` | `40cf094c73b3298698097e1d0988ca8fd187df1772b1b9beb4aa3c26a0ac59df` | **EXTEND** (494 lines today) with the a–i crash-injection matrix (§5). |
| `config/validation-check-registry.json` | *(binds landed shape)* | **EDIT.** Register the new `revocation-epoch-recovery` behavioral check (§6), modelled on the landed `c2-sci-service-coverage` entry (line 1398) / `ala-service-coverage` (line 1376). |
| `scripts/testing/harness_qa/phases/phase0.py` | *(binds landed shape)* | **EDIT.** Add the recovery-determinism probe via `results.extend(...)`, modelled on `_check_intent_classifier_coverage` (line 1325, check id `0.10.10`). |
| `scripts/ai/_aq-qa-bash` | *(binds landed shape)* | **EDIT.** Mirror the same check id in the bash harness, modelled on the `0.10.10` `_check` line (line 1635), per the dual-harness check-id contract. |

**Landed reality that C6d changes (verified).** The authority today uses a **single-index**
`DurableReplayLedger` (`revocation_epoch.py:474-539`): one empty marker per consumed pair,
named `sha256(request_id ∥ "\x00" ∥ idempotency_key)` (`:498-503`), created by
`check_and_record` with `O_CREAT|O_EXCL|O_NOFOLLOW` + `fsync(file)` + `fsync(dir)`
(`:507`, `:523`, `:528`). `apply_bump` (`:609`) runs the whole transaction under one exclusive
`epoch.lock` (`_acquire_epoch_lock:549`, `fcntl.flock LOCK_EX:553`): `verify_bump` (`:633`) →
`read_epoch` (`:648`) → expected-epoch compare (`:652`) → **`ledger.check_and_record`** (`:660`,
records the marker) → on collision `DENY_REPLAY` (`:664`) → **`_write_epoch_atomic`** (`:668`,
temp+`fsync`+`os.replace`+dir `fsync`, `:574`/`:578`/`:581`) → best-effort audit receipt
(`:684`).

The defect is structural and the module **admits it in its own docstring**
(`:620-622`, `:42`): the marker is recorded **before** the epoch write. A crash between
`:660` and the durable completion of `:668` leaves the marker present but the epoch un-advanced;
the identical signed retry then hits the marker at `:660`, returns `DENY_REPLAY` at `:664`, and
**can never bump** — the transaction is permanently wedged. There is **no journal, no
`recover()`, no two-index shape, and no recover-before-listen barrier** in the landed code; the
transport `__main__` (`:301-309`) binds and serves immediately with no reconciliation. rev5 §2.2
*designed* the journal + two-index + recover shape but left the four determinism gaps of
Finding 4 open. C6d designs it correctly.

The final freeze must reproduce every listed hash, confirm the three new StateDirs are absent at
the base, bind the revised packet hash, reject all other changed paths, and stop on HEAD drift.

---

## 2. The journal + two-index primitive (design basis retained from rev5 §2.2)

C6d replaces the "burn a bare combined-key marker, then separately advance the epoch" split with
a single **write-ahead bump-intent journal** that is the authoritative record for the whole
transaction, guarded by **two independent single-use indexes** and finalized before the socket
accepts. This is the rev5 §2.2 shape (decomposition §0.3), corrected on the four points rev5 left
open (§4).

### 2.1 On-disk state (three new StateDirectories, all 0700, authority-owned)

Under the authority StateDirectory root (`/var/lib/aq-revocation-epoch-authority`,
`revocation-epoch-authority.nix:84`):

- `journal/<entry_id>` — **one** journal entry per transaction. `entry_id =
  sha256(request_id ∥ "\x00" ∥ idempotency_key)`, used **only as a filename**; uniqueness is
  enforced by the two indexes below, not by this composite. The entry holds the full intended
  receipt: `{request_id, idempotency_key, actor_key_id, reason_code, old_epoch, new_epoch,
  phase, attempt_gen, issued_at_authority, committed_at?}`.
- `by-request-id/<sha256(request_id)>` — independent uniqueness index for `request_id`.
- `by-idempotency-key/<sha256(idempotency_key)>` — independent uniqueness index for
  `idempotency_key`.

Each index file records the `entry_id` it points at. Two **independent** indexes (not the single
combined marker of `:498-503`) are what make "the same `request_id` reused with a *different*
`idempotency_key` (or the reverse)" a detectable **conflict** rather than a silently-admitted
second entry.

The `journal/`, `by-request-id/`, `by-idempotency-key/` dirs are declared as
`systemd.tmpfiles.rules` mode `0700 aq-revocation-epoch-authority aq-revocation-epoch-authority`
alongside the existing `ledger/` rule (`revocation-epoch-authority.nix:125`).

### 2.2 The journal entry state machine

Phases: `intent → committed` (success), `intent → aborted` (uncommitted, released for reuse).
`attempt_gen` is a monotonically increasing per-`entry_id` retry counter (starts `0`; each
`aborted→intent` reuse increments it). It is **operator-visible** (surfaces a retry count) and
lets `recover()` distinguish a fresh intent from a rewritten one. Terminal states are `committed`
and `aborted`; `intent` is the only non-terminal state.

### 2.3 Migration from the landed single-index ledger

On the dormant `f1f409ef` baseline the `ledger/` directory is **empty**: the sole owner key is
`revoked` and no admissible signer has ever committed a bump, so there are zero markers. C6d
therefore requires **no data migration** — the journal + two indexes supersede
`DurableReplayLedger` with a no-op cutover. **Fail-closed guard:** should a legacy `ledger/`
marker ever be found non-empty at `recover()` (it cannot be on this baseline), it is a
consumed-but-unrecoverable key with no journal entry → typed **`quarantined`** (operator-visible,
never a silent bump, never `0`). A general legacy-marker import path is explicitly **out of
scope** (§7) — it is unnecessary here and would be a separate reviewed slice if ever needed.

---

## 3. The deterministic recovery algorithm

Everything below runs **under the single exclusive `epoch.lock`** (`_acquire_epoch_lock:549`),
so the live `apply_bump` path and the startup `recover()` pass are **totally serialized** — there
is no TOCTOU between reading a journal entry and acting on it, and no concurrent writer.

### 3.1 Live transaction (C6d-hardened `apply_bump`), under `epoch.lock`

0. `verify_bump` (unchanged, `:633`). Deny on any signature/schema failure.
1. `read_epoch()` → `current` (`:648`); typed unavailable deny on malformed/symlink/I-O
   (`resolve_current_epoch` no-follow discipline, `:166`/`:217`) — never `0`.
2. **Reserve both uniqueness identities.** `O_CREAT|O_EXCL|O_NOFOLLOW`-create
   `by-request-id/<H(request_id)>` then `by-idempotency-key/<H(idempotency_key)>`, each
   `fsync(file)`+`fsync(dir)`, each storing `entry_id`.
   - **BOTH newly created** → fresh reservation → go to step 3.
   - **EITHER already exists** → this is a replay-or-recovery → **immediately roll back any index
     THIS call just created** (if `by-request-id` was created but `by-idempotency-key` returned
     `EEXIST`: `unlink(by-request-id/…)` + `fsync(dir)` *now*, before anything else — Finding 4
     case 2), then hand off to `resolve(entry_id)` (§3.2). Never mutate the epoch on this branch.
3. **Establish the write-ahead intent for `entry_id`:**
   - `journal/<entry_id>` **absent** → `O_CREAT|O_EXCL|O_NOFOLLOW`-create it with
     `phase:"intent"`, `attempt_gen:0`, `old_epoch=current`, `new_epoch=current+1`, full receipt
     fields; `fsync(file)`+`fsync(dir)`.
   - `journal/<entry_id>` present in **`phase:"aborted"`** → **atomically rewrite it in place to
     `phase:"intent"`, `attempt_gen := prev+1`** (temp + `fsync` + `os.replace` + dir `fsync`) —
     the deterministic `aborted→intent` reuse (Finding 4 case 1). **No `O_EXCL` is attempted on
     the tombstone pathname**, so the retry is never blocked by the tombstone.
   - present in `intent`/`committed` here ⇒ impossible after a *fresh* index reservation ⇒ torn
     state ⇒ `quarantined` (this is only reachable through `recover()`, §3.3, not the fresh path).
4. **Epoch CAS** — `_write_epoch_atomic(current+1)` (`:564`): temp + `fsync` + `os.replace` + dir
   `fsync`. **This is the durable commit point of the epoch.**
5. **Phase commit** — atomically rewrite `journal/<entry_id>` to `phase:"committed"` +
   `committed_at` (temp + `fsync` + `os.replace` + dir `fsync`). The committed journal entry **is**
   the durable receipt.
6. **Projection (best-effort)** — `_append_audit_receipt` (`:586`) from the committed entry; a
   failure marks the *event* `audit_pending` (`:686` semantics), never the transaction incomplete —
   the journal is authoritative.

### 3.2 `resolve(entry_id)` — the deterministic branch (also the unit of `recover()`)

Read the journal entry and `read_epoch()` → `current`, then branch on `{phase, current}`:

| Journal state | Epoch reads | Meaning (crash vector) | Deterministic action |
|---|---|---|---|
| `committed` | any | success already durable (h, or legit idempotent retry) | Return the receipt reconstructed from the entry. Exactly-once. |
| `intent` | `current == new_epoch` | CAS committed, phase-commit crashed (g) | **Finalize**: rewrite `committed` (temp+fsync+replace+dir fsync); return receipt. |
| `intent` | `current == old_epoch` | CAS never happened (W1 / d) | **Abort**: rewrite `phase:"aborted"` (temp+fsync+replace+dir fsync) **first**, THEN release both indexes (`unlink by-request-id/…` + `fsync(dir)`; `unlink by-idempotency-key/…` + `fsync(dir)`). Return a typed retryable deny (NOT `DENY_REPLAY`). The identical retry then re-reserves fresh (step 2) and, at step 3, rewrites the `aborted` entry back to `intent` and bumps. |
| `aborted` | any | tombstone (terminal) | `recover()`: leave it terminal. Live path: step 3 rewrites it to `intent`. |
| `intent` | `current ∉ {old,new}` | an unrelated bump advanced the epoch while this intent was unresolved | Typed **`quarantined`** (operator-visible terminal; never fabricate a commit, never `0`). |

**W1 never returns `DENY_REPLAY` for an uncommitted intent** — this is the exact defect the
landed `:660`→`:664` record-before-commit ledger cannot avoid.

### 3.3 `recover()` — the index↔journal reconciliation pass (replaces "iterate non-terminal entries")

rev5 left the startup pass as prose ("iterate non-terminal journal entries"). Finding 4 case 3/4
requires an **explicit bipartite reconciliation** over BOTH index dirs AND the journal dir,
because a crash after an index fsync but before the intent create leaves an **orphan index whose
target journal is absent**. `recover()` runs to completion under `epoch.lock`:

1. **Orphan-index sweep (journal-absent).** For every entry in `by-request-id/` and
   `by-idempotency-key/` whose pointed-at `journal/<entry_id>` is **absent** (vectors a, b, c —
   including the half-reservation where only one index exists): the reservation never reached a
   durable intent. Because the epoch CAS (step 4) can only follow a **durable** intent (step 3),
   *absence of the intent journal is proof the transaction did not commit*. Release the orphan
   index(es): `unlink` + `fsync(dir)`. Deterministic, no epoch read needed.
2. **Journal resolution.** For every `journal/<entry_id>`, run `resolve(entry_id)` (§3.2):
   finalize a committed-but-unphased intent (g), abort+release an uncommitted intent (d), return
   committed (h), leave a terminal `aborted`, or `quarantine` a torn `{epoch,phase}`.
3. **Dangling-index-after-abort cleanup (vector i).** Because abort rewrites `phase:"aborted"`
   **durably before** unlinking indexes, a crash mid-release leaves an `aborted` journal plus one
   surviving index. Step 1 already releases that surviving index (its target journal exists but is
   terminal `aborted` → step 1's "journal-absent" test excludes it, so add: an index pointing at a
   **terminal `aborted`** journal is also released). Net: after `recover()` no index points at an
   `aborted` or absent journal.

`recover()` completes **before** the socket binds/listens/accepts (§3.4). No request is ever
served against an unreconciled journal.

### 3.4 recover-before-listen barrier + `sd_notify(READY=1)`

The authority process runs `revocation_epoch.recover()` to completion **under `epoch.lock`**
**before** `serve()` calls `bind()`/`listen()`/`accept()`. Concretely, the transport `__main__`
(`revocation_epoch_transport.py:301-309`) changes from "bind-and-serve immediately" to:
acquire `epoch.lock` → `recover()` → release → `serve()` (which then binds and listens). Because
the authority binds its own socket (no systemd socket-activation is used), ordering is purely
in-process: **`recover()` → `bind` → `listen` → `accept`**. Readiness — `sd_notify(READY=1)`
under `Type=notify` — is emitted **only after `recover()` returns**, so any dependent unit and any
client observes the authority ready only once the journal is reconciled. The `.nix` unit
(`revocation-epoch-authority.nix:135-171`) changes `Type=simple` (`:139`) to `Type=notify` and the
transport emits readiness after recovery; the accept loop cannot run before `recover()` completes.

---

## 4. How this closes rev5 Finding 4 (all four cases)

| Finding 4 case | Landed/ rev5 gap | C6d closure |
|---|---|---|
| **1. W1 retry wedged** | rev5 rewrote the journal to `aborted` but step-2 still `O_EXCL`'d the same `journal/<entry_id>` pathname (tombstone present) so the identical retry could not proceed; the landed ledger returns `DENY_REPLAY` (`:664`) forever. | §3.1 step 3: the retry does **not** `O_EXCL` the tombstone — it **atomically rewrites the `aborted` entry back to `intent`** with `attempt_gen+1`. Deterministic under the lock; the identical request actually bumps. |
| **2. Partial dual-index reservation** | request-id index reserves, idempotency-key index conflicts → orphan request-id index; rev5's "resolve the existing journal" never specified the rollback. | §3.1 step 2: on the second index's `EEXIST`, the index THIS call just created is **unlinked + `fsync(dir)` immediately**, before resolving — no half-reservation persists. |
| **3. Orphan index (crash after index fsync, before journal create)** | indexes durable but `journal/<entry_id>` absent; rev5 iterated journal entries only, so an orphan index was never reconciled. | §3.3 step 1: `recover()` sweeps BOTH index dirs; an index whose target journal is **absent** is proof of non-commit → released. Covers the half-reservation (one index) too. |
| **4. Undefined startup reconciliation** | rev5 "iterate non-terminal journal entries" is not an algorithm over the index↔journal bipartite state. | §3.3: an **explicit bipartite reconciliation** (orphan-index sweep → per-journal `resolve()` → dangling-index-after-abort cleanup), each mapping to exactly-once or `quarantined`. |

---

## 5. Durability ordering + crash-consistency argument (the a–i matrix)

**Durability invariant chain — each barrier durable before the next begins:**

```
reserve by-request-id (fsync file+dir)  →  reserve by-idempotency-key (fsync file+dir)
  →  write-ahead intent (fsync file+dir)  →  epoch CAS (fsync temp, os.replace, fsync dir)
  →  phase:committed rewrite (fsync temp, os.replace, fsync dir)  →  projection (best-effort)
```

Because every barrier is durable before the next, the on-disk state at **any** crash point
uniquely determines the outcome, and `recover()` (§3.3) + `resolve()` (§3.2) map each to
exactly-once. `test-revocation-epoch.py` is EXTENDED with an injection at each boundary:

| Vector | Crash point | On-disk state | `recover()` action | Guarantee |
|---|---|---|---|---|
| a | before either index fsync | no index, no journal | nothing to do | retry reserves & bumps |
| b | after one index fsync, before the second | one orphan index, no journal | §3.3.1 releases the orphan (half-reservation) | retry reserves & bumps; no wedged identity |
| c | after both indexes, before intent fsync | two orphan indexes, no journal | §3.3.1 releases both | retry reserves & bumps |
| d | after intent durable, before epoch temp write | `intent`, epoch `old` | §3.2 abort + release both indexes | retry rewrites `aborted→intent`, bumps; never `DENY_REPLAY` |
| e | after epoch temp fsync, before `os.replace` | `intent`, epoch `old` (replace not applied) | same as (d) — CAS not durable | retry bumps; no double-bump |
| f | after `os.replace`, before epoch dir fsync | `intent`; epoch reads `old` OR `new` | epoch `old` ⇒ (d); epoch `new` ⇒ (g) | `os.replace` atomic; either way exactly-once |
| g | after epoch commit, before phase-commit rewrite | `intent`, epoch `new` | §3.2 finalize → `committed` | receipt returned; exactly-once |
| h | after phase-commit, before projection | `committed`, epoch `new` | §3.2 return committed; audit reconciled | receipt returned; `audit_pending` cleared |
| i | during `aborted→intent` index release (partial unlink) | `aborted` journal + one dangling index | §3.3.3 releases the dangling index | retry re-reserves & bumps; exactly-once |

Each vector asserts: `recover()` reads the durable epoch, reconstructs the correct receipt,
aborts+releases an uncommitted intent, or `quarantines` — and an idempotent retry returns
**exactly one** committed receipt (never two bumps, never a lost bump reported as replay, never a
committed-but-unobservable bump, never a half-reserved identity that permanently wedges a valid
retry).

---

## 6. Service-Coverage inventory (decomposition §0.4)

C6d adds **no new public surface** → per §0.4 it **binds an already-landed coverage path** rather
than shipping a new `test-<slice>-service-coverage.py`, and names it explicitly:

- **env-contract** — no new flag/socket. The authority socket/path env is already documented
  (`AQ_REVOCATION_EPOCH_*` in `env-contract.yaml`; the `.nix` sets `AQ_REVOCATION_EPOCH_EPOCH_PATH`
  / `_LEDGER_DIR` at `revocation-epoch-authority.nix:150-151`). C6d adds no capability flag.
- **Nix service + import** — **bound to the landed import**: `revocation-epoch-authority.nix` is
  already imported at `default.nix:26`; C6d edits the module (three StateDirs + recover-before-
  listen) but adds no new module and does not touch the import. Module stays `enable = false;`,
  `RestrictAddressFamilies = ["AF_UNIX"]` (`:165`), `NoNewPrivileges`/`ProtectSystem="strict"`
  (`:158`/`:160`) unchanged.
- **Durable primitive** — the `O_CREAT|O_EXCL|O_NOFOLLOW` + `fsync(file)`+`fsync(dir)` test-and-set
  is the core of both indexes and the journal create (§3.1); the extended crash-matrix test asserts
  it.
- **Flag-gated call path** — n/a: C6d is a recovery property of the authority startup, not a
  gated call path; gate-OFF byte-parity holds because the authority stays `enable=false` and C6d
  changes only its internal durability, not any legacy request trace.
- **Dashboard API + UI** — **no new section.** The authority is already dashboard-visible (the epoch
  section consumed by C2-SCI's `read-epoch`). Recovery status folds into the **existing authority
  health row**: recover-before-listen means an authority that finished recovery is `healthy`,
  one that cannot reconcile stalls readiness (no `sd_notify(READY=1)`) and surfaces as
  `degraded|unavailable`. A separate card would duplicate that signal without giving the operator a
  new action, so none is added. *(Rationale recorded per the review's Finding-3 observability bar.)*
- **Crypto/service tests exist** — `test-revocation-epoch.py` EXTENDED with the a–i matrix (§5).
- **Integration-check registration (NEW, required).** Register **`revocation-epoch-recovery`** in
  `config/validation-check-registry.json` (modelled on the `c2-sci-service-coverage` entry at
  line 1398: `id`, `description`, `trigger_paths` = [`revocation_epoch.py`,
  `revocation_epoch_transport.py`, `revocation-epoch-authority.nix`, `test-revocation-epoch.py`],
  `command`, `tier:"behavioral"`, `timeout_seconds`, `enabled:true`), **AND** wire the
  recovery-determinism probe in **BOTH** harnesses per the dual-harness check-id contract:
  - `scripts/testing/harness_qa/phases/phase0.py` — a new `_check_revocation_epoch_recovery(ctx)`
    returning `CheckResult`, added via `results.extend(...)`, modelled on
    `_check_intent_classifier_coverage` (line 1325). Allocate the **next-free id `0.10.51`**
    (current max is `0.10.50`).
  - `scripts/ai/_aq-qa-bash` — the mirror `_check 1 "0.10.51" "revocation-epoch recovery determinism" …`
    line, modelled on the `0.10.10` entry (line 1635).
  - The probe asserts (an integration exercise, not just unit tests): an identical never-committed
    signed request **actually bumps on retry** (never `DENY_REPLAY`), and each a–i vector yields
    exactly-once receipt or a typed `quarantined`; and that the authority does not accept before
    `recover()` completes (recover-before-listen).

---

## 7. Exclusions

C6d touches **only** the files in §1. Explicitly excluded (each is a later slice or out of scope):

- `authorize_launch`, the launch socket/group, single-use launch tokens — **C6a / C6-S** (C6d
  adds no dispatch op; the transport edit is `__main__`-only).
- The offline owner-key submission path, `aq-epoch-bump` verbs — **C6c**.
- Any owner public-key allowlist change or epoch bump — **P-F4** (C6c activation), not C6d.
- TEG / `dispatch-gateway` / in-principal provider execution / egress — **C6b / C6e / C4**.
- `slot_queue` / `dispatch.py` scheduler-gate fence, `CAPABILITY_SCHEDULER_LEASE_GATE` — later C6.
- A general legacy `DurableReplayLedger`-marker **import/migration** path (unnecessary on the
  dormant baseline, §2.3; a separate reviewed slice if a non-empty ledger is ever found).
- The auto-revert guard (decomposition §0.2 — no C6 slice modifies it).
- Provider invocation, network, DDL, deployment, activation, flag flips.

Any need to touch an excluded path is a **stop condition** requiring a new reviewed design, not
expansion of C6d.

---

## 8. Freeze, authorization, and activation

**Freeze criteria (all must hold):**
1. Deterministic W1 reuse — an identical signed request that never committed **actually bumps on
   retry**, never `DENY_REPLAY`.
2. W2 receipt reconstruction from the committed journal (vectors g, h).
3. Partial-reservation rollback (case 2) and orphan-index reconciliation (cases 3, 4) recovered.
4. Each of the a–i crash vectors (§5) yields exactly-once idempotent receipt or a typed
   `quarantined` — proven by the extended `test-revocation-epoch.py`.
5. `recover()` completes before the socket accepts; readiness gated on it (recover-before-listen).
6. The `revocation-epoch-recovery` integration check is **GREEN in both harnesses** (phase0 +
   bash), per §6.
7. The freeze binds the exact candidate hashes, reproduces the §1 base hashes/absences, confirms
   the three new StateDirs absent at base, rejects all other changed paths, stops on HEAD drift.

**Authorization / activation note — C6d needs NO owner activation.** C6d is **default-safe**: it
is pure durability/recovery hardening of an authority that ships `enable = false;`. It performs
**no epoch bump** (the bump is offline-owner-signed and C6d neither signs nor submits one), flips
**no flag**, provisions **no key**, and opens **no network**. `recover()` runs only when the
authority unit is *already* enabled — and enabling that unit is a separate, later owner act that
C6d does not perform and does not depend on. There is no owner activation act tied to C6d. The
baseline stays dormant.

**Dependencies / order.** Foundation slice — **lands first** (decomposition §8). No predecessor.
Successors C6-S, C6a, and C6c reuse the recover-before-listen barrier and the StateDir machinery
this slice defines.

---

**RECORD: PREPARED_ONLY revision 1. No implementation, freeze, activation, epoch bump, provider
traffic, deployment, restart, network authority, or flag flip is granted by this document. C6d is
the foundation slice of `C6-DECOMPOSITION-20260924.md`; it requires its own independent binding
review → hash-bound freeze → default-OFF build, per the decomposition's per-slice contract. This
document closes rev5 (`f68ccf91`) Finding 4 (HIGH) at design level; the rev5 §2.2 shape it builds
on is the retained design basis (decomposition §0.3).**
