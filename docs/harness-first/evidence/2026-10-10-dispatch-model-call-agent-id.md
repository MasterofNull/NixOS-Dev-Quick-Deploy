# Evidence: Dispatch Telemetry Agent and Lane ID Tracking on Model Calls

## Context
Date: 2026-10-10
Slice: `feat/dispatch-model-call-agent-id`
Component: `scripts/ai/lib/dispatch.py`, `scripts/testing/test-dispatch-model-call-agent-id.py`, `scripts/testing/fixtures/local-inference-l2b-payload-golden.json`
Implementer Task: `antigravity-20261010-165325-4enn5v`

## Problem
In the canonical agent-run event stream (`agent-run-events.jsonl`), local `model_call` events originating from `source="delegate-to-local"` historically had `agent_id=null` and `lane_id=null`. Meta-optimization (`ai-stack/meta-optimization/routing_source.py`) reported every local call as agent "unknown", preventing per-agent routing and model allocation analysis.

## Solution
1. **Accurate Defaults and Environment Overrides in Dispatch**:
   - Updated `_write_progress()` in `scripts/ai/lib/dispatch.py` to resolve:
     - `effective_agent_id`: caller `agent_id` or `os.getenv("AQ_AGENT_ID")` or `"local"`.
     - `effective_lane_id`: caller `lane_id` or `os.getenv("AQ_LANE_ID")` or `"local-direct"`.
   - Propagated `agent_id` and `lane_id` to `_agent_events.emit_event("model_call", ...)` adhering to `make_event` envelope schema.
2. **Behavioural Test Suite**:
   - Added `scripts/testing/test-dispatch-model-call-agent-id.py` verifying defaults, full environment overrides, and partial overrides without source code inspection.
3. **L2B Golden Pin Re-hash**:
   - Re-hashed `scripts/ai/lib/dispatch.py` in `scripts/testing/fixtures/local-inference-l2b-payload-golden.json`.

## Validation Evidence
- `python3 scripts/testing/test-dispatch-model-call-agent-id.py`: PASS (all 4 cases verified).
- `python3 scripts/testing/test-dispatch-classify-tokens.py`: PASS (4/4 tests).
- `python3 scripts/testing/test-local-inference-l2b.py`: PASS (16/16 L2B checks).
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: 55/55 checks PASS.
