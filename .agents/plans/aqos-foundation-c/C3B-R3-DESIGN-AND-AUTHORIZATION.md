---
title: "Foundation C C3b R3: Default-OFF Execution Cell Runner (bwrap) — Design Packet"
slice: "C3b / R3"
status: "R3_DESIGN_REVIEWED_PASS — build blocked on single-use owner activation (enforcement-tier)"
review: "antigravity/gemini (independent, codex-substitution) PASS — 9/9 obligations CLOSED, SF-2 resolved favorably (no global userns change), R0 #7 + switchboard byte-parity resolved; Q-R3-1..4 endorsed; 2 findings folded (Delegate=true, RuntimeDirectory). Opus-verified. codex confirmatory queued Aug-4."
revision: 1
kind: "design-only"
implementation_authorization: "NONE — enforcement-tier: requires single-use owner activation before build"
activation_authorization: "NONE"
author: "Opus (codex-substitution — codex usage-limited to 2026-08-04; catch-up audit queued)"
predecessors:
  - "C3b R0 PASS, R1 PASS (+code 102/102), R2 PASS (+code in progress)"
  - "C2 tool-lease gate, flag OFF (97131faa)"
successors:
  - "C3b R4 revocation + performance gate"
  - "C3b R5 default-OFF switchboard adapter"
---

# Foundation C — C3b R3: Default-OFF Execution Cell Runner

## 0. Provenance & authority
Authored by Opus (codex-substitution; codex usage-limited to 2026-08-04, confirmatory audit
queued). Independent review → antigravity/gemini lane + codex-on-return. **DESIGN-ONLY.**
**R3 is ENFORCEMENT-TIER** (it constructs and runs a real confined process): per the packet's
R0–R6 discipline + Rule 15, R3 IMPLEMENTATION requires a **single-use owner activation** before any
build — this design authorizes nothing to be built, deployed, flag-flipped, or committed as runner
code. It composes R1 (grant verification) + R2 (self-contained clone) into a socket-activated runner
that confines a bounded command in bwrap. **Default OFF; no switchboard adoption (that is R5); no
network (C4); no live traffic.**

## 1. Scope (R0 §5 R3 row — bounded)
Deliver: a **dedicated, socket-activated runner service**; its **verified request protocol** (UDS,
grant-verified); **bwrap cell construction** over an R2 `CellReady`; the **supervision + kill + final
epoch fence**; the **Nix service unit** (runner-only scoped namespace relaxation, switchboard
untouched); and **offline runner tests**. **Out of scope:** switchboard routing/adoption (R5),
network profiles (C4), the measured perf gate (R4 — R3 only wires the cgroup accounting it needs),
auto-merge, live traffic.

## 2. SF-2 resolved (host userns grounding — favorable)
Grounded 2026-07-29: `unshare --user --map-root-user` succeeds and `/proc/sys/user/
max_user_namespaces = 111259` — **the host kernel already permits unprivileged user namespaces.**
Therefore R3 needs **NO** global `security.unprivilegedUsernsClone` change (the R0 SF-2 threat item
is closed favorably). Only the **runner's own** systemd unit relaxes `RestrictNamespaces` to exactly
`CLONE_NEWUSER|CLONE_NEWNS` (+ the pid/net/ipc/uts/cgroup namespaces bwrap unshares are created
*inside* the user namespace, so no host privilege is granted). The switchboard unit's
`RestrictNamespaces=true` + `NoNewPrivileges=true` + empty caps (`switchboard.nix:534/526/519`)
remain **byte-for-byte unchanged** (obligation 9, monotonic hardening).

## 3. The runner service (boundary + posture)
A new dedicated service `aq-execution-cell-runner` (the R0-named component):
- **Socket-activated** on a UDS `/run/aq-execution-cell-runner/control.sock`,
  `SocketMode=0660`, `SocketUser=aq-execution-cell-runner`, `SocketGroup=aq-execution-cell-clients`;
  only the switchboard identity joins the client group. **`SO_PEERCRED`** authenticates every peer;
  a non-client peer → drop. The UDS is **transport only** — it conveys no authority.
- **Dedicated unprivileged system user** `aq-execution-cell-runner`; **no** membership in any
  privileged group.
- Hardening kept: `NoNewPrivileges=true`, `CapabilityBoundingSet=""`, `ProtectSystem=strict`,
  `ProtectHome=true`, `PrivateTmp`, private devices; writable paths limited to
  `StateDirectory=aq-execution-cell-runner` (cell root + quarantine under `/var/lib/…`). The ONLY
  relaxation vs the switchboard is the scoped `RestrictNamespaces` above.
- **Bounded concurrency:** `maxConcurrentCells` default 1 (max 2 before a new review); a bounded
  request queue; low-cardinality telemetry only.

