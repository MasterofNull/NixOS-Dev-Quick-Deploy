#!/usr/bin/env bash
set -euo pipefail

# Validate safe thought/planning telemetry schema, rendering, and redaction contracts.

echo "Validating safe thought/planning telemetry contract..."

python3 - <<'PY'
import json
import sys
import tempfile
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts" / "ai" / "lib"))

import agent_run_events as events  # noqa: E402

schema = json.loads((root / "config/schemas/maeah/agent-run-event.schema.json").read_text(encoding="utf-8"))
schema_event_types = set(schema["properties"]["event_type"]["enum"])
assert {"thought", "planning"} <= events.EVENT_TYPES, "thought/planning missing from runtime event types"
assert schema_event_types == events.EVENT_TYPES, "schema event enum drift"

thought = events.make_event(
    "thought",
    source="test-telemetry-thought-event",
    run_id="safe-thought-fixture",
    payload={
        "kind": "local_model_reasoning_block",
        "summary": "Local model emitted an internal reasoning block; raw chain-of-thought was suppressed.",
        "char_count": 123,
        "content_hash": events.stable_digest("private reasoning fixture"),
        "redaction_level": "raw_reasoning_suppressed",
    },
)
assert "content" not in thought["payload"], "raw thought content must not be persisted"
assert thought["payload"]["redaction_level"] == "raw_reasoning_suppressed", "missing suppression marker"

planning = events.make_event(
    "planning",
    source="test-telemetry-thought-event",
    run_id="safe-thought-fixture",
    payload={
        "plan_step": "validate-before-claim",
        "rationale_summary": "Contract checks run before dashboard claims.",
        "evidence_refs": ["agent-run-event.schema.json"],
    },
)

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "agent-run-events.jsonl"
    events.append_jsonl(path, thought)
    events.append_jsonl(path, planning)
    loaded = events.load_jsonl(path)
assert {ev["event_type"] for ev in loaded} == {"thought", "planning"}, "thought/planning JSONL round trip failed"
PY

grep -q 'raw_reasoning_suppressed' "ai-stack/switchboard/switchboard.py" \
  || { echo "safe reasoning suppression missing from switchboard"; exit 1; }
grep -q '"planning"' "ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py" \
  || { echo "coordinator planning telemetry producer missing"; exit 1; }
! grep -q 'payload={"content": thought_text}' "ai-stack/switchboard/switchboard.py" \
  || { echo "raw thought_text persistence is forbidden"; exit 1; }
grep -q '<option value="thought">thought</option>' "dashboard.html" \
  || { echo "dashboard thought filter missing"; exit 1; }
grep -q '<option value="planning">planning</option>' "dashboard.html" \
  || { echo "dashboard planning filter missing"; exit 1; }
grep -q 'sandbox=""' "assets/dashboard.js" \
  || { echo "artifact iframe sandbox missing"; exit 1; }

echo "PASS: safe thought/planning telemetry contract verified."
exit 0
