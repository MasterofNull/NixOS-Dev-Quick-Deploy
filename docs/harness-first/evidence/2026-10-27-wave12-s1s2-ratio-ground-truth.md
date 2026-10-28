# Wave 12 follow-up: S1/S2 routing card from ground truth (2026-10-27)

Source: Claude peer review of Waves 9-12 (`.agents/delegation/outputs/claude-20261026-214612-q4ny9d.log`, finding 1). PR #632 merged before the blocker was fixed.

## Defect
- `cockpitRoutingRatio` read `runtime-summary.summary.active_agent_runs` (field does not exist -> always 0), clamped to 85-99%, fell back to a hardcoded 95%. Card always showed `S1: 99% · S2: 1%`.
- Triage line multiplied `success_rate` (already 0-100) by 100; null rendered as `100%`.
- HTML placeholders (`97 / 97 PASS`, `< 140ms`, `S1: 94% · S2: 6%`, `100% IDEMPOTENT`) and JS fallback `100% IDEMPOTENT` displayed invented values.

## Fix
- Ratio now reads the existing producer `/aistack/routing/summary` -> `routing_windows.windows["24h"]` (switchboard routing ring; local = S1, remote = S2). Missing data -> `--`. No clamp.
- `success_rate` rendered as-is; null -> `--`.
- All placeholders/fallbacks -> `--`.
- Regression test for Wave 12 triage patterns (SEGV/code=dumped, apparmor DENIED, exit-code) in `scripts/testing/test-aq-triage.py`.

## Evidence
- Live payload (2026-10-27): 24h window count=16, local_pct=87.5, remote_pct=12.5. Rendering logic evaluated against it: `S1: 88% · S2: 12% (24h, n=16)`.
- `node --check assets/dashboard.js` OK; `python3 scripts/testing/test-aq-triage.py`: 8 tests OK, 6 fixtures pass.

## Known gap
- `cockpitApiHealth` has no producer wired in JS; it now shows `--` honestly. Tracked in issues-backlog.