## 4. Request protocol (grant-verified, deny-closed)
Per request over the UDS:
1. **Peer check** — `SO_PEERCRED` ∈ client group, else drop (no error oracle).
2. **Verify grant** — deserialize the signed grant; run R1 `verify_grant(grant, PUBLIC_KEY, now,
   current_epoch, reservation_set)`. The runner holds ONLY the Ed25519 **public** key (R1 SF-1 — a
   compromised runner cannot forge). Any `Denial` → typed denial, no cell. Authority-degrade
   (`AuthorityUnavailableContext`) → deny privileged; only the C2-signed safe-read set survives.
3. **Create cell** — R2 `create_cell(verified_grant, bare_mirror_path, cell_state_root, …)`; on any
   `TypedFailure` → typed denial + quarantine (no partial run).
4. **Confine + run** — build bwrap argv from the VERIFIED grant only (§5) and run the grant's single
   **bounded command descriptor** (never caller shell text) inside the cell, tracked in a dedicated
   **cgroup v2** scope.
5. **Supervise** (§6) → **validate** (§7) → **typed result** (GREEN diff-retained-for-review /
   RED / QUARANTINED). **No auto-merge, ever** — a retained diff is an orchestrator-and-review
   decision outside R3.

## 5. bwrap argv (derived only from the verified grant; deny-closed baseline)
`--unshare-all` (user+mount+pid+net+ipc+uts+cgroup) + `--unshare-net` (explicit deny-all egress;
C4 is the only future authority that may add a profile) + `--die-with-parent` + `--new-session`;
`--clearenv` + a fixed minimal env allowlist; `--ro-bind /nix/store /nix/store`; the minimal
read-only runtime inputs; `--proc /proc`, a minimal `--dev /dev`, `--tmpfs /tmp`; **one** writable
bind = the R2 cell root; **no** host home, **no** live repo / `.git`, **no** device/secret/mount
beyond the above; **no** ambient capabilities. If bwrap is missing, userns is unavailable, or cell
construction fails → typed `confinement-unavailable` denial. **There is NO unsandboxed / in-process
/ direct-exec fallback** (explicitly forbid the aider `AI_AIDER_SANDBOX_FALLBACK_UNSAFE` pattern).

## 6. Supervision, revocation, kill (folds R0 finding #7)
- The authoritative epoch source is `capability_lease_gate.resolve_current_epoch` reading
  `config/capability-lease-epoch` (frozen R1 dependency). Poll epoch + process liveness every
  **250 ms**; a **runner-generated** heartbeat bound to `{grant_digest, receipt_id, pid,
  proc_starttime, cgroup_path}` with a **1 s** local deadline (caller heartbeats are NEVER trusted).
- Terminal triggers: timeout, heartbeat miss, **epoch bump (revocation)**, peer/receipt mismatch,
  worker crash, malformed result. On any trigger: mark receipt TERMINATING, `cgroup`-scoped
  SIGTERM, wait ≤ 500 ms, then `cgroup.kill`/SIGKILL, wait ≤ 4.5 s for the WHOLE tracked tree to
  disappear. **Failure to prove the tree is gone → QUARANTINED**, never GREEN, never a false
  finite-redelivery claim.
- **Final epoch fence:** only after the tree is proven absent AND the out-of-cell validator returns,
  the runner **re-reads the authoritative epoch** and re-checks grant freshness + heartbeat/receipt
  binding immediately before publishing GREEN. Any failure flips the result to RED/QUARANTINED.

## 7. Out-of-cell validator (folds R0 §6.4)
The cell's git metadata + files are **untrusted evidence**, not the verdict. A separate validator
(outside the cell, its own confinement) receives only `{grant_digest, base_oid, cell_root, declared
output paths}`. It obtains the base tree from the trusted object source (or a fresh validator-built
clone), and compares filesystem **bytes/modes/symlink-targets/adds/deletes** directly against the
base. It runs **no** `git diff`, hooks, filters, clean/smudge, textconv, attributes, config, or
cell-controlled executables; it clears repo/system/global git config. Every changed path MUST equal
one declared, signed, canonically-rebased output path (via R1 `PathPlan` / R2 resolution). Any
undeclared change, special file, path escape, unreadable entry, base mismatch, validator timeout, or
error → typed **RED**. Only the validator's signed result satisfies the §6 final GREEN fence.

## 8. Nix declaration (Rule 13; monotonic — obligation 9)
- NEW `nix/modules/services/execution-cell-runner.nix`, imported by
  `nix/modules/services/default.nix`; options under `mySystem.ai.executionCellRunner`:
  `enable` (default **false**), `socketPath`, `stateDirectory`, `maxConcurrentCells` (1, max 2),
  `requestTimeoutSeconds`.
- NEW system user/group `aq-execution-cell-runner` + client group `aq-execution-cell-clients`
  (switchboard identity only).
- `systemd.sockets.aq-execution-cell-runner` + `systemd.services.aq-execution-cell-runner` with the
  §3 hardening; `RestrictNamespaces` = exactly `CLONE_NEWUSER CLONE_NEWNS`; executable PATH contains
  exactly the packaged runner deps + `${pkgs.bubblewrap}/bin/bwrap`.
