---
title: "Foundation C — R7: Trusted-Repo Mirror + Durable Reservation Provisioning (GREEN cell round-trip)"
slice: "C3b / R7"
status: "DESIGN — PREPARED_ONLY; independent review + single-use owner activation required before build"
tier: "enforcement"
kind: "design-only"
author: "Opus (orchestrator, analysis-tier)"
base_head_at_design: "a439527f"
predecessors:
  - "runner-hardening rev4 accepted+integrated (0cf1192e); R6 deploy-exercise PASS (bugs #2/#5/#6/#7/#8 fixed, validated live)"
  - "R2 clone primitive (execution_cell_clone.py, R2_REVIEWED_PASS); R1 grant; R5 adapter"
successors:
  - "unblocks C6 'runner live-cell exercise' retained gate; then C4/C3a-2 (which need working cells)"
---

# Foundation C — R7: Provisioning for the GREEN cell round-trip

## 0. Why this slice exists
The R6 shadow dogfood proved the confinement runner's **plumbing + security** end-to-end on real
deployment (mint → Ed25519 sign → UDS → SO_PEERCRED accept → verify → reserve). It stops at the
`unknown-trusted-repo` gate because R3 **deliberately** shipped no `trusted_repo_mirrors` provisioning
(`execution_cell_runner.py:1080`), and the replay store is the in-memory `#8` stopgap. R7 provisions
exactly the deferred pieces so a real `write_file` effect reaches a **typed GREEN receipt** through a
bwrap cell — and thereby satisfies **C6's retained "runner live-cell exercise" prerequisite**.

## 1. Scope (bounded)
Deliver, all shadow-first / default-consistent with R6:
1. a **bare git mirror** of the repository the runner clones from (the R2 clone source), kept fresh
   enough that the adapter's `base_revision = git HEAD` is resolvable in the mirror;
2. the **`trusted_repo_mirrors` wiring** — `AQ_EXECUTION_CELL_RUNNER_TRUSTED_REPO_MIRRORS="primary=<mirror>"`
   keyed to match the adapter's `trusted_repo_id` (default `"primary"`, already emitted — no adapter
   code change);
3. a **durable single-writer reservation store** replacing the in-memory `ReplayReservationSet` stopgap.
**Out of scope:** making cells authoritative (they stay shadow / deny-closed to the real result);
C4 egress; C6 scheduler seam; the C2 scheduler-context transport (C6's *other* retained gate).

## 2. Bare mirror (the clone source)
- A dedicated bare mirror at a runner-readable, non-repo path — recommend
  `AQ_EXECUTION_CELL_RUNNER_MIRROR_ROOT = /var/lib/aq-execution-cell-runner/mirror.git`
  (inside the runner StateDirectory, `0700` runner-owned — the runner is the only reader; the bwrap
  cell clones from it with `--no-local` per R2).
- **Freshness contract:** the adapter mints `base_revision = git rev-parse HEAD` of the working repo.
  The mirror MUST contain that OID or the R2 clone fails `clone-failed`. Provision a **path/timer sync**
  (systemd `.path` on the repo `.git` + a `.timer` floor) that `git fetch`es the working repo into the
  bare mirror. For the shadow this is best-effort (a slightly-stale mirror only causes a typed
  `clone-failed` deny, never a wrong result); before authoritative use, the mint must instead pin
  `base_revision` to an OID the mirror is proven to contain (a fetch-then-mint handshake — noted for R8).
- The mirror is created + owned declaratively (Nix `systemd.tmpfiles` / an oneshot `git clone --bare`),
  never by the unprivileged cell.

## 3. `trusted_repo_mirrors` wiring
- `nix/modules/services/execution-cell-runner.nix`: add
  `AQ_EXECUTION_CELL_RUNNER_TRUSTED_REPO_MIRRORS = "primary=${mirrorPath}"` to `runnerEnvironment`,
  and a `mirrorPath` option (default under StateDirectory). `build_config_from_env` already parses this
  env into the mirrors map (`:1129-1131`); no runner code change for the wiring itself.
- `trusted_repo_id` key `"primary"` matches the adapter default — verify parity in an acceptance test
  (adapter mint id == a runner mirrors key), so a future rename can't silently reintroduce
  `unknown-trusted-repo`.

## 4. Durable reservation store (replaces the `#8` stopgap)
- Implement a durable single-writer store behind the existing `try_reserve/commit/fail` contract
  (`execution_grant.py` `ReservationInterface`): stable lock inode, strict parse, monotonic
  reserved→committed|failed transitions, temp-same-dir write + file fsync + atomic replace + dir fsync,
  crash-recovery ordering — reusing the proven pattern the C6 WAL / C3a-2 `delegate_reservation` design
  specify (do not re-invent; share the primitive if landed).
- Wire it in `build_config_from_env` in place of `eg.ReplayReservationSet()`; keep the in-memory
  double as the test/reference implementation only.
- Persist under the runner StateDirectory (`0700`), so replay protection survives runner restarts.

## 5. Ceiling (freeze at R7 freeze)
- EDIT `nix/modules/services/execution-cell-runner.nix` — `mirrorPath` option, the mirror-provisioning
  oneshot/timer + tmpfiles, and the `TRUSTED_REPO_MIRRORS` env. **switchboard.nix untouched** (anchor).
- EDIT `ai-stack/switchboard/execution_cell_runner.py` `build_config_from_env` — swap the in-memory
  reservation store for the durable store constructor. No change to verify/clone/cell/validator logic.
- NEW `scripts/ai/lib/…` durable reservation store (or reuse a shared one) + its offline test.
- NEW acceptance: a **live GREEN deploy-exercise** (post-rebuild, adapter ON): fresh unique effect →
  mint→sign→UDS→accept→verify→reserve→**repo-trust PASS**→bwrap cell→validator→**typed GREEN receipt**;
  real tool-calling unchanged; C2/C5 unaffected; replay survives a runner restart.
- MUST NOT: alter grant verify / SO_PEERCRED / R1-R2-R5 frozen semantics, make cells authoritative, or
  touch the switchboard hardening anchor.

## 6. Acceptance bar
GREEN round-trip live (above); mirror freshness handled (stale mirror → typed `clone-failed` deny,
never a wrong result); durable store proven across a runner restart (a committed grant stays
non-replayable); `trusted_repo_id`↔mirrors-key parity test; shadow stays deny-closed / no live impact;
switchboard anchor byte-unchanged.

## 7. Ceremony (enforcement-tier)
design → independent review (codex binding) → freeze (subject = this doc + the exact runner/nix diff
hashes) → single-use owner activation → build flag-consistent → independent acceptance → orchestrator
integration → owner R6-style re-activation (adapter ON) → the live GREEN deploy-exercise.

## 8. Downstream
Satisfies **C6's "runner live-cell exercise"** retained gate (C6 still separately needs the C2
scheduler-context issuer/transport + active intervention lever + gateway/health preflight). Unblocks
**C4** (egress on working cells) and **C3a-2** (delegate broker into working cells).
