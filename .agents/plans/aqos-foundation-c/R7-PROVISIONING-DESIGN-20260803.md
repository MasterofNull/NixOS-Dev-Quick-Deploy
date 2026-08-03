---
title: "Foundation C — R7: Trusted-Repo Mirror + Durable Reservation Provisioning (GREEN cell round-trip)"
slice: "C3b / R7"
status: "DESIGN REVISION 2 — PREPARED_ONLY; independent re-review + single-use owner activation required before build"
tier: "enforcement"
kind: "design-only"
author: "Opus (orchestrator, analysis-tier)"
base_head_at_design: "a439527f"
review_history:
  - reviewer: "fresh Claude flagship (binding-substitute, codex offline)"
    verdict: "REQUEST_REVISION"
    findings: "7 (env JSON format, stale-mirror typed code, C6->C4 misattribution, both reservation stores durable, intra-process thread lock, _fsync_write_json reuse, parity test)"
predecessors:
  - "runner-hardening rev4 accepted+integrated (0cf1192e); R6 deploy-exercise PASS (bugs #2/#5/#6/#7/#8 fixed, validated live)"
  - "R2 clone primitive (execution_cell_clone.py, R2_REVIEWED_PASS); R1 grant; R5 adapter"
successors:
  - "satisfies the runner live-cell exercise = a C4 (then C3a-2) retained gate (per FOUNDATION-C-REV3-CODEX-ACCEPTANCE:43-46); NOT a C6 gate"
---

## REV2 (2026-08-03) — folds the binding-substitute review (REQUEST_REVISION, 7 findings)
Fresh-flagship review confirmed the architecture (OID-bound content, quarantine, reservation
interface) is sound, but found the slice as-written would NOT reach GREEN. All 7 folded:
1. **Env format (blocking):** `AQ_EXECUTION_CELL_RUNNER_TRUSTED_REPO_MIRRORS` is parsed by
   `build_config_from_env` via `json.loads` (a dict), NOT `key=value` — a `key=value` string throws
   `ValueError` -> `mirrors={}` -> the runner still denies `unknown-trusted-repo`. **Must emit JSON**
   `{"primary":"<mirrorPath>"}`.
2. **Stale-mirror typed code:** a stale-but-valid mirror clones OK then fails
   `git cat-file -e <oid>^{commit}` -> **`base-oid-unreachable`**, NOT `clone-failed` (which is only the
   missing/corrupt-mirror path). The acceptance bar must assert `base-oid-unreachable`.
3. **C6 -> C4 re-attribution:** the "runner live-cell exercise" is a **C4** (then C3a-2 transitively)
   retained gate per `FOUNDATION-C-REV3-CODEX-ACCEPTANCE-20260801.md:43-46`, not C6. R7 unblocks C4.
4. **Both stores durable, separate files:** `build_config_from_env` builds TWO stores (`reservation_set`
   grant-id replay + `cell_reservation_set` cell-single-use, distinct domains) — both go durable with
   SEPARATE backing files (sharing one cross-collides the domains).
5. **Intra-process thread lock:** the runner serves each connection in its own thread and calls
   `try_reserve` before the semaphore; `flock` gives cross-process but NOT intra-process safety (threads
   share the open-file description). The store needs a `threading.Lock` (or per-call open+flock) + a
   concurrent-`try_reserve` acceptance test.
6. **Reuse the landed primitive:** build the durable store on R2's `_fsync_write_json`
   (`execution_cell_clone.py:188`, temp-write+fsync+atomic-replace+dir-fsync). `delegate_reservation` /
   the C6 WAL are design-only, NOT landed — do not point at them.
