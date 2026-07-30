# Collaborative Round — c3b-r2-review

Opened: 2026-07-30T04:54:22Z
Target artifact (if a review round): .agents/plans/aqos-foundation-c/

## Task
ROLE: independent binding DESIGN reviewer for Foundation C slice C3b, stage R2 (self-contained
clone primitive). Read-only — no edits/commits. DESIGN review (no code yet). You substitute for
codex (usage-limited to Aug 4; codex confirmatory-audits on return). Be rigorous and specific.
VERIFY claims against the ACTUAL code — if the doc names a file/API, confirm it exists before
accepting it (do not approve prose; do not fabricate).

READ:
- .agents/plans/aqos-foundation-c/C3B-R2-DESIGN-AND-AUTHORIZATION.md (under review)
- .agents/plans/aqos-foundation-c/C3B-DESIGN-AND-AUTHORIZATION.md (R0) + C3B-R0-REVIEW-OPUS.md
  (R0 finding #5 = no live .git bind; #6 = WorkspaceManager non-atomic/delete-and-report-success)
- .agents/plans/aqos-foundation-c/C3B-R1-DESIGN-AND-AUTHORIZATION.md (R2 consumes its VerifiedGrant/
  PathPlan/base_revision)
- Ground against real code: ai-stack/orchestration/workspace_isolation.py (_init_git_worktree ~191,
  cleanup_workspace) and scripts/testing/test-tier0-staged-isolation.sh:54 (the git clone
  --no-hardlinks self-contained-clone precedent).

TEST THESE OBLIGATIONS (§8) — for each: CLOSED or a concrete gap with exact §ref + fix:
1. Cells never bind/read the live .git; the clone is self-contained (no objects/info/alternates, no
   .git gitfile pointer, no symlink escape). Is the isolation actually guaranteed by the specified
   commands, or is there a path where alternates/hardlinks/shared objects leak the live repo?
2. base OID verified present AND is the checked-out HEAD; unreachable → typed failure, no partial cell.
3. Creation transactional — partial → QUARANTINED, never READY, never a success receipt (fixes R0 #6).
   Is the atomic-rename / fsync'd-receipt readiness actually crash-safe?
4. Path rebase (§4) TOCTOU-safe (fd-relative openat2 RESOLVE_BENEATH / fd-only walk, no realpath-
   precheck) and component-aware; every escape (abs, .., symlink, out-of-cell, prefix-not-containment)
   denies. Any residual TOCTOU?
5. teardown/reconcile typed + idempotent; cleanup-failure → Quarantined, never delete-and-report-
   success; reconcile never escapes the cell state root.
6. bare-mirror source (§3.1) is read-only, never mutated by a cell; refresh out-of-band + locked. Is
   the mirror genuinely safer than cloning the live .git at a pinned OID, and is the refresh race-free?
7. Scope containment — no socket, bwrap, Nix, switchboard, network, or auto-merge surface in R2.
8. R2 re-checks grant freshness/epoch (R1 pure fns) before any disk effect.

ALSO: any NEW fail-open or isolation-escape the design introduces? Is the R1→R2→R3 handoff (§6)
clean? Are the referenced anchors real (workspace_isolation.py, the clone precedent)? Weigh
Q-R2-1/2/3 (mirror refresh, --no-local cost, fresh-clone-only).

OUTPUT: `VERDICT: PASS` / `VERDICT: FAIL` / `VERDICT: REQUEST_REVISION` on the FIRST line, then
findings by severity (BLOCKING/SHOULD-FIX/NICE-TO-HAVE) with exact §ref + concrete fix. No review
outcome authorizes build or activation.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/c3b-r2-review.md` and writes `antigravity.md`. No API keys.
