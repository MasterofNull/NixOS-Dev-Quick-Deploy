# Harness-First Task Evidence

Date: 2026-11-19
Task ID: HF-20261119-002

## Objective
- Recurring HIGH alert attn-42b0a317cc394698 "aq-qa phase 0 could not run: ... timed out after 705 seconds". Root cause: phase 0 grew to ~116 check functions run strictly one after another in `phase0.run()`. Measured on the live host (load avg 22-33), the serial sum is 1204 s; ~10 subprocess/git-fixture checks account for ~900 s (factory_readiness_preflight 243 s, factory_gate_retrofit 103 s, factory_gate_install 85 s, capability_outcome_resolver 74 s, worktree_isolation_safety 72 s, aq_confine_behavioral 61 s, state_authorities 53 s, integration_guard 51 s). The monitor's outer deadline (`HARNESS_TIMEOUT_S=705`, set in ai-stack.nix from a 282 s measurement in 2026-10-08) therefore killed the whole phase and reported "could not run" with no per-check result. The service journal shows every run at 8.5-11.8 min wall and 7.7-9.9 min CPU (CPU-bound, not queued on llama or the network); the runs finishing near 11.7 min wall (22:04, 22:49 on 2026-11-18) are the ones that hit the limit. llama-dependent checks (graphrag, local_inference_*) total only ~120 s and the network is not involved.
- Fix (producer): `harness_qa/core/scheduler.py` runs phase 0 checks in a bounded daemon-thread pool with a per-check deadline and a whole-phase budget; a check that does not finish becomes a SKIP row "DEGRADED: ..." (names llama busy / host load), a check whose subprocess timed out has its FAIL demoted to the same DEGRADED SKIP (no verdict), a crashing check is a real FAIL, and results keep plan order. The phase always returns a partial per-check result. Limits are env-overridable and host-derived: `AQ_QA_PHASE0_WORKERS` (default cpus/4, 1..4), `AQ_QA_PHASE0_BUDGET_S` (default 85% of `HARNESS_TIMEOUT_S`, else 5 s per check), `AQ_QA_PHASE0_CHECK_TIMEOUT_S` (default budget/4). The monitor sets the budget from its own timeout, raises a separate MEDIUM "QA phase 0 degraded" alert listing incomplete checks, and never counts a degraded run as clean (no recovery retirement). Real FAILs still alert at the existing severities.

## Workflow/Session IDs
- Workflow ID: none (bounded implementer slice)
- Session ID: Simurg@claude/sonnet under orchestrator da0ef470

## Delegation Decision
- Delegated by orchestrator (Rule 17); implemented directly by the sonnet implementer lane; no local-model dispatch (diagnosis needed live host timing).

## Commands Executed
```bash
journalctl -u ai-stack-health-monitor.service -n 60 --no-pager
nice -n 19 python3 <timeit.py>          # each _check_* in phase0.run(), sequential (before)
HARNESS_TIMEOUT_S=705 nice -n 19 python3 <after.py>   # phase0.run() with the new scheduler (after)
python3 scripts/testing/test-qa-phase0-bounded.py
python3 scripts/testing/test-ai-stack-health-monitor.py
python3 scripts/testing/test-boot-stability-regressions.py
python3 scripts/testing/test-dashboard-program-progress.py
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Before (serial, load avg ~25, 116 checks): 1204.6 s total; the 22 checks of >=10 s sum to 1032 s. Top: factory_readiness_preflight 242.8 (FAIL via its own scaled timeout), factory_gate_retrofit 102.8, factory_gate_install 84.6, capability_outcome_resolver 73.9, worktree_isolation_safety 71.9, aq_confine_behavioral 60.6, state_authorities 53.2, integration_guard 50.5, local_direct_health_contract 38.0, local_inference_l2b 34.4, dashboard_program_progress 33.8, provider_projection 29.3, graphrag 29.2, local_inference_contract 20.8.
- After (4 workers, same loaded host, HARNESS_TIMEOUT_S=705 so budget 599 s): phase 0 wall 292.5 s, 197 PASS / 14 SKIP / 5 FAIL, zero DEGRADED rows. The 5 FAILs are pre-existing/environmental and also appeared before (ai-prompt-eval.service failed unit; dashboard HTTP -1 x2; 0.10.40 dataset; flagship_cli needs the reserved invocation id only `main()` supplies, an artifact of the timing driver).
- Unit tests: test-qa-phase0-bounded.py PASS (hung check cut with partial result and order kept, real FAIL and crash stay FAIL, budget exhaustion degrades running and unstarted checks with a llama-busy reason, env limits, subprocess-timeout demotion, monitor treats DEGRADED as non-failure and never clean); test-ai-stack-health-monitor.py PASS; test-boot-stability-regressions.py PASS; two source-text assertions updated for the `plan.append(...)` form. test-dashboard-program-progress.py: 2 live-endpoint tests time out on this loaded host (dashboard HTTP -1, same as the baseline), unrelated.
- Deploy: no rebuild. The unit runs `scripts/health/ai-stack-health-monitor.py` from the repo checkout and the monitor derives the phase budget from HARNESS_TIMEOUT_S, so a checkout sync activates it. The nix `HARNESS_TIMEOUT_S=705` / `TimeoutStartSec=765` stay valid as the outer backstop.

## Rollback Plan
- git revert the commit; no runtime or deploy state touched. Setting `AQ_QA_PHASE0_WORKERS=1` restores serial execution while keeping the deadlines.

## Residual Risk
- Parallel checks share the repo and host; any check with hidden shared state could interfere (none observed in the 292 s run). Abandoned threads/subprocesses of a cut check run until their own timeout, bounded by the unit cgroup.
- The 8 fixture checks above remain heavy (~900 s CPU serial); worth a follow-up to make them faster or move them to a slower cadence. Not done here (scope).
- A DEGRADED SKIP has no verdict; a persistent degraded set means reduced coverage and is surfaced by the MEDIUM alert, not hidden.

## Hint Feedback
- No hints used.
