# Power gate: battery and temperature limits are overridable and host-derived

Date: 2026-11-18
Task ID: HF-POWER-GATE-OVERRIDES-20261118

## Objective
- Owner directive 2026-11-18: no hardwired limits, the system deploys across many hardware environments. Audit (`.agents/delegation/outputs/hardwired-limits-audit-20261118.md`) found `MIN_BATTERY_PCT = 50` and `MAX_TEMP_C = 80.0` in `scripts/ai/lib/power_gate.py` not overridable; 80 C is wrong for fanless parts and for server CPUs with a 95-105 C critical point.
- Delivered: `AQ_POWER_GATE_MIN_BATTERY_PCT` (default 50, clamped 0-100) and `AQ_POWER_GATE_MAX_TEMP_C`. When the temp override is absent the ceiling derives from the CPU's own trip points (thermal_zone `trip_point_*_temp` of type critical/hot/high on x86_pkg_temp zones, hwmon `temp*_crit` / `temp*_max` on k10temp/coretemp/zenpower) as the lowest value minus `AQ_POWER_GATE_TEMP_MARGIN_C` (default 15), capped at 100 C (no floor; superseded by the 2026-11-19 retro fix); no readable trip point keeps 80 C. Non-CPU sensors (acpitz) are ignored. The temperature ceiling is now in the `readings` as `max_temp_c`.

## Workflow/Session IDs
- Workflow ID: none (bounded implementer slice). Session: Simurg@claude/sonnet; orchestrator Simurg@claude/opus-5.5#da0ef470.

## Delegation Decision
- Sonnet 5.5 implementer (Rule 17) dispatched by the orchestrator. No review or merge by this lane; independent review is left to another lane.

## Commands Executed
```bash
git worktree add -b fix/power-gate-overrides .agents/delegation/worktrees/power-gate-overrides origin/main
python3 scripts/testing/test-local-power-gate.py
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- `test-local-power-gate.py`: 18/18 OK. The 10 existing tests pass unchanged (defaults preserved: 50% battery, 80 C with no trip points). 8 new tests: battery override, temp override, invalid env falls back, derivation from hwmon crit (fanless crit 85 gives 70 C and defers at 72 C), server-class crit 105 gives 90 C and runs at 85 C, derivation from thermal_zone trips (passive trip ignored, margin env), floor/ceiling clamps, non-CPU trip points ignored.
- Tier0 output is in the commit hand-off.

## Review fix (Codex REQUEST_CHANGES cf3258ab)
- `_env_float` rejects non-finite values (`nan`, `inf`, `-inf`): `AQ_POWER_GATE_MAX_TEMP_C=nan` made `temp >= max` always false (gate open on a hot CPU), and a nan battery floor or margin clamped to 0. They now fall back to the derived default with a `power-gate: WARN` line on stderr (invalid non-numeric strings warn too). Regression: `test_non_finite_env_values_fail_closed_to_default`.

## Rollback Plan
- Revert the commit, or set `AQ_POWER_GATE_MAX_TEMP_C=80` and `AQ_POWER_GATE_MIN_BATTERY_PCT=50` to pin the old behaviour without reverting.

## Residual Risk
- On this laptop (hyperd) no CPU trip point is readable from /sys (checked: `cpu_trip_points` returns []), so the derived ceiling stays at the 80 C fallback and behaviour is unchanged here.
- Trip points are read once per evaluation from sysfs; a CPU exposing none keeps the 80 C fallback. BUSY_ENTER/BUSY_LEAVE remain relative to ncpu and are not yet env-overridable (audit lists them as optional).
- Not run on a fanless or server host; the derivation is exercised against fake sysfs trees only.

## Hint Feedback
- aq-hints not consulted; scope came from the audit file. No hint feedback.
