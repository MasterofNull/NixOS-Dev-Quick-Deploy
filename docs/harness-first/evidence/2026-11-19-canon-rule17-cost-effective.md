# Canon Rule 17: most cost-effective correct lane

## Objective
Owner directive 2026-11-19: routing selects "the most cost effective, efficient, and correct models for the given task and prompt", not the cheapest. Reword Rule 17 and its SSOT so correctness comes first for gates (a lane must be able to perform the gate), then most cost-effective among correct lanes; a cheap result that must be redone is not cost-effective. Rule number, no-self-implement, explicit model override, Claude default `sonnet` / haiku-only-mechanical are kept. This is canon (compiled-source) wording, shipped as its own change; no code behavior changes.

## Workflow/Session IDs
Worktree agent-aa0faeef7072c5ef8, branch docs/canon-rule17-cost-effective. Simurg@claude/sonnet-5.5 implementer slice.

## Delegation Decision
Bounded canon-wording slice, dispatched by the orchestrator to a Sonnet implementer with explicit model override (Rule 17).

## Commands Executed
- rg -n -i cheapest canon docs/architecture .agent/*.md
- edited canon/blocks/behavioral-rules.md, canon/blocks/mvp-delivery-sop.{md,summary.md}, docs/architecture/role-matrix.md, .agent/WORKFLOW-CANON.md, .agent/GEMINI.md (hand-written section)
- python3 scripts/governance/canon-compile.py --write; --check
- rg -l -i cheapest scripts/testing (hits assert only runtime route-reason strings, not rule text)
- scripts/governance/tier0-validation-gate.sh --pre-commit; harness-first-static-gates

## Validation Evidence
canon-compile --check: OK no canon drift. LOCAL-AGENT.md stays at 200 lines. Gate outputs recorded in the commit/PR report.

## Rollback Plan
Revert the commit; re-run canon-compile.py --write.

## Residual Risk
Historical PRDs under .agent/PROJECT-*-PRD.md still say "cheapest"; they are dated design records, left untouched. Runtime route-reason strings ("cheapest healthy lane") in code are unchanged.

## Hint Feedback
None.
