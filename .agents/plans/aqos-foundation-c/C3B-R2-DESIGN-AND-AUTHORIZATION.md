---
title: "Foundation C C3b R2: Self-Contained Clone Primitive — Design Packet"
slice: "C3b / R2"
status: "R2_REVIEWED_PASS"
review: "antigravity/gemini (independent, codex-substitution) PASS — 8/8 obligations CLOSED, R0 #5/#6 resolved; 1 SHOULD-FIX (openat2 via ctypes/syscall + fallback) + 1 NICE (--template='') folded. Opus-verified. codex confirmatory queued for Aug-4."
revision: 1
kind: "design-only"
implementation_authorization: "NONE"
activation_authorization: "NONE"
author: "Opus (codex-substitution — codex usage-limited to 2026-08-04; catch-up audit queued)"
predecessors:
  - "C3b R0 design PASS (C3B-R0-REVIEW-OPUS.md)"
  - "C3b R1 design PASS (R1_REVIEWED_PASS) — grant + classification"
  - "C2 tool-lease gate, flag OFF (97131faa)"
successors:
  - "C3b R3 default-OFF runner (bwrap cell)"
---

# Foundation C — C3b R2: Self-Contained Clone Primitive

## 0. Provenance & authority
Authored by Opus (codex-substitution; codex usage-limited to 2026-08-04, confirmatory audit
queued in `AGENT-CATCHUP-QUEUE.md`). Independent review routed to the antigravity/gemini lane +
codex-on-return. **DESIGN-ONLY.** Authorizes no runner service, no bwrap, no Nix, no switchboard
adapter, no activation, no commit. Consumes the R1 `VerifiedGrant`; produces an isolated,
verified filesystem workspace for R3 to confine.

## 1. Scope (R0 §5 R2 row — bounded)
Deliver a **transactional, self-contained clone/workspace primitive** at a grant's verified base
OID, a **trusted path-rebase**, and a **typed failure / quarantine / reconcile API**. This is the
first stage that touches the filesystem/git (R1 was pure). **Out of scope (later stages):** the
socket runner + request protocol (R3), bwrap confinement (R3), the switchboard adapter (R5),
network (C4), Nix/service changes, any live traffic, any auto-merge.

## 2. Why not `git worktree` (fixes R0 finding #5, and #6's non-atomicity)
The existing `WorkspaceManager._init_git_worktree` (workspace_isolation.py:191) is unusable for a
cell: (a) a worktree keeps a `.git` file pointing into the **live** repository's
`.git/worktrees/…` common metadata — binding it into a cell would leak live repo state, which R0
§6.1 forbids; (b) it is non-atomic — it `git branch` then `git worktree add`, catches the error,
and can leave a dangling branch while returning an apparently-live workspace; cleanup likewise
"deletes and reports success". R2 does **not** reuse that code path for cells. (The manager may be
retained for other, non-cell uses; C3b cells use the new primitive below.)

## 3. The self-contained clone primitive
### 3.1 Trusted source (folds R0 review Q3 — dedicated bare mirror)
Cells clone from a **dedicated, read-only bare mirror** of the repository, NOT from the live
working repo's `.git`. Rationale: cloning directly from the live `.git` at a pinned OID is
*object-immutable* but still races live `git gc`/repack/prune and ambient writes. A bare mirror
(`git clone --mirror` target, refreshed out-of-band under its own lock) gives a stable, read-only
object source with no working tree and no concurrent mutation during a clone. The mirror path and
its refresh policy are named at R2 freeze; the mirror is never written by a cell.

### 3.2 Creation (transactional, self-contained)
Given `VerifiedGrant.base_revision` (a full, R1-syntactic-validated OID):
1. Allocate a fresh cell root under a private state dir (never inside the live repo).
2. `git clone --template="" --no-local --no-hardlinks <bare-mirror> <cell-root/clone>`
   (self-contained — its own `.git`, no shared/alternates objects pointing at the source;
   precedent: `scripts/testing/test-tier0-staged-isolation.sh:54`). `--template=""` (antigravity
   NICE-TO-HAVE) prevents any global git-template hooks/config on the runner host from being copied
   into the cell. Explicitly assert the clone has **no `alternates`** and no gitfile pointer to any
   external `.git`.
