# Health spider: remove the dead owner_acceptance_allowlist_unauthorized handler

## Objective

Remove an unreachable branch from `HealthSpider.handle_anomaly` in `scripts/ai/aq-health-spider`. Since the Nix-store anchor (4ac4f7caf, PR #680), `_owner_acceptance_check` no longer emits `owner_acceptance_allowlist_unauthorized`, so its attention-queue push could never run (Rule 23). Follow-up from Gemini review `gemini-20261104-013216-gagxjb` (LOW); backlog VA-DEAD-ALLOWLIST-UNAUTHORIZED-HANDLER.

## Workflow/Session IDs

- Branch `fix/va-dead-unauthorized-handler`, worktree `.agents/delegation/worktrees/va-dead-handler`, from origin/main f77faf19d.
- Implementer: Claude Haiku; orchestrator claude-opus; 2026-11-04.

## Delegation Decision

Mechanical single-file deletion with a checkable result: Haiku (Rule 17).

## Commands Executed

- `rg -n "allowlist_unauthorized" scripts config`
- `python3 -c "import ast; ast.parse(open('scripts/ai/aq-health-spider').read())"`
- `python3 scripts/testing/test-pm-tracker-owner-acceptance.py`
- `python3 -m pytest -q scripts/testing/test-health-spider-loop-regression.py`

## Validation Evidence

- No references remain in `scripts/` or `config/`.
- Parse ok.
- Owner-acceptance suite: 54 tests OK. Health-spider loop regression: 6 passed.

## Rollback Plan

Revert the commit. The removed branch was unreachable, so behaviour does not change either way.

## Residual Risk

None. The other three owner-acceptance alert types keep their handling; the dashboard and telemetry surface is unchanged. Live effect needs no rebuild beyond the next spider restart.

## Hint Feedback

None.
