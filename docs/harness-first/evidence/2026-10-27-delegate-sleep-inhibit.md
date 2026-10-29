# Evidence: delegate-to-* sleep/idle inhibitor (P1.6)

## Source
Host journal 2026-10-27: `journalctl --since today | rg 'System returned from sleep'` showed 5 suspends.

## Defect
Each resume triggers `llama-cpp-resume.service` (WantedBy=sleep.target, `systemctl restart --no-block llama-cpp.service`), restarting the local model and killing in-flight delegated reviews ("Remote end closed connection without response", e.g. task local-20261027-135418-g28x0y). Long headless delegated tasks did not hold any inhibitor, so idle auto-suspend was allowed. (The 5 suspends were later found to be lid closes; see 2026-10-27-mobility-sleep-resilience.md.) Root cause is the missing inhibitor on the producer (delegate-to-*), not the resume unit, which is unchanged.

## Fix
- New shared helper `scripts/ai/lib/sleep-inhibit.sh`: `aq_sleep_inhibit_prefix <task-id>` sets `AQ_INHIBIT_PREFIX` to `systemd-inhibit --what=idle --who=aq-delegate --why="delegated task <id> running" --mode=block`; if `systemd-inhibit` is absent it prints one stderr warning and leaves the prefix empty (unwrapped).
- The long-lived worker launch is prefixed in `delegate-to-local` (both setsid dispatch variants, background), `delegate-to-codex`, `delegate-to-gemini`, `delegate-to-claude` (background worker and blocking-mode provider). The lock lives exactly as long as the wrapped process. It uses `--what=idle` only: it prevents idle auto-suspend and does NOT block manual `systemctl suspend` or lid-close suspend, so sleep the user asks for works normally. Lid-closed keep-awake is the separate opt-in `aq-keep-awake`.
- Test `scripts/testing/test-delegate-sleep-inhibit.py` registered as `delegate-sleep-inhibit` in `config/ci-checks.json`.

## Evidence
- `python3 scripts/testing/test-delegate-sleep-inhibit.py`: 3 tests OK (stubbed argv has `--what=idle`, `--mode=block`; absent case runs unwrapped with exactly one warning; each script's launch carries the prefix and no unwrapped `nohup bash ...-background-worker.sh` remains).
- `bash -n` clean on all four delegate scripts and the helper; `check-ci-manifest-coverage.sh` PASS.
- No real task dispatched; no live-system changes.

## Known gap
- Recorded registry `pid` for codex/gemini/claude background tasks is now the `systemd-inhibit` wrapper pid (it forks and waits on the worker), not the worker itself; kill/liveness via that pid still tracks task lifetime but signals go to the wrapper. Not live-validated end-to-end.
- Blocking (`--wait`) paths of delegate-to-local/codex/gemini are not wrapped (only claude's provider is); `delegate-to-antigravity` (python, legacy) is out of scope.
- This inhibitor does not stop lid-close suspend (logind ignores `sleep` inhibitors for the lid switch by default; only `handle-lid-switch` does). Addressed by opt-in `aq-keep-awake`.

## Objective
Stop idle auto-suspend from interrupting long delegated tasks, without blocking sleep the user asks for.

## Workflow/Session IDs
Orchestrator session 50391bdd. Branch `fix/delegate-sleep-inhibit`. Part review `local-20261028-122302-evtd5q`, integration review `local-20261028-135324-cqxzfo`.

## Delegation Decision
The orchestrator dispatched the implementation to a worktree. Local Qwen reviewed it (Codex budget exhausted, Rule 18 substitution).

## Commands Executed
- `python3 scripts/testing/test-delegate-sleep-inhibit.py`
- `bash -n` on the four delegate scripts and the helper
- `scripts/governance/tier0.d/check-ci-manifest-coverage.sh`

## Validation Evidence
The test passes 3 tests and the manifest coverage check passes (see Evidence above).

## Rollback Plan
Revert the PR. The inhibitor holds no state beyond the lifetime of the wrapped process.

## Residual Risk
See Known gap above: the registry pid is now the wrapper's, the blocking paths are not wrapped, and lid-close is not covered here.

## Hint Feedback
No hint covered suspend behavior. The cause was found from the host journal.
