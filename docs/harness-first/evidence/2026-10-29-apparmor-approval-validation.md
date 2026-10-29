# AppArmor approval validates rules first; fix agent rejects whole batch — 2026-10-29

## Objective

Close two defects that the Codex confirmatory review `codex-20261029-111100-t8ezt0` (REQUEST_CHANGES on merged `35ea3f65`, #638) found: owner approval could archive an invalid AppArmor rule as approved, and the fix agent staged the valid part of a batch that contained rejected rules.

## Workflow/Session IDs

- Claude session 50391bdd (system-integrity-recovery P1.1 follow-up).
- Finding: `codex-20261029-111100-t8ezt0`. Implementation: Claude Sonnet (Codex's rolling budget was exhausted, Rule 18 substitution).

## Delegation Decision

Codex found the defects; its fix dispatch first ran on a stale base (backlog DELEGATE-BASE-STALE), then the rolling budget ran out, so Claude Sonnet implemented. Claude orchestrator reviewed the diff and reran the suites. Local Qwen reviews the branch; Codex re-reviews when its budget frees.

## Commands Executed

```
python3 scripts/testing/test-apparmor-fix-agent-safety.py
python3 scripts/testing/test-apparmor-fix-agent-generalization.py
```
Red check: the four new tests were run against the merged `aq-approve` and `apparmor-fix-agent.py` (from `git show HEAD:`) and failed there.

## Validation Evidence

- Safety suite: 10 tests OK (4 new). Generalization suite: 6 tests OK.
- New tests and their failure on the merged code:
  - invalid rule only inside a comment is not approved (merged: approved, exit 0);
  - valid rule only in a comment or another profile is not "present" (merged: treated as present);
  - mixed valid/hostile batch writes nothing and exits non-zero (merged: exit 0, valid subset staged);
  - all-rejected batch does not report "all paths already covered" (merged: exit 2 with that message).

## Rollback Plan

Revert the commit. The previous behavior returns: approval-time validation is skipped when the rule text appears in the file, and batches are filtered rather than rejected.

## Residual Risk

- The profile-block parser is line-based (`security.apparmor.policies."<profile>"`, then `profile = ''` to `'';`). A profile written in another Nix shape reads as "not present", which fails safe: the executor runs and validates.
- The fix is live only once the owner's checkout is updated; it currently runs pre-#638 code (backlog DEPLOY-DRIFT-SSOT).

## Hint Feedback

The confirmatory-review queue caught a security defect in merged code that the original local review passed. Codex confirmatory reviews of security PRs should stay in the queue even when the PR already merged.
