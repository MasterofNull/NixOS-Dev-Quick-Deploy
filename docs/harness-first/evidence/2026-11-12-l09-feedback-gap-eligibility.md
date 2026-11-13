# Evidence: feedback-to-gap eligibility (2026-11-12)

## Objective
`sync_feedback_corrections_to_gaps` exported any query rated negative at least `min_occurrences` times to query-gaps.jsonl, ignoring the linked interaction's eligibility. Infrastructure errors, cancellations, infeasible work, partial/success outcomes, unknown attribution and unlinked feedback therefore became adverse learning signals. The export now reuses the #750 `_learning_sink_policy` as the sole eligibility decision. Branch `fix/l09-feedback-gap-eligibility`.

## Workflow/Session IDs
- Implementer: Claude sub-agent (Sonnet 5.5), 2026-11-12, brief `.agents/delegation/outputs/wave-f/l09-feedback-gap-eligibility.md`.
- Independent review: owed by a non-author lane.

## Delegation Decision
Bounded single-slice implementation delegated to the balanced-tier Claude lane (Rule 17). No commit, push or tier0 run by the implementer.

## Commands Executed
```bash
cd ai-stack/mcp-servers/hybrid-coordinator
python3 -m pytest -q tests/test_interaction_tracker_attribution.py tests/test_mcp_handlers_dispatch.py
```

## Validation Evidence
- 55 passed. New cases drive the real `sync_feedback_corrections_to_gaps` to a temp JSONL: eligible agent_error failure exported; infrastructure_error, cancelled, infeasible, partial, success, unknown and unsupplied attribution not exported; null and missing interaction ids not exported; mixed-eligibility query counts only eligible rows; Qdrant lookup failure writes nothing; raw feedback rows unchanged.
- A malformed (non-UUID) interaction id is excluded as unlinked without failing the Qdrant batch, so other eligible rows still export; id case/dash variants are normalized before matching. Selection is `ORDER BY created_at DESC` so the bounded window is the newest feedback.
- Not run: tier0, full suite, live coordinator path.

## Rollback Plan
Revert the commit. No schema or stored-data changes; learning_feedback rows are never modified.

## Residual Risk
- Eligibility depends on caller-declared attribution (see learning-attribution evidence).
- Selection is bounded to `limit * 20` negative linked rows per cycle; older rows beyond the bound are not considered.
- Queries previously exported remain in the JSONL (dedupe only prevents re-adding).
- Coordinator runs from Nix-pinned source: owner-run rebuild needed for activation; not activated.

## Hint Feedback
No aq-hints query was made; no hint feedback to record.
