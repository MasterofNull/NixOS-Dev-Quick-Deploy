# PROJECT-CONTINUE-EDITOR-RESCUE-PRD

## Problem
`aq-qa 0` is blocked by three Continue/editor checks. Evidence shows two distinct causes:
- `0.5.2`: stale user Continue config, now remediated by `home-manager switch`.
- `0.5.4` and `0.5.5`: `ai-switchboard.service` is live but returns `404` for `/health`, so the Continue-local profile smoke checks cannot inspect runtime readiness.

## Goal
Restore the switchboard `/health` contract used by QA and editor-facing telemetry, then verify the Continue/editor checks recover.

## Scope
### In scope
- Add the missing switchboard `/health` endpoint in `ai-stack/switchboard/switchboard.py`.
- Expose the already-existing profile catalog and local runtime snapshot in the health payload.
- Validate the specific failing QA checks and repo-wide gate behavior.

### Out of scope
- Further flake input updates.
- Refactoring the switchboard route architecture.
- Unrelated dashboard or editor UX work.

## Acceptance Criteria
- `curl http://127.0.0.1:8085/health` returns HTTP 200 JSON.
- Payload includes `profiles`, `local_runtime`, and `local_lane_status`.
- `aq-qa 0` no longer fails `0.5.2`, `0.5.4`, or `0.5.5`.

## Security / Safety
- Health payload exposes only runtime configuration already intended for local observability.
- No auth changes or new external dependencies.
- Restart only the repo-backed `ai-switchboard.service` after syntax validation.

## Rollback
- Revert the small route addition and restart `ai-switchboard.service` if the endpoint causes regression.
