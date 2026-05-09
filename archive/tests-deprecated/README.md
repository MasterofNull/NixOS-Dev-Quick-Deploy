# Deprecated Test Archive

Status: Archived
Owner: AI Stack Maintainers
Last Updated: 2026-05-09

Purpose: preserve legacy or superseded checks that are no longer part of the
active repo validation path.

## What Moved Here

- 64 files removed from `scripts/testing/` during script/test consolidation
- 7 already-deprecated compatibility files retained alongside them:
  - `check-ai-stack-health-v2.py`
  - `check-ai-stack-health.sh`
  - `check-tls-log-warnings.sh`
  - `telemetry-smoke-test.sh`
  - `test-ai-stack-health.sh`
  - `test-container-recovery.sh`
  - `validate-deploy-doc-flags.sh`

## Archive Criteria

- not referenced by `scripts/governance/tier0-validation-gate.sh`
- not needed by current roadmap verification
- superseded by bounded harness tooling or newer focused tests

## Recovery

If one of these checks becomes necessary again:

1. move it back under `scripts/testing/`
2. rewire any current command or fixture paths it depends on
3. add it back to the active validation flow explicitly

Do not treat this directory as an active test surface.
