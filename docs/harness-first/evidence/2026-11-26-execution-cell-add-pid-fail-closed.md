# Execution-cell runner: fail closed when the pid cannot enter its cgroup

## Objective
Backlog EXECUTION-CELL-PROD-ADD-PID-FAIL-OPEN: `_confine_run_validate` in `ai-stack/switchboard/execution_cell_runner.py` ignored the `False` return of `add_pid_to_cgroup` (EACCES when cgroup migration is not permitted). The cell then ran with an empty cgroup, and `_supervise` -> `terminate_cgroup_tree` could report "proven absent" vacuously for a child that was never contained (same defect #879 fixed in the test fixture).

## Workflow/Session IDs
Headless containment bug-fix slice, worktree agent-ae0401d49b68d1ed2. No workflow run id; no full tier0; not committed (staged only).

## Delegation Decision
Direct implementation: bounded single-concern fix delegated by the orchestrator. No further sub-agents.

## Commands Executed
- `rg add_pid_to_cgroup`: call sites are runner.py:761 (production, return ignored), perf harness :1242 (return ignored), two test fixtures (already asserted by #879).
- Fix: runner now checks the return; on False calls new `_kill_unattached_child` (`os.killpg(pid, SIGKILL)`, fallback `popen.kill()`, reap) and returns `Decision(QUARANTINED, "cgroup-attach-failed", STAGE_CONFINE_RUN)` with `tree_proven_absent=False` (no proof claimed). New `REASON_CGROUP_ATTACH_FAILED`.
- Perf harness `revocation-under-load` fixture now records a failure, kills its stray `sleep` procs and returns if the add fails.
- New test `test_add_pid_failure_fails_closed` in `scripts/testing/test-execution-cell-runner.py` (pure stubs for `build_bwrap_argv`, `create_cgroup`, `add_pid_to_cgroup`, `Popen`; `_supervise` stubbed to raise if reached).
- `python3 scripts/testing/test-execution-cell-runner.py`; `ruff check`; `basedpyright`; `python3 scripts/governance/check-cross-surface-contract.py`.

## Validation Evidence
- Before: `add_pid_to_cgroup(cgroup_path, popen.pid)` at runner.py:761 discarded its result and fell straight into `_supervise` (line 763) and the proof path.
- After: runner test 63/63 passed (2 R6-canary skips), including the 6 new `add_pid_fail_*` checks (child spawned, QUARANTINED, reason cgroup-attach-failed, tree_proven_absent is False, child dead, receipt schema valid; the last needs jsonschema, else skipped).
- Negative control: with the new guard disabled the new test fails (`_supervise reached after add_pid_to_cgroup failure`, 58/59); restored, 63/63.
- The success path is unchanged (existing GREEN/kill-proof tests still pass).
- ruff/basedpyright: no diagnostics on the touched lines; all remaining findings in the three files are pre-existing (ruff 11, basedpyright 5). check-cross-surface-contract: PASS.

## Rollback Plan
Revert the three touched files; behaviour returns to the prior fail-open path. No config, schema or data migration involved (the new reason string is a free-form low-cardinality reason; receipt schema unchanged).

## Residual Risk
- The direct kill covers the child's process group/session only; a descendant that called `setsid` before the failed attach could escape. The cell is quarantined (not proven absent) precisely because this is not claimed.
- Quarantine here arrives before supervision, so the cgroup dir is cleaned only if empty (existing `_cleanup_cgroup_dir`).
- Deployed runner runs under `Delegate=true`, where migration is permitted, so this should be rare; it surfaces misdelegation loudly instead of silently.

## Hint Feedback
No aq-hints consulted (headless slice). The #879 evidence doc (`2026-11-26-execution-cell-epoch-bump.md`) was the direct predecessor and root-cause source.
