# CI unit tests on Python 3.13 (deployed runtime), 2026-11-19

## Objective
Dependabot #814 (numpy >=2.5.5 for aidb) failed `unit-tests (aidb)` because CI installed on Python 3.11 and numpy 2.5.5 needs >=3.12. The system runs Python 3.13 (`nix eval --raw nixpkgs#python3.version` = 3.13.17; services use `pkgs.python3.withPackages`). CI now tests that runtime. Single source of truth: new repo file `.python-version` (`3.13`), read via `python-version-file` by `tests.yml` unit-tests and `test-coverage.yml` (both install and run service/runtime code: hybrid-coordinator and dashboard requirements). Left at 3.11 on purpose: `tests.yml` parity-scorecard-gate (harness scripts, not service runtime) and `security.yml` (pip-audit/shell audit only). Root cause: CI used 3.11 while the system runs 3.13, so bumps requiring >=3.12 failed CI despite being valid for the runtime.

## Workflow/Session IDs
Worktree `.agents/delegation/worktrees/aidb-ci-py313`, branch `fix/aidb-ci-python-3.13`; Claude sub-agent (Sonnet 5.5) slice from the resume-20261118 orchestration.

## Delegation Decision
Bounded CI config slice, two one-line edits plus one file; implemented by a Sonnet sub-agent (cheapest eligible lane, Rule 17). No local-Qwen dispatch: the work was dominated by dependency installs, not code.

## Commands Executed
- `nix shell nixpkgs#python313`, throwaway venv per service under `.agents/delegation/outputs/aidb-py313/` (gitignored); `pip install -r ai-stack/mcp-servers/<svc>/requirements.txt`.
- The workflow's test command per service: `pytest ai-stack/mcp-servers/<svc> -m "not integration" --cov=...` with the workflow's PYTHONPATH.
- `dashboard/backend/requirements.txt` install plus `scripts/testing/run-targeted-coverage.sh` (test-coverage.yml job) in the hybrid-coordinator venv.
- `config/root-file-allowlist.txt` gained `.python-version` (root-hygiene gate; intentional new root file).
- NixOS-only: `LD_LIBRARY_PATH` set to nixpkgs gcc lib so manylinux numpy wheels find libstdc++ (ubuntu runners have it).

## Validation Evidence
- Install on 3.13.17: aidb rc=0 (resolved numpy 2.5.5), hybrid-coordinator rc=0, nixos-docs rc=0; no package lacked 3.13 support.
- hybrid-coordinator: `356 passed, 2 skipped, 2 warnings, 4 subtests passed in 36.37s`.
- aidb and nixos-docs: `no tests ran` (rc=5), which the workflow maps to a skip with exit 0; these two services have no pytest files, so their CI job proves the requirements install.
- test-coverage job path: dashboard requirements installed; `run-targeted-coverage.sh` ran, `orchestration_framework: 57.3% (threshold 20.0%)`.
- Not verified locally: the GitHub-hosted `actions/setup-python` reading `python-version-file` (standard feature; will be exercised by the PR's CI).

## Rollback Plan
Revert the commit (removes `.python-version`, restores `python-version: "3.11"` in both workflows).

## Residual Risk
Ubuntu runner wheels for 3.13 resolved identically on PyPI, but runner-specific differences are only proven by the PR's CI. A root `.python-version` is also read by pyenv/uv locally; it matches the deployed runtime. Tests exist only for hybrid-coordinator, so aidb regressions at runtime are not unit-covered (pre-existing).

## Hint Feedback
No aq-hints were consulted for this slice (CI-config only); none to rate.
