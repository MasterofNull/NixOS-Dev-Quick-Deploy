# PROJECT: Gemini Quality Hardening

## Problem
Recent Gemini-authored work exposed recurring integration failures: untracked imported modules, invented profile names, frontend/backend contract drift, placeholder telemetry presented as live data, dead tests, and source-tree assumptions that break under deployed runtime paths. Gemini health checks also duplicated oversized state into `/tmp`, exhausting tmpfs.

## Goal
Keep Gemini available for coding work, but constrain it with stronger proof requirements and repair the concrete defects currently visible in recent Gemini-authored slices.

## Scope
### In
- Remove Gemini-driven `/tmp` amplification.
- Repair confirmed live defects from the audit.
- Tighten Gemini instructions/configuration around bounded reviewed slices.
- Add validation that catches phantom profiles and duplicate dashboard QA launches.
- Replace misleading or undeployable consensus behavior with runtime-valid behavior.

### Out
- Blanket rollback of Gemini work.
- Disabling Gemini entirely.
- Unrelated dashboard redesign.

## Acceptance Criteria
1. `/tmp` remains healthy and Gemini health checks do not clone large chat history.
2. Confirmed live audit defects are fixed and regression-tested.
3. Gemini rules require tracked files, schema checks, no placeholder production telemetry, collected tests, runtime-path validation, and small reviewable slices.
4. Dashboard QA surfaces share one single-flight runner.
5. Intent routing references only canonical profiles.
6. Focused tests and mandatory validation gates pass before commit.

## Security / Safety
- Do not expose Gemini OAuth material during diagnostics.
- No new secrets, hardcoded ports, or broader privileges.
- Temp cleanup is bounded to user-approved stale `/tmp/tmp.*` homes.

## Rollback
Revert the hardening commit to restore prior behavior, then re-apply smaller slices if any sub-change proves incompatible.
