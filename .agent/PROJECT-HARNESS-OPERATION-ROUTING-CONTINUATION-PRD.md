# PROJECT: Harness Operation Routing Continuation

## Problem
An interrupted routing slice introduced a new `harness_operation` intent and a `local-harness-ops` profile, but the profile was not registered in the canonical routing contract. That leaves the repo with a partially wired lane that can classify requests into a profile the harness does not recognize.

## Goal
Finish the interrupted slice safely by routing `harness_operation` requests through an existing valid local profile instead of adding a new profile surface.

## Scope
### In
- Normalize `harness_operation` routing to an existing valid local lane.
- Align forced local-offload metadata with that valid lane.
- Add regression coverage for `harness_operation` classification.
- Remove the unused partial `local-harness-ops` policy entry.

### Out
- No broader routing-contract refactor.
- No new switchboard profile.
- No unrelated consensus-arbiter changes.

## Constraints
- Preserve Gemini's intent: routine harness checks should remain local.
- Prefer existing canonical profile names over adding a new lane.
- Keep the slice isolated from unrelated dirty-tree work.

## Acceptance Criteria
1. `harness_operation` resolves to a valid existing local profile.
2. No remaining `local-harness-ops` references remain in active routing config/code.
3. Regression tests cover keyword classification for `harness_operation`.
4. Touched Python/JSON files validate cleanly and focused tests pass.

## Security Notes
- No new secrets, URLs, ports, or privileges.
- This change reduces configuration drift by removing an unregistered routing lane.

## Rollback
Revert this slice commit to restore the prior interrupted state if downstream behavior unexpectedly depends on `local-harness-ops`.
