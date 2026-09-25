---
title: "Foundation C — C6-S: Shared launch-socket + principal contract (mechanism B — dedicated TEG-only launch socket + aq-revocation-launch-clients group; freezes the two-socket topology before C6a/C6c fan out)"
slice: "C6-S (foundation topology slice of the C6 decomposition — lands immediately after C6d, before C6a/C6c)"
status: "PREPARED_ONLY — authorizes NOTHING (no build, no freeze, no activation, no epoch bump, no provider traffic, no flag flip). Design + authorization note only."
revision: 1
kind: "design-only"
implementation_authorization: "NONE"
activation_authorization: "NONE"
base_head: "f1f409ef97f73fb6ae152a297ba0c0367e30bf22"
parent_decomposition: ".agents/plans/aqos-foundation-c/C6-DECOMPOSITION-20260924.md (factory/c6-decomposition-v2) §2 — C6-S slice spec; §0.4 Service Coverage Contract; §8 build order"
sibling_foundation: ".agents/plans/aqos-foundation-c/C6d-DESIGN-AND-AUTHORIZATION.md (factory/c6d-design-v2, rev2) — shares the authority module + transport __main__ + recover-before-listen barrier + StateDir/Type=notify model; C6-S composes ON TOP of C6d and must not contradict it"
closes_finding: "CODEX-C6-REV5-BINDING-REVIEW-20260924.md Finding 2 (HIGH) — the claimed TEG-only authority boundary was FALSE at the anchored Nix baseline; AND CODEX-C6-DECOMPOSITION-REVIEW-20260924.md Finding 1 — the launch/control-socket topology must be selected and frozen BEFORE C6a/C6c"
mechanism: "B — a dedicated TEG-only launch socket (launch.sock) + a new aq-revocation-launch-clients group. Mechanism A (making a shared socket's SO_PEERCRED authoritative) was REJECTED (decomposition §2)."
authoring_role: "architect (design/planning only)"
owner_activation_needed: "NO — default-safe topology freeze; the launch socket is an idle second listener with no reachable op until C6a lands; no epoch bump, no flag, no key, no owner act"
build_order: "C6d → C6-S → {C6a ∥ C6c} → [AMEND-C4] → C4 → C6b → C6e (decomposition §8). C6-S lands SECOND — after C6d, before C6a and C6c fan out — so neither builds on an unfrozen transport surface."
---

# Foundation C — C6-S: Shared launch-socket + principal contract (mechanism B)

## 0. What this slice is, and why it is second

C6-S is the **second foundation slice** of the freeze-eligible C6 decomposition
(`C6-DECOMPOSITION-20260924.md` §2, §8). It exists so that **no later slice revises a
transport surface a prior slice already froze**: the decomposition review found that v1
deferred the launch/control-socket-group decision to C6b while C6c already declared it needed
"a decided group model" as a dependency — a future/parallel input is not a frozen dependency,
so C6c could not freeze. C6-S closes that seam by **selecting and freezing the socket/principal
topology now**, as a fixed input both C6a (`authorize_launch` op) and C6c (owner submission)
consume.

C6-S also closes **rev5 Finding 2 (HIGH)** — the binding re-review proved the claimed
"TEG-only authority boundary" was **false at the anchored Nix baseline**: two service
principals besides the owner already hold membership of `aq-revocation-epoch-clients`, and
rev5's proposed fix (delete one line + edit a nonexistent membership) would not have achieved
TEG-exclusivity. C6-S makes TEG exclusivity a **property of which socket/group exists**, not of
a per-op peer check layered onto a shared socket, **while preserving the separately
least-privileged epoch-read path** on the untouched control socket.

