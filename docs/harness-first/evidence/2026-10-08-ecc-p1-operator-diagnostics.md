# ECC P1 operator diagnostics and eval dimensions

## Objective
Implement only the gaps P0-A proved (PARITY-GAP-LEDGER: Memory/learning "partial diagnostics", Eval/verification
candidate 5, Observability/UI, outcome catalog `accessibility-review` partial) as one operator diagnostics command,
a QA check (0.10.57) and dashboard visibility.

## Workflow/Session IDs
Slice ECC P1 (implementer, Sonnet step-up for multi-surface integration). No workflow run id issued.

## Delegation Decision
Orchestrator-dispatched implementer slice; no further delegation.

## Commands Executed
- `python3 scripts/testing/test-ecc-diagnostics.py`
- `python3 scripts/ai/aq-ecc-diagnostics`
- phase-0 check `_check_ecc_diagnostics` invoked directly; related P0-A/B/C fixtures re-run.

## Validation Evidence
Fixture PASS (6 checks: memory recall degraded/unverified, missing repo all-unverified, lifecycle states,
eval-dimension gap, CLI exit codes/worst-wins, dashboard summary never raises). Live report is DEGRADED
(accessibility-review open gap; one oversize memory record; lifecycle dormant => UNVERIFIED). Tier-0 not run by the
implementer (requires git operations blocked in the worktree); coordinator runs it at commit.

## Rollback Plan
Revert the commit; the change adds one CLI, one lib, one test, one QA check, one dashboard row and one additive
JSON key. No services, timers, config or P0-B/P0-C internals changed.

## Residual Risk
Eval dimensions are static marker presence in existing tests (`covered-static`), not a runtime verdict.
Memory scan covers repo `.agent/memory` by default. Accessibility rubric intake and WorkspaceManager hardening
are not selected (no focused comparison / measured use yet).

## Hint Feedback
None recorded.
