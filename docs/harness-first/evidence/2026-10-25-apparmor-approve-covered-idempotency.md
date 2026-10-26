# Evidence: AppArmor Fix Agent Commit-Staged Idempotency

## Objective
Fix `_git_commit` in `scripts/automation/apparmor-fix-agent.py` to check `git diff --cached --quiet` before committing, returning the current HEAD commit hash cleanly when all proposed rules are already covered in `mcp-servers.nix`, rather than causing `git commit` to exit 1 on empty commit and marking `aq-approve` as failed.

## Workflow/Session IDs
- Session ID: `57a807e7-c3e6-4e8e-833b-ce38fb8d47cd`
- PRD: `PRD-HEALTH-SPIDER-AUTONOMOUS-HEALING.md`
- Branch: `fix/apparmor-approve-already-covered`

## Delegation Decision
- Implementer: Antigravity orchestrator in isolated git branch.
- Reviewer: Codex independent parity check.

## Commands Executed
- `python3 scripts/testing/test-apparmor-fix-agent-generalization.py`
- `bash scripts/governance/tier0-validation-gate.sh --pre-commit`

## Validation Evidence
- Unit test passed: `test_git_commit_no_staged_changes_returns_head` (6/6 tests passing).
- Verified idempotency when approving an alert whose rules have already landed in the codebase.
- Tier 0 pre-commit gate passed (71/71 checks pass).

## Rollback Plan
- Revert commit on `fix/apparmor-approve-already-covered` or checkout prior commit `de482aa8`.

## Residual Risk
- None; `git diff --cached --quiet` is a standard fast plumbing check that avoids empty commit failures.

## Hint Feedback
- `git diff --cached --quiet` cleanly distinguishes between an empty stage and real code changes.
