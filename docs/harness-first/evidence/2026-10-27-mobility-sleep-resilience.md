# Evidence: mobility / sleep resilience for local delegated tasks (P1.6 + P1.8)

## Source
Host journal 2026-10-27: all 5 suspends were lid closes (`systemd-logind: Lid closed. Suspending...`). Each resume ran `llama-cpp-resume.service` (WantedBy=sleep.target), which unconditionally `systemctl restart --no-block llama-cpp.service`, killing in-flight delegated tasks ("Remote end closed connection without response"). The unit was added 2026-03 for ROCm GPU re-init; the server now uses Vulkan. logind `LidSwitchIgnoreInhibited` defaults to yes, so a `sleep` inhibitor never stopped lid suspends; `HandleLidSwitch=suspend` comes from `nix/modules/hardware/mobile.nix`.

## Defect
1. The per-task lock (P1.6) used `--what=sleep:idle`, which would also block sleep the user asks for, yet still not stop lid suspends.
2. Resume restarted the model unconditionally.
3. A request dropped by a restart failed the task with no retry.

## Fix
- `scripts/ai/lib/sleep-inhibit.sh`: `--what=idle` only (idle auto-suspend); manual and lid sleep are unaffected.
- `scripts/ai/aq-keep-awake on|off|status|watch`: opt-in (default off; state `${XDG_STATE_HOME:-~/.local/state}/aq/keep-awake.json`). The watcher (30 s) holds `systemd-inhibit --what=handle-lid-switch:sleep --who=aq-keep-awake` only while mode is on AND a delegated task runs (registry `running` with live pid, or an `aq-delegate` inhibitor) AND guards pass: AC online or battery >= threshold (default 40%), and max `/sys/class/thermal` zone <= limit (default 90 C). On release while the lid is closed (guard tripped, task ended, or mode turned off) it runs `systemctl suspend`. Transitions go to the journal via stdout. Unit `aq-keep-awake` declared in `nix/modules/services/keep-awake.nix`, option `mySystem.aiStack.keepAwake.enable` (default false).
- `scripts/ai/aq-llama-resume-gate` (llama-cpp-resume ExecStart): waits up to 60 s for `/health` plus a 1-token completion (`enable_thinking:false`); restarts llama-cpp (`--no-block`) only if that fails. Port from `llama.port` via env in `nix/modules/roles/ai-stack.nix`.
- `scripts/ai/lib/conn_retry.py` wired at task level in `scripts/ai/delegate-to-local` (direct mode; `dispatch.py` is untouched because the L2B golden pins its hash): the dispatch command runs under `conn_retry.py`; on connection reset / closed / refused it waits up to 120 s for `/health` (`LLAMA_PORT`), re-runs the same dispatch once under task id `<id>-r1` (same output file, `retry_of: <id>`). No registry row is deleted: the original row goes to `failed_retried` (`retried_as: <id>-r1`) when the retry starts, then resolves to the retry's final status with `retried: true`, `retry_reason`, `first_attempt_status: failed_retried`; `<output>.retry.json` records the same. Other errors are not retried.

## Evidence
- `python3 scripts/testing/test-mobility-sleep-resilience.py`: 12 tests OK (decision matrix AC/battery/threshold/thermal/tasks; suspend-on-release only with lid closed and lock held; state file default off; resume gate healthy -> no restart, unhealthy -> restart; stub server dropping the first connection -> exactly one retry via the CLI wrapper, none on HTTP 400, give-up when llama never healthy).
- `python3 scripts/testing/test-delegate-sleep-inhibit.py`: 3 tests OK (`--what=idle`).
- `bash -n`, `nix-instantiate --parse` and `check-ci-manifest-coverage.sh` results in the slice report. No real suspend, inhibitor, dispatch or rebuild performed.

## Known gap
- Not live-validated: real lid-close with the watcher, `systemctl suspend` polkit permission from the user service, and the resume gate after a real resume (needs owner rebuild).
- Resume gate no longer re-inits GPU state; if Vulkan ever needs it after suspend, the completion probe fails and the fallback restarts (cost: up to 60 s extra).
- Retry is one shot and does not resume partial streamed output (output is overwritten). Only direct mode; agent/hybrid/ralph are not covered.
- Thermal/battery sensors that are absent are treated as passing.
- `config/suspend-resume-workloads.json`: `aq-keep-awake` registered; `llama-cpp-inference` updated to `restart_on_resume_if_unhealthy`.

Follow-up (2026-10-28): the delegate scripts load `lib/sleep-inhibit.sh` optionally. A missing helper prints a stderr warning and the task runs without an idle inhibitor (it is a convenience, not a safety control). Unconditional sourcing had broken three Claude-path tests whose fixtures run `delegate-to-claude` from a partial `lib/` copy (test-delegate-claude-model-routing, test-claude-dispatch-payload-safety, test-delegate-to-claude-lifecycle); they pass again.

## Objective
Stop sleep and resume from killing local delegated work (P1.6 and P1.8). Resume should not restart a healthy model, a request dropped by one restart should be retried once, and lid-closed keep-awake should be available as opt-in.

## Workflow/Session IDs
- Orchestrator session 50391bdd. Branch `fix/delegate-sleep-inhibit`, reviewed head fe78418a.
- Part reviews: `local-20261028-122302-evtd5q` (task lock), `local-20261028-123124-4f3kb2` (keep-awake), `local-20261028-124406-juikmv` (resume gate plus retry).
- Integration review: `local-20261028-135324-cqxzfo`.

## Delegation Decision
The orchestrator dispatched the implementation to a worktree. Local Qwen gave the part reviews and the integration review. Codex's daily budget was exhausted, so local Qwen substituted (Rule 18). The author lane did not review its own work.

## Commands Executed
- `python3 scripts/testing/test-mobility-sleep-resilience.py`
- `python3 scripts/testing/test-delegate-sleep-inhibit.py`
- `bash -n` on the changed shell scripts, and `nix-instantiate --parse` on the changed Nix files
- `scripts/governance/tier0.d/check-ci-manifest-coverage.sh`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`
- `scripts/governance/ci-merge-parity.sh`

## Validation Evidence
- The mobility test passes 12 tests, and the inhibitor test passes 3.
- The manifest coverage check passes.
- On the main merge commit, tier0 reported 65 passed and 0 failed.

## Rollback Plan
- Keep-awake: `aq-keep-awake off`, or set `mySystem.aiStack.keepAwake.enable = false` and rebuild.
- Resume gate and retry: revert the PR. The gate restarts llama-cpp whenever its health probe fails, so a faulty gate falls back to the old behavior.

## Residual Risk
See Known gap above: no live lid-close, `systemctl suspend` from the user service, or post-resume gate run yet. Retry is one shot, direct mode only. Absent sensors count as passing.

## Hint Feedback
The harness had no signal tying the lost reviews to lid suspends. The cause was found from the journal. Keep-awake transitions now go to the journal, and the retry records `retry_of` in the registry.
