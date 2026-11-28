# Harness-First Task Evidence

Date: 2026-11-27
Task ID: HF-20261127-ATHENA-A1

## Objective
- A1-SOURCE-TRUST: skeptical-prior source trust (observe by default) and flagged-source containment
  on the retrieval path. Contract: `.agents/plans/athena-patterns-20261127/DESIGN.md` section 3.

## Workflow/Session IDs
- Workflow ID: athena-patterns-20261127
- Session ID: claude-20261127-101352-vixyjt (orchestrator, claude-sonnet-5-5)

## Delegation Decision
- Implemented by codex: `codex-20261127-103320-fyh2gk`; bounded review fixes
  `codex-20261127-104701-tzkqly`, `codex-20261127-104842-htv8ef`, `codex-20261127-105017-i7ntmd`.
- Local headless Codex cap bypassed with `--force-budget` (owner directive 2026-11-19).
  No Claude implement slot was free (orchestrator delegate held it).
- Review: a lane other than codex and claude, through aq-land.

## Commands Executed
```bash
scripts/ai/aq-session-start --task "athena-patterns-prd"
scripts/ai/aq-hints "trust scoring retrieval, topic drift memory hint, token budget soft hard"
python3 scripts/testing/test-source-trust.py
rg -l route_handler scripts/testing ai-stack -g 'test*.py'   # each run with python3
scripts/governance/check-python-types.py --staged
```

## Validation Evidence
- `test-source-trust.py`: 11 tests OK, also under the coordinator unit's own Python environment.
- It drives the real `route_search` body with stubbed dependencies.
- Import of `core.route_handler` and `knowledge.source_trust` from this tree with the unit's
  Python and PYTHONPATH layout (`AI_STRICT_ENV=false`): OK.
- 18 test files reference `route_handler`: 16 pass. 2 fail identically on `origin/main`
  (bb0f07a47): `tests/test_optimizations_simple.py` (`No module named 'route_handler'`) and
  `test-ai-insights-roadmap-surfaces.py` (roadmap readiness assertion). Logged in the backlog.
- Defect reproduced: `logging.getLogger("h").warning("x", n_removed=1)` raises `TypeError`.
- Type/lint gate on staged files: PASS within baseline.
- `route_handler.py` is a pinned live source in `local-inference-l2b-payload-golden.json`; the
  pin is updated here. The change touches only the retrieval filter block, no payload building.
- Not validated live: the coordinator runs from the Nix store; needs an owner deploy.

## Rollback Plan
- `AI_SOURCE_TRUST_MODE=off` on the coordinator restores previous ordering (the summary fix and
  logger fix stay), or revert the squash commit. No data migration.

## Residual Risk
- After deploy, `ai-mcp-integrity-check.service` may report `route_handler.py` as changed until
  its baseline is refreshed (an owner act).
- `source_trust_level` is set by authenticated ingestion callers and is trusted when `trusted`.
- Containment depends on the existing regex scanner; a payload it misses is not contained.
- Metric counts annotations per result list, so one chunk in two lists counts twice.
- `enforce` ranking quality is unmeasured; default stays `observe` pending `promotion_gate`.

## Hint Feedback
- Hints returned were generic (token plan, local-first); not specific to this slice. No hint IDs used.
