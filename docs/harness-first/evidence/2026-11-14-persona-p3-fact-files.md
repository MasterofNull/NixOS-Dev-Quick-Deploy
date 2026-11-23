# Harness-First Task Evidence

Date: 2026-11-14
Task ID: HF-20261114-persona-p3

## Objective
- Requested: Persona P3, shared memory as git-tracked fact files (owner approved the build 2026-11-14 in the CLI; the section 4 conflict-rate measurement is its observability).
- Delivered: `.agent/memory/facts/` convention with one seed fact; `scripts/governance/tier0.d/check-fact-files.py` (format, privacy, 10-per-commit cap, cross-lane overwrite/delete/rename/split needs `owner_reply`, `--report` counters); `scripts/ai/lib/fact_subjects.py` wired into `aq-session-start` as `## Shared Facts`; frontmatter-script skip; canon `persona` block updated and compiled to all agent files; PRD 4.4/5 re-scoped; plan DESIGN.md section 9 records the resolved open questions.

## Workflow/Session IDs
- Workflow ID: none (bounded implementer slice under the orchestrator).
- Session ID: Simurg@claude/sonnet-5.5 implementer for orchestrator Simurg@claude/opus-5.5#da0ef470; reviewers of the design: gemini-20261113-200328-cgpr0z, local-20261113-200313-d2r29u.

## Delegation Decision
- Delegated by the orchestrator to a Sonnet implementer (Rule 17, cheapest eligible). The design author lane is claude, so the PR review must come from a non-claude lane (Rule 18). Gemini's drop-in reference was adapted: it only checked the staged diff, did not list subjects or fetch the baseline, had no report, no email or entropy privacy rule and accepted any single delete path.

## Commands Executed
```bash
git fetch origin && git worktree add -b feat/persona-p3-fact-files .agents/delegation/worktrees/persona-p3 origin/main
git checkout origin/design/persona-p3-fact-files -- .agents/plans/persona-p3-collapse-20261113
python3 scripts/testing/test-persona-fact-files.py
python3 scripts/governance/canon-compile.py --write && python3 scripts/governance/canon-compile.py --check
python3 scripts/governance/check-agent-instruction-parity.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
python3 scripts/governance/tier0.d/check-fact-files.py --report
```

## Validation Evidence
- Tests: 14 unit tests pass (format, persona-off label parity, cap, privacy, sequential and stale-branch overwrite printing both claims, same-lane update, delete, rename, split, branch-only delete, report counters, session-start listing newest-first capped at 20).
- Canon: `--check` OK, instruction parity OK within budget.
- Full gate outputs are pasted in the implementer report to the orchestrator.
- Not yet shown: real cross-lane recall (acceptance 1) and a live conflict with Codex (acceptance 2). They need a Codex lane to land a fact after this merges, so tracker item P3-A1 stays open.

## Rollback Plan
- `git revert` the squash commit. Off switch without revert: do not commit fact files; the check is a no-op when none change. No service, route or database was added.

## Residual Risk
- Nothing proves a human wrote `owner_reply`; control is the persona refusal list and the independent reviewer reading it.
- A lone delete cannot carry `owner_reply` in pre-commit (no commit message yet), so it must be a two-fact scoped split.
- The check fetches `origin/main` (8 s cap); offline it compares against the last fetched ref.
- Activation (Rule 15) is incomplete until a second lane lands a fact and the 50-fact or 30-day report review happens.

## Hint Feedback
- Hint IDs used: none (aq-hints not queried; the design branch and review logs were the full context).
- Feedback: none.
