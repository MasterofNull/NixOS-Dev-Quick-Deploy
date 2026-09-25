---
title: "Foundation C — C6 Decomposition v2 (review-revised): six individually-freezable slices (C6d, C6-S, C6a, C6c, C6b, C6e) + a pre-C4 contract-amendment step"
slice: "C6 (decomposition / per-slice charter)"
status: "PREPARED_ONLY — authorizes NOTHING (no build, no freeze, no activation, no epoch bump, no provider traffic, no flag flip)"
kind: "decomposition-plan"
revision: "v2 — the review-revised decomposition (supersedes the v1 body of this same file)"
implementation_authorization: "NONE"
activation_authorization: "NONE"
base_head: "f1f409ef97f73fb6ae152a297ba0c0367e30bf22"
supersedes_scope_of: "C6-DESIGN-AND-AUTHORIZATION.md rev5 (factory/c6-rev5 @ f68ccf912f07c4a872f17c1cbe6c469eac444350) — the MONOLITHIC single-freeze scope only; rev5's proven components are RETAINED as the per-slice design basis (see §0.3)"
closes_review: ".agent/collaboration/CODEX-C6-DECOMPOSITION-REVIEW-20260924.md (REQUEST_REVISION — 3 HIGH findings on the v1 decomposition; the C6a–e seams were confirmed SOUND)"
prior_review_closed: ".agent/collaboration/CODEX-C6-REV5-BINDING-REVIEW-20260924.md (REQUEST_REVISION — 5 HIGH findings on the monolithic rev5 design)"
authoring_role: "architect (design/planning only)"
---

# Foundation C — C6 Decomposition (v2, review-revised)

## 0. Why this document exists — and what v2 changes

C6 (the operator epoch-revocation kill-lever + F2.5 scheduler-launch gate) failed **five** whole-design
binding revisions as a MONOLITHIC packet. v1 of this document re-scoped C6 into small,
individually-freezable slices (C6a–e ↔ rev5 Findings 1–5). Its independent decomposition review
(`.agent/collaboration/CODEX-C6-DECOMPOSITION-REVIEW-20260924.md`, subject `factory/c6-decomposition`,
baseline `f1f409ef`) returned **REQUEST_REVISION** and confirmed the important thing: **the finding
seams are SOUND** — the C6a↔F1 … C6e↔F5 mapping is correct, C6d-first is the right foundation, the
retained rev5 work is not lost, and the landed-code corrections are accurate. What was **not**
executable was the dependency/order/inventory contract. This v2 keeps the seams and closes the three
HIGH findings.

**The three HIGH findings v2 closes (the SPEC):**

1. **Socket topology was chosen too late.** v1 deferred the launch/control-socket-group decision
   (mechanism A vs B) to C6b, while C6c already declared it needed "a decided group model (C6b)" as a
   dependency — a future/parallel "bounded input" is not a frozen dependency, so C6c could not freeze.
   → **v2 adds a foundation slice `C6-S` that freezes the socket/principal topology (mechanism B)
   BEFORE C6a and C6c**, so neither builds on an unfrozen transport surface.
2. **The C4↔C6 contradiction was "resolved" by a doc sync AFTER the claimed C4-freeze milestone** —
   which cannot retroactively satisfy C4's existing, stronger prerequisite (C4's design + readiness docs
   name the lever as the durable epoch authority **plus** the live F2.5 scheduler gate). → **v2 makes the
   narrowed prerequisite an explicit, independently-reviewed pre-C4 contract AMENDMENT that must be
   accepted BEFORE C4 freeze**, and stops counting C6a as part of the kill-lever.
3. **The "exact landed files" were not sufficient for independently shippable slices** — no Nix
   import/wiring, no AQ-QA integration-check registration, no live-backed dashboard/API surface, despite
   the repository's Service Coverage Contract. → **v2 gives every slice a complete Service-Coverage
   inventory** (Nix import + registry/phase0 integration check + dashboard/API), or explicitly binds an
   already-landed coverage path that exercises the new surface.

