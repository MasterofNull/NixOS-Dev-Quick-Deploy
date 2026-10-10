# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-081

## Objective
- Fix telemetry producers to populate `agent_id` and `lane_id` on canonical `model_call` events.
- Root Cause: `_write_progress()` in `scripts/ai/lib/dispatch.py` and `_emit_token_event()` in `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py` omitted `agent_id` and `lane_id` when calling `_agent_events.emit_event("model_call", ...)` and `_are.make_event("model_call", ...)`.
- Impact: Meta-optimization per-agent routing breakdown (`ai-stack/meta-optimization/routing_source.py`) grouped all historical local model calls under agent type `"unknown"` because `agent_id` and `lane_id` were null in the canonical log stream.

## Material Changes
- `scripts/ai/lib/dispatch.py`:
  - Updated `_write_progress` to accept optional `agent_id` and `lane_id` parameters.
  - Added deterministic fallback resolution:
    - `agent_id`: `agent_id or os.getenv("AQ_AGENT_ID") or ("local-qwen" if source == "delegate-to-local" else (role or source))`
    - `lane_id`: `lane_id or os.getenv("AQ_LANE_ID") or ("local" if "local" in source else "unknown")`
  - Write `agent_id` and `lane_id` into progress data dictionary and pass both to `_agent_events.emit_event("model_call", ...)`.
  - Passed `role=config.role` and `run_id=task_id` into `_write_progress` across `DirectRunner` and `AgentRunner`.
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`:
  - Enriched `plan_ev`, `mc_ev`, and `ev` (`token_usage`) in `_emit_token_event` with `agent_id`, `lane_id`, and `role`.
  - Enriched `plan_ev` and `system_prompt` events in the local agent dispatch branch.
- `scripts/testing/test-meta-optimization-routing-source.py`:
  - Added `test_model_call_telemetry_agent_id` to verify propagation and environment fallbacks.
- `scripts/testing/fixtures/local-inference-l2b-payload-golden.json`:
  - Updated frozen live source hashes for `dispatch.py` and `ai_coordinator_handlers.py`.

## Commands Executed
```bash
python3 -m py_compile scripts/ai/lib/dispatch.py ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py scripts/testing/test-meta-optimization-routing-source.py
python3 scripts/testing/test-meta-optimization-routing-source.py
python3 scripts/testing/test-agent-run-event-envelope.py
python3 scripts/testing/test-local-inference-l2b.py
scripts/ai/aq-qa 0
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- `test-meta-optimization-routing-source.py` passes all tests including `test_model_call_telemetry_agent_id`.
- `test-agent-run-event-envelope.py` passes schema and redaction verification.
- `test-local-inference-l2b.py` passes 16 L2B checks with updated hashes.
- `aq-qa 0` passes (195 checks passed, 0 failed).
- `tier0-validation-gate.sh --pre-commit` passed all 55 gates.
- `py_compile` clean across all modified files.

## Rollback Plan
- Revert commit on `origin/main`.
