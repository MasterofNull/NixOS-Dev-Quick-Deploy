# Evidence: untrusted-author hold in aq-pm-tracker (P0.10)

Directive (owner, 2026-10-27): every tracker item shipped by the Gemini/Antigravity lane leaves SHIPPED until
independently re-verified.

## Change
- `config/pm-tracker-untrusted-provenance.json`: 84 untrusted PRs (74 with `Author-lane: antigravity` among
  PRs merged 2026-10-19..27, plus #580-#589 labeled claude/sonnet but produced by Gemini). Per-PR retro verdicts
  are not recorded: the batch reports are free-form and only batch A uses a parseable per-PR line.
- `scripts/ai/aq-pm-tracker`: new `UNVERIFIED` projected state (40%), `hold` field in JSON, `held:` lines in
  human output, `--check` fails closed on missing/malformed config.
- Test `scripts/testing/test-pm-tracker-untrusted-hold.py` (registered as `pm-tracker-untrusted-hold` in
  `config/ci-checks.json`).

## Before/after (`aq-pm-tracker --all-json`, source_health complete)
Rule: hold if ANY matching commit is an untrusted PR; clears only by a valid receipt or a trusted matching commit newer than the newest untrusted one.
Program rollup 98% -> 88%; 38 items SHIPPED -> UNVERIFIED.

| plan | shipped | held | rollup |
|---|---|---|---|
| agent-auth | 11 -> 3 | 8 | 100 -> 56 |
| aq-decide | 11 -> 1 | 10 | 100 -> 45 |
| aqos-foundation-c | 8 -> 6 | 2 | 90 -> 77 |
| aqos-requirements-inventory | 16 -> 13 | 3 | 100 -> 89 |
| capability-integration | 10 -> 9 | 1 | 100 -> 94 |
| durable-proactive-mesh | 6 -> 2 | 4 | 100 -> 60 |
| ecc-parity-integration | 8 -> 7 | 1 | 100 -> 92 |
| software-dev-factory-rollout | 11 -> 9 | 2 | 100 -> 89 |
| sota-intelligence-intake-mesh | 4 -> 3 | 1 | 82 -> 70 |
| sota-rounding | 31 -> 25 | 6 | 100 -> 88 |

## Validation
- `python3 scripts/testing/test-pm-tracker-untrusted-hold.py` -> `PASS: pm-tracker untrusted-author hold`
- `bash scripts/governance/tier0.d/check-ci-manifest-coverage.sh` -> PASS
- `bash scripts/governance/tier0.d/check-pm-tracker.sh` -> PASS: 27 plan tracker(s) valid

## Limitations
- Only items that project SHIPPED/ACTIVATED are held; items already below that (IN-PROGRESS) are untouched.
- `assets/aqos-progress-tracker.html` now lists UNVERIFIED (own kanban column, dashed red border).
- Activation (Rule 15): the hold is live in the projector as soon as merged.
