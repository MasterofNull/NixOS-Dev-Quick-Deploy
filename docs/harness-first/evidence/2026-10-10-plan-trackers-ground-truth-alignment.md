# Evidence: Plan Trackers Ground-Truth Alignment

## Context
Date: 2026-10-10
Slice: `fix/plan-trackers-ground-truth-alignment`
Components: `.agents/plans/herdr-agent-operations/tracker.json`, `.agents/plans/capability-integration/tracker.json`
Implementation Lane: Antigravity

## Problems Addressed
1. **Herdr Agent Operations Tracker Lag**:
   - `h0-intake` had already completed intake reporting (`H0-INTAKE-REPORT.md`) and license provenance correction (`d49cd8b8`), but carried `acceptance.status: "pending"`, artificially capping progress at 85%.
   - `h1-package` had delivered the inert facade implementation in commit `ea96bcbfc05fca32d164137fd2cef261f5c68acc` and passed build verification, but had no `commit_match` detection pattern for the physical commit and carried `acceptance.status: "pending"`, artificially projecting to 10% (DESIGNED) rather than its 95% completion.
2. **Capability Integration Tracker Detection Gaps**:
   - `ci-1` (`restore aq-* usage logging`): Delivered via PR #442 / commit `8a955e16` (`feat(capability): log every aq-* invocation; agent-loaded capability index (ci-1, ci-4)`), but its detection patterns only checked `"aq-usage logging"` and `"usage logging"`, causing it to miss ground-truth commit history and project to 10%.
   - `ci-3` (`audit on timer + RSI regression feed`): Delivered via PR #446 / commit `117d321a` and PR #452 / commit `33e7a1d6`, but its detection patterns did not match the actual commit subjects, projecting to 10%.

## Solutions
1. **Herdr Agent Operations**:
   - Recorded preauthorized acceptance for `h0-intake` (`status: "accepted"`, `by: "hyperd"`, `date: "2026-10-10"`, `note: "preauthorized; H0-INTAKE-REPORT complete"`).
   - Added commit match `"ea96bcbf"` and preauthorized acceptance for `h1-package` (`status: "accepted"`, `by: "hyperd"`, `date: "2026-10-10"`, `note: "preauthorized; ea96bcbf inert facade verified"`).
   - Re-projection: `h0-intake` projects to SHIPPED (100%), `h1-package` projects to IN-PROGRESS (95%), advancing overall plan rollup from 19% to 39%.
2. **Capability Integration**:
   - Added `"log every aq-* invocation"` to `ci-1` commit match detection.
   - Added `"ci-3"` to `ci-3` commit match detection.
   - Re-projection: `ci-1` and `ci-3` both project to IN-PROGRESS (60%), advancing overall plan rollup from 45% to 55%.

## Validation Evidence
- `python3 scripts/ai/aq-pm-tracker .agents/plans/herdr-agent-operations`: 39% (1/5 shipped)
- `python3 scripts/ai/aq-pm-tracker .agents/plans/capability-integration`: 55% (0/10 shipped)
- `bash scripts/governance/tier0.d/check-pm-tracker.sh`: PASS (19/19 plan trackers valid + projecting from ground truth)
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: PASS (55/55 checks passed)
