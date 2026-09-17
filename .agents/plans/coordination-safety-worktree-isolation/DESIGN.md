# Coordination-safety: isolate implementer lanes in worktrees (only the orchestrator commits to main)

status: active · owner: hyperd · priority: P0 (recurring hazard, endangers all concurrent multi-agent work)

## Problem (observed 3× — Rule 19 root-cause, not a one-off)
Concurrent multi-agent work on the SHARED checkout keeps contending on the single git index:
- Codex's P0-A was staged in `main`'s index while the orchestrator needed to commit CI hardening — committing
  would have hijacked Codex's in-flight slice (this session).
- A sub-agent's staged output was cross-contaminated with another lane's files.
- Earlier `48d92962` concurrent-staging pollution (already logged).

Root cause: `scripts/ai/delegate-to-codex` and `scripts/ai/delegate-to-local` run the implementer agent in
the SHARED checkout (`REPO_ROOT`), so it stages/commits into the same index as the orchestrator and every
other lane. Sub-agent tools in this session share the checkout unless isolation is
explicitly established. As parallel lanes increase, this risks a commit sweeping
up another lane's work. The delegate wrappers landed isolation in e8a905e8; its
corrective now validates ownership, retains evidence and fails editing closed.

## Principle (the fix)
**Every implementer lane works in its own isolated git worktree and hands back a patch/branch; only the
orchestrator commits to `main`.** No two lanes should stage into the same index.
Isolation must be verified for each runner rather than inferred from tool names.

## Design
- **Worktree-per-delegation (core):** `delegate-to-codex` / `delegate-to-local` create a fresh
  `git worktree add <tmp> HEAD` (detached or a per-task branch `delegate/<task-id>`) for each dispatch, run the
  agent with CWD = that worktree, and on completion capture the result as a **patch** (`git diff` /
  `git format-patch`) or leave it on the per-task branch — NEVER staging/committing into the shared `main`
  index. The task record points at the patch/branch. Worktrees, private branches
  and patches are retained after handback; cleanup requires separate authority.
- **Escape hatch:** a documented `--shared` / `--no-worktree` flag for the rare case that genuinely needs the
  shared checkout (e.g. a read-only analysis) — default is ISOLATED.
- **Orchestrator-only-commit-to-main:** the seat-holding orchestrator reviews the handed-back patch/branch and
  performs the single `main` commit (existing review + trunk-protection flow). Implementers never commit to
  `main`.
- **Backstop guard (defense-in-depth):** a lightweight check/lock so that even a misbehaving lane cannot
  concurrently stage into a shared index that another lane is mid-transaction on — e.g. a coordination check
  in the pre-commit path that refuses when the index already contains another lane's claimed-in-flight paths,
  or an advisory index-lock keyed by task-id. Hooks are cooperative (same-user), so this is a friction-reducer,
  not a security boundary (same caveat FT-7 records for CI-vs-attestation).
- **Parity (Rule 16):** the "implementers isolate in worktrees; only orchestrator commits main" discipline is
  written into CLAUDE.md, .agent/CODEX.md, .agent/LOCAL-AGENT.md, .agent/GEMINI.md, .agent/WORKFLOW-CANON.md
  from one source — every lane follows it.

## Slices (each: isolated implementation, non-author review, tier0, trunk envelope)
- **CS-1 — worktree-isolate the delegation scripts:** add default worktree isolation + `--shared` escape to
  `delegate-to-codex` and `delegate-to-local`; hand back a patch/branch and retain evidence. Backward-safe:
  existing `--check`/`--status`/`--list` unchanged; only the execution working-dir changes. Prove with a
  concurrent dispatch that no shared-index contention occurs.
- **CS-2 — discipline doc + parity:** the coordination principle into all agent instruction files (Rule 16) +
  WORKFLOW-CANON; parity-matrix updated.
- **CS-3 — backstop guard:** the concurrent-staging refusal/lock in the pre-commit/coordination path + a test.
- **CS-4 — validation:** two lanes dispatched in parallel land via patches without touching each other's index;
  regression: single-lane flow unchanged; QA/dashboard visibility of active delegated worktrees.

## Constraints
Do NOT break the active delegation flow (`--check`/`--status`/`--list`/quota-precheck stay). Backward-compatible
default with a read-only escape hatch. Minimal-code: reuse `git worktree` + the
existing patch/branch hand-back pattern; don't build a new orchestration engine. This is coordination-critical infra
(top risk-tier): implement in an isolated worktree, independent review, live concurrent-dispatch proof before
claiming fixed. Change is canonical → parity (Rule 16). Do it while no delegation is live (verified now: none).
