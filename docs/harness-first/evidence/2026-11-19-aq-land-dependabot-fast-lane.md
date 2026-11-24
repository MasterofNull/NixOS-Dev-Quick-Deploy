# aq-land dependency-bump fast review lane (2026-11-19)

## Objective
Give Dependabot manifest-only PRs a purpose-built review path in `scripts/ai/aq-land`: review criteria that require reading upstream release notes for the whole version range, and a default lane order of gemini,codex (local cannot read release notes). Receipt, review record, CI wait, merge and freshness are unchanged; review-disposition still requires a real independent review.

## Workflow/Session IDs
Slice branch `feat/aq-land-dep-fast-lane`, built on PR #838 head b67362577. Owner-approved frozen design; no workflow run id (bounded implementer slice).

## Delegation Decision
Bounded single-file change plus criteria file and tests, implemented by a Sonnet implementer sub-agent (Rule 17). Independent review is required at landing; the author does not review itself.

## Commands Executed
- `python3 scripts/testing/test-aq-land.py`
- `python3 scripts/testing/test-aq-land-outcome.py`
- `python3 scripts/testing/test-aq-land-pre-review-gate.py`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`
- `GITHUB_EVENT_NAME=pull_request GITHUB_BASE_REF=main ./scripts/governance/ci-clean-env.sh --all --only harness-first-static-gates`

## Validation Evidence
Eligibility is decided in review() from the same pinned origin/main...head range as the reviewer diff, on every round (checkpoint `fast_lane` reflects the reviewed head); a malformed policy (non-list or empty globs, bare `*`/`**`) logs `fast-lane: policy invalid, normal review path`. Trigger: `--author-lane dependabot` (case-insensitive) and every file in the net diff vs origin/main matches `dependabot_manifest_exemption.manifest_globs` (same fnmatchcase semantics as the evidence gate). New tests in `DepFastLane`: applies (criteria used, gemini first, local unused, log line, checkpoint `fast_lane`); not with a non-manifest file; not for a non-dependabot author; explicit `--lanes` controls reviewer order, and `--criteria-file` adds criteria alongside the dependency baseline. Full command output is in the slice report.

## Review evidence recovery (2026-11-24)

The fast lane derives the package and version range from the manifest diff. For a supported single-package update, a PASS must include that package and full version range, links to the upstream release notes, the authoritative input and its path, and the closure comparison command followed by a semicolon and an explicit result. A changed closure requires the deployed runtime validation and its successful result. The independent reviewer checks those claims against the actual deployment and upstream changes.

Missing or malformed evidence makes the lane unavailable and sends the review to the next eligible lane. A substantive rejection still blocks. Multiple-package changes and unsupported manifest changes use the regular review path. Keep remediation that changes Nix deployment inputs on a maintainer branch so Dependabot can continue to manage its manifest branch.

Hosted review and deployment acceptance are pending.

## Rollback Plan
Revert this commit. The fast lane is inert unless `--author-lane dependabot` is passed, so non-Dependabot landings are unaffected in the meantime.

## Residual Risk
Review quality depends on the reviewer lane having web access to release notes; `aq-land` checks the required evidence fields, and the reviewer verifies their accuracy. If the policy file cannot be read the fast lane does not apply (normal path) and aq-land logs `fast-lane: policy unreadable, normal review path`.

## Hint Feedback
No aq-hints were consulted for this slice; nothing to report.
