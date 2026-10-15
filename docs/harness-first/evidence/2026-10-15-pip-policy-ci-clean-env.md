# Python tooling policy: allowlist ci-clean-env.sh and run the policy check in CI

## Objective

Unblock every push blocked by the pre-push quick lint step "Python tooling policy". `scripts/governance/ci-clean-env.sh:15` runs `python -m pip install -r <reqs>` inside its own throwaway venv. This is intentional: it reproduces CI's bare python env. The file was not on `config/python-tooling-policy-allowlist.txt`, so the policy check failed. Adds the allowlist entry, adds a `python-tooling-policy` manifest entry in `config/ci-checks.json`, and runs the check in the `syntax` job of `.github/workflows/test.yml` so CI enforces it too.

## Workflow/Session IDs

- Orchestrator session: eb012479-4564-462f-8e6f-4824d5a77754
- Branch: fix/pip-policy-allow-ci-clean-env (from origin/main)
- Worktree: .agents/delegation/worktrees/pip-policy
- Commit: not created; changes are staged for orchestrator review

## Delegation Decision

Mechanical, single-concern fix (allowlist line, one manifest entry, one workflow step, one evidence doc). Executed directly in the delegated worktree under the orchestrator's explicit instructions. No independent review performed in this slice; the orchestrator owns review and commit.

## Commands Executed

- `git fetch -q origin && git worktree add -b fix/pip-policy-allow-ci-clean-env .agents/delegation/worktrees/pip-policy origin/main`
- `bash scripts/governance/check-python-tooling-policy.sh` (before edits: FAIL, 1 violation at `scripts/governance/ci-clean-env.sh:15`)
- Edits: allowlist entry, `config/ci-checks.json` entry, `.github/workflows/test.yml` step "Enforce Python tooling policy (uv-first)" in the `syntax` job
- `bash scripts/governance/tier0.d/check-ci-manifest-coverage.sh`
- `bash scripts/governance/check-python-tooling-policy.sh`
- `python3 scripts/testing/test-python-tooling-policy.py`
- `./scripts/governance/run-ci-checks.sh --all --only python-tooling-policy`

## Validation Evidence

- Coverage: `[tier0.d/check-ci-manifest-coverage] PASS` (exit 0)
- Policy check: `[python-tooling-policy] PASS: uv-first Python tooling policy enforced.` (exit 0)
- Unit test: `All policy tests passed`, `Policy check passed on real repo` (exit 0)
- Runner: `[PASS] python-tooling-policy: 0.6s` / `run-ci-checks: 1 pass, 0 fail, 0 warn` (exit 0)
- Manifest entry has `ci_workflow` `.github/workflows/test.yml#syntax`, which exists. The new CI step calls `run-ci-checks.sh --all --only python-tooling-policy`, so the `--only` id is covered.
- Manifest `paths` is `scripts/**`, `**/*.sh`, `**/*.py`, `.github/workflows/**`, and the allowlist. `.github/workflows/**` is included because the policy check also scans workflow files.

## Rollback Plan

Revert the single commit, or remove the three hunks: the allowlist line `scripts/governance/ci-clean-env.sh`, the `python-tooling-policy` object in `config/ci-checks.json`, and the "Enforce Python tooling policy (uv-first)" step in `.github/workflows/test.yml`. The pre-push check will then fail again on `ci-clean-env.sh` until one of those is restored.

## Residual Risk

- The allowlist entry has no per-entry reason, because the file's existing entries carry none. The intent is recorded here: the script installs only into its own mktemp venv to reproduce CI's bare env (W6-S3).
- `scripts/testing/test-python-tooling-policy.py` `test_policy_with_temp_files` passes an empty temp allowlist and does not assert on the result. It therefore prints 25 violations from the real repo and still exits 0. This is pre-existing and was not changed in this slice. It should be tracked in `memory/issues-backlog.md`.
- Adding the policy step to CI may surface other bare `pip install` uses in workflows if the allowlist diverges later. Current state on this branch: PASS.

## Hint Feedback

Root cause: #523 added a venv `pip install` in `ci-clean-env.sh`. The policy check is not in the CI manifest and no workflow runs it, so CI did not catch the violation. The pre-push quick lint did.
