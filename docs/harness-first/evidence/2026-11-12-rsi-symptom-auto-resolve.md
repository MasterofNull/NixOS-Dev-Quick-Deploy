# Health-check RSI incidents close themselves when the check passes again

Date: 2026-11-12

## Objective

The RSI ledger held 99 open incidents; 28 came from `health-spider:*` producers describing transient symptoms (failed unit,
probe timeout) that had cleared, while live QA reported 207 passed / 0 failed. Nothing closed them, so the owner's
approval inbox listed 28 "RSI repair needs sign-off" items for problems that no longer existed. Close such an incident,
with evidence, when the same check runs and passes again.

## Workflow/Session IDs

- Branch `fix/rsi-symptom-auto-resolve`, worktree `.agents/delegation/worktrees/rsi-auto-resolve`, base main 60687d873.
- Claimed via `aq-claim` (lane claude). No overlap with the active Codex SOTA sessions (checked their worktree and plans).

## Delegation Decision

Sonnet 5.5 implementer (Rule 17 default); brief `.agents/delegation/outputs/wave-f/rsi-auto-resolve.md`. Orchestrator
reviewed the lifecycle diff (lock-checked resolve, producer scope, timestamp format). Independent review via aq-land.

## Commands Executed

- `python3 -m unittest scripts/testing/test-rsi-osi-trigger.py`
- Re-run: test-rsi-sweep, test-rsi-adapters, test-prsi-rsi-intake, test-rsi-requeue, test-prsi-queue-fail-closed,
  test-health-spider-loop-regression, test-health-spider-osi-layered-probe, test-dashboard-approval-inbox, test-rsi-hung-delegate
- Read-only: the live ledger and the checks the spider runs (HTTP zones, `systemctl --failed`, dashboard probes)

## Validation Evidence

- test-rsi-osi-trigger: 16 tests OK, new `TestHealthIncidentAutoResolve`: symptom opens an incident; the same check passing
  resolves it with "symptom cleared: <check> passed at <ts>" and its queue row becomes `rsi_resolved`; a re-failing probe,
  a different probe passing, the `systemctl` pseudo-unit (check could not run) and a still-failed unit all stay open; a
  non-health-spider producer raises and stays open; an incident seen after the observation stays open;
  `RSI_AUTO_RESOLVE=0` resolves nothing. All existing RSI/spider/inbox tests above pass.
- Read-only estimate on the live ledger: about 27 of 28 open health-spider incidents resolve on the next spider run; the
  `dashboard-agent-runs` probe still times out, so that incident stays open (correctly).

## Rollback Plan

Set `RSI_AUTO_RESOLVE=0` for the spider (kill switch, no rebuild), or revert the PR. Resolved incidents keep their
resolution evidence; a recurring symptom re-opens through `failure()`.

## Residual Risk

- Clears are judged per check; a symptom with no matching passing check never auto-resolves (stays for review).
- The spider service picks up the new script after a checkout sync and service restart.

## Hint Feedback

The approval inbox count was the visible symptom; the ledger's producer field located the cause.
