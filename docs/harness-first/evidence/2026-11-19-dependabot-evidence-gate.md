# Dependabot manifest-only evidence-gate exemption

## Objective
Dependabot PRs #808-#824 touch high-impact paths (e.g. requirements.txt) and can never add a docs/harness-first/evidence file, so "Syntax Validation" always failed. Add a tightly scoped exemption in `scripts/testing/check-harness-first-pr-evidence-gate.sh`: pass only when `PR_AUTHOR` is exactly `dependabot[bot]` and every changed file matches `dependabot_manifest_exemption.manifest_globs` in `config/harness-first-policy.json`. `PR_AUTHOR` is set in `.github/workflows/test.yml` from `github.event.pull_request.user.login`.

## Workflow/Session IDs
Session da0ef470 (Simurg@claude/sonnet-5.5), branch fix/dependabot-evidence-gate.

## Delegation Decision
Bounded single-slice CI gate fix; implemented directly by the delegated sub-agent, independent review to follow via aq-land.

## Commands Executed
- `python3 scripts/testing/test-check-harness-first-pr-evidence-gate.py`
- `bash scripts/testing/check-harness-first-static-gates.sh`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Validation Evidence
Regression tests: dependabot + manifest-only passes; dependabot + non-manifest file fails; human + manifest-only fails; lookalike author fails. Results are recorded in the PR body.

## Rollback Plan
Revert the commit; the gate returns to requiring an evidence file for every high-impact change.

## Residual Risk
Exemption trusts the workflow-supplied author login. A manifest bump from Dependabot is judged by the independent review-disposition check and CI, not by this gate. Manifest globs in the policy file are reviewable in any PR that edits them (a non-Dependabot PR gets no exemption).

## Hint Feedback
No aq-hints used for this slice; none to report.
