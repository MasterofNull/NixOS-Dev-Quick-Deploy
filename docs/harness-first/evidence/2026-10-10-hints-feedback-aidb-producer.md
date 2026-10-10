# Evidence: Hints Feedback AIDB Producer (Meta-Optimization Telemetry Fix)

**Date**: 2026-10-10
**Author**: Antigravity (Gemini lane)
**Slice**: Meta-Optimization Hints Feedback Producer Fix
**Branch**: `fix/hints-feedback-aidb-producer-20261010`
**Issue**: Meta-optimizer and harness evolution tracker lacked hint usage feedback data because `interaction_history` table in PostgreSQL received no records with `metadata.hint_template`.

## 1. Objective & Root Cause

`meta_optimizer.py` and `harness_evolution_tracker.py` analyze hint effectiveness by querying PostgreSQL `interaction_history`:
```sql
SELECT metadata->>'hint_template' as hint_template, ...
FROM interaction_history
WHERE metadata->>'hint_template' IS NOT NULL
GROUP BY metadata->>'hint_template'
```
Previously, `handle_hints_feedback` in `ai-stack/mcp-servers/hybrid-coordinator/knowledge/hints_handlers.py` only appended feedback entries to a local JSONL file (`_hint_feedback_log_path()`) without publishing interaction records to AIDB's `/history/record` endpoint. Consequently, `interaction_history` never received any rows with `metadata.hint_template`, starving the meta-optimization analysis pipeline of feedback signals.

## 2. Changes

- `ai-stack/mcp-servers/hybrid-coordinator/knowledge/hints_handlers.py`:
  - Added `_publish_hint_feedback_to_aidb(entry)`: asynchronously forwards hint feedback to AIDB `POST /history/record` with `metadata.hint_template = hint_id`, `outcome = 'success'`/`'failure'`, `agent_type`, and `value_score`.
  - Non-blocking execution via `asyncio.create_task` with fail-safe error handling ensuring feedback logging is never interrupted if AIDB is unavailable.
- `scripts/testing/test-hints-feedback-aidb-producer.py`:
  - Unit test suite verifying payload structure, outcome mapping, error handling, and end-to-end handler dispatch.

## 3. Validation

- Unit tests:
  ```bash
  python3 scripts/testing/test-hints-feedback-aidb-producer.py
  # Ran 4 tests in 0.108s - OK
  ```
- Regression suites:
  ```bash
  python3 scripts/testing/test-hints-agent-lessons.py
  python3 scripts/testing/test-hints-route-selection.py
  python3 scripts/testing/test-meta-optimization-routing-source.py
  ```
- Tier-0 validation gate:
  `scripts/governance/tier0-validation-gate.sh --pre-commit` passed with 0 errors.
