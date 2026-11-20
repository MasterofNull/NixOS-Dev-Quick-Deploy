# Canon dependency-hygiene summary: restore "Trigger" wording

## Objective

Restore the capitalized "Trigger" label in `canon/blocks/dependency-hygiene.summary.md` so that
`scripts/testing/test-dependency-hygiene-ladder.py::test_canon_blocks_exist` passes again. The
first bullet is kept to one line, and the second bullet is unchanged.

## Workflow/Session IDs

- Branch: `fix/canon-dependency-trigger-wording` (from `origin/main`)
- Worktree: `.claude/worktrees/agent-aefbceebe7cc918b6`
- Delegation: implementer sub-agent (Haiku 5.5)

## Delegation Decision

Bounded mechanical single-file wording fix with a checkable result (test pass). Dispatched to the
cheapest eligible lane (Rule 17) with the Haiku model override.

## Commands Executed

```
git fetch origin main
git checkout -b fix/canon-dependency-trigger-wording origin/main
python3 <edit of canon/blocks/dependency-hygiene.summary.md line 3>
python3 scripts/governance/canon-compile.py --write
python3 scripts/testing/test-dependency-hygiene-ladder.py
python3 scripts/governance/canon-compile.py --check
```

## Validation Evidence

- `canon-compile.py --write`: updated AGENTS.md, CLAUDE.md (.claude/CLAUDE.md), .agent/CODEX.md,
  .agent/GEMINI.md, .agent/LOCAL-AGENT.md (block `dependency-hygiene`).
- `test-dependency-hygiene-ladder.py`: `Ran 4 tests ... OK`.
- `canon-compile.py --check`: `OK: no canon drift`.
- Summary line 3 now reads:
  `- **Security ladder** — **Trigger**: ONLY a failing security gate, scoped to the implicated package; no broad churn. **Ladder**: (1) Fixed release -> raise floor; ...`

## Rollback Plan

Revert the single commit (`git revert <sha>`) or reset the branch to `origin/main`. The change is
text-only in canon source plus its compiled propagation into five instruction files.

## Residual Risk

- The test gate `Manifest test groups` is not a required check, so the #841 regression merged red.
  This is a process gap and is tracked separately; this fix does not change the required-check set.
- Instruction-file line budgets depend on the summary bullet staying one line. The bullet is one line.

## Hint Feedback

Root cause: #841 merged the dependency-hygiene summary bullets and lowercased "Trigger" to
"trigger", which broke the test's case-sensitive assertion. The test was not a required check, so
the regression landed on `main`.
