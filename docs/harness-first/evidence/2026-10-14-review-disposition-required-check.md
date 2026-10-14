# Evidence: Review-Disposition Required PR Check (W5-S1)

## Context
Date: 2026-10-14
Slice: `feat/review-disposition-required-check`
Component: `scripts/governance/check-review-disposition.py`, `.github/workflows/review-disposition.yml`, `.github/pull_request_template.md`, canon delivery-workflow block + agent instruction files
Author lane: claude; independent reviewer: claude-sonnet (independent reviewer)

## Problem
Root cause: review-disposition and reviewer independence were convention only; nothing machine-enforced them on PRs.

## Solution
A PR check validates Author-lane / Review-Disposition / Reviewed-subject-sha256 / Reviewed-head-sha / Reviewed-by fields; PR template and canon (all agent files, Rule 16) updated.

## Validation Evidence
- `python3 scripts/testing/test-review-disposition-check.py`: `Ran 6 tests ... OK`.
- Canon `--check` reported no drift (reviewer run).
- tier0 `--pre-commit`: see commit/PR.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| claude | claude-sonnet (independent reviewer) | PASS_WITH_FOLLOWUPS |

Review notes: Same-lane review where Author-lane is claude; queued for cross-lane confirmatory review.

## Follow-ups
- Strip fenced code / HTML comments before field matching (low).

## Rule 15 Activation Attestation
- Integrated: YES - workflow runs on pull_request; canon synced to all agent files.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: GitHub required-check status on every PR.
- Intervenable: DEFERRED (dated 2026-10-14): making it a required branch-protection check is an owner action.
- PM-tracked: W5-S1 in `.agents/plans/sota-rounding` (plan lands via a separate docs PR); status projected, not hand-set.