7. **Stronger parity test:** run the actual env string through `build_config_from_env` and assert
   `"primary" in config.trusted_repo_mirrors` (also catches #1).

# Foundation C — R7: Provisioning for the GREEN cell round-trip

## 0. Why this slice exists
The R6 shadow dogfood proved the confinement runner's **plumbing + security** end-to-end on real
deployment (mint → Ed25519 sign → UDS → SO_PEERCRED accept → verify → reserve). It stops at the
`unknown-trusted-repo` gate because R3 **deliberately** shipped no `trusted_repo_mirrors` provisioning
(`execution_cell_runner.py:1080`), and the replay store is the in-memory `#8` stopgap. R7 provisions
exactly the deferred pieces so a real `write_file` effect reaches a **typed GREEN receipt** through a
bwrap cell — and thereby satisfies the **"runner live-cell exercise"**, which is a **C4** (then C3a-2
transitively) retained gate per `FOUNDATION-C-REV3-CODEX-ACCEPTANCE-20260801.md:43-46` — NOT a C6 gate.

## 1. Scope (bounded)
Deliver, all shadow-first / default-consistent with R6:
1. a **bare git mirror** of the repository the runner clones from (the R2 clone source), kept fresh
   enough that the adapter's `base_revision = git HEAD` is resolvable in the mirror;
2. the **`trusted_repo_mirrors` wiring** — `AQ_EXECUTION_CELL_RUNNER_TRUSTED_REPO_MIRRORS={"primary":"<mirror>"}`
   (JSON — see §3), keyed to match the adapter's `trusted_repo_id` (default `"primary"`, already emitted
   — no adapter code change);
