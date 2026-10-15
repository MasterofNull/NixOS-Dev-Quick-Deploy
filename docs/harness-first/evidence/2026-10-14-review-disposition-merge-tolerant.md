# Evidence: Review-Disposition Merge-Tolerant Head Binding

## Objective
Stop the review-disposition check failing with `stale review` when GitHub "Update branch" merges main into a PR branch and the net change is unchanged. Root cause: head binding compared raw SHAs, so a merge-only update invalidated review. Fix: accept when the reviewed head is an ancestor of the PR head and the verbatim patch-id (whitespace-exact) of the net change vs base is identical and non-empty; fail closed otherwise.

## Workflow/Session IDs
Orchestrator session eb012479-4564-462f-8e6f-4824d5a77754. Author lane: claude (claude-sonnet implementer). Branch `fix/review-disposition-merge-tolerant`.

## Delegation Decision
Bounded single-slice fix delegated to the Sonnet implementer (Rule 17) by the orchestrator; no commit by the implementer, changes left staged for independent review.

## Commands Executed
- `python3 -m py_compile scripts/governance/check-review-disposition.py`
- `python3 scripts/testing/test-review-disposition-check.py`
- `python3 scripts/governance/canon-compile.py --write` then `--check`

## Validation Evidence
- Test run: `Ran 11 tests ... OK` (6 existing + 5 new temp-git-repo fixtures: merge-only update passes; extra commit fails with "net change differs"; whitespace-only indentation change fails; amended/non-ancestor fails; missing reviewed commit fails).
- Pass path printed: `review rebound: head ... is a merge-only update of reviewed ... (net change identical, verbatim patch-id ...)`.
- Canon: `OK: no canon drift` after `--write` (delivery-workflow block, `.agent/WORKFLOW-CANON.md`).
- Workflow checkout now uses `fetch-depth: 0` so ancestry and merge-base are computable; `pr.base.sha` from the event is the base.
- Real-world end-to-end on a live PR "Update branch": DEFERRED (2026-10-14) until merged.

## Rollback Plan
Revert the commit; the check returns to strict SHA equality.

## Residual Risk
Identity remains declarative. A merge that resolves conflicts changes the net diff and is correctly rejected (re-review needed). Patch-id equality is relative to the PR base sha at event time; a base moving without head change is not re-evaluated until the next event.

## Hint Feedback
No harness hints were consulted for this slice; none helpful or harmful.
