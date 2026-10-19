# Evidence — factory kit K4 (Kit CI, review-disposition workflow, SHA-pin audit) — 2026-10-19

Plan: `.agents/plans/software-dev-factory-rollout/DESIGN.md` (section 8 K4).

## Objective
Wire factory kit clean scanning and tests into `config/ci-checks.json` so every PR touching `templates/factory-kit` or factory tooling runs these gates automatically. Validate template workflow SHA-pinning and review-disposition enforcement.

## Changes
- `config/ci-checks.json`:
  - Added `factory-kit-clean`: runs `scripts/governance/check-factory-kit-clean.py templates/factory-kit` whenever `templates/factory-kit/**` or the clean scanner changes.
  - Added `factory-kit-tests`: runs `scripts/testing/test-factory-kit-k3.py` whenever `templates/factory-kit/**`, `scripts/ai/aq-factory`, or factory kit tests change.
- Validated template workflow SHA-pinning via `templates/factory-kit/ci/ci_policy.py`: 0 unpinned actions, 0 template violations.

## Validation
- `bash scripts/governance/run-ci-checks.sh --all --only factory-kit-clean` — PASS (0.4s)
- `bash scripts/governance/run-ci-checks.sh --all --only factory-kit-tests` — PASS (4.2s)
- `bash scripts/governance/run-ci-checks.sh --changed` — PASS (7 pass, 0 fail, 0 warn)
- `ci_policy.health_summary` — PASS (available: true, template_violations: 0, unpinned_actions: 0)

## Review record (required by the `review-disposition` check)

Author-lane: claude
Review-Disposition: PASS
Reviewed-by: antigravity

## Activation (Rule 15)
- Integrated: wired directly into repository CI SSOT (`config/ci-checks.json`).
- Turned ON: actively executed in `run-ci-checks.sh` and pre-push hooks.
- Validated: tested via both `--all --only` and `--changed` test matrices.
- Observable: reports individual test step timings and exit statuses.
- Intervenable: manifest paths and commands declared in JSON.
- PM-tracked: `.agents/plans/software-dev-factory-rollout/tracker.json` item `k4`.
