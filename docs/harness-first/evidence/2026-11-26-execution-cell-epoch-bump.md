# Execution-cell epoch-bump test: host failure root cause

## Objective
Backlog EXECUTION-CELL-RUNNER-HOST-FAIL: `scripts/testing/test-execution-cell-runner.py` failed 55/56 on the host (`epoch_bump_process_actually_dead`). Find the root cause and fix without weakening the epoch-bump kill guarantee.

## Workflow/Session IDs
Headless debug slice, worktree agent-a1fb705166ff33973. No workflow run id (no full tier0, no commit).

## Delegation Decision
Direct implementation: single-file test fix, bounded debug slice delegated by the orchestrator. No further sub-agents.

## Commands Executed
- `python3 scripts/testing/test-execution-cell-runner.py` (reproduce: 55/56, FAILED epoch_bump_process_actually_dead)
- Experiment: create cgroup under the detected parent, `add_pid_to_cgroup` a `sleep 5`, `terminate_cgroup_tree`: add returned False, cgroup.procs empty, result `(True, False)`, `sleep` still alive (state S) after wait(2).
- Experiment: write the pid to cgroup.procs directly: `PermissionError: [Errno 13]`; test process cgroup is `0::/user.slice/user-1000.slice/session-3.scope`.
- `systemd-run --user --scope python3 scripts/testing/test-execution-cell-runner.py` (5x)
- Fixed test run plain on host (5x)

## Validation Evidence
Root cause: TEST/ENVIRONMENT bug, not a product bug. cgroup v2 only allows moving a pid if the writer can write the common ancestor of the source and destination cgroups. The test process lives in `session-3.scope` (outside `user@1000.service`), the target is under `user@1000.service/background.slice`, so the common ancestor `user-1000.slice` is not writable: EACCES. The fixture ignored the `add_pid_to_cgroup` return value, so the cell cgroup stayed empty and `terminate_cgroup_tree` reported "proven absent" vacuously while the unmoved `sleep` lived. The production kill path (SIGTERM per cgroup.procs, then `cgroup.kill`, then empty-proof) is sound: run from inside the user service subtree (`systemd-run --user --scope`) the unmodified test passed 56/56 with the process really dead. The deployed runner runs under a Delegate=true service, where migration is permitted.

Fix (scripts/testing/test-execution-cell-runner.py only):
- `_can_migrate_pid_into_cgroup()` probes a real pid migration; `_CGROUP_MIGRATION_OK`.
- The two kill-proof tests (`epoch_bump_mid_run_kills_tree`, `kill_cannot_prove_removal_quarantines`) SKIP (R6-canary-deferred, with note) when migration is impossible, instead of asserting on a vacuous proof.
- `_maybe_reexec_in_user_scope()`: when migration is impossible, systemd-run is on PATH and AQ_EXEC_CELL_REEXEC is unset, the test `execv`s itself under `systemd-run --user --scope --quiet -E AQ_EXEC_CELL_REEXEC=1` (exit code propagates since the process is replaced). Skip only if systemd-run is absent or the re-exec'd run still cannot migrate.
- New regression assertions `epoch_bump_pid_in_cgroup` / `proof_budget_pid_in_cgroup` require the pid to actually appear in cgroup.procs before the kill proof runs. The `process_actually_dead` assertion is unchanged.

Results:
- Plain host, 3 runs after the re-exec change: 58/58 passed each, 2 skips (R6 canary), kill-proof tests run. Before the re-exec, plain host 5 runs: 46/46, 4 skips. Originally 55/56 failed.
- AQ_EXEC_CELL_REEXEC=1 forced, no scope: 46/46, the two kill-proof tests SKIP with the note.
- Under `systemd-run --user --scope`, 5 runs: 58/58 passed each, 2 skips; epoch_bump_pid_in_cgroup and epoch_bump_process_actually_dead PASS, so the real guarantee is exercised and holds.
- A first attempt that made the shared `_CGROUP_PARENT` None broke 5 unrelated tests; reverted in favor of the separate flag.

## Rollback Plan
`git checkout scripts/testing/test-execution-cell-runner.py` (test-only change; no production code touched).

## Residual Risk
If systemd-run or a user manager is unavailable (minimal CI, containers) the two kill-proof tests skip; the test remains CI-exempt (sandbox-env). Host invocation no longer needs a manual systemd-run. Other cgroup-using scenarios were not audited for the same silent-add behavior.

## Hint Feedback
No aq-hints consulted (headless slice); rg + direct experiments sufficed. Suggest a hint: "cgroup.procs write EACCES = common-ancestor rule; run under systemd-run --user --scope".
