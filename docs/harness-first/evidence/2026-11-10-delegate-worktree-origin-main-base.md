# Delegate worktree base selection (`origin/main` when local `main` is behind) evidence

Date: 2026-11-10

Root cause discovered during Wave 2026-11-10-A orchestration:
`scripts/ai/lib/worktree-isolation.sh` (`wt_create`) unconditionally branched
delegate worktrees from local `HEAD`. Because the delivery workflow prohibits
mutating the main checkout directly and lands via PRs on `origin/main`, local
`main` lags behind `origin/main` between deploys, causing every delegated
implementer worktree to start from a stale base.

Changes (`codex-20261110-092615-amfrhk`):

1. `scripts/ai/lib/worktree-isolation.sh`: `wt_create` now selects the worktree
   base offline in priority order:
   - explicit `AQ_DELEGATE_BASE` override if verifiable (`^{commit}`),
   - `origin/main` when verifiable and local `HEAD` is an ancestor of
     `origin/main` (`git merge-base --is-ancestor HEAD origin/main`),
   - fallback to local `HEAD` (preserving unpushed local commits, diverged
     branches, and repos without `origin`).
2. `scripts/testing/test-worktree-isolation.py`: added temporary-repository
   regression coverage for no-origin, behind `origin/main`, valid/invalid
   `AQ_DELEGATE_BASE` override, diverged local commit, and local ahead of
   `origin/main`.

Validation:

- `bash -n scripts/ai/lib/worktree-isolation.sh` — pass.
- `python3 scripts/testing/test-worktree-isolation.py` — pass (including new
  base-selection matrix).
- `python3 scripts/testing/test-ci-checks-manifest.py` — pass.

Activation attestation (2026-11-10): immediately active for all subsequent
`delegate-to-codex` and `delegate-to-local` worktree creations in the repo.
