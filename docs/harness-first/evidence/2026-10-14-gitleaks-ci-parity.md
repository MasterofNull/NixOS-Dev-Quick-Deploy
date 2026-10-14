# Evidence: Local Gitleaks CI Parity

## Context
Date: 2026-10-14
Slice: `fix/local-gitleaks-ci-parity`
Component: `.githooks/pre-commit`, `scripts/governance/tier0.d/check-gitleaks-ci-parity.sh`, `scripts/testing/test-gitleaks-ci-parity.py`
Author lane: claude; independent reviewer: claude-sonnet (independent reviewer)

## Problem
Root cause: PR #506 failed CI Secret Detection while local gates passed: local pre-commit used a regex subset and tier0 did not run gitleaks, so local and CI scans diverged.

## Solution
Local pre-commit and a new tier0.d check run the same gitleaks scan (config `.gitleaks.toml`) that CI runs.

## Validation Evidence
- `python3 scripts/testing/test-gitleaks-ci-parity.py`: `PASS`.
- New tier0 check takes ~11s (over the 5s tier0.d budget; accepted for CI parity).
- tier0 `--pre-commit`: see commit/PR.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| claude | claude-sonnet (independent reviewer) | PASS_WITH_FOLLOWUPS |

## Follow-ups
- Crash vs finding message distinction in the check (low).

## Rule 15 Activation Attestation
- Integrated: YES - pre-commit hook and tier0.d run on every commit.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; full real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: DEFERRED (dated 2026-10-14): no new dashboard/alert in this slice; existing logs/health unchanged.
- Intervenable: DEFERRED (dated 2026-10-14): no new operator control in this slice; existing controls unchanged.
- PM-tracked: no tracked plan item; no status hand-set.
