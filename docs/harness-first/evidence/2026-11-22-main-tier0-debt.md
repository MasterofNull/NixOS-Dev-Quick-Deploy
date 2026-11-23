## Objective
Clear tier0 `--pre-commit` failures present on main: basedpyright diagnostics in `scripts/testing/test-brief-caps.py` (from #833) and missing cited paths in two persona plan files (from #827).

## Workflow/Session IDs
Session: Simurg@claude/sonnet-5.5 implementer slice, branch `fix/main-tier0-debt-20261122` (worktree agent-aa0f2368c4ef89e47).

## Delegation Decision
Bounded single-slice cleanup dispatched to a Sonnet-tier implementer by the orchestrator (Rule 17); no cheaper lane needed for a mechanical type/citation fix.

## Commands Executed
- `basedpyright scripts/testing/test-brief-caps.py` (before: 20 error lines incl. duplicates; after: 0)
- `ruff check scripts/testing/test-brief-caps.py`
- `python3 scripts/testing/test-brief-caps.py`
- `python3 scripts/governance/tier0.d/check-plan-paths.py` (staged)
- `scripts/governance/tier0-validation-gate.sh --pre-commit`
- `ci-clean-env.sh --all --only harness-first-static-gates`

## Validation Evidence
- Type fixes: `_load_dispatch()` helper asserts the import spec/loader (Any-typed module); attribute monkeypatching replaced by `mock.patch.object` inside an `ExitStack`; `log_message` override matches the base signature. Tests unchanged in intent: 25 tests OK.
- Plan paths: `.agent/PROJECT-COLLECTIVE-PERSONA-PRD.md:200` `tier0.d/check-fact-files.py` -> `scripts/governance/tier0.d/check-fact-files.py` (file moved/was mis-cited). `.agents/plans/persona-p3-collapse-20261113/DESIGN.md:22` `codex/gpt-6.1` is an example lane/model label, not a path; backticks dropped so it is not read as a repo path. No content deleted.
- Gate outputs: tier0 --pre-commit 71 passed, 0 failed (no AI_STRICT_ENV override needed); ci-clean-env harness-first-static-gates PASS; basedpyright 0 errors; ruff clean; test-brief-caps 25 OK.

## Rollback Plan
Revert the single commit; changes are test/doc-only.

## Residual Risk
The focused routing-registry check needs QDRANT_URL etc. in agent shells (env, not code); run with AI_STRICT_ENV=false from agent shells.

## Hint Feedback
Root cause: #833 and #827 merged while tier0's python type gate and plan-paths check failed on their files (gates not enforced at merge). Fixed the producers, no baseline growth or gate weakening.
