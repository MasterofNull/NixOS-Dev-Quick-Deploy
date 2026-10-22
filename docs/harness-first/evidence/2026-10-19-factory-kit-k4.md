# Evidence — factory kit K4 (Kit CI, review-disposition workflow, SHA-pin audit) — 2026-10-19

Plan: `.agents/plans/software-dev-factory-rollout/DESIGN.md` (section 8 K4).

## Objective
Declare factory kit clean scanning and tests in `config/ci-checks.json`, then invoke both manifest entries from the existing `syntax` job in `.github/workflows/test.yml`, so pull-request CI runs them. Validate template workflow SHA-pinning and review-disposition enforcement.

## Changes
- `config/ci-checks.json`:
  - Added `factory-kit-clean`: runs `scripts/governance/check-factory-kit-clean.py templates/factory-kit` whenever `templates/factory-kit/**` or the clean scanner changes.
  - Added `factory-kit-tests`: runs `scripts/testing/test-factory-kit-k3.py` whenever `templates/factory-kit/**`, `scripts/ai/aq-factory`, or factory kit tests change.
- `.github/workflows/test.yml`: installs gitleaks 8.24.3 and calls `run-ci-checks.sh --all --only` for each factory kit check in the `syntax` job. These explicit invocations make the checks part of pull-request CI; manifest path filters remain available to changed-file runner calls.
- Validated template workflow SHA-pinning via `templates/factory-kit/ci/ci_policy.py`: 0 unpinned actions, 0 template violations.

## Validation
- `bash scripts/governance/run-ci-checks.sh --all --only factory-kit-clean` — PASS (0.4s)
- `bash scripts/governance/run-ci-checks.sh --all --only factory-kit-tests` — PASS (4.2s)
- `bash scripts/governance/run-ci-checks.sh --changed` — PASS (7 pass, 0 fail, 0 warn)
- `ci_policy.health_summary` — PASS (available: true, template_violations: 0, unpinned_actions: 0)
- `CI=true bash scripts/governance/run-ci-checks.sh --all --only factory-kit-clean` — PASS (1 pass, 0 fail, 0 warn; 0.2s).
- `CI=true bash scripts/governance/run-ci-checks.sh --all --only factory-kit-tests` — PASS (1 pass, 0 fail, 0 warn; 1.4s).
- `scripts/governance/run-ci-checks.sh --list --all --only factory-kit-clean --only factory-kit-tests` — PASS; both IDs resolve from the manifest.
- `bash -n scripts/governance/run-ci-checks.sh`, `python3 -m json.tool config/ci-checks.json`, and focused workflow wiring assertions — PASS. `actionlint` was unavailable, so the workflow did not receive an actionlint parse check.

## Historical review record

The following disposition applies only to committed subject `5b0cc25649ec5283afaf53ccf9c52facd015293f`. The CI-wiring follow-up requires fresh independent review before it is recorded as accepted.

Author-lane: claude
Review-Disposition: PASS (committed subject only)
Reviewed-by: antigravity

## Activation (Rule 15)
- Integrated: both manifest check IDs are explicitly invoked by the repository `syntax` CI job.
- Turned ON (configured; hosted CI result pending): the `syntax` job will install pinned gitleaks and invoke both checks on the next GitHub pull-request run; local pre-push also uses the manifest.
- Validated: tested via both `--all --only` and `--changed` test matrices.
- Observable: reports individual test step timings and exit statuses.
- Intervenable: manifest paths and commands declared in JSON.
- PM-tracked: `.agents/plans/software-dev-factory-rollout/tracker.json` item `k4`.
