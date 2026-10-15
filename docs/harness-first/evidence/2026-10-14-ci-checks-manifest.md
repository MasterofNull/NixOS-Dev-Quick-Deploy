# Evidence: Shared CI-Checks Manifest and Coverage Gate (W6-S1)

## Context
Date: 2026-10-14
Slice: `feat/ci-checks-manifest`
Component: `config/ci-checks.json`, `scripts/governance/run-ci-checks.sh`, `scripts/governance/tier0.d/check-ci-manifest-coverage.sh`, `scripts/governance/check-world-writable.sh`, `.githooks/pre-push`, `.github/workflows/test.yml`, `.github/workflows/validate-shell-scripts.yml`
Author lane: claude; independent reviewer: claude-sonnet (independent reviewer) + orchestrator verification of follow-up delta

## Problem
Root cause: CI-only hard checks (e.g. the harness-first evidence gate that broke 3 PRs) had no local runner, so failures surfaced only after push. Parity audit: .agents/plans/sota-rounding/evidence.

## Solution
A single manifest lists the CI checks; CI and pre-push both run them via run-ci-checks.sh, and a tier0.d coverage gate fails when a CI-run script is absent from the manifest.

## Validation Evidence
- `python3 scripts/testing/test-ci-checks-manifest.py`: 8 tests `PASS`.
- `scripts/governance/run-ci-checks.sh --all`: `run-ci-checks: 14 pass, 0 fail, 0 warn`.
- `scripts/governance/tier0.d/check-ci-manifest-coverage.sh`: `PASS`.
- tier0 `--pre-commit`: see commit/PR.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| claude | claude-sonnet (independent reviewer) + orchestrator verification of follow-up delta | PASS_WITH_FOLLOWUPS |

## Follow-ups
- Coverage regex bypasses (cd scripts, variable paths, extensionless scripts) are WARN-only.
- advanced-parity and skill-bundle checks remain CI-only.

## Rule 15 Activation Attestation
- Integrated: YES - pre-push hook and CI workflows invoke the manifest runner.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; full real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: DEFERRED (dated 2026-10-14): no new dashboard/alert in this slice; existing logs/health unchanged.
- Intervenable: DEFERRED (dated 2026-10-14): no new operator control in this slice; existing controls unchanged.
- PM-tracked: commit subject carries `W6-S1` for the sota-rounding tracker; status projected.
