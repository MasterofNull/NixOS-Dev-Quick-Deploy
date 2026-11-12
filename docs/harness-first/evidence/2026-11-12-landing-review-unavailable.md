# A reviewer reply that says it could not run now gets a re-run hint; a test stops leaking worktrees

Date: 2026-11-12

## Objective

Two delivery-tooling defects found today. (1) On PR #755 a Gemini review whose sandbox timed out on every command replied
"unable to proceed ... check the status of the environment" with `Review-Disposition: REQUEST_CHANGES` and no finding;
aq-land stopped with the generic "fix the findings" message, which hid that nothing was reviewed. Design (after two Codex P1
reviews showed text heuristics cannot safely bypass a rejection): a REQUEST_CHANGES/FAIL ALWAYS stops aq-land and never falls
through to another lane. A conservative detector (`reviewer_could_not_run`) only improves the STOP text: it names the
suspicion, prints the exact `--lanes` list of the remaining eligible lanes to re-run with (or says none is left), and records
`review_suspect` in the checkpoint. It never creates a receipt or PASS. The "no verdict" fall-through is unchanged.
(2) `delegate-to-codex` armed a 1-hour quota cooldown from fixture text quoted in the diff a review was reading; now only the CLI's own column-0 `ERROR:` line containing "hit your usage limit" counts (same rule as aq-payload-audit), and the reset is read from that line only.
(3) A test registered git worktrees and `delegate/codex-*` branches in the real repository (24 leaked entries under /tmp).

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

- test-aq-land: 53 tests OK. New: the real Gemini outage reply stops with "re-run with --lanes codex,local" and never calls
  codex or local, no PR is created and the checkpoint records `review_suspect`; the same reply on the only lane stops with
  "no other eligible lane is left"; Codex's mixed example ("lock is released twice ... unable to proceed ... timed out"), a
  `file:line` finding, a prose finding and a bulleted finding all stop with the plain "fix the findings" text and no hint.
  Existing no-verdict, quota and timeout fall-through tests pass unchanged.
- test-delegate-codex-quota-precheck (quota line): a column-0 ERROR line arms the cooldown with its reset; the same text indented, "+"/"-" prefixed, line-number prefixed, or inside an echo in a diff arms nothing. 22 passed.
- test-delegate-codex-quota-precheck: before the fix 15 passed but the run added worktrees and 12 `delegate/codex-*`
  branches to the real repo; after, 16 passed including `(h) real repo worktree list unchanged` (231 before and after).

## Rollback Plan

Revert the PR. Leaked-entry cleanup is separate and recorded in PULSE.

## Residual Risk

- A genuine outage reply still costs one manual re-run with `--lanes <others>`; this is deliberate, since an automatic bypass
  of REQUEST_CHANGES could let a later lane's PASS land a real finding. The hint detector is phrase-based and only affects
  message text; a misjudgement in either direction cannot change the verdict.
- Other tests that call `delegate-to-codex` were read, not run, for leaks.

## Hint Feedback

The review output file named the cause directly; reading it before retrying avoided treating an outage as a defect.
