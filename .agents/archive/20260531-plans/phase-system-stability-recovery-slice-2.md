# Phase — System Stability Recovery Slice 2

## Objective
Make post-switch health decisive by default so a rebuild that leaves the system unhealthy cannot be reported as successful.

## Scope Lock
### In
- `nixos-quick-deploy.sh`
- focused regression coverage for post-flight health policy
- focused CI wiring for the new guard

### Out
- automatic rollback implementation
- Redis data migration or destructive repair
- kernel track redesign

## Workstreams
1. Add an explicit post-flight health policy with a strict default and warn-only escape hatch.
2. Route system and MCP health checks through the strict path.
3. Add regression coverage and focused CI wiring.

## Validation
- `bash -n nixos-quick-deploy.sh scripts/governance/run-focused-ci-checks.sh`
- `python3 scripts/testing/test-postflight-health-policy.py`
- focused CI checks
- Tier 0 when runtime services are healthy enough for repo policy gates

## Rollback
Revert the slice commit or run with `POST_FLIGHT_HEALTH_POLICY=warn` temporarily if operators need legacy behavior during recovery.
