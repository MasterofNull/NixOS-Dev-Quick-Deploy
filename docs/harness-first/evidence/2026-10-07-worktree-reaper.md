# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-006

## Objective
- Owner-approved (2026-10-07) reaper for zero-change delegate worktrees/branches and orphaned lean-ctx graphs (181 worktrees, ~1.5 GB graphs accumulated; CS-1 wt_teardown deliberately retains everything).

## Workflow/Session IDs
- Workflow ID: wf-worktree-reaper-20261007
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Implementer: Claude Haiku 4.5 (worktree-isolated, temp-repo tests only). Reviewer: Claude Opus 5.5 — rejected first dry-run (scanned 542 vs ~173 real; 537 false-dirty), accepted after porcelain-stanza parse + tool-artifact ignore fix.

## Commands Executed
```bash
python3 scripts/testing/test-aq-worktree-reap.py
scripts/ai/aq-worktree-reap --repo <repo> --json            # dry run
scripts/ai/aq-worktree-reap --repo <repo> --json --graphs --apply
```

## Validation Evidence
- 6/6 tests PASS (clean zero-commit delegate reaped; ahead/dirty/non-delegate kept; orphan graph archived).
- Real dry run: scanned 181, reapable 68, kept_dirty 15, kept_ahead 60, kept_locked 1, prunable 4; main checkout and active delegate worktrees not candidates; RSI validation does not read worktree paths.

## Rollback Plan
- Reaped worktrees had zero commits beyond origin/main and clean status: `git worktree add <path> -b <branch> origin/main` recreates any of them. Graphs are moved (not deleted) to ~/.lean-ctx/graphs-archive/<date>/.

## Residual Risk
- Not yet scheduled (manual/ops invocation); a timer is a follow-up once proven.

## Hint Feedback
- No aq-hints consulted.
