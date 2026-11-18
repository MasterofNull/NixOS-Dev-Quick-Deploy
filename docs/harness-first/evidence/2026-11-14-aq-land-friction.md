# aq-land delivery friction: four fixes

Date: 2026-11-14
Task ID: HF-20261114-AQLAND

## Objective
- Fix four aq-land frictions logged 2026-11-14 (issues-backlog, AQ-LAND): resume crash without `--body-file`, relative paths broken by `os.chdir`, receipt published after the body edit that triggers review-disposition, and two CI-only gates failing after the review was spent.
- Delivered: `scripts/ai/aq-land` and `scripts/testing/test-aq-land.py` only.

## Workflow/Session IDs
- Workflow ID: none (bounded slice from the orchestrator)
- Session ID: Simurg@claude/sonnet; orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
- Delegated to a Sonnet 5.5 implementer (Rule 17). Review is by a separate lane; the implementer does not self-review, open the PR or merge.

## Commands Executed
```bash
python3 scripts/testing/test-aq-land.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Root causes: (1) `body()` read `Path(args.body_file)`; an empty value is `Path('')` = `.`, so resume raised IsADirectoryError. (2) `Land.__init__` chdir'd to the worktree before the file args were resolved. (3) `locked()` ran `stage_pr` (which edits the body and triggers review-disposition) before `stage_receipt`; the receipt needs the PR number, so only the edit moved: `stage_pr(edit=False)` creates/finds the PR, the receipt is published, then `stage_pr` edits the body. (4) the PR body format and harness-first static gates ran only in CI.
- Fixes: resume falls back to `<state dir>/body.md`; file args are resolved to absolute before chdir; the edit follows the receipt; `preflight` imports `problems()` from `scripts/governance/check-pr-body-format.py` and runs `check-harness-first-static-gates.sh` (override `AQ_LAND_STATIC_GATES`; skipped with a message if the script is absent from the worktree).
- Tests (class `Friction` in test-aq-land.py, temp `AQ_DELEGATION_DIR`): resume without body file; no body and no saved body stops before review; relative paths; receipt before `pr edit`; bad body format and failing static gates stop in preflight with no review or push. Output is pasted in the hand-off report.

## Rollback Plan
- `git revert <sha>`. Trigger: aq-land failing to land a PR, or preflight blocking a valid body.

## Residual Risk
- A brand-new PR is still created with its body before the receipt exists, so its first review-disposition run can fail; the existing rerun logic in `wait_and_merge` covers it.
- Preflight now needs a body (`--body-file` or a saved body) even when a PR is already merged and state was wiped.
- The static-gates preflight sees only files staged or committed against origin/main, as the CI script does.

## Hint Feedback
- No aq-hints used; the code paths were read directly.
