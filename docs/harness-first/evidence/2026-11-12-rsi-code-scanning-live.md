# The RSI sweep keeps code-scanning alerts live and closes fixed ones

Date: 2026-11-12

## Objective

The `code-scanning` sweep adapter read an alerts export last written 2026-10-07 and nothing refreshed it, so the source
read "unknown" for five weeks: 62 live open alerts (2 critical) were untracked, and 49 open incidents had fixed or
dismissed alerts because only a manual `aq-rsi reconcile` closes them. The 15-minute sweep now refreshes the export and
closes incidents whose alerts are all closed upstream.

## Workflow/Session IDs

- Branch `fix/rsi-code-scanning-live`, worktree `.agents/delegation/worktrees/rsi-code-scanning`.

## Delegation Decision

Sonnet 5.5 implementer (Rule 17 default); brief `.agents/delegation/outputs/wave-f/rsi-code-scanning-live.md`.
Independent review via aq-land.

## Commands Executed

- `python3 scripts/testing/test-rsi-sweep.py`
- `python3 scripts/testing/test-rsi-intake-code-scanning.py`

## Validation Evidence

- test-rsi-sweep: 50 tests OK; new `CodeScanningLiveTests`: stale default export refreshed from an injected fetch;
  fetch failure leaves the export untouched and reads unknown; an explicit path never fetches; `run()` resolves an
  incident whose alerts are fixed with "code-scanning alerts closed upstream ..." evidence while an incident whose alert
  is still open stays open; two incidents with the same producer and error but different paths resolve by id only; fixed/dismissed alerts are never recorded as new incidents.
- test-rsi-intake-code-scanning: 11/11 pass (the intake already plans only `state == "open"` alerts).
- Live dry-run from the worktree (`aq-rsi sweep --dry-run --json`, export redirected to a scratch dir via
  `AI_SECURITY_AUDIT_DIR`): export refreshed from GitHub; code-scanning `findings` with 15 open alert groups;
  49 open incidents would resolve with closed-upstream evidence.

## Rollback Plan

Set `RSI_SWEEP_CODE_SCANNING_REFRESH_S` very large to stop refreshes (the adapter then reverts to stale -> unknown), or
revert the PR. Resolved incidents keep their evidence; a recurring alert re-opens through `failure()`.

## Residual Risk

- The refresh needs `gh` authenticated for the sweep's user; on failure the source reads unknown, as before.
- `aq-rsi reconcile` is unchanged and remains available for manual runs.

## Hint Feedback

`aq-rsi reconcile --dry-run` showing 49 resolvable incidents located the missing scheduler.
