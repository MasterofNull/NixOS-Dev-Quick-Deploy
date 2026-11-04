# Verified acceptance record items shape fix

## Objective

Independent review of `0f997963f887c4895404a4169f9368de3b8ee3ec` found that a record with a valid SHA-256 digest but a non-list `items` value could raise during owner acceptance validation and PM projection. `_recorded_problem` now rejects every non-list `items` value with a structural error before iterating. Projection consequently labels the acceptance `SHIPPED (unverified)`.

The regression covers integer, object, string, and null `items` values. Each record is hashed from its actual serialized bytes, then checked for a validation error and an unverified projection.

## Workflow/Session IDs

Branch `feat/verified-owner-acceptance`, worktree `.agents/delegation/worktrees/verified-acceptance`.

## Delegation Decision

Implementers were bounded Sonnet-tier sub-agents (Rule 17).

## Commands Executed

- `python3 scripts/testing/test-pm-tracker-owner-acceptance.py`
- `python3 scripts/testing/test-pm-tracker-acceptance-authority.py`

## Validation Evidence

- `python3 scripts/testing/test-pm-tracker-owner-acceptance.py` — 43 tests passed.
- `python3 scripts/testing/test-pm-tracker-acceptance-authority.py` — 15 tests passed. Expected negative-case diagnostics were emitted by the authority harness.

No tier0 gate, commit, push, or live activation was run as part of this delegated fix.

## Rollback Plan

Revert the commit; trackers are untouched.

## Residual Risk

None recorded in this file.

## Hint Feedback

None.
