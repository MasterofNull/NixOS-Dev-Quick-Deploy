# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-060

## Objective
- The FE-1 PRM A/B run was INVALID. The eval timeout (1800+300s) was shorter than the agent hard wall budget (3600s), and a timeout killed only the delegate wrapper. The setsid-detached agent kept running into later runs on the single inference slot, so all 10 rows were rc=-1 at about 2100s with pass=true. One stray agent was found still running 37 minutes after the eval exited.
- Fix in aq-prm-eval:
  - The delegate runs in its own process group; on timeout the group gets SIGTERM, then SIGKILL after 15s.
  - Detached agents are reaped by the PIDs in the eval's own delegation registry, both before each run (recorded as orphan_killed) and after it.
  - passes() runs only after cleanup is confirmed.
  - AQ_AGENT_WALL_BUDGET_S (an existing knob) is set to timeout-120, so the agent stops before the eval gives up.
  - New row fields: timed_out, overlapped, completion_reason, tool_calls, completed_cleanly.
  - Top-level `valid` is false on any timeout or overlap, so an invalid A/B can no longer look like a result.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer (process-lifecycle correctness). The orchestrator diagnosed the run from event timelines and stopped the stray agent.

## Commands Executed
```bash
python3 scripts/testing/test-prm-eval-harness.py   # 12/12 (fake setsid agent: group kill, orphan reap, cleanup-before-pass, valid flag, budget env)
python3 scripts/testing/test-prm-steering.py       # 10/10
scripts/ai/aq-prm-eval --dry-run                   # fixtures OK
```

## Validation Evidence
- Behavioural tests using a real detached child process; nothing calls local inference.

## Rollback Plan
- Revert.

## Residual Risk
- The local agent's slow convergence on small edits (logged separately) will likely produce timed_out rows. These are now reported honestly as invalid, not as passes.

## Hint Feedback
- None.
