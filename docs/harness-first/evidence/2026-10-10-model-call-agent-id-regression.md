# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-160

## Objective
Repair the model_call agent_id/lane_id regression on main: PR #470 replaced PR #462's informative fallbacks in `scripts/ai/lib/dispatch.py::_write_progress` with constants ("local" / "local-direct"), discarding role-based attribution and breaking `test_model_call_telemetry_agent_id` in `test-meta-optimization-routing-source.py`. Restore #462 semantics; reconcile #470's test.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f
- Branch: fix/model-call-agent-id-regression-20261010

## Delegation Decision
Bounded single-file fix plus test reconciliation, delegated to an implementer sub-agent by the orchestrator after independent review found the overlap. Root cause: #470 was built from a stale brief and self-merged over #462 (producer fix, no workaround).

## Commands Executed
- `python3 scripts/testing/test-meta-optimization-routing-source.py` (before: AssertionError at line 248, agent_id != "local-qwen")
- Restored fallbacks in `dispatch.py`: agent_id = caller or AQ_AGENT_ID or ("local-qwen" if source == "delegate-to-local" else role or source); lane_id = caller or AQ_LANE_ID or ("local" if "local" in source else "unknown")
- Reconciled `scripts/testing/test-dispatch-model-call-agent-id.py` (real fallbacks, env overrides, non-local role/source fallback cases)
- Re-pinned dispatch.py sha256 in `scripts/testing/fixtures/local-inference-l2b-payload-golden.json` (equals the pre-#470 pin because dispatch.py is byte-identical to pre-#470)
- Ran the four test scripts below plus `test-local-inference-l2b.py`

## Validation Evidence
- test-meta-optimization-routing-source.py: PASS
- test-dispatch-model-call-agent-id.py: PASS (6 cases)
- test-agent-run-event-envelope.py: PASS
- test-dispatch-classify-tokens.py: 4/4 PASS
- test-local-inference-l2b.py: PASS: 16 checks

## Rollback Plan
Revert the single commit; this returns main to the #470 state (constants, with the routing-source test failing).

## Residual Risk
Low. The two tests now encode the same semantics. Process risk remains that self-merged overlapping PRs can regress each other; not addressed here.

## Hint Feedback
No harness hints were consulted for this slice; none to rate.