- **`Delegate = true`** on the runner service (antigravity SHOULD-FIX; answers Q-R3-3): an
  unprivileged runner can only write `cgroup.kill` / control its cell cgroup subtree if systemd
  delegates it — required for the §6 whole-tree reap. Delegate the minimal controllers needed
  (`pids`, `memory` for the R4 accounting), not the full set.
- **`RuntimeDirectory = "aq-execution-cell-runner"`** (antigravity NICE-TO-HAVE) so systemd
  creates/owns/tears down the `/run/aq-execution-cell-runner/` socket dir with correct mode/owner,
  rather than the service managing `/run` paths itself.
- **`switchboard.nix` unchanged, byte-for-byte** (asserted by test).
- NEW flag `CAPABILITY_EXECUTION_CELLS` default "0" + its `config/env-contract.yaml` declaration.

## 9. Offline runner tests (acceptance — no live traffic, no switchboard)
Hermetic, using a throwaway bare mirror + a real UDS in a temp runtime dir:
- valid grant + trivial bounded command (`noop`, `single-file-write`) → GREEN; the write lands
  ONLY in the cell; the out-of-cell validator confirms exactly the declared path changed.
- `--unshare-net` blocks egress (IPv4/IPv6/DNS/loopback-service/inherited-socket tests all fail-closed).
- an in-cell process attempting a write outside the cell (via `..`/symlink/abs) → refused by the
  kernel/rebase, RED/quarantine.
- bwrap/userns unavailable (simulate) → `confinement-unavailable` DENY, **never** an unsandboxed run.
- epoch bump mid-run → tree killed (cgroup), rollback/quarantine, no GREEN; final epoch fence flips a
  would-be GREEN to RED when the epoch moves after validation.
- teardown that cannot prove removal → Quarantined; reconcile idempotent.
- non-client UDS peer (SO_PEERCRED) → dropped; a replayed grant_id → denied (R1 reservation).
- flag OFF → the runner refuses/does-not-construct cells (default-OFF proof); switchboard.nix byte-parity.

## 10. Review obligations (independent reviewer must test)
1. runner is the ONLY userns holder; switchboard hardening byte-for-byte unchanged; no global userns change.
2. UDS is transport-only; SO_PEERCRED enforced; no error oracle; UDS conveys no authority.
3. grant verified by R1 with the PUBLIC key only; deny-closed; authority-degrade → safe-read only.
4. bwrap argv derived only from the verified grant; deny-all net; single writable = cell root; no
   live .git/home/secret/device; NO unsandboxed fallback.
5. epoch/heartbeat supervision + cgroup whole-tree kill + prove-absence-or-quarantine + final epoch fence.
6. out-of-cell validator ignores all cell-controlled git config/hooks/attributes; declared-paths-only.
7. no auto-merge; GREEN only retains a diff for separate orchestrator review.
8. Nix: runner-only scoped RestrictNamespaces, NoNewPrivileges, empty caps, ProtectSystem=strict,
   StateDirectory; flag default OFF + env-contract.
9. scope: no switchboard adoption, no network, no live traffic, no perf-gate claim (R4 owns numbers).

## 11. Ceremony (enforcement-tier)
design → independent review → freeze (subject = this doc; predecessor hashes R1 code + R2 code +
capability_lease*.py + gate @ their commit; the exact Nix hardening declarations; runner protocol +
bwrap argv; validator contract; offline vectors) → **single-use owner activation** (hash-bound,
`aq-event emit --agent owner --type activation.grant`) → build **flag-default-OFF** → independent
review → commit. Turning the flag ON + Nix `enable=true` in the running system is a FURTHER separate
owner act (R6 canary). Standing authorization does NOT activate R3.

## 12. Open questions for review
- Q-R3-1: persistent socket-activated runner (this design) vs per-call `systemd-run` transient unit
  (systemd creates the sandbox; nothing in userspace fights RestrictNamespaces). R0 deferred the
  transient design for a separate comparison — reviewer: is the persistent runner the right R3
  baseline, with transient as a later documented alternative? (Recommend yes.)
- Q-R3-2: validator confinement — its own bwrap cell vs a minimal separate hardened unit. Recommend
  its own minimal cell (no net, ro base, its own throwaway validation clone).
- Q-R3-3: cgroup v2 delegation for an unprivileged runner — does the runner get a delegated cgroup
  subtree (systemd `Delegate=`) sufficient for `cgroup.kill`, without extra privilege? (Ground before freeze.)
- Q-R3-4: is the bounded "command descriptor" vocabulary for R3 limited to noop/read-validate/
  single-file-write (matching R1's conservative classification), deferring richer commands to a
  later reviewed slice? (Recommend yes — smallest enforceable first cell.)

**Requested reviewer result:** `PASS` / `FAIL` / `REQUEST_REVISION` against R3 scope + the §10
obligations. No review outcome authorizes build or activation; R3 build additionally requires
single-use owner activation.
