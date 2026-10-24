#!/usr/bin/env python3
"""Unit tests for agent monitoring, shadow events, and audit trail integrity."""

import sys
import unittest
import tempfile
from pathlib import Path

# Add scripts/ai/lib to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "ai" / "lib"))

import agent_run_events as are
import workflow_shadow_contract as wsc


class TestAgentMonitoringAndAudit(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.log_path = Path(self.tmp_dir.name) / "agent-events.jsonl"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_emit_and_validate_agent_run_event(self):
        run_id = "test-run-1234"
        event = are.make_event(
            event_type="tool_call",
            source="test_harness",
            run_id=run_id,
            status="running",
            role="implementer",
            lane_id="antigravity",
            tool_name="ctx_read",
            payload={"path": "scripts/ai/lib/aq_decide.py"},
        )
        are.validate_event(event)
        self.assertEqual(event["schema_version"], are.SCHEMA_VERSION)
        self.assertEqual(event["run_id"], run_id)
        self.assertEqual(event["event_type"], "tool_call")
        self.assertEqual(event["tool_name"], "ctx_read")

    def test_tamper_evident_jsonl_append(self):
        run_id = "test-run-audit"
        for i in range(1, 4):
            event = are.make_event(
                event_type="model_call" if i == 1 else "tool_result",
                source="test_harness",
                run_id=run_id,
                status="running" if i < 3 else "succeeded",
                role="orchestrator",
                lane_id="codex",
                payload={"step": i},
            )
            are.append_jsonl(self.log_path, event)

        loaded = are.load_jsonl(self.log_path)
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0]["payload"]["step"], 1)
        self.assertEqual(loaded[2]["status"], "succeeded")

    def test_workflow_shadow_contract_invariants(self):
        # Validate that workflow shadow contract exposes canonical event versions and statuses
        self.assertIn("event", wsc.VERSIONS)
        self.assertIn("started", wsc.STATUSES)
        self.assertIn("completed", wsc.STATUSES)
        self.assertIn("failed", wsc.STATUSES)


if __name__ == "__main__":
    unittest.main()