3. a **durable single-writer reservation store** replacing the in-memory `ReplayReservationSet` stopgap.
**Out of scope:** making cells authoritative (they stay shadow / deny-closed to the real result);
C4 egress; C6 scheduler seam; the C2 scheduler-context transport (C6's *other* retained gate).

## 2. Bare mirror (the clone source)
- A dedicated bare mirror at a runner-readable, non-repo path — recommend
  `AQ_EXECUTION_CELL_RUNNER_MIRROR_ROOT = /var/lib/aq-execution-cell-runner/mirror.git`
  (inside the runner StateDirectory, `0700` runner-owned — the runner is the only reader; the bwrap
  cell clones from it with `--no-local` per R2).
- **Freshness contract:** the adapter mints `base_revision = git rev-parse HEAD` of the working repo.
  The mirror MUST contain that OID, else the R2 clone succeeds (rc 0) but the `git cat-file -e
  <oid>^{commit}` fence fails → typed `base-oid-unreachable` (`clone-failed` is only the missing/corrupt-
  mirror path). Provision a **path/timer sync** (systemd `.path` on the repo `.git` + a `.timer` floor)
  that `git fetch`es the working repo into the bare mirror. For the shadow this is best-effort (a
  slightly-stale mirror only causes a typed `base-oid-unreachable` deny, never a wrong result — content
  is OID-bound: git can't serve different bytes under the same OID, and HEAD must equal the minted OID);
  before authoritative use, the mint must instead pin
  `base_revision` to an OID the mirror is proven to contain (a fetch-then-mint handshake — noted for R8).
- The mirror is created + owned declaratively (Nix `systemd.tmpfiles` / an oneshot `git clone --bare`),
  never by the unprivileged cell.

## 3. `trusted_repo_mirrors` wiring (rev2 — JSON)
- `nix/modules/services/execution-cell-runner.nix`: add
  `AQ_EXECUTION_CELL_RUNNER_TRUSTED_REPO_MIRRORS = builtins.toJSON { primary = mirrorPath; }` to
  `runnerEnvironment` (i.e. the literal env value `{"primary":"<mirrorPath>"}`), and a `mirrorPath`
  option (default under StateDirectory). **The env MUST be JSON** — `build_config_from_env` parses it
  with `json.loads` (`:1130-1137`); a `key=value` string throws `ValueError` -> `mirrors={}` ->
  `unknown-trusted-repo` (the exact failure R7 exists to fix). No runner code change for the wiring.
- `trusted_repo_id` key `"primary"` matches the adapter default. **Parity test (strengthened):** run the
  actual env string through `build_config_from_env` and assert `"primary" in config.trusted_repo_mirrors`
  — this catches both a future id/key rename AND the JSON-format regression above.

## 4. Durable reservation store (replaces the `#8` stopgap) — rev2
- Implement a durable store behind the existing `try_reserve/commit/fail` `ReservationInterface`
  (`execution_grant.py:490-548`): strict parse, monotonic `reserved→committed|failed`, atomic durable
  write. **Build on the LANDED primitive** — R2's `_fsync_write_json` (`execution_cell_clone.py:188`:
  temp-same-dir write + file fsync + atomic replace + dir fsync). Do NOT point at `delegate_reservation`
  or the C6 WAL — those are design-only, not landed.
- **Both instances, separate backing files.** `build_config_from_env` builds TWO stores (`:1174-1175`):
  `reservation_set` (grant-id replay) and `cell_reservation_set` (cell-single-use) — distinct uniqueness
  domains. Both become durable, each with its OWN file (e.g. `…/reservations/grant.json` +
  `…/reservations/cell.json`); a shared file would cross-collide the admission and cell-build domains.
- **Intra-process thread safety (critical).** The runner serves each connection in its own thread
  (`:1063`) and calls `try_reserve` from `verify_grant` (`:578`) BEFORE the concurrency semaphore.
  `flock` gives cross-process but NOT intra-process safety (threads share the open-file description). The
  store MUST hold a `threading.Lock` around the read-modify-write (or open+flock per call). Acceptance
  includes a concurrent-`try_reserve` test (two threads, one reservation, exactly one winner).
- Wire both in `build_config_from_env` in place of `eg.ReplayReservationSet()`; keep the in-memory double
  as the test/reference implementation only. Persist under the runner StateDirectory (`0700`) so replay
  protection survives runner restarts.

## 5. Ceiling (freeze at R7 freeze)
- EDIT `nix/modules/services/execution-cell-runner.nix` — `mirrorPath` option, the mirror-provisioning
  oneshot/timer + tmpfiles, and the `TRUSTED_REPO_MIRRORS` env. **switchboard.nix untouched** (anchor).
- EDIT `ai-stack/switchboard/execution_cell_runner.py` `build_config_from_env` — swap BOTH in-memory
  stores (`reservation_set` + `cell_reservation_set`) for durable constructors (separate files). No
  change to verify/clone/cell/validator logic.
- NEW `scripts/ai/lib/…` durable reservation store (built on R2's `_fsync_write_json` +
  `threading.Lock`) + its offline test (incl. a concurrent-`try_reserve` case: two threads, one winner).
- NEW acceptance: a **live GREEN deploy-exercise** (post-rebuild, adapter ON): fresh unique effect →
  mint→sign→UDS→accept→verify→reserve→**repo-trust PASS**→bwrap cell→validator→**typed GREEN receipt**;
  real tool-calling unchanged; C2/C5 unaffected; replay survives a runner restart; stale mirror →
  `base-oid-unreachable`.
- MUST NOT: alter grant verify / SO_PEERCRED / R1-R2-R5 frozen semantics, make cells authoritative, or
  touch the switchboard hardening anchor.

## 6. Acceptance bar
GREEN round-trip live (above); mirror freshness handled (stale mirror → typed `base-oid-unreachable` deny (a stale mirror clones OK then fails `git cat-file -e <oid>^{commit}`; `clone-failed` is only the missing/corrupt-mirror path),
never a wrong result); durable store proven across a runner restart (a committed grant stays
non-replayable); `trusted_repo_id`↔mirrors-key parity test; shadow stays deny-closed / no live impact;
switchboard anchor byte-unchanged.

## 7. Ceremony (enforcement-tier)
design → independent review (codex binding) → freeze (subject = this doc + the exact runner/nix diff
hashes) → single-use owner activation → build flag-consistent → independent acceptance → orchestrator
integration → owner R6-style re-activation (adapter ON) → the live GREEN deploy-exercise.

## 8. Downstream
Satisfies the **"runner live-cell exercise"**, which is a **C4** (then **C3a-2** transitively) retained
gate per `FOUNDATION-C-REV3-CODEX-ACCEPTANCE-20260801.md:43-46` — so R7 unblocks **C4** (egress on
working cells) and thence **C3a-2** (delegate broker into working cells). It does NOT clear a C6 gate:
C6's own retained gates are the C2 scheduler-context issuer/transport + owner public-key/service-hardening
source (a separate slice).
