# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-100

## Objective
- The first live run of meta-optimization-analysis after #458 + nrs (2026-10-10 09:47 PDT) finished but
  produced 0 proposals for two hidden reasons:
  - `generate_all_proposals` ran the four analyses with `asyncio.gather` on ONE asyncpg connection →
    `Error analyzing lesson library: cannot perform operation: another operation is in progress`.
  - The aiohttp client timeout was 120s; the local model (busy with the PRM eval, minutes per long prompt)
    timed out, `TimeoutError` has an empty message (`LLM call failed:`), and the empty response was then
    logged as "No routing optimization opportunities identified" — a failure reported as a clean result.
- Fix: analyses run sequentially (also matches the single local inference slot); client timeout
  `META_OPT_LLM_TIMEOUT_S` default 900s; LLM errors log the exception type; an empty LLM response logs
  "<X> analysis skipped: local LLM returned nothing" instead of "no opportunities".
- Also lands the template-conformant versions of the three 2026-10-10 evidence docs from #457/#458/#459
  (the PRs merged before the re-sectioned docs were pushed; CI "Syntax Validation" requires the template).

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Orchestrator-implemented: two single-site fixes found during live validation of an already-reviewed
  slice; a dispatch round-trip costs more than the change (Rule 17 deviation, recorded here + PULSE).

## Commands Executed
```bash
journalctl -u meta-optimization-analysis --since 09:47 --no-pager
python3 scripts/testing/test-meta-optimization-routing-source.py
bash scripts/testing/check-harness-first-pr-evidence-gate.sh
```

## Validation Evidence
- `test-meta-optimization-routing-source.py` PASS, with two new tests:
  - `test_analyses_never_overlap`: max concurrency 1, fixed order, a failing analysis is skipped while the
    others still run. Against the previous `gather()` code it FAILS (`max: 4`), so it guards the bug.
  - `test_llm_failure_is_reported_not_hidden`: TimeoutError is logged with its type; an empty LLM response
    yields the "skipped" warning and never "No routing optimization opportunities".
- Live run otherwise healthy: connected to PostgreSQL (aidb), proposals JSON written to
  `/var/lib/ai-stack/meta-optimization/proposals/`, unit Deactivated successfully.

## Rollback Plan
- Revert the PR commit.

## Residual Risk
- With the PRM eval holding the local slot, a 900s call can still time out; it is now reported as skipped.
- Unit has no TimeoutStartSec; worst case is 3 LLM calls x 900s.
- No rebuild needed: the unit execs `<repo>/ai-stack/meta-optimization/meta_optimizer.py` (verified in
  the unit script), so the fix is live on the next timer run after merge + `git pull`.

## Hint Feedback
- None.
