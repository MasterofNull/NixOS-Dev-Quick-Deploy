# Phase — System Stability Recovery Slice 3

## Objective
Prevent unsafe stateful-service downgrades before switch, using the Redis regression as the first concrete guardrail.

## Scope Lock
### In
- `nixos-quick-deploy.sh`
- focused regression coverage for Redis downgrade protection
- focused CI wiring

### Out
- Redis data migration
- destructive repair of live state
- generic package solver for every stateful service

## Workstreams
1. Compare the currently running Redis package version with the target flake Redis version.
2. Block downgrades by default, with a warn-only escape hatch for controlled recovery.
3. Add regression coverage and CI wiring.

## Validation
- `bash -n nixos-quick-deploy.sh scripts/governance/run-focused-ci-checks.sh`
- `python3 scripts/testing/test-stateful-downgrade-policy.py`
- focused CI checks

## Rollback
Revert the slice commit or run with `STATEFUL_DOWNGRADE_POLICY=warn` for an explicitly accepted recovery scenario.
