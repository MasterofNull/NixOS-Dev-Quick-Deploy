## Objective
Make stopping a delegated task real. Before this change `/cancel` and `/kill` in `aq-subagent-interactive` only appended a line to `.agents/delegation/control/<id>.jsonl`; only the local agent loop reads that, between turns, and it only asks the model to finalize. No process was signalled and the registry row did not change. A Gemini delegate hung 96 minutes on 2026-11-06 with no owner control (Rule 15, intervenable).

## Workflow/Session IDs
Branch fix/delegate-real-stop, worktree `.agents/delegation/worktrees/real-stop`. Date 2026-11-06. Bug fix under the feature freeze. Sibling branch fix/aq-workspace-live also edits `aq-subagent-interactive` (the "Queued only" note after `/cancel`); edits here are in non-adjacent hunks.

## Delegation Decision
Implemented by the orchestrator-assigned agent in the worktree; staged, not committed.

## Commands Executed
Minimal-code ladder: `TaskRegistry.cmd_cancel` (reached only by `dispatch.py cancel|kill-all`, unused by the console) already did SIGTERM, SIGKILL after grace, and a `cancelled` row. Hardened it instead of adding a new engine or a new entrypoint; reused the existing `cancelled` terminal status (already understood by fleet monitor and projections).
- `scripts/ai/lib/task_registry.py`: `proc_start_time()`; `append()` records `pid_start_time`; `cmd_cancel` now proves the pid is the task before signalling (recorded start time must match, or for unmarked rows the task id must be in `/proc/<pid>/cmdline`), refuses otherwise, no-ops on terminal rows, never killpgs the caller's group or a group the task does not lead, records `stopped_by`, `stopped_at`, `stop_reason`, `stop_detail`, and prints exactly what happened. Exit codes: 0 stopped or no-op, 1 survived (row `cancel-failed`), 2 refused, 3 unknown task.
- `scripts/ai/aq-delegation-registry`: new `stop <task-id> [--reason R] [--by W] [--grace S]`. With a non-default `--registry` the PENDING/HANDOFF writes stay beside that registry.
- `scripts/ai/lib/registry-update.py`: `set ... pid` also records `pid_start_time`.
- `scripts/ai/delegate-to-{gemini,codex,claude}`: background launch is now `setsid nohup ...` so the task leads its own session and group (local already used setsid); claude also records the start time. Local rows get the start time from `append()`.
- `scripts/ai/aq-subagent-interactive`: `/kill` calls `aq-delegation-registry stop` and prints its output (failures in red with exit code); `/cancel` stays the queued request.
- `scripts/testing/test-delegate-real-stop.py` (new, in group `tests-misc-d-h`), and `test-task-registry-transactional.py` adjusted so its cancel tests carry a start-time marker.
- No real task touched; tests use a fixture registry and throwaway process groups. Nothing deleted; worktrees and outputs are left in place.

## Validation Evidence
`python3 scripts/testing/test-delegate-real-stop.py`: `Ran 11 tests ... OK`, covering running tree stopped with group gone and row updated, SIGTERM-ignorer gets SIGKILL, reused pid refused (process still alive, row unchanged), unmarked row without task id refused, terminal row no-op, unknown task exit 3, already-gone process row marked, caller's own group never killpg'd, `/kill` console output truthful on success and on failure, wrappers launch with setsid, `set pid` records start time.
`python3 scripts/testing/test-task-registry-transactional.py`: `Ran 8 tests ... OK`.
`scripts/governance/tier0.d/check-ci-test-coverage.sh`: `PASS (760 tests: 610 declared, 150 exempt)`.
Mutation checks (each made exactly one test fail, then restored): drop start-time check -> reused-pid test; remove SIGKILL -> ignorer test; drop terminal no-op -> noop test; drop killpg -> 3 tests; drop own-group guard -> caller-group test; accept unproven cmdline -> unmarked test; drop reason recording -> row test; route `/kill` away from stop -> source test; console prints success on failure -> console test; remove setsid from gemini wrapper and drop start time in registry-update -> wrapper/marker tests.

After merging the workspace repair, the console note was corrected: /cancel is a queued request read only by the local agent, and /kill stops any lane through the real stop.

## Rollback Plan
Revert the files above. Rows gain optional fields only; no migration.

## Residual Risk
- Tasks started before this change have no `pid_start_time` and (gemini/codex/claude) sit in the caller's process group. `stop` accepts them only if the task id is in the pid's command line, then signals that pid alone and says child processes may survive; otherwise it refuses. Not verified against a real old task (none touched).
- Not verified end to end with a real gemini/codex/claude/local launch (would start paid or local tasks); wrapper changes are covered by syntax check and source assertions only. `systemd-inhibit` as recorded pid is covered only by the group-kill reasoning.
- `/kill` interactive loop routing is covered by a source assertion plus a direct `stop_task` call, not a live prompt session.
- After merging the sibling branch, its "Queued only" note says claude/codex/gemini "must be stopped outside this console"; that sentence is stale for `/kill` and should be reworded.
- Tier0 and the full run-ci-checks were not run (out of scope). No rebuild required: scripts and tests only; checkout sync suffices.
