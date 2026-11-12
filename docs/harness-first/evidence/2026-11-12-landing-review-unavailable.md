# A reviewer that could not run no longer blocks a landing; a test stops leaking worktrees

Date: 2026-11-12

## Objective

Two delivery-tooling defects found today. (1) On PR #755 a Gemini review whose sandbox timed out on every command replied
"unable to proceed ... check the status of the environment" with `Review-Disposition: REQUEST_CHANGES` and no finding;
aq-land treated that as a real rejection and stopped. (2) A test registered git worktrees and `delegate/codex-*` branches in
the real repository (24 leaked entries under /tmp).

## Workflow/Session IDs

- Branch `fix/landing-review-unavailable`, worktree `.agents/delegation/worktrees/landing-reliability`, base main 76533d451.
- Claimed via `aq-claim` (lane claude). Failing review: `.agents/delegation/outputs/aq-land/fix_q4-default-ratified/review-gemini-72747e59081d-gemini-3.8-flash-high.out`.

## Delegation Decision

Sonnet 5.5 implementer (Rule 17 default); brief `.agents/delegation/outputs/wave-f/landing-reliability.md`. Orchestrator
reviewed the classification rule (never a PASS; any concrete finding still stops). Independent review via aq-land.

## Commands Executed

- `python3 scripts/testing/test-aq-land.py`
- `bash scripts/testing/test-delegate-codex-quota-precheck.sh`, with `git worktree list --porcelain` of the real repo before and after

## Validation Evidence

- test-aq-land: 52 tests OK, including: could-not-run REQUEST_CHANGES falls through to the next lane; REQUEST_CHANGES with a
  `file:line` finding that also mentions a timeout still stops and the next lane is never called; could-not-run on the only
  lane stops with "no eligible independent lane left".
- test-delegate-codex-quota-precheck: before the fix 15 passed but the run added worktrees and 12 `delegate/codex-*`
  branches to the real repo; after, 16 passed including `(h) real repo worktree list unchanged` (231 before and after).

## Rollback Plan

Revert the PR. Leaked-entry cleanup is separate and recorded in PULSE.

## Residual Risk

- Could-not-run detection is phrase-based; an unusual wording is still treated as a rejection (fails toward blocking, never
  toward accepting).
- Other tests that call `delegate-to-codex` were read, not run, for leaks.

## Hint Feedback

The review output file named the cause directly; reading it before retrying avoided treating an outage as a defect.
