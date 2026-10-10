# Harness-First Task Evidence

Date: 2026-10-09
Task ID: HF-20261009-090

## Objective
- Owner parity rule: the retired ai-validate-and-commit was the only commit-message drafter, so that capability moves into the live `aq-commit-agent` instead of being lost. New `aq-commit-agent --draft-message` is deterministic (no LLM) and read-only. It prints a conventional `type(scope): <summary>` draft from the staged diff, with files grouped by directory (max 15, then +N), a Root cause placeholder and the Co-Authored-By trailer ($AQ_AGENT_NAME). It exits 2 when nothing is staged. The existing transaction path is unchanged.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- A Haiku attempt produced a standalone rewrite at the worktree root (not integrated; it changed import behaviour), which was moved out. The orchestrator implemented it in the real script plus lib/commit_draft.py.

## Commands Executed
```bash
python3 scripts/testing/test-aq-commit-agent-draft.py   # PASS (executes the real script in a temp repo)
python3 scripts/testing/test-integration-guard.py      # PASS (transaction path unchanged)
```

## Validation Evidence
- Type/scope inference, grouping, truncation, trailer, nothing-staged exit 2, and an unchanged index after drafting.

## Rollback Plan
- Revert the commit.

## Residual Risk
- Type inference is heuristic; the summary remains an explicit placeholder for the author.

## Hint Feedback
- None.
