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

## Hardening (Codex review codex-20261028-123423-qympvo, REQUEST_CHANGES)
- P1 evidence-type bypass: the hold no longer exempts `systemd_unit`/`command` items.
- P1 detection-edit bypass: config `items` freezes the held set (`plan/item`); `--check-untrusted-items` (tier0) is remove-only, removal needs a bound-receipt clearance.
- P1 unrelated receipts: a receipt clears only if its PR is a trusted PR whose commit matches the item, or `clears["plan/item"]` names it.
- Fail-open projection: missing/malformed config marks output degraded (`hold_degraded`, `rollup_authoritative: false`) and commit-derived completions read UNKNOWN.
- Dates parsed as ISO-8601 (malformed never clears); receipt registry resolved via `scripts/ai/lib/delegation_dir.py`.
- Held items, `--all-json` (source_health complete), before -> after hardening: aqos-requirements-inventory 2 -> 2, capability-integration 1 -> 1, ecc-parity-integration 1 -> 1, all other plans 0 -> 0 (total 4 -> 4; frozen into `items`). No systemd/command item currently has untrusted matching evidence.

## Hardening round 2 (Codex re-review codex-20261028-130418-l36g73)
- Receipt binding now required on every clearing path (incl. `clears` and frozen-entry removal): trusted `(#N)` commit matching the frozen patterns and touching the plan tracker / freeze record.
- Direct (no `(#N)`) commits no longer count as trusted. `items` is now an object of original patterns covering all 41 items with any untrusted matching commit in history.
- Remove-only check compares against the union of merge-base and base-ref-tip configs.
- Held counts (`--all-json`): 4 -> 5 (aqos-requirements-inventory 2 -> 3, capability-integration 1, ecc-parity-integration 1; others 0). Most of the 41 frozen items are currently IN-PROGRESS, so the hold is dormant for them until they project SHIPPED.

## Limitations
- Only items that project SHIPPED/ACTIVATED are held; items already below that (IN-PROGRESS) are untouched.
- `assets/aqos-progress-tracker.html` now lists UNVERIFIED (own kanban column, dashed red border).
- Activation (Rule 15): the hold is live in the projector as soon as merged.
