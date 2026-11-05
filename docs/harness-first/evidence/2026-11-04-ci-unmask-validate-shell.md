# CI: unmask validate-shell-scripts ShellCheck step

## Objective

Remove the `continue-on-error: true` mask from the `shellcheck` job's "Run ShellCheck" step in `.github/workflows/validate-shell-scripts.yml`, now that PR #691 has fixed every shellcheck warning-severity finding under `scripts/` (288 -> 0). Closes register entry CI-MASK-VALIDATE-SHELL-SCRIPTS-RUN-SHELLCHECK.

## Workflow/Session IDs

- Orchestrator: claude-opus, 2026-11-04.
- Implementer: Claude Haiku 5.5 (Rule 17, mechanical edit with checkable result).
- Branch: `fix/ci-unmask-validate-shell`, worktree `.agents/delegation/worktrees/unmask-vss`, base `origin/main` 9e3e49dd4 (includes PR #691).

## Delegation Decision

Mechanical slice: two lines removed from one workflow, one register heading and status flipped plus one bullet appended, one evidence file. Cheapest eligible Claude tier (Haiku) with checkable results (shellcheck count, mask checker, diff stat).

## Commands Executed

- `shellcheck --severity=warning` over every shell file under `scripts/` (`*.sh`, `*.bash`, and extensionless files with a bash/sh shebang), 513 files.
- `python3 scripts/governance/check-workflow-masks.py`
- `git -C <wt> diff --numstat -- .github/workflows/validate-shell-scripts.yml`
- `git -C <wt> add` on the three changed files; no commit.

## Validation Evidence

- ShellCheck `--severity=warning` over 513 shell files under `scripts/`: 0 findings, exit 0.
- `check-workflow-masks: PASS`.
- Workflow diff: 2 lines removed (`continue-on-error: true` and the `# KNOWN-FAILING:` comment), 0 added.

## Rollback Plan

Revert the commit. The change removes a mask; reverting restores `continue-on-error: true` and the register status to OPEN.

## Residual Risk

- The ShellCheck step now fails the workflow on any warning-severity finding under `scripts/`. Any new finding from a future change will turn CI red by design; this is the intended gate.
- The step runs in CI on GitHub runners. The local run above used the local shellcheck binary; CI-side confirmation is pending the PR run.
- Other masks in `shellcheck.yml` and `nix-build.yml` remain open (CI-MASK-SHELLCHECK-SHELLCHECK-ANALYSIS, CI-MASK-NIX-BUILD-CHECK-FLAKE).

## Hint Feedback

No harness hints were queried for this slice. Observed friction: the auto-mode classifier denied one read-plus-grep Bash call in a batch with Read calls, so it was re-issued alone; the shellcheck run wrote its scratch output to `/tmp` instead of the scratchpad.
