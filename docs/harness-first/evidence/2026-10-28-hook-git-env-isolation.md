# Hook GIT_* environment isolation for test/QA launches (2026-10-28)

## Source
Incident 2026-10-28: a test run by the pre-commit tier0 gate inside a git hook inherited
GIT_DIR / GIT_INDEX_FILE / GIT_WORK_TREE. The test's temp-repo `git init/add/commit/worktree add`
acted on the real repository: core.bare=true, a tree-wiping commit on a branch, a stray branch.
About 27 tests under scripts/testing git-init temp repos without scrubbing GIT_*.

## Defect
Hooks export repository-locating GIT_* variables. Every subprocess launched from tier0, the
CI-manifest runner, merge-parity and the focused-CI runner inherited them, so any test that
creates its own repo operated on the real one. Fixing 27 tests individually would not stop the
next one.

## Fix
One shared helper, used at each launch point (producer fix, Rule 19):
- `scripts/governance/lib/clean-git-env.sh`: `clean_git_env_run <cmd...>` = `env -u` for GIT_DIR,
  GIT_WORK_TREE, GIT_INDEX_FILE, GIT_OBJECT_DIRECTORY, GIT_ALTERNATE_OBJECT_DIRECTORIES,
  GIT_COMMON_DIR, GIT_PREFIX, GIT_NAMESPACE, GIT_CEILING_DIRECTORIES.
- `scripts/governance/lib/clean_git_env.py`: `clean_git_env(env=None)` equivalent for Python runners.
Launch points covered:
- `scripts/governance/tier0-validation-gate.sh`: 7 AQOS `python3 scripts/testing/test-*.py` gates,
  roadmap verification script, QA phase 0 (`scripts/ai/aq-qa`, which covers every harness_qa phase
  subprocess), canon-compiler and evidence-collector tests, the harness regression suite loop.
- `scripts/governance/run-ci-checks.sh`: manifest check subprocess env.
- `scripts/governance/run-focused-ci-checks.sh`: registry check subprocess env (its own staged
  `git diff --cached` keeps GIT_INDEX_FILE).
- `scripts/governance/ci-merge-parity.sh`: run-ci-checks and coverage check inside the temp worktree.
- `.githooks/pre-push`: ci-merge-parity and run-ci-checks invocations.
Tier0's own staged-file git calls are untouched and keep GIT_*.

## Evidence
- Guard `scripts/testing/test-hook-git-env-isolation.py` (registered as `hook-git-env-isolation` in
  config/ci-checks.json): with GIT_DIR/GIT_INDEX_FILE/GIT_WORK_TREE pointing at a decoy repo, a child
  doing git init/add/commit through the helper leaves the decoy HEAD, core.bare, branches and status
  unchanged and its repo inside tmp; a negative control proves the unscrubbed env does hit the decoy;
  static checks assert each launch point above uses the helper. Result: PASS.
- `check-ci-manifest-coverage.sh`: PASS. `bash -n` on all changed shell files: ok.

## Known gap
- `tier0.d/*.sh` extension checks still run with GIT_* intact (several need the staged index); none
  currently git-init temp repos, but a future one would be unprotected until it calls the helper.
- Tests run outside these launchers (a developer invoking a test by hand inside a hook) are not covered;
  the 27 tests are not individually hardened.
- Not exercised end-to-end through a real commit/push hook (decoy simulation only).