3. **Verify the OID is present and is the checked-out tree:** `git cat-file -e <oid>^{commit}`
   then `git checkout --detach <oid>`; confirm `git rev-parse HEAD == <oid>`. If the mirror lacks
   the OID → typed `base-oid-unreachable` failure (no partial cell).
4. Only after all checks pass is the cell marked READY (an atomic rename of a `.staging` dir to
   the ready path, or a written+fsync'd typed readiness receipt bound to `grant_digest` + OID).
   A failure at any step yields a typed failure and a QUARANTINED partial, never a READY cell and
   never a success receipt (fixes R0 #6).

### 3.3 Isolation invariants (asserted, tested)
- No `objects/info/alternates`, no `.git` gitfile pointer, no symlink from the cell to the live
  repo or its `.git`; the bare mirror is opened read-only; the live working tree is never touched.
- The cell root is outside the live repo and outside `$HOME/Documents/...`; nothing the cell does
  can reach the live tree by construction.

## 4. Trusted path rebase (consumes R1 `PathPlan`)
R1 produced a **pure** `PathPlan` (syntactic-only). R2 performs the **real** resolution against the
cell root, TOCTOU-safely:
- Resolve each logical path to a host path **only** under the cell root using descriptor-relative
  resolution (open the cell-root dir once, resolve components beneath it; on Linux prefer
  `openat2(RESOLVE_BENEATH|RESOLVE_NO_SYMLINKS)`, else an fd-only `openat(O_PATH|O_DIRECTORY|
  O_NOFOLLOW)` component walk that never re-resolves a checked pathname — same discipline the
  write broker will use). No `realpath`-precheck-then-open. **Impl note (antigravity SHOULD-FIX):**
  Python exposes no native `openat2`; the implementation must call it via `ctypes`/`os.syscall`
  (syscall 437) on Linux, with the `openat(O_NOFOLLOW)` fd-walk as the portable fallback for
  dev/test hosts where `openat2` is unavailable — never a `realpath`-precheck path.
- Caller-facing conventions (e.g. `$HOME/Documents/...`) are translated by **trusted R2 code** to
  a cell-relative destination; the grant/caller never selects a host bind target (R0 finding #4).
- Any escape (abs host, `..`, symlink, out-of-cell, component-prefix-not-containment) → typed
  `path-escape` denial. R2 re-checks the R1 component-aware containment against the *resolved* fds,
  not just the strings.

## 5. Typed failure / quarantine / reconcile API (fixes R0 #6)
Every operation returns a typed result; nothing "deletes and reports success":
- `create_cell(grant) -> CellReady | TypedFailure` — TypedFailure ∈ {base-oid-unreachable,
  clone-failed, isolation-violation, path-escape, disk-exhausted, quarantined}.
- `teardown_cell(cell) -> TornDown | Quarantined` — a cleanup that cannot *prove* removal (e.g.
  EBUSY, partial rmtree) → **Quarantined** with a typed receipt, never TornDown.
- `reconcile() -> ReconcileReport` — an idempotent sweeper over the quarantine + state dirs that
  reclaims orphans (crash-left cells, quarantined teardowns) with verified proof of removal; safe
  to run repeatedly; never touches the live repo or anything outside the cell state root.
- Every transition emits a typed receipt bound to `grant_digest` + cell id (the R3 runner projects
  these into `workspace.snapshot`/`workspace.rollback`).

## 6. R1 → R2 → R3 handoff
- **R2 consumes from R1:** the immutable `VerifiedGrant`, `base_revision`, `PathPlan`,
  `resource_limits`. R2 verifies the grant is still fresh/non-stale at cell-create time (re-checks
  expiry + epoch via the R1 pure functions) before touching disk.
- **R2 produces for R3:** a `CellReady{cell_root, resolved_paths, grant_digest, base_oid,
  readiness_receipt}` — a verified, isolated workspace. R3 wraps it in bwrap and runs the bounded
  command; R3, not R2, owns confinement, the socket, epoch supervision, and the final GREEN fence.
- R2 introduces **no** socket, bwrap, Nix, or switchboard surface.

## 7. Offline testability (acceptance)
All R2 acceptance is offline (temp dirs + a throwaway bare mirror; no service, no network):
- create_cell at a valid OID → CellReady; `git rev-parse HEAD == oid`; assert no alternates / no
  external `.git` pointer / no symlink escape.
- unreachable OID, corrupt mirror, disk-full (simulated), interrupted-mid-clone → typed failure +
  QUARANTINED partial, never READY, never success receipt.
- path rebase: each escape class (abs, `..`, symlink swap, out-of-cell, prefix-not-containment) →
  path-escape deny; a valid in-cell logical path → resolved fd under the cell root.
- teardown that cannot prove removal → Quarantined; reconcile() reclaims orphans idempotently and
  is a no-op on a clean state; reconcile never escapes the cell state root.
- stale/expired grant at create time → deny before any disk write (R1 re-check).
- isolation fuzz: a crafted mirror with a symlink/alternates trying to reach outside → rejected.

## 8. Review obligations (independent reviewer must test)
1. cells never bind/read the live `.git`; self-contained clone (no alternates/gitfile/symlink escape).
2. base OID is verified present AND is the checked-out HEAD; unreachable → typed failure, no partial cell.
3. creation is transactional — a partial is QUARANTINED, never READY, never a success receipt (R0 #6).
4. path rebase is TOCTOU-safe (fd-relative, no realpath-precheck) and component-aware; every escape denies.
5. teardown/reconcile are typed + idempotent; cleanup-failure → Quarantined, never delete-and-report-success.
6. the bare-mirror source is read-only and never mutated by a cell; refresh is out-of-band + locked.
7. R2 stays in scope — no socket, bwrap, Nix, switchboard, network, or auto-merge surface.
8. R2 re-checks grant freshness/epoch (R1 pure fns) before any disk effect.

## 9. Freeze criteria
Freeze pins: this document; the R1 predecessor hash; the bare-mirror source path + refresh/lock
policy; the clone/verify command set + isolation assertions; the path-rebase resolution contract;
the typed failure/quarantine/reconcile API + receipt schema; the offline test vectors. Any changed
reviewed byte → re-review. **R2 PASS is not implementation authorization**; R2 code is a
cheapest-eligible implementer slice (filesystem/git primitive — above local's envelope ⇒ Claude-fast,
Rule-17 recorded), independently reviewed before commit. R3+ (enforcement: runner + bwrap) each
need their own hash-bound design and single-use owner activation.

## 10. Deferred / open questions for review
- Q-R2-1: bare-mirror refresh cadence + lock — how fresh must the mirror be, and who refreshes it
  (a systemd timer? on-demand under lock?) without ever letting a cell write it? Reviewer to weigh.
- Q-R2-2: `--no-local` full-clone cost on the APU vs a `--reference`-free shallow clone at the OID —
  the R4 perf gate measures this; R2 must not pick a faster-but-object-sharing clone that breaks
  isolation (isolation wins over speed; pooling/sharing is a separate reviewed slice).
- Q-R2-3: is a per-cell fresh clone acceptable, or is a read-only object cache needed (isolation-
  preserving) — deferred to R4 perf; R2 specifies fresh-clone-only.
- SF-2 (global userns) remains an R3 host-grounding item; not R2.

**Requested reviewer result:** `PASS` / `FAIL` / `REQUEST_REVISION` against R2 scope and the §8
obligations. No review outcome authorizes build or activation.