**Adopted decision — mechanism B (decomposition §2, decision 5).** A **dedicated TEG-only launch
socket** (`launch.sock`) plus a **dedicated `aq-revocation-launch-clients` group** carries
`authorize_launch`; the **existing control socket** is UNTOUCHED and keeps its
separately-authorized read/bump clients. **Mechanism A is rejected** (making a whole shared
socket's `SO_PEERCRED` authoritative) — it would couple the launch fence to a per-op peer check
on the same socket the least-privileged read/bump clients use, and rev5 already treats
`SO_PEERCRED` as defense-in-depth-only.

**This is design-only and PREPARED_ONLY.** It authorizes no implementation, no freeze, no build,
no activation, no epoch bump, no flag flip. The baseline at `f1f409ef` is dormant (sole owner
key `revoked`, gate env absent, authority `enable=false`); C6-S does not change that. C6-S adds
**no dispatch op** and **no consumer**: `authorize_launch` handling is C6a; the TEG membership is
C6b; the owner submission is C6c. It freezes only the socket/group/path topology.

---

## 1. Current anchored baseline (verified against `f1f409ef`)

Every SHA-256 below was computed at `f1f409ef97f73fb6ae152a297ba0c0367e30bf22`. Every file:line
citation was verified against HEAD in this worktree (`command git diff --stat f1f409ef..HEAD`
shows **no source-file drift** — only the sibling design docs differ, so the working tree equals
the anchor for every path cited here).

| Existing path | SHA-256 | C6-S role |
|---|---|---|
| `nix/modules/services/revocation-epoch-authority.nix` | `b539e5de6dd89eb4fd93ed2119055ad9440897b1c408a98f6c23d9ded0db0172` | **EDIT.** Declare the `launch.sock` listener (tmpfiles rule + `serve()` bind) restricted to `aq-revocation-launch-clients`; declare `users.groups.aq-revocation-launch-clients = {};`; add that group to the **authority user's** `extraGroups` (`:102`) for socket-chgrp only; add `AQ_REVOCATION_LAUNCH_SOCKET_PATH` / `AQ_REVOCATION_LAUNCH_CLIENT_GROUP` to the unit `Environment` (`:146-152`). Control socket (`:79`), `aq-revocation-epoch-clients` (`:110`), owner membership (`:111`), and hardening (`:159`/`:161`/`:166`) UNCHANGED. Keeps `enable = false;`. |
| `scripts/ai/lib/revocation_epoch_transport.py` | `066b30c326898d6ef8e4ab085cf82ce131bb9812b08a61993de86b0812a6be28` | **EDIT (`__main__` + a bounded multi-listener helper).** Today `serve()` (`:128`) binds ONE socket and `__main__` (`:301-309`) does `serve(_sp, build_env_handler())`. C6-S makes `__main__` bind **both** sockets after C6d's `recover()` returns, each with its **own per-socket handler**: the control socket keeps `build_env_handler()` (read-epoch/bump, UNCHANGED); the launch socket gets a **deny-all stub handler** (no op reachable — `authorize_launch` is added in C6a). NO change to `build_env_handler()` dispatch, no new op. |
| `config/env-contract.yaml` | *(binds landed shape)* | **EDIT.** Add `AQ_REVOCATION_LAUNCH_SOCKET_PATH` (default `/run/aq-revocation-epoch-authority/launch.sock`) and `AQ_REVOCATION_LAUNCH_CLIENT_GROUP` (default `aq-revocation-launch-clients`) alongside the existing `AQ_REVOCATION_EPOCH_SOCKET_PATH` canonical (`:1339`). New capability flags default `"0"`; these are socket-path/group references (no flag). |
| `dashboard/backend/api/routes/aistack.py` | *(binds landed shape)* | **EDIT (minimal, folded — see §6).** Add a compact `result["revocation_epoch_authority"]` section modelled on the ALA section (`:2090`) / C2-SCI section (`:2112`) reporting `control_socket`, `launch_socket` (`present\|absent`), `launch_group_teg_only`. No new dashboard **card** — rendered within the existing Foundation-C authority health block. |
| `assets/dashboard.js` | *(binds landed shape)* | **EDIT (minimal, folded).** Read `revocation_epoch_authority` and render the launch-vs-control socket rows inside the existing Foundation-C authority health block (no new card). |
| `nix/modules/services/lease-signing-authority.nix` | `2fb53e4c02b42e6478b999781b47b7d283ce3ab0d2283cd5bc88b139be9ad445` | **NO EDIT.** Cited as ground truth: the **ALA** service principal holds `aq-revocation-epoch-clients` at `:76` (`extraGroups = ["aq-lease-signing-clients" "aq-revocation-epoch-clients"]`). C6-S must NOT touch this — the ALA's least-privileged `read-epoch` path on the control socket is preserved. |
| `nix/modules/services/c2-scheduler-context-issuer.nix` | `e14ce66359953e3fc05c9c7fa4242a70db5ed575ab1ce6c2fd94173f95d55800` | **NO EDIT.** Cited as ground truth: the **C2-SCI** issuer principal holds `aq-revocation-epoch-clients` at `:114`; `:122` merely DECLARES the group (`users.groups.aq-revocation-epoch-clients = {};`, not a `primaryUser` membership); `:123` adds `primaryUser` to `aq-c2-scheduler-context-clients` (NOT the revocation group). C6-S must NOT touch this — the C2-SCI `read-epoch` path is preserved. |
| `nix/modules/services/default.nix` | `7873bff56d33f7d798bafa4cc1ecceebdb10975d1ae62c83e48fdcafe94e0ecc` | **NO EDIT.** Already imports `./revocation-epoch-authority.nix` at **line 26** — the authority (and therefore the second socket C6-S adds to it) is already wired into the system. C6-S binds this landed import (Service-Coverage row 2). |
| `config/validation-check-registry.json` | *(binds landed shape)* | **EDIT.** Register the new `revocation-launch-socket-topology` behavioral check (§6), modelled on `c2-sci-service-coverage` (`:1398`) / `ala-service-coverage` (`:1376`). |
| `scripts/testing/harness_qa/phases/phase0.py` | *(binds landed shape)* | **EDIT.** Add the topology probe via `results.extend(...)`, modelled on `_check_intent_classifier_coverage` (`:1325`). Allocate the **next-free id `0.10.52`** (see §6 — `0.10.51` is reserved by the sibling C6d design). |
| `scripts/ai/_aq-qa-bash` | *(binds landed shape)* | **EDIT.** Mirror the same `0.10.52` check id in the bash harness per the dual-harness check-id contract. |

**Landed reality that C6-S changes (verified).**

- The authority serves **one** UDS: `revocation-epoch-authority.nix` `socketPath` defaults to
  `/run/aq-revocation-epoch-authority/control.sock` (`:79`); the transport `__main__` reads
  `AQ_REVOCATION_EPOCH_SOCKET_PATH` (`revocation_epoch_transport.py:302`) and calls
  `serve(_sp, build_env_handler())` (`:309`). `serve()` (`:128`) binds exactly one socket
  (`:142`), `chmod 0o660` (`:143`), chgrps it to `AQ_REVOCATION_EPOCH_CLIENT_GROUP` (`:148`,
  default group `aq-revocation-epoch-clients`, set by the unit at `:148` of the `.nix`), then
  `listen(16)` (`:158`) and `accept()` (`:159`).
- **The control-socket client group `aq-revocation-epoch-clients` is NOT TEG-only today** (the
  exact Finding-2 defect). Its members at `f1f409ef`:
  - the authority's own user — `revocation-epoch-authority.nix:102` (`extraGroups =
    ["aq-revocation-epoch-clients"]`), solely so `serve()` can chgrp the socket to the group
    (`:98-101` comment; chown-to-group requires membership);
  - `primaryUser` (the owner-bump path) — `revocation-epoch-authority.nix:111`
    (`users.users.${primaryUser}.extraGroups = mkAfter ["aq-revocation-epoch-clients"]`);
  - the **ALA** service principal — `lease-signing-authority.nix:76`;
  - the **C2-SCI** issuer principal — `c2-scheduler-context-issuer.nix:114`.
  So deleting `revocation-epoch-authority.nix:111` (rev5's proposal) removes only the owner and
  **leaves ALA + C2-SCI able to reach the socket**; and `c2-scheduler-context-issuer.nix:122` is
  a group DECLARATION rev5 mistook for a shared-UID membership to edit. `SO_PEERCRED` is
  read+logged as **defense-in-depth only** (`revocation_epoch_transport.py:69`, `serve()` log at
  `:163-171`), never authority.
- There is **no launch socket, no `aq-revocation-launch-clients` group, and no
  `authorize_launch` op** anywhere in the landed code.

The final freeze must reproduce every listed hash, confirm the launch socket / launch group /
launch-path env are absent at the base, bind the revised packet hash, reject all other changed
paths, and stop on HEAD drift.

---

## 2. The frozen two-socket topology (mechanism B)

C6-S freezes exactly this transport/principal contract; C6a attaches its op to it and C6c lands
its owner submission on it, both citing this freeze.

### 2.1 The two sockets

| Socket | Default path | Mode / owner-group | Reachable ops | Client group | Group members (at end of the full C6 sequence) |
|---|---|---|---|---|---|
| **control** (unchanged) | `/run/aq-revocation-epoch-authority/control.sock` (`.nix:79`) | `0660`, group `aq-revocation-epoch-clients` (`serve():143/148`) | `read-epoch`, `bump` (`transport:283`,`:290`) | `aq-revocation-epoch-clients` (`.nix:110`) | authority-user (`:102`, chgrp only), owner/`primaryUser` (`:111`, bump), ALA (`lease-signing:76`, read), C2-SCI (`c2:114`, read) |
| **launch** (NEW, C6-S) | `/run/aq-revocation-epoch-authority/launch.sock` | `0660`, group `aq-revocation-launch-clients` | *(none in C6-S; `authorize_launch` added in C6a)* | `aq-revocation-launch-clients` (NEW, declared empty) | authority-user (chgrp only), **TEG** (joins in C6b) — and NO one else, ever |

Both sockets live in the **same** RuntimeDirectory (`/run/aq-revocation-epoch-authority`, the
`0755` world-traversable dir declared at `.nix:117`), so no new directory rule is needed — only a
new socket inode inside it. Both are **AF_UNIX-only** (the unit's
`RestrictAddressFamilies = ["AF_UNIX"]` at `.nix:166` covers the whole process; C6-S adds no new
address family).

### 2.2 The exact group/membership edits (the precise close of Finding 2)

This is the operative list. **Which principal goes in which group; which line adds/removes what:**

1. **NO edit to `aq-revocation-epoch-clients` membership.** ALA (`lease-signing-authority.nix:76`),
   C2-SCI (`c2-scheduler-context-issuer.nix:114`), owner (`revocation-epoch-authority.nix:111`),
   and the authority user (`revocation-epoch-authority.nix:102`) all stay members. The
   least-privileged `read-epoch` path (ALA, C2-SCI) and the owner-`bump` path on the **control**
   socket are preserved byte-for-byte. **C6-S does NOT delete `revocation-epoch-authority.nix:111`**
   — rev5's proposed deletion is unnecessary and would not have achieved exclusivity anyway.
2. **NEW group, declared empty:** in `revocation-epoch-authority.nix`, add
   `users.groups.aq-revocation-launch-clients = {};` (mirroring the empty declaration of
   `aq-revocation-epoch-clients` at `:110`, and exactly as `c2-scheduler-context-issuer.nix:122`
   declares a group empty). **No human or service principal is added to it in C6-S** — the TEG
   JOINS it in C6b (`dispatch-gateway.nix`).
3. **Authority user joins the launch group for chgrp only:** edit the authority user's
   `extraGroups` at `revocation-epoch-authority.nix:102` from `["aq-revocation-epoch-clients"]` to
   `["aq-revocation-epoch-clients" "aq-revocation-launch-clients"]`. This is required for the same
   reason as `:98-101`: `serve()` chgrps the socket to its client group, and chown-to-group
   requires the process's user to be a member. It grants **no launch authority** — the authority
   is the *server* of the launch socket, never a *client* of its own `authorize_launch` op; no
   process running as the authority user ever connects to request a launch token.
4. **The owner/`primaryUser` is NOT added to `aq-revocation-launch-clients`** (`:111` unchanged).
   The operator kill-lever stays on the **control** socket, structurally severed from the launch
   surface — so narrowing the launch surface can never sever the kill-lever, and the launch surface
   can never be reached by the owner-bump path. This is the surface C6c's owner submission lands on.
5. **NEW launch socket declared:** a `systemd.tmpfiles`/`serve()`-created inode
   `launch.sock` in the existing `0755` runtime dir (`.nix:117`), `0660`, chgrped to
   `aq-revocation-launch-clients`, bound after `recover()` (§3).

### 2.3 Why this is an enforceable boundary — and whether `SO_PEERCRED` is authoritative

**Socket-level group gating is the authoritative check under mechanism B; `SO_PEERCRED` remains
defense-in-depth logging only.** The reasoning is asymmetric between the two sockets and this
asymmetry is the whole point:

- On the **control** socket the trust boundary is **the owner-signed bump document**, verified
  inside `apply_bump` against the public allowlist (`revocation-epoch-authority.nix:12-19`,
  `:80`). `read-epoch` is non-mutating; `bump` advances nothing without an active-owner Ed25519
  signature. So it is *safe* for owner + ALA + C2-SCI + authority-user to be able to connect —
  connecting grants nothing (`transport:1-13` module docstring: "transport membership is NEVER
  sufficient authority"). This is why C6-S leaves that group's membership untouched.
- On the **launch** socket the op `authorize_launch` (C6a) carries **no owner signature** — rev5
  §3.2 established the token is minted by the authority under its lock, not owner-signed. Because
  `SO_PEERCRED` is defense-in-depth-only (`transport:9-10`, `:69-71`, `:163-171`), a *shared*
  socket could not enforce "only the TEG may launch" — precisely rev5's false claim. Under
  mechanism B the **kernel-enforced `0660` group permission on a separate inode IS the
  authority**: only members of `aq-revocation-launch-clients` can `connect()` to `launch.sock`,
  and the only consumer ever added to that group is the TEG (C6b). ALA (holds
  `aq-revocation-epoch-clients`, not launch), C2-SCI (same), and the owner (holds
  `aq-revocation-epoch-clients` only) are **structurally excluded** from the launch socket — the
  exclusion is a property of group membership, checked by the kernel at `connect()`, not of any
  in-process peer inspection.

**Defense-in-depth recommendation carried to C6a (not a C6-S freeze condition).** Because the
launch op is un-signed, C6-S RECOMMENDS that C6a additionally assert an operation-specific
`SO_PEERCRED` check binding the connecting peer's uid/gid to the TEG principal, as belt-and-
suspenders. But the **freeze's authority claim rests on the group boundary**, not on
`SO_PEERCRED`; C6-S changes nothing about `SO_PEERCRED`'s log-only posture (`transport:163-171`
untouched). This directly answers Finding 2's "specify an operation-specific TEG peer check, a
dedicated launch socket/group, or the necessary membership edits" — C6-S chooses the dedicated
socket/group as the enforceable boundary and states the membership edits exactly (§2.2).

---

## 3. How C6-S composes with C6d (recover-before-listen, readiness, StateDirs)

C6-S lands **after** C6d and builds directly on C6d's transport `__main__` edit. It must not
contradict C6d's recover-before-listen / `Type=notify` / StateDirectory model
(`C6d-DESIGN-AND-AUTHORIZATION.md` §3.4, §1). The composition rule:

**Both listeners bind only after `recover()` returns; readiness signals only after BOTH are
listening.** Concretely:

1. **C6d** changed the transport `__main__` (`revocation_epoch_transport.py:301-309`) from
   "bind-and-serve immediately" to: **acquire `epoch.lock` → `revocation_epoch.recover()` →
   release → `serve()`**, and changed the unit `Type=simple` (`.nix:139`) to `Type=notify`,
   emitting `sd_notify(READY=1)` only after `recover()` returns.
2. **C6-S** extends that `__main__` to bind **two** sockets after the *same single* `recover()`
   pass — recovery is a property of the shared journal/epoch state, not of any one socket, so it
   runs **once**, before either socket binds. The transport binds `control.sock` and `launch.sock`
   (each `bind` → `chmod 0660` → chgrp → `listen`) and multiplexes `accept()` across both in one
   loop (a `selectors.DefaultSelector` over the two listening sockets — the minimal bounded change
   to the existing single-socket `serve()`; the generic accept/`read_frame`/dispatch machinery at
   `transport:159-185` is reused per connection, with the per-socket handler chosen by which
   listener produced the connection).
3. **`sd_notify(READY=1)` fires only after `recover()` has returned AND both sockets are
   `listen()`-ing.** No dependent unit and no client observes the authority ready until the
   journal is reconciled (C6d) and both sockets are accepting (C6-S). The in-process order is
   purely: `recover()` → `bind(control)` → `bind(launch)` → `listen(both)` →
   `sd_notify(READY=1)` → `accept` loop. Because the authority binds its own sockets (no systemd
   socket-activation), there is no external ordering to reconcile.
4. **StateDirectories are unchanged by C6-S.** C6-S adds no StateDirectory — the launch socket is
   a `/run` runtime inode, not durable state, and the launch **ledger** is C6a's concern (C6a adds
   the launch-ledger StateDirectory reusing C6d's recover-before-listen ordering). C6-S touches
   only `/run` (the socket) and group declarations.

**No contradiction with C6d.** C6-S does not alter `recover()`, the journal, the two uniqueness
indexes, `Type=notify`, or the readiness semantics — it only makes the post-recovery bind cover
two sockets instead of one. C6d's `__main__`-only edit-surface claim
(`C6d-DESIGN-AND-AUTHORIZATION.md` §1) is preserved: C6-S's transport change is likewise confined
to `__main__` + a bounded multi-listener helper, and does not touch `build_env_handler()`'s call
site (`transport:296`) or `apply_bump`'s signature.

---

## 4. How this closes rev5 Finding 2 (and decomposition Finding 1)

| Concern | Landed/ rev5 gap | C6-S closure |
|---|---|---|
| **Claimed TEG-only boundary FALSE at the anchor** | rev5 asserted the TEG was the only member able to reach the authority control socket; in fact ALA (`lease-signing:76`) + C2-SCI (`c2:114`) + owner (`authority:111`) all hold `aq-revocation-epoch-clients`. | §2.1/§2.2: `authorize_launch` moves to a **separate** `launch.sock` gated by a **new** `aq-revocation-launch-clients` group whose only ever-added consumer is the TEG (C6b). ALA/C2-SCI/owner hold only `aq-revocation-epoch-clients` → structurally excluded from launch. |
| **rev5's fix would not work** | Deleting `authority:111` removes only the owner; editing `c2:122` edits a group declaration, not a membership. | §2.2 item 1: C6-S makes **no** membership edit to `aq-revocation-epoch-clients` and does **not** delete `:111`; exclusivity comes from the separate socket/group, not from removing members of the shared one. |
| **`SO_PEERCRED` non-authoritative** | rev5 relied on a peer check that is log-only (`transport:163-171`). | §2.3: the **kernel-enforced `0660` group on a separate inode** is the authority; `SO_PEERCRED` stays log-only; C6a MAY add an op-specific peer check as belt-and-suspenders (not a freeze condition). |
| **Least-privileged epoch-read path must be preserved** | Finding 2 requires exclusivity "while preserving a separately least-privileged epoch-read path." | §2.2 item 1: the control socket + `aq-revocation-epoch-clients` are untouched, so ALA/C2-SCI `read-epoch` and the owner `bump` path keep their exact current least-privileged access. |
| **Topology chosen too late (decomposition Finding 1)** | v1 deferred the socket/group model to C6b; C6c depended on it → C6c could not freeze. | This slice freezes the topology **now** (before C6a/C6c). C6a cites the launch socket; C6c cites the control-socket owner-bump path. Neither waits on the other, and neither builds on an unfrozen surface. |

---

## 5. Exclusions

C6-S touches **only** the files in §1. Explicitly excluded (each is a later slice or out of scope):

- The `authorize_launch` **op dispatch**, the single-use launch-token ledger, and its `consume`
  verb — **C6a** (C6-S's launch handler is a deny-all stub; no op is reachable).
- The **TEG principal joining `aq-revocation-launch-clients`**, `dispatch_gateway.py` /
  `dispatch-gateway.nix`, in-principal provider execution — **C6b**.
- The offline owner-key **submission path** and `aq-epoch-bump` verb reconciliation — **C6c**
  (which lands on the C6-S control-socket owner-bump path).
- Any owner public-key allowlist change or epoch bump — **P-F4** (C6c activation), not C6-S.
- The deterministic journal recovery / `recover()` / two-index shape / `Type=notify` change —
  **C6d** (C6-S composes on top of it; §3).
- TEG egress confinement / C4 gate — **C6e / C4**.
- `slot_queue` / `dispatch.py` scheduler-gate fence, `CAPABILITY_SCHEDULER_LEASE_GATE` — later C6.
- The auto-revert guard (decomposition §0.2 — no C6 slice modifies it).
- Provider invocation, network, DDL, deployment, activation, flag flips.

Any need to touch an excluded path is a **stop condition** requiring a new reviewed design, not
expansion of C6-S.

---

## 6. Service-Coverage inventory (decomposition §0.4)

C6-S adds **no new public consumer surface** (the launch socket carries no reachable op until
C6a) → per §0.4 it **binds the already-landed revocation-epoch authority coverage path** rather
than shipping a new `test-<slice>-service-coverage.py`, and names it explicitly, PLUS registers
one new topology integration check:

- **env-contract** (row 1) — **NEW references, no flag.** `AQ_REVOCATION_LAUNCH_SOCKET_PATH`
  (default `/run/aq-revocation-epoch-authority/launch.sock`) and
  `AQ_REVOCATION_LAUNCH_CLIENT_GROUP` (default `aq-revocation-launch-clients`) added to
  `config/env-contract.yaml` alongside the existing `AQ_REVOCATION_EPOCH_SOCKET_PATH` canonical
  (`:1339`). These are socket-path/group references, not capability flags — C6-S introduces **no**
  capability flag, so the "new flags default `\"0\"`" rule has nothing to gate.
- **Nix service + import** (row 2) — **bound to the landed import:** `revocation-epoch-authority.nix`
  is already imported at `default.nix:26`. C6-S edits that module (second socket + new group +
  authority-user launch-group membership + two env refs) but adds **no new module** and does not
  touch the import. The module stays `enable = false;`, `RestrictAddressFamilies = ["AF_UNIX"]`
  (`:166`), `NoNewPrivileges` / `ProtectSystem = "strict"` (`:159`/`:161`) unchanged; the launch
  socket uses the dedicated `aq-revocation-launch-clients` group.
- **Durable primitive** (row 3) — n/a: C6-S adds no ledger/atomic primitive (the launch-token
  `O_EXCL` ledger is C6a).
- **Flag-gated call path** (row 4) — n/a: C6-S adds no gated call path. **Gate-OFF byte-parity
  holds** (§7): the authority stays `enable=false`; when enabled, the launch socket's deny-all
  stub handler adds no reachable op and changes no `read-epoch`/`bump` trace on the control socket.
- **Dashboard API + UI** (rows 5, 6) — **minimal, folded into the existing authority health
  block; no new card.** Ground-truth note (reported faithfully): there is currently **no dedicated
  `revocation_epoch_authority` result section** in `aistack.py` — the authority is only indirectly
  visible via the C2-SCI section's `read-epoch` consumption, and that path touches **only the
  control socket**, so the launch-vs-control topology is **not observable** through it. To satisfy
  §0.4 rows 5-6 and review Finding 3's observability bar, C6-S adds a **compact live-backed**
  `result["revocation_epoch_authority"]` section (modelled on the ALA section at `aistack.py:2090`
  / C2-SCI at `:2112`): `control_socket` / `launch_socket` = `present\|absent` (probed live from
  `/run`, no hard-coded healthy state, no `--` placeholder), `launch_group_teg_only` (bool: the
  launch group's non-authority members ⊆ {TEG}). `assets/dashboard.js` renders these two rows
  **inside the existing Foundation-C authority health block** — **no new dashboard card** (a
  separate card would duplicate the block without giving the operator a new action). *(This
  extends the decomposition §2 file list, which named only the `.nix`/transport/env-contract
  files; the decomposition's own §2 coverage paragraph already calls for "extend the existing
  authority health row to show both sockets" — C6-S makes that concrete with the minimal
  API+UI edit, flagged here for the reviewer.)*
- **Crypto/service tests exist** (row 7) — the topology assertions live in the integration probe
  below (C6-S ships no new crypto; the launch socket has no op). No new `test-*.py` unit file is
  required; the probe is the coverage.
- **Integration-check registration (NEW, required)** (row 8) — register
  **`revocation-launch-socket-topology`** in `config/validation-check-registry.json` (modelled on
  the `c2-sci-service-coverage` entry at `:1398`: `id`, `description`, `trigger_paths` =
  [`revocation-epoch-authority.nix`, `revocation_epoch_transport.py`, `config/env-contract.yaml`,
  `dashboard/backend/api/routes/aistack.py`, `assets/dashboard.js`], `command`, `tier:"behavioral"`,
  `timeout_seconds`, `enabled:true`), **AND** wire the topology probe in **BOTH** harnesses per
  the dual-harness check-id contract:
  - `scripts/testing/harness_qa/phases/phase0.py` — a new `_check_revocation_launch_socket_topology(ctx)`
    returning `CheckResult`, added via `results.extend(...)`, modelled on
    `_check_intent_classifier_coverage` (`:1325`). Allocate the **next-free id `0.10.52`**.
    **Verified at `f1f409ef` the current max id is `0.10.50` in BOTH `phase0.py` and `_aq-qa-bash`;
    the sibling C6d design reserves `0.10.51`, so C6-S takes `0.10.52`** to avoid a collision when
    both land.
  - `scripts/ai/_aq-qa-bash` — the mirror
    `_check 1 "0.10.52" "revocation launch-socket topology" …` line, per the dual-harness contract.
  - **The probe asserts** (an integration exercise, not just static parsing): the **launch socket
    exists and admits only `aq-revocation-launch-clients`** (its inode is `0660` and group-owned by
    that group; no other principal group can `connect`); the **control socket still admits
    `aq-revocation-epoch-clients` for `read-epoch`/`bump`**; the **owner-bump path is NOT in the
    launch group** (`primaryUser` ∈ `aq-revocation-epoch-clients`, ∉ `aq-revocation-launch-clients`);
    **both sockets are AF_UNIX-only**; and the launch socket has **no reachable op** (a well-formed
    request over it yields a typed deny — C6-S's stub — until C6a lands).

---

## 7. Freeze, authorization, and activation

**Freeze criteria (all must hold):**
1. The **two-socket topology is frozen**: `launch.sock` declared, `0660`, chgrped to the new
   `aq-revocation-launch-clients` group; control socket + `aq-revocation-epoch-clients` byte-for-
   byte unchanged; both AF_UNIX-only.
2. **Membership is exactly as §2.2**: no member added to or removed from `aq-revocation-epoch-clients`;
   `aq-revocation-launch-clients` declared **empty** of non-authority principals (TEG joins in C6b);
   authority user in **both** groups (chgrp only); owner (`:111`) in `aq-revocation-epoch-clients`
   only, **not** the launch group.
3. ALA (`lease-signing:76`) + C2-SCI (`c2:114`) retain `read-epoch` on the control socket; the
   owner-`bump` path is present on the control socket and NOT on the launch group (the surface C6c
   lands on).
4. **Composes with C6d (§3):** both sockets bind only after `recover()` returns; `sd_notify(READY=1)`
   fires only after both are listening; no change to C6d's `recover()`/journal/`Type=notify`.
5. **Gate-OFF byte-parity — scoped to C6-S's own freeze criterion:** the authority ships
   `enable=false`; with the launch handler a deny-all stub, **no new op is reachable and every
   existing `read-epoch`/`bump` call trace on the control socket is byte-for-byte identical**. The
   parity claim is scoped to C6-S's edit (the added idle listener + group), not to the whole C6
   gate — `CAPABILITY_SCHEDULER_LEASE_GATE` is out of scope (§5).
6. The **`revocation-launch-socket-topology` integration check is GREEN in both harnesses**
   (phase0 `0.10.52` + bash mirror), per §6.
7. The freeze binds the exact candidate hashes, reproduces the §1 base hashes, confirms the launch
   socket / launch group / launch-path env are **absent at the base**, rejects all other changed
   paths, and stops on HEAD drift.

**Authorization / activation note — C6-S needs NO owner activation.** C6-S is **default-safe**:
it declares an **idle second listener** on an authority that ships `enable = false;`. The launch
socket has **no reachable op** until C6a lands and **no member besides the authority-user's
chgrp role** until the TEG joins in C6b, so binding it grants nothing and reaches no one. C6-S
performs **no epoch bump**, flips **no flag**, provisions **no key**, opens **no network**
(AF_UNIX only), and adds **no capability flag**. Enabling the authority unit is a separate, later
owner act that C6-S does not perform and does not depend on. There is **no owner activation act
tied to C6-S**. The baseline stays dormant.

**Dependencies / order.** Requires **C6d** (StateDir/`recover()`/`Type=notify` machinery + the
recover-before-listen barrier the launch socket composes with — §3). **Lands immediately after
C6d, before C6a and C6c** (decomposition §8). Successors: **C6a** attaches `authorize_launch` to
the launch socket frozen here; **C6c** lands the offline owner submission on the control-socket
owner-bump path frozen here; **C6b** adds the TEG to `aq-revocation-launch-clients`. This freeze
is the transport/principal contract C6a and C6c cite.

---

**RECORD: PREPARED_ONLY revision 1. No implementation, freeze, activation, epoch bump, provider
traffic, deployment, restart, network authority, or flag flip is granted by this document. C6-S is
the second foundation slice of `C6-DECOMPOSITION-20260924.md` (§2, §8); it requires its own
independent binding review → hash-bound freeze → default-OFF build, per the decomposition's
per-slice contract. This document closes rev5 (`f68ccf91`) Finding 2 (HIGH) at design level via
mechanism B (a dedicated TEG-only `launch.sock` + `aq-revocation-launch-clients` group, control
socket + `aq-revocation-epoch-clients` untouched) and decomposition-review Finding 1 (freeze the
socket topology before C6a/C6c). It composes on top of C6d's recover-before-listen /
`Type=notify` model (§3) and contradicts none of it. The rev5 §3.2 in-principal-execution basis
that the launch socket ultimately serves is retained as the C6b design basis (decomposition
§0.3).**
