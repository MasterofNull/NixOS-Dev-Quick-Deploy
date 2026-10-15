# CI merge-commit parity + clean-env runner (W6-S3, W6-S6)

## Objective

Close the gap between local checks and CI seen on 2026-10-14: CI tests the PR merge commit in a bare python env, local tested the branch in a full env. Adds `ci-merge-parity.sh` (HEAD + origin/main in a temp worktree, wired into pre-push), manifest entries for whole-tree gitleaks and the harness-first PR evidence gate, and `ci-clean-env.sh` (throwaway venv with only CI's python requirements). Stacks on W6-S1 (PR #515).

## Workflow/Session IDs

- Orchestrator session: eb012479-4564-462f-8e6f-4824d5a77754
- Plan: .agents/plans/sota-rounding (W6-S3, W6-S6)
- Branch: feat/ci-merge-parity-clean-env (from origin/feat/ci-checks-manifest)

## Delegation Decision

Bounded implementer slice delegated by the orchestrator to a claude-sonnet implementer (Rule 17 cheapest-eligible Claude lane). Author lane: claude. Independent review and tier0 are run by the orchestrator; implementer did not commit. After a power loss wiped the first worktree, the change was re-applied from transcript in the durable worktree with the five review fixes folded in.

## Commands Executed

- `python3 scripts/testing/test-ci-merge-parity.py`
- `bash scripts/governance/tier0.d/check-ci-manifest-coverage.sh`
- `scripts/governance/run-ci-checks.sh --all --only gitleaks-tree --only harness-first-pr-evidence`
- `scripts/governance/ci-clean-env.sh --all --only harness-first-static-gates`
- `scripts/governance/ci-merge-parity.sh`

## Validation Evidence

- Fixture tests: failure that exists only after merging main is caught while the branch alone passes; clean merge passes; conflicting merge fails with an "Update the branch" message; CI_MERGE_PARITY_SKIP=1 prints WARN; fetch failure prints WARN and the BASE line; a main-only change does not trigger a path-scoped check (selection uses the PR diff); clean-env fails a check needing an un-installed module, cleans its venv, and an uninstallable requirement aborts with "NOT running checks".
- CI changes: test.yml harness-first static-gates step now calls ci-clean-env.sh (same check, bare env). gitleaks workflows are NOT swapped (SARIF upload steps); recorded under ci_exempt with reason, manifest entry gitleaks-tree uses identical flags.

## Rollback Plan

Revert the commit. Pre-push falls back to the W6-S1 `--changed` run; test.yml step reverts to `run-ci-checks.sh --all --only harness-first-static-gates`. Emergency skip of the merge step: `CI_MERGE_PARITY_SKIP=1 git push` (prints WARN and runs the branch-only checks).

## Residual Risk

- Merge-parity selects checks from the PR's own diff (`BASE...HEAD`, exported as CI_CHECKS_CHANGED_FILES), matching CI path filters; main-only changes do not trigger path-scoped checks. `--all` is the escape hatch. It tests committed HEAD only (uncommitted changes WARN) and fetches the base first (WARN on fetch failure, stale base possible).
- ci-clean-env needs network (or PIP_FIND_LINKS wheelhouse) to install pyyaml; offline it fails explicitly, never passes silently.
- Only manifest-check jobs are clean-env; heavier python jobs keep their own installs. Follow-up: add their requirement sets as profiles.
- gitleaks missing locally yields WARN (FAIL in CI) from the runner.

## Hint Feedback

No aq-hints were consulted for this slice; scope came from the orchestrator dispatch. No hint feedback to report.
