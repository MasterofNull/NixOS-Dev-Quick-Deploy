# CI merge parity: build a real merge commit

## Objective
Make `scripts/governance/ci-merge-parity.sh` test the same thing GitHub CI tests: a real merge commit. The old script used `git merge --no-commit`, so HEAD stayed on the branch tip and main's new files sat in the index. Checks that read `git diff --cached` (for example `check-harness-first-pr-evidence-gate.sh`) blamed the PR for files main gained from other PRs. On branch feat/verified-owner-acceptance this failed on `docs/harness-first/evidence/2026-11-01-routing-s1-preflight.md`, while CI on refs/pull/N/merge passed.

## Workflow/Session IDs
Branch fix/ci-merge-parity-real-merge, worktree `.agents/delegation/worktrees/merge-parity-real-merge`. Date 2026-11-04. No workflow run ID was issued for this slice.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17, balanced tier, bounded single-script slice with a checkable result). Local Qwen and Codex were not used for this slice.

## Commands Executed
- `git merge-tree --write-tree HEAD <base>` to compute the merged tree. Exit 1 keeps the existing conflict FAIL message.
- `git commit-tree <tree> -p HEAD -p <base>` to make an unreferenced throwaway merge commit. No hooks, no refs.
- `git worktree add --detach -q <tmp> <merge>`.
- `bash -n scripts/governance/ci-merge-parity.sh`
- `shellcheck scripts/governance/ci-merge-parity.sh`
- `python3 scripts/testing/test-ci-merge-parity.py`
- `python3 scripts/testing/test-hook-git-env-isolation.py`

## Validation Evidence
- `bash -n`: exit 0.
- shellcheck: 2 info notes (SC1091, SC2329) before and after; none added.
- `test-ci-merge-parity.py`: Ran 9 tests, OK. New test `test_merge_is_real_commit_with_clean_index` shows that inside the parity worktree `git diff --cached` is empty, `git diff origin/main...HEAD` lists only the branch file, and HEAD has two parents. The conflict test still passes.
- `test-hook-git-env-isolation.py`: PASS.
- The test fixture was also fixed to copy `scripts/governance/lib/clean-git-env.sh` and `clean_git_env.py`. Without them the script's `source` line failed in the fixture repo and 8 of 9 tests failed.

## Rollback Plan
Revert the commit. The script returns to `git merge --no-commit`. No data, refs or config are changed by the script.

## Residual Risk
The merge commit author and date are fixed placeholders (ci-parity), so the merge sha differs from GitHub's. Checks that depend on the merge sha itself are not covered. Throwaway commit objects stay in the object store until git gc.

## Hint Feedback
No aq-hints were consulted for this slice. The failure was reproduced from the task description and the script source.
