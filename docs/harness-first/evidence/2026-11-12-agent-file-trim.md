# Always-on agent files trimmed ~12%; the 24,600-byte budget is a ceiling

Date: 2026-11-12

## Objective

The five always-on agent files sat at their byte budget (CODEX.md was 10 bytes under 24,000 before #760), so
every new canon block forced a raise. Owner decision 2026-11-12: keep 24,600 as the ceiling, make no further
raises, and trim the files. The owner-endorsed meta-prompt rule (calm, positive phrasing instead of shouted
emphasis) was applied while trimming.

## Workflow/Session IDs

- Branch `feat/agent-file-trim`, worktree `.agents/delegation/worktrees/agent-file-trim`.

## Delegation Decision

Sonnet 5.5 implementer (Rule 17 default); brief `.agents/delegation/outputs/wave-f/agent-file-trim.md`.
Orchestrator review of every rewritten rule row for unchanged meaning; independent review via aq-land.

## Commands Executed

- `python3 scripts/governance/canon-compile.py --write` / `--check`
- `python3 scripts/governance/check-agent-instruction-parity.py`
- `python3 scripts/testing/test-agent-instruction-parity.py`
- `python3 scripts/testing/test-capability-index.py`

## Validation Evidence

- Bytes before -> after: AGENTS.md 24198 -> 21263; CLAUDE.md 24387 -> 21452; CODEX.md 24426 -> 21491;
  GEMINI.md 24376 -> 21441; LOCAL-AGENT.md 24155 -> 21220.
- Rules 15, 17, 18, 19, 20, 21 and the Fable-parity enforcement line now carry a one-line contract plus an SSOT
  pointer. Detail missing from each SSOT was added there first ("contract detail (moved from the canon block,
  2026-11-12)" sections in DEFINITION-OF-DONE, role-matrix, agent-agnostic-factory DESIGN, ROOT-CAUSE PRD,
  pm-tracker-standard DESIGN, FABLE-PARITY-CONTRACT; Rule 21 stewardship text added to role-matrix, its only
  previous copy being out-of-repo auto-memory; `FABLE_PARITY=0` kill switch now documented in the contract).
- Rules 7, 8, 8a, 8b, 11, 12, 13, 14, 16, 23: calm phrasing only; meaning unchanged (orchestrator read each row).
- dependency-hygiene summary gained its missing heading.
- No-raise guard: `check-agent-instruction-parity.py` fails when `budget_bytes` > 24600 unless
  `agent_files.budget_owner_decision` is set; new test `test_budget_raise_needs_owner_decision`.
- canon --check OK; parity OK; test-agent-instruction-parity 7 OK; test-capability-index PASS.

## Rollback Plan

Revert the PR: canon blocks and the compiled agent files return together; SSOT additions are additive and can stay.

## Residual Risk

- Three details now live only in their SSOT (Rule 18 "never a history rewrite", Rule 20's projection inputs,
  Rule 19's ratification date). Agents follow the pointer for them.
- Lane regions were not reviewed for duplication (owners' text).

## Hint Feedback

The parity checker's byte report located the budget pressure; canon-compile made the trim a single-source edit.