**Adopted decisions (from the review's "Open decisions"):**
- **Egress = C4 as a HARD pre-activation gate.** The interim netns/nftables path is **NOT
  pre-authorized** as a generic escape hatch. If ever needed it is a separately-reviewed exact
  mechanism — and note that **nftables alone cannot enforce a provider *URL* identity across DNS/address
  changes**, so a URL-scoped "egress boundary" is not an OS boundary. (Supersedes v1 §5.2's Primary/Fallback.)
- **C6b isolation = mechanism B** (dedicated TEG-only launch socket + `aq-revocation-launch-clients`
  group), and that topology is frozen in **C6-S before C6a/C6c**, not deferred to C6b.

**Owner decision (2026-09-24) still stands: there is NO urgency.** The live mechanism-test risk is
reverted at `f1f409ef` (PR #333, merge `785ff50b` / revert `2ef1406e`): the baseline is dormant (gate env
removed, sole owner key `revoked`, authority running but with no admissible signer). This document
authorizes nothing; each slice gets its own design → independent binding review → freeze → default-OFF
build, one at a time.

### 0.1 Verified landed-code facts (each finding checked against `f1f409ef`)

The rev5 findings remain factually correct at the anchor. Verified in this worktree against `f1f409ef`:

| # | Reviewer claim | Verified landed fact |
|---|---|---|
| 1 | The authority transport recognizes only `read-epoch` / `bump`; `authorize_launch` cannot be reached; single-use token consume is undefined. | `scripts/ai/lib/revocation_epoch_transport.py` `build_env_handler().handler()` accepts **only** `{"op":"read-epoch"}` and `{"bump":{...}}` (lines ~283/290). `serve()` (line ~128) is a generic loop; the handler owns dispatch. No `authorize_launch` op, no launch ledger, no consume verb anywhere. |
| 2 | `aq-revocation-epoch-clients` is NOT TEG-only; ALA + C2-SCI principals also hold it; rev5's claimed c2 line-122 shared-UID removal does not exist. | Members of `aq-revocation-epoch-clients`: `primaryUser` (`revocation-epoch-authority.nix:111`), the **ALA** service principal (`lease-signing-authority.nix:76` — `extraGroups=["aq-lease-signing-clients" "aq-revocation-epoch-clients"]`), the **C2-SCI** issuer principal (`c2-scheduler-context-issuer.nix:114` — `extraGroups=["aq-c2-scheduler-context-clients" "aq-revocation-epoch-clients"]`), and the authority's own user (`:102`, to chgrp the socket). `c2-scheduler-context-issuer.nix:122` is a group **declaration** (`users.groups.aq-revocation-epoch-clients = {};`), NOT a `primaryUser` membership — rev5's claimed "coordination edit removing a shared-UID revocation membership" there is editing nothing. Deleting `authority:111` removes only `primaryUser`; ALA + C2-SCI still reach the socket. `SO_PEERCRED` is log-only today (`serve()` passes it "for LOGGING only"). |
| 3 | The offline owner-key ceremony has no callable submission path; the CLI verb is `build` not `prepare`; `submit` writes 0700 authority state; `bump` uses a host private key + needs the group. | `scripts/ai/aq-epoch-bump` verbs are **`build`** (unsigned request, prints bytes-to-sign — rev5 wrongly calls this `prepare`), **`submit --signed`** (calls `apply_bump` **in-process** against `--epoch-path`/`--ledger-dir`, which are the authority's `0700` StateDirectory the owner UID cannot write), and **`bump`** (one-shot: reads/signs with a **host private-key file** — violates "private key never on host" — then submits `{"bump":request}` over the UDS, requiring `aq-revocation-epoch-clients` membership). After a TEG-only group narrowing, no offline-signed doc has an authorized route to the running authority. |
| 4 | W1 retry / dual-index recovery non-deterministic despite the claimed `aborted→intent` transition. | `apply_bump` (`scripts/ai/lib/revocation_epoch.py:609`) runs under `_acquire_epoch_lock` (`:549`, `fcntl.flock LOCK_EX` on `epoch.lock`) → `_write_epoch_atomic` (`:564`). rev5 §2.2 rewrites the journal to `aborted` but step-2 still does `O_CREAT|O_EXCL` on the same journal pathname (tombstone present) → the identical retry cannot re-create it and cannot "actually bump"; partial dual-index rollback and orphan-index→journal reconciliation are unspecified. |
| 5 | Deferring enforceable TEG network confinement to C4 is not acceptable under rev5's activation order; a URL is not an OS boundary; C4-before-C6 vs C4-blocked-on-C6 contradiction. | rev5 §3.2 scopes TEG egress "to the provider URL(s)" (a routing target, not an OS boundary; AF_INET reachable) and §6 orders the C6 flag-enable **before** C4. `DESIGN-PACKET.md §8` resequence (owner-ratified 2026-07-29) orders **C4 before C6**; `C4-ACTIVATION-READINESS-20260806.md` says C4 freeze is **blocked on** the C6 intervention lever. Contradiction is real; §7 below resolves it via the pre-C4 amendment. |

### 0.2 Ground rules for every slice (inherited HARD constraints)

- **Design/planning only.** No slice is authorized to build, freeze, activate, bump the epoch, emit
  provider traffic, or flip a flag. Each slice is designed → independently binding-reviewed → frozen →
  built default-OFF, individually.
- **Fail-closed, no standing authority.** Every unavailable/malformed/racing read returns a typed deny
  (never `0`, never fail-open). No capability is a standing grant; the launch token is single-use and
  expiring; the owner key is offline-held and never a host/`/run/secrets` secret.
- **Off-is-inert byte-parity.** With `CAPABILITY_SCHEDULER_LEASE_GATE=0` (the `f1f409ef` default), every
  legacy request keeps its exact current call trace; no new op is reachable.
- **Small enough to freeze.** Each slice closes exactly ONE reviewer concern and edits a bounded,
  enumerated file set with its own acceptance + freeze criteria **and its own Service-Coverage inventory**
  (§0.4).
- **Activation safety-net.** The landed dead-man auto-revert guard (`scripts/ai/lib/activation_guard.py`,
  `scripts/ai/aq-activation-guard`, `nix/modules/services/activation-auto-revert-guard.nix`, default-OFF)
  is the safety-net for the eventual gate flip. The revert is **flag-based** (remove
  `CAPABILITY_SCHEDULER_LEASE_GATE` + rebuild), **never** an epoch bump (the bump is offline-owner-signed
  and cannot be auto-run by the sweep). No C6 slice modifies the guard.

### 0.3 rev5's proven parts — RETAINED as the per-slice design basis (do not re-derive)

Cite rev5 `f68ccf91` when each slice is designed:

- **The one-lock serialization proof** (rev5 §3.3): `authorize_launch` and `apply_bump` both take the
  authority's single exclusive `epoch.lock`, so they are totally ordered. **→ design basis for C6a.**
- **In-principal TEG execution** (rev5 §3.2): the provider `urlopen()` executes inside the TEG principal;
  the caller receives only response *bytes*; no launch capability crosses back. **→ design basis for C6b.**
- **The dormant-baseline / P-F4 monotonic-advance reasoning** (rev5 §0.1, §6): the freeze binds the
  rev-4 allowlist (mechtest revoked, no active key); P-F4 is an activation-time public-only monotonic
  advance that does not mutate frozen code bytes. **→ design basis for C6c activation.**
- **The recover-before-listen barrier + two-independent-uniqueness-index shape** (rev5 §2.2): correct in
  intent; C6d fixes the `aborted→intent` reuse and the rollback/reconciliation gaps. **→ design basis
  for C6d.**
- **The authority-unavailable posture** (rev5 §3.5, DESIGN-PACKET §9): deny-closed + LOUD alert, never
  total DoS. **→ cross-cutting basis for all slices.**

**v2 correction to v1's §0.3 kill-lever composition:** the "C6 intervention lever" that C4's freeze
prerequisite names is the *durable, reachable, owner-authorized epoch-bump path* = **C6d + C6-S + C6c**.
It does **NOT** include **C6a** (`authorize_launch`). C6a shares the authority's lock/state machinery but
its only consumer is the TEG (C6b); a launch-authorization op with no live consumer is not part of the
operator kill-lever. C6a's actual dependency is stated separately in §3 and §7.

### 0.4 The Service Coverage Contract every shippable slice must satisfy (template)

The repository enforces that a landed capability is default-OFF, confined, integration-checked, and
live-visible — not merely unit-tested. The canonical template is `scripts/testing/test-c2-sci-service-coverage.py`
(and its twin `test-ala-service-coverage.py`), registered as `c2-sci-service-coverage` /
`ala-service-coverage` in `config/validation-check-registry.json`. Each C6 slice that introduces a new
surface MUST inventory, and its own `test-<slice>-service-coverage.py` MUST assert, the applicable rows:

1. **env-contract** — every new flag/socket-path documented in `config/env-contract.yaml`; new capability
   flags default to `"0"`.
2. **Nix service + import** — the module defaults `enable = false;`, is AF_UNIX-only + hardened
   (`NoNewPrivileges`, `ProtectSystem = "strict"`), uses its dedicated principal, wires the correct
   client group(s), **and is imported in `nix/modules/services/default.nix`** (a new module that is not
   imported is invisible to the system).
3. **Durable primitive** — where a single-use/atomic ledger is claimed, an `O_EXCL` test-and-set is present.
4. **Flag-gated call path** — gate/dispatch reference the flag and gate the new call behind an `enabled()`
   predicate; gate-OFF byte-parity.
5. **Dashboard API** — `dashboard/backend/api/routes/aistack.py` exposes a live-backed section for the new
   surface (no hard-coded healthy state, no `--` placeholder).
6. **Dashboard UI** — `assets/dashboard.js` reads that section and renders the rows.
7. **Crypto/service tests exist** — the slice's unit + integration tests are present on disk.
8. **Integration-check registration** — `config/validation-check-registry.json` registers the slice's
   `*-service-coverage` id, AND the integration probe is registered in BOTH the phase harness
   (`scripts/testing/harness_qa/phases/phase0.py` — remember `results.extend(...)`) AND the bash mirror
   (`scripts/ai/_aq-qa-bash`) per the dual-harness check-id contract.

A slice that does not add a new public surface (C6d, C6-S) may **bind an already-landed coverage path**
that exercises its edit instead of shipping a new coverage test — but must name that path explicitly.

---

## 1. Slice C6d — Deterministic journal recovery (FOUNDATION — lands first)

**Closes reviewer Finding 4 (HIGH) / rev4 Finding 5.** No new public surface; hardens an already-landed
primitive.

**Scope.** The recoverable write-ahead intent journal in `revocation_epoch.py` + authority
StateDirectories, fixing the three gaps rev5 left open:
1. **Atomic `aborted → intent` reuse via a new attempt-generation path** so an `O_EXCL` retry can actually
   bump (rev5's tombstone at the same journal pathname blocked the identical retry).
2. **Partial dual-index rollback** — if `by-request-id` reserves but `by-idempotency-key` conflicts, roll
   back the request-id index immediately.
3. **Orphan-index → journal reconciliation algorithm** (not merely iterating non-terminal journal
   entries): indexes whose target journal does not exist must be reconciled.
Two independent `O_EXCL` uniqueness indexes (`by-request-id/`, `by-idempotency-key/`); the a–i crash
matrix (rev5 §2.2); the **recover()-before-listen** barrier enforced in the authority `ExecStart` (this
barrier + the StateDirs are the shared machinery C6a and C6c both reuse).

**Exact landed files edited.**
- `scripts/ai/lib/revocation_epoch.py` — `recover()` + `aborted→intent` attempt-generation + dual-index
  rollback + orphan reconciliation.
- `nix/modules/services/revocation-epoch-authority.nix` — `journal/`, `by-request-id/`,
  `by-idempotency-key/` StateDirectories + recover-before-`listen()` ExecStart ordering.
- EXTEND `scripts/testing/test-revocation-epoch.py` — the a–i crash-injection matrix.

**Service-Coverage inventory.** *No new public surface* → **binds the already-landed revocation-epoch
authority coverage path.** `revocation-epoch-authority.nix` is already imported at
`nix/modules/services/default.nix:26`; the authority is already dashboard-visible (the epoch section
consumed by C2-SCI's `read-epoch`). NEW required: a **deterministic-recovery integration check** —
register `revocation-epoch-recovery` in `config/validation-check-registry.json` and wire it in BOTH
`phase0.py` (`results.extend`) and `_aq-qa-bash`, asserting an identical never-committed signed request
actually bumps on retry (never `DENY_REPLAY`) and each a–i vector yields exactly-once receipt or a typed
`quarantined`. No new dashboard section (recovery status folds into the existing authority health row).

**Dependencies / order.** **Foundation slice — lands first.** Root of the critical path. *No owner activation.*

**Acceptance + freeze criteria.** Deterministic W1 reuse (an identical signed request that never
committed actually bumps on retry — never `DENY_REPLAY`); W2 receipt reconstruction; partial-reservation
and orphan-index cases recovered; each of the a–i crash vectors yields exactly-once idempotent receipt or
a typed `quarantined`; recover completes before the socket accepts; the recovery integration check is
GREEN in both harnesses.

**Owner activation needed?** **No.** Pure durability/recovery hardening; default-OFF; no bump.

---

## 2. Slice C6-S — Shared launch-socket + principal contract (NEW foundation slice; freezes the topology)

**Closes reviewer Finding 1 of the decomposition review (HIGH) — "select and freeze the launch/control-socket
topology before C6c/C6a."** This slice exists so that no later slice revises a transport surface a prior
slice already froze.

**Adopted decision — mechanism B.** A **dedicated TEG-only launch socket + dedicated
`aq-revocation-launch-clients` group** carries `authorize_launch`; the **existing control socket**
(`/run/aq-revocation-epoch-authority/control.sock`) is UNTOUCHED and keeps its **separately-authorized
read/bump clients** (`aq-revocation-epoch-clients`: ALA + C2-SCI for `read-epoch`, the owner-bump path for
`bump`). Mechanism A (making a whole socket's `SO_PEERCRED` check authoritative) is **rejected**: B keeps
the least-privileged read/bump path structurally intact and makes TEG exclusivity a property of *which
socket/group exists*, not of a per-op peer check layered onto a shared socket.

**Scope (contract only — no consumer wired here).** Define and freeze, as the transport/principal contract
both C6a and C6c build on:
- a **second listening socket** on the authority (`launch.sock`) whose directory/mode admits **only** the
  `aq-revocation-launch-clients` group;
- the new **`aq-revocation-launch-clients` group** (declared here; the TEG principal JOINS it in C6b —
  C6-S declares the group empty, exactly as `c2-scheduler-context-issuer.nix:122` declares
  `aq-revocation-epoch-clients` empty);
- the **owner-bump principal path** on the *control* socket kept **distinct** from the launch group, so
  narrowing the launch surface never severs the operator kill-lever (this is the surface C6c's owner
  submission lands on);
- the socket-path env references in `config/env-contract.yaml`
  (`AQ_REVOCATION_LAUNCH_SOCKET_PATH` alongside the existing epoch socket path).

C6-S adds **no dispatch op** and **no consumer** — `authorize_launch` handling is C6a; the TEG membership
is C6b; the owner submission is C6c. It freezes only the socket/group/path topology so those three build
on a fixed surface.

**Exact landed files edited.**
- `nix/modules/services/revocation-epoch-authority.nix` — declare the `launch.sock` listener + its
  `tmpfiles`/mode restricted to `aq-revocation-launch-clients`; declare
  `users.groups.aq-revocation-launch-clients = {};`; keep the control socket + `aq-revocation-epoch-clients`
  unchanged; keep the owner-bump path on the control socket.
- `scripts/ai/lib/revocation_epoch_transport.py` — bind/serve the second socket (generic `serve()` loop
  only; NO new op dispatch — `authorize_launch` is added in C6a).
- `config/env-contract.yaml` — `AQ_REVOCATION_LAUNCH_SOCKET_PATH` reference.

**Service-Coverage inventory.** Extends the already-landed revocation-epoch authority coverage:
`revocation-epoch-authority.nix` stays imported at `default.nix:26`. NEW required — a **topology
integration check** `revocation-launch-socket-topology` registered in
`config/validation-check-registry.json` + wired in `phase0.py` and `_aq-qa-bash`, asserting: the launch
socket exists and admits only `aq-revocation-launch-clients`; the control socket still admits
`aq-revocation-epoch-clients` for read/bump; the owner-bump path is NOT in the launch group; both sockets
are AF_UNIX-only. Dashboard: extend the existing authority health row to show both sockets (launch vs
control) `present|absent` — no new card.

**Dependencies / order.** Requires **C6d** (StateDir/ExecStart machinery + recover-before-listen — the
launch socket must not accept before recovery). **Lands immediately after C6d, before C6a and C6c.** *No
owner activation.*

**Acceptance + freeze criteria.** The two-socket topology is frozen and byte-parity inert while gate-OFF
(the launch socket has no reachable op until C6a lands); ALA + C2-SCI retain `read-epoch` on the control
socket; the owner-bump path is present on the control socket and NOT on the launch group; the topology
integration check is GREEN in both harnesses. This freeze is the transport contract C6a and C6c cite.

**Owner activation needed?** **No.**

---

## 3. Slice C6a — Authority-transport `authorize_launch` + single-use launch-token consume

**Closes rev5 Finding 1 (HIGH).** *(NOT part of the C4 kill-lever — see §7.)*

**Scope.** Add the `authorize_launch` operation on the **launch socket frozen by C6-S** and back it with
`revocation_epoch.authorize_launch()` running under the SAME exclusive `epoch.lock` as `apply_bump` (rev5
§3.3 serialization proof — the retained sound core). Define the **atomic single-use launch-token ledger
transition** rev5 left undefined: `issue → consume`, each `O_CREAT|O_EXCL|O_NOFOLLOW` + `fsync(file)` +
`fsync(dir)`, the token bound to `{nonce, context_digest, task_id, task_revision, epoch,
gateway_instance, issued_at, deadline≤250ms}`, plus an explicit **consume** operation (verifier +
duplicate-consume serialization under the lock) so two provider-start attempts cannot reuse one token.
Add the launch-ledger StateDirectory, reusing C6d's recover-before-listen ordering.

**Exact landed files edited.**
- `scripts/ai/lib/revocation_epoch_transport.py` — add the `authorize_launch` op dispatch to
  `build_env_handler().handler()`, bound to the C6-S launch socket (control socket keeps only
  `read-epoch`/`bump`).
- `scripts/ai/lib/revocation_epoch.py` — new `authorize_launch()` under `_acquire_epoch_lock`; single-use
  launch-authorization ledger + `consume()` verb.
- `nix/modules/services/revocation-epoch-authority.nix` — launch-ledger StateDirectory (ownership/mode);
  reuse C6d's recover-before-`listen()` ordering (no new socket — C6-S already declared it).
- EXTEND `scripts/testing/test-revocation-epoch.py` — serialization + single-use + expiry vectors.

**Service-Coverage inventory.** NEW `scripts/testing/test-c6a-authorize-launch-service-coverage.py`
(mirrors `test-c2-sci-service-coverage.py`) asserting: `authorize_launch` reachable ONLY on the C6-S launch
socket; the `O_EXCL` single-use ledger primitive present; gate-OFF byte-parity (op inert/unreachable when
disabled). Register `c6a-authorize-launch-coverage` in `config/validation-check-registry.json` + wire the
**authority-op integration probe** in `phase0.py` (`results.extend`) and `_aq-qa-bash` (an authority-level
issue→consume→duplicate-deny exercise — *not just unit tests*, per review Finding 3). Dashboard:
`aistack.py` adds `result["revocation_launch_authorization"]` (states: `op_present|op_absent`,
`ledger_durable`) and `assets/dashboard.js` renders the row.

**Dependencies / order.** Requires **C6d** (recover-before-listen + StateDir machinery) and **C6-S** (the
launch socket + group topology it attaches the op to). Its only consumer is the TEG (C6b). **Fans out from
C6-S in parallel with C6c.**

**Acceptance + freeze criteria.** Serialization proof reproduced against `apply_bump` (one lock, total
order); token single-use (duplicate consume denies); ≤250 ms deadline enforced;
context/gateway/task-revision binding enforced (wrong-inode/wrong-task/wrong-gateway/wrong-context deny);
`authorize_launch` reachable over the C6-S launch socket only; gate-OFF byte-parity; the authority-op
integration probe GREEN in both harnesses; the coverage test GREEN. Freeze binds candidate hashes + the
retained rev5 §3.3 proof.

**Owner activation needed?** **No.** Build default-OFF; op inert until gate-ON; no epoch bump. (Gate-ON is
C6b/C6e's concern.)

---

## 4. Slice C6c — Callable offline owner-key submission path (completes the amended C4 lever)

**Closes rev5 Finding 3 (HIGH) / rev4 Finding 4.** With C6d and C6-S, this is the slice whose completion
satisfies the **amended** C4 freeze prerequisite (§7).

**Scope.** Reconcile the ACTUAL `aq-epoch-bump` verbs with the offline-key model and inventory a real,
callable **prepare → offline-sign → submit-to-authority** courier path with **no host private key** and
**no owner-UID access to the 0700 authority StateDirectory**. Facts to reconcile (verified §0.1): the
design's `prepare` is really **`build`**; **`submit --signed`** calls `apply_bump` in-process against the
authority's `0700` dirs (owner cannot write); **`bump`** reaches the socket but signs with a **host**
private key. Design decision: add an offline `submit --signed --socket <path>` path on `aq-epoch-bump`
that sends a pre-signed `{"bump": <signed doc>}` to the running authority **over the CONTROL socket's
owner-bump path frozen in C6-S** — **without** reading any host private key and **without** touching the
0700 StateDirectory (the authority applies the verified bump itself). The owner-bump path is the C6-S
control-socket path kept **distinct** from the C6-S launch group, so narrowing the launch surface never
severs the operator kill-lever.

**Exact landed files edited.**
- `scripts/ai/aq-epoch-bump` — add offline `submit --signed --socket` (no host key) targeting the C6-S
  control-socket owner-bump path; correct the `build`/`submit`/`bump` reconciliation; document the `bump`
  host-key one-shot as NOT the offline model's path.
- `config/env-contract.yaml` — the fixed authority control-socket reference for owner submission.
- `nix/modules/services/revocation-epoch-authority.nix` — only if the owner-bump membership needs an
  attribute beyond what C6-S froze (coordinated with C6-S; the group model is already fixed there).

**Service-Coverage inventory.** NEW `scripts/testing/test-c6c-owner-submission-service-coverage.py`
asserting the callable owner path exists with no host-key read and no 0700 write; revoked/unknown/
non-monotonic keys deny. Register `c6c-owner-submission-coverage` in
`config/validation-check-registry.json` + wire an integration probe in `phase0.py` and `_aq-qa-bash`.
**Dashboard (required by review Finding 3):** `aistack.py` exposes `result["owner_epoch_bump_lever"]` with
the three states **`operational` | `none(revoked-only)` | `unavailable`**, and `assets/dashboard.js`
renders those rows (no `--` placeholder, no hard-coded healthy state).

**Dependencies / order.** Requires **C6d** (durable epoch + reachable authority) and **C6-S** (the decided
socket/group model + the owner-bump control-socket path). **Does NOT require C6a** — the owner kill-lever
does not use `authorize_launch`. **Fans out from C6-S in parallel with C6a.** Completing C6c (with C6d +
C6-S) is the event that satisfies the amended C4 freeze prerequisite (§7).

**Acceptance + freeze criteria.** The owner can produce an offline signature and DELIVER it to the running
authority through the C6-S owner-bump control-socket path with no host private key and no owner-UID 0700
access; revoked/unknown/non-monotonic keys deny; the lever is observably `operational` vs
`none(revoked-only)` vs `unavailable` on the dashboard; coverage + integration checks GREEN in both harnesses.

**Owner activation needed?** **Yes — P-F4** (owner OFFLINE keygen + public-only monotonic allowlist advance
rev-4→rev-5 adding `owner-2026-09 status:active`, per rev5 §2.3/§6) is an activation-time owner act. The
code build is default-OFF/dormant; until P-F4 the lever is observably `none(revoked-only)` /
non-operational.

---

## 5. Slice C6b — TEG-exclusive launch authorization + in-principal provider execution

**Closes rev5 Finding 2 (HIGH).** The TEG launch fence — NOT part of the C4 kill-lever; its activation is
gated AFTER C4 (§7).

**Scope.** Make `authorize_launch` reachable **only** by the TEG principal by having the TEG principal
**JOIN the `aq-revocation-launch-clients` group frozen in C6-S** (mechanism B — the topology is already
decided; C6b only adds the member). This structurally excludes the ALA (`lease-signing-authority.nix:76`)
and C2-SCI (`c2-scheduler-context-issuer.nix:114`) principals — they hold `aq-revocation-epoch-clients` on
the control socket, never `aq-revocation-launch-clients` on the launch socket — and it needs **no** per-op
`SO_PEERCRED` layering on a shared socket (this corrects rev5's false claim that deleting `authority:111`
+ editing `c2:122` achieves TEG-exclusivity). Also lands the **in-principal provider execution** boundary
(rev5 §3.2, retained sound core): the TEG owns `urlopen()` and returns only response *bytes*; no
token/lease/context crosses back to the caller.

**Exact landed files edited.**
- NEW `scripts/ai/lib/dispatch_gateway.py` — TEG adapter: private ALA→C2 clients, the `authorize_launch`
  client (on the C6-S launch socket) + token consume, gateway-owned lifecycle CAS record, in-principal
  provider-execution adapter.
- NEW `nix/modules/services/dispatch-gateway.nix` — dedicated TEG principal joining
  `aq-revocation-launch-clients`; public untrusted submission socket; private client memberships;
  `enable = false;`; AF_UNIX-only + hardened.
- EDIT `nix/modules/services/default.nix` — **import `./dispatch-gateway.nix`** (required — the module is
  invisible otherwise).
- EDIT `scripts/ai/lib/dispatch.py` — gate-ON lease-bearing path submits envelope to the TEG, receives
  response bytes; gate-OFF byte-parity.
- EDIT `scripts/ai/lib/slot_queue.py` — accept context only from the TEG in-process handoff;
  `held→launch_authorized` recorded as downstream bookkeeping of the C6a fence.
- NEW `scripts/testing/test-dispatch-gateway.py`.

**Service-Coverage inventory.** NEW `scripts/testing/test-c6b-dispatch-gateway-service-coverage.py`
(mirrors `test-c2-sci-service-coverage.py`) asserting: `dispatch-gateway.nix` defaults `enable = false;`,
AF_UNIX-only, hardened, dedicated principal, joins `aq-revocation-launch-clients`, and **is imported in
`default.nix`**; `CAPABILITY_SCHEDULER_LEASE_GATE` documented default `"0"` in env-contract; the gate/
dispatch path is flag-gated; the TEG returns only provider bytes. Register `c6b-dispatch-gateway-coverage`
in `config/validation-check-registry.json` + wire the integration probe in `phase0.py` and `_aq-qa-bash`.
**Dashboard:** `aistack.py` adds `result["trusted_execution_gateway"]` (states:
`enabled|disabled|unavailable`, launch-client membership, egress-boundary present) and `assets/dashboard.js`
renders the TEG rows.

**Dependencies / order.** Requires **C6a** (the `authorize_launch` op + consume contract) and **C6-S** (the
launch socket/group it joins). **Built default-OFF** after C6a; **its gate-ON activation is placed after
C4** (§7). Not on the C4-unblocking path.

**Acceptance + freeze criteria.** Proven the shared owner UID **and** the ALA + C2-SCI principals cannot
obtain a launch token (they are not in `aq-revocation-launch-clients`), while all three retain (or do not
need) the least-privileged `read-epoch` path on the control socket; the TEG principal can; caller receives
only provider response bytes (no token/lease/context in reply or telemetry); gate-OFF byte-parity;
coverage + integration checks GREEN; the TEG dashboard section live-backed.

**Owner activation needed?** Build default-OFF (`enable=false`). **Gate-ON flag-flip is a later owner
activation**, HARD-gated on C6e's egress resolution (C4 in force) + the auto-revert guard armed.

---

## 6. Slice C6e — TEG egress boundary = C4 as a HARD pre-activation gate

**Closes rev5 Finding 5 (HIGH).** Adopts the review's egress decision.

**Adopted decision (no interim escape hatch).** A provider URL is a routing target, not an OS boundary
(Finding 5), and **nftables alone cannot enforce a provider *URL* identity across DNS/address changes** —
so a URL-scoped firewall rule is NOT an OS boundary. Therefore C6e makes **C4 a HARD pre-activation gate
for TEG egress**: the TEG service stays `enable=false` / gate-OFF until C4's network profile confines it.
The interim netns/nftables path from v1 is **NOT pre-authorized** as a generic escape hatch. If it is ever
genuinely needed, it requires a **separately-reviewed exact mechanism** (its own design → binding review →
freeze) — this decomposition does not pre-bless it. The auto-revert guard (§0.2) covers the eventual
gate-flip risk, and there is no urgency.

**Exact landed files edited.**
- `nix/modules/services/dispatch-gateway.nix` — the C4-gate hook: the TEG lease-bearing egress path is
  reachable only when C4's confining network profile is in force (declared dependency; no standalone
  egress).
- `config/env-contract.yaml` — TEG egress reference tied to the C4 profile.
- This decomposition document is the normative ordering-resolution artifact; the C4/C6 activation-readiness
  docs are synced by the §7 pre-C4 amendment (a doc change, gated BEFORE C4 freeze — not after).

**Service-Coverage inventory.** Extends C6b's `test-c6b-dispatch-gateway-service-coverage.py` (or a
sibling `test-c6e-egress-gate-coverage.py`): asserts no TEG lease-bearing egress activation is reachable
without C4's confining profile in force; the TEG dashboard section reports the egress-boundary state.
Register `c6e-egress-gate-coverage` in `config/validation-check-registry.json` + wire the probe in
`phase0.py` and `_aq-qa-bash`.

**Dependencies / order.** Requires **C6b** (the TEG principal must exist to confine it) and **C4 in force**.
**Gates the TEG gate-ON activation** (not the build). Last in the sequence.

**Acceptance + freeze criteria.** No TEG lease-bearing egress activation is possible without C4's confining
profile in force; the egress-boundary state is live-visible; coverage + integration checks GREEN. (No
interim netns/nftables boundary is frozen here; if later required it is a separate reviewed slice.)

**Owner activation needed?** The TEG **gate-ON flag-flip** is the owner activation, guarded by C4 in force
+ the auto-revert guard armed.

---

## 7. The pre-C4 contract amendment + C4↔C6 ordering resolution (closes decomposition Finding 2)

### 7.1 Why a doc-sync-after-milestone is not enough

C4's design makes the C6 intervention lever a **freeze prerequisite** (not merely a flag-on one) and today
defines that lever as the durable epoch authority **plus** the live F2.5 scheduler gate
(`C4-DESIGN-AND-AUTHORIZATION.md:12,143-144,191-219`; `C4-ACTIVATION-READINESS-20260806.md:27,43-63`;
`C6-DESIGN-AND-AUTHORIZATION.md:86-90,221-236`). v1 proposed to redefine the lever as C6d+C6a+C6c and to
sync the C4/C6 readiness docs in C6e — **after** the claimed C4-freeze milestone. That is backwards: a
follow-up doc sync cannot retroactively make C6c completion satisfy a prerequisite whose current text
requires the scheduler gate too. The narrowing must be an **accepted contract change that lands BEFORE C4
freeze.**

### 7.2 The pre-C4 contract-amendment step (explicit, gated before C4 freeze)

**Step [AMEND-C4] — a scoped design change, independently reviewed, accepted BEFORE any C4 freeze:**
1. **Amend `C4-DESIGN-AND-AUTHORIZATION.md` §4/§8 and both readiness docs** so C4's freeze prerequisite is
   *precisely*: **"an operational, owner-authorized, signed epoch-bump path"** = **C6d + C6c (+ the C6-S
   socket/transport foundation they require)** — the durable epoch + a reachable authorized owner-bump
   path. The live F2.5 scheduler gate and `authorize_launch` are **removed** from the C4 prerequisite.
2. **Bind C4's own epoch-recheck / channel-teardown behavior as the enforcement** that makes C4 egress
   revocable: C4 already closes channels / invalidates UDS endpoints / terminates cells on epoch bump
   (`C4-DESIGN-AND-AUTHORIZATION.md:138-144`). The amendment states explicitly that *this C4 behavior*,
   driven by the C6d+C6c owner-bump lever, is what makes a C4-widened egress revocable — the revocability
   lives in C4's teardown reacting to the epoch bump, not in the C6 TEG launch fence.
3. **State C6a's actual dependency separately** (per review): C6a is required by **C6b** (its only
   consumer), NOT by C4. C6a is **NOT** counted as part of the C4 kill-lever merely because it shares the
   authority's lock/state machinery.
4. This amendment goes through its **own independent binding review**. Only once it is **accepted** is
   rev5 §6's "C6 flag-enable before C4" **superseded — and only for the TEG-egress activation** (C6b+C6e),
   not for the kill-lever.

### 7.3 The resolved ordering (both "orderings" true, no cycle)

Once [AMEND-C4] is accepted:
- **C6 kill-lever = C6d + C6-S + C6c** lands **BEFORE C4 freeze** and satisfies the amended prerequisite.
  (C4 opens network egress and must be able to bump the epoch to revoke an over-scoped lease before
  widening the network — that ability is exactly this lever, and C4's own teardown enforces it.)
- **C6 TEG-egress seam = C6a → C6b → C6e** is **built** default-OFF (C6a/C6b may build before C4), but its
  **gate-ON activation** is HARD-gated behind C4 in force (§6). This is the part DESIGN-PACKET §8's
  "C4 before C6" correctly orders after C4.

There is no cycle: C4 freeze depends on {C6d, C6-S, C6c, accepted [AMEND-C4]}; none of those depends on
C4. C6a/C6b build independently; only their *activation* waits on C4.

---

## 8. Dependency-ordered sequence + critical path

```
  C6d ─▶ C6-S ─┬─▶ C6a ───────────────────────────────────▶ C6b(build, OFF) ─▶ C6e ─▶ TEG gate-ON
   (foundation) │                                                    │              (needs C4 in force
   recover-     │                                                    │               + auto-revert armed)
   before-      └─▶ C6c ══(owner epoch-bump lever)══╗                │
   listen +                                          ║                │
   StateDirs         [AMEND-C4] accepted ◀═══════════╝                │
   + 2-socket        (C4 prereq := C6d+C6c+C6-S;                      │
   topology           C4 teardown = enforcement)                      │
                              │                                       │
                              ▼                                       │
                     [ C4 freeze eligible ] ─▶ C4 review/freeze/land ─┘
```

Dependency-ordered build sequence (each: design → independent binding review → freeze → default-OFF build):

1. **C6d** — deterministic journal recovery (foundation; recover-before-listen + StateDirs reused by C6-S/
   C6a). *No owner activation.*
2. **C6-S** — shared launch-socket + principal contract (mechanism B; freezes the two-socket/group
   topology). *No owner activation.*
3. **fan out from C6-S (parallel):**
   - **C6a** — `authorize_launch` op + single-use launch-ledger + consume (on the C6-S launch socket).
     *No owner activation. Consumed only by C6b — NOT part of the C4 lever.*
   - **C6c** — callable offline owner submission path (on the C6-S control-socket owner-bump path).
     **Completes the amended C4 freeze prerequisite.** *Owner activation = P-F4 at its own activation time.*
4. **[AMEND-C4]** — amend + independently review C4 design + C4/C6 readiness docs so the prerequisite is
   the operational owner-authorized signed epoch-bump path (C6d+C6c+C6-S), binding C4's own epoch-recheck/
   teardown as the enforcement. **Accepted BEFORE C4 freeze.** Only then is rev5 §6 superseded (TEG-egress
   only).
5. **[C4 freeze eligible]** once [AMEND-C4] is accepted AND C6d+C6c (with C6-S) is operational.
6. **C6b** — TEG-exclusive `authorize_launch` consumer + in-principal execution. *Built default-OFF; gate-ON
   is a later owner act gated by C6e/C4.*
7. **C6e** — C4-as-HARD-pre-activation-gate for TEG egress; **gates TEG gate-ON activation**.

**Critical paths:**
- **To unblock C4's freeze (near-term milestone):** `C6d → C6-S → C6c` + accepted **[AMEND-C4]**. C6c
  completing (with C6d+C6-S) under the amended prerequisite is the event that makes C4 freeze-eligible.
  **C6a is NOT on this path.**
- **To full C6 scheduler-seam activation:** `C6d → C6-S → C6a → C6b → C6e` (+ C4 in force).

C6a and C6c fan out from C6-S and can be designed in parallel — the cross-dependency v1 had (C6c needing
"C6b's group model") is **removed**: the group/socket model is frozen in C6-S, which both consume as a
fixed input.

---

## 9. Decomposition decisions for the reviewer / owner to confirm

1. **Slice set = the five findings + one foundation topology slice.** C6a↔F1, C6b↔F2, C6c↔F3, C6d↔F4,
   C6e↔F5, plus the NEW **C6-S** (socket/principal topology, closing decomposition-review Finding 1).
   **Confirm C6-S as a distinct foundation slice** (vs folding it into C6a's transport contract — kept
   separate here because C6c also depends on the topology and must not wait on C6a).
2. **Build order: C6d → C6-S → {C6a ∥ C6c} → [AMEND-C4] → C4 → C6b → C6e.** **Confirm** the C6-S-second
   and the parallel C6a/C6c fan-out.
3. **C4↔C6 resolution via a pre-C4 contract amendment (§7).** The intervention lever is redefined as
   **C6d+C6-S+C6c** (operational owner-authorized signed epoch-bump path), C4's own teardown is bound as
   the revocability enforcement, C6a is stated as a C6b dependency (NOT part of the lever), and rev5 §6 is
   superseded for TEG-egress activation ONLY after the amendment is accepted. **This is the crux and needs
   an explicit owner/reviewer nod** — it authorizes the C4 amendment to proceed to its own independent review.
4. **Egress = C4 as a HARD pre-activation gate (§6).** No interim netns/nftables escape hatch is
   pre-authorized; if ever needed it is a separately-reviewed exact mechanism (nftables cannot enforce a
   provider-URL identity across DNS changes). **Confirm** (adopted from the review's open decision).
5. **C6b isolation = mechanism B, frozen in C6-S (§2).** Dedicated TEG-only launch socket +
   `aq-revocation-launch-clients` group; existing control socket keeps read/bump clients. **Confirm**
   (adopted from the review's open decision; mechanism A rejected).
6. **Per-slice Service-Coverage inventory (§0.4 + each slice).** Every new-surface slice ships a
   `test-<slice>-service-coverage.py` (mirroring `test-c2-sci-service-coverage.py`), a registered
   `*-coverage` id in `config/validation-check-registry.json`, a dual-harness integration probe
   (`phase0.py` + `_aq-qa-bash`), and a live-backed `aistack.py` + `dashboard.js` surface; C6d/C6-S bind
   the already-landed revocation-epoch coverage path. **Confirm the inventory satisfies the Service
   Coverage Contract** for independent shippability.
7. **rev5 corrections carried in (unchanged from v1):** (a) the CLI verb is `build`, not `prepare`; (b)
   `c2-scheduler-context-issuer.nix:122` has no shared-UID revocation membership to remove; (c) removing
   `primaryUser` from `aq-revocation-epoch-clients` does not by itself achieve TEG-exclusivity — mechanism
   B's separate launch socket/group (C6-S) does. **Confirm accepted.**

### Decisions still needing owner/reviewer confirmation
- **[AMEND-C4] authorization** — this decomposition proposes amending C4's frozen-design prerequisite; the
  amendment itself must clear its own independent binding review before any C4 freeze. Owner nod needed to
  proceed to that review (decision 3).
- **P-F4 activation timing for C6c** — the offline keygen + public-only allowlist rev-4→rev-5 advance is an
  owner activation act; C6c builds dormant until then.

---

**RECORD: PREPARED_ONLY decomposition v2. No implementation, freeze, activation, epoch bump, provider
traffic, deployment, or flag flip is authorized. Each slice (C6d, C6-S, C6a, C6c, C6b, C6e) requires its
own design → independent binding review → hash-bound freeze → default-OFF build, one at a time, with its
Service-Coverage inventory (§0.4). The [AMEND-C4] contract amendment (§7) requires its own independent
review and must be accepted BEFORE C4 freeze. rev5 (`f68ccf91`) proven components (§0.3) are the retained
design basis; its monolithic single-freeze scope remains superseded by this decomposition. This v2 closes
the three HIGH findings of `.agent/collaboration/CODEX-C6-DECOMPOSITION-REVIEW-20260924.md`; the C6a–e
seams it confirmed SOUND are unchanged.**
