# Local Agent Failure Observability PRD

Status: ACCEPTED_PENDING_COMMIT
Owner: Codex orchestrator
Date: 2026-08-28

## Problem

Measured dogfood task `local-20260827-202157-06ngvs` reached a valid `edit_file`
envelope, then `aq-agent-loop` exited nonzero after about 580 seconds. The detached
dispatcher discarded the child exit code and stderr, leaving only the initial waiting
stub. The retained evidence cannot distinguish an executor exception from a tool relay
or process-lifecycle failure.

## Slice objective

Make every nonzero local-agent child exit diagnosable without exposing prompt or tool
payload contents.

## Scope

- `scripts/ai/lib/dispatch.py`
- `scripts/testing/test-local-delegation-artifact.py`
- `.agent/memory/issues-backlog.md`

## Acceptance criteria

1. `AgentRunner` writes child stderr to a task-specific sidecar adjacent to the output.
2. A nonzero child exit records the numeric exit code and a bounded stderr tail in the
   terminal output/progress evidence.
3. Evidence contains no prompt, tool arguments, environment, or unbounded stderr.
4. A hermetic fake child proves the contract; existing delegation artifact checks pass.
5. Phase 0 and Tier0 are run after integration. Any independent Phase-0 timeout is a
   separate forward slice, not a weakened assertion.
6. One controlled local dogfood task is run only after this slice is accepted and
   committed; its captured reason determines the next executor fix.

## Exclusions

- No inference parameter, model, tool authority, cancellation, routing, or service change.
- No overnight queue run.
- No reapplication of reverted cancellation F1.

## Terminal policy

One implementation, one independent terminal review. Safe follow-ups advance to a new
slice; no same-slice review replay.

## Acceptance evidence

- Failure-observability F2 subject: `3ba58871d9ad01ec1633db70114fbeafe354a45b270b3f094798bb27560c960d` — independent PASS.
- Final three-file integration subject: `933d807455183b81667e16c3eca9bb90b8557f842598c9fd06b3f1ce023e2398` — independent PASS.
- Focused delegation artifact suite: 14/14 PASS in 4.26 seconds; 13 reverted cancellation-lifecycle checks remain explicitly skipped/queued.
