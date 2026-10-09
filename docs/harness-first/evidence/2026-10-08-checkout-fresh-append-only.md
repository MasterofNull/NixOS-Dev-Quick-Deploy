# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-200

## Objective
- The nrs preflight fast-forward was refused when a merged PR and the live RSI sweep had both appended to .agent/memory/issues-backlog.md (the sweep appends incidents to that tracked file every 15 min). The guard now re-applies local changes automatically, but only when every overlapping file is (a) allowlisted (issues-backlog.md, PULSE.log; rsi-incidents.json is deliberately excluded because it is rewritten, not appended) and (b) a byte-exact pure append over HEAD, with nothing staged and the mode unchanged. Otherwise it blocks as before. On any failure the tree is restored byte-for-byte.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer, stepped up from Haiku: correctness-critical git logic, and a Haiku worktree escape earlier the same night. The orchestrator verified the tests and the diff scope.

## Commands Executed
```bash
bash scripts/testing/test-check-checkout-fresh.sh   # 10/10 pass (6 existing + 4 new)
bash -n scripts/governance/check-checkout-fresh.sh
```

## Validation Evidence
- T7: pure append plus incoming append → ff, file = incoming + local suffix. T8: non-append edit → exit 3, untouched. T9: mixed allowlisted and non-allowlisted overlap → exit 3, untouched. T10: second ff fails (untracked collision) → exit 3, byte-identical rollback, no leftover save dir.

## Rollback Plan
- Revert the commit, or set AUTO_FAST_FORWARD=0.

## Residual Risk
- A sweep append landing in the milliseconds between the pre-checkout comparison and git checkout would be lost. The sweep runs every 15 min.

## Hint Feedback
- None.
