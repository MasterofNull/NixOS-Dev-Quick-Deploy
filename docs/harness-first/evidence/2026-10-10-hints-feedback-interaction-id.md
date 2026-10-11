# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-150

## Objective
- Fix the hint-feedback producer added by PR #464 (merge 48348e6b): it POSTed to AIDB /history/record without an interaction_id, and InteractionHistoryStore.record_interaction passed interaction.get("interaction_id") (None) explicitly, overriding the UUID PK server_default, so Postgres rejected every insert (AIDB 500, visible only at warning/debug). Also retain a reference to the fire-and-forget publish task so it cannot be garbage-collected.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Independent review of Antigravity's self-merged PR #464 found the defect; a bounded implementer sub-agent applied the minimal fix in an isolated worktree. Root cause: producer omitted the id AND the store treated a missing id as an explicit NULL. Both layers fixed.

## Commands Executed
```bash
python3 scripts/testing/test-hints-feedback-aidb-producer.py   # 8 tests, 3 skipped without sqlalchemy
PYTHONPATH=<nix sqlalchemy 2.0.49> python3 scripts/testing/test-hints-feedback-aidb-producer.py   # 8 tests OK
bash scripts/testing/check-harness-first-pr-evidence-gate.sh
```

## Validation Evidence
- With sqlalchemy available: Ran 8 tests, OK. Reverting only interaction_history.py makes the two None/missing-id tests FAIL (compiled postgres INSERT contained interaction_id=NULL), confirming the tests exercise the real statement construction.
- Producer payload now asserted to carry a valid UUID interaction_id; task-reference retention/release asserted.
- Callers that pass an id are unchanged (test_supplied_interaction_id_still_inserted).

## Rollback Plan
- Revert the commit; no schema or data migration involved.

## Residual Risk
- Takes effect only after the hybrid-coordinator (producer) and AIDB (store) services are restarted/rebuilt (owner act). Until then hint feedback keeps failing to persist in interaction_history. No live AIDB insert was exercised (no live POSTs by policy).

## Hint Feedback
- None.
