#!/usr/bin/env python3
"""
Unit and regression tests for the operator intervention writer (aq-agent-send over
control_channel) and its cockpit rendering.

aq-human-intervention was archived (.agent/archive/20261127-aq-human-intervention): of its
five kinds only inject and cancel were ever read by agent_executor; pause, resume, skip
and edit_intent were queued but treated as plain text. aq-agent-send writes exactly the
two kinds the consumer understands.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEND_CLI = REPO_ROOT / "scripts/ai/aq-agent-send"
MONITOR_CLI = REPO_ROOT / "scripts/ai/aq-cockpit-monitor"


class TestAgentSend(unittest.TestCase):

    def setUp(self):
        self.control_dir = REPO_ROOT / ".agents" / "delegation" / "control"
        self.control_dir.mkdir(parents=True, exist_ok=True)
        self.test_task_id = "test-task-intervention-123"
        self.queue_file = self.control_dir / f"{self.test_task_id}.jsonl"

    def tearDown(self):
        self.queue_file.unlink(missing_ok=True)

    def run_cli(self, *args, task_id=None):
        cmd = [sys.executable, str(SEND_CLI), task_id or self.test_task_id, *args]
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def records(self):
        return [json.loads(ln) for ln in self.queue_file.read_text().splitlines() if ln.strip()]

    def test_inject_message(self):
        res = self.run_cli("Focus on memory safety instead of speed optimization")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("queued inject", res.stdout)
        recs = self.records()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["kind"], "inject")
        self.assertIn("Focus on memory safety", recs[0]["text"])

    def test_cancel(self):
        res = self.run_cli("Operator emergency stop", "--cancel")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("queued cancel", res.stdout)
        self.assertEqual(self.records()[-1]["kind"], "cancel")

    def test_messages_append_in_order(self):
        self.assertEqual(self.run_cli("first").returncode, 0)
        self.assertEqual(self.run_cli("second", "--cancel").returncode, 0)
        self.assertEqual([r["kind"] for r in self.records()], ["inject", "cancel"])

    def test_unsafe_task_id_rejected_without_writing(self):
        res = self.run_cli("hi", task_id="../x")
        self.assertEqual(res.returncode, 1)
        self.assertFalse((self.control_dir.parent / "x.jsonl").exists())

    def test_usage_error_without_message(self):
        res = subprocess.run([sys.executable, str(SEND_CLI), self.test_task_id],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 2)

    def test_cockpit_monitor_integration(self):
        """Verify aq-cockpit-monitor displays intervention dock status correctly."""
        self.assertEqual(self.run_cli("Cockpit integration test", "--cancel").returncode, 0)

        res_monitor = subprocess.run([str(MONITOR_CLI), "--once"], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
        self.assertEqual(res_monitor.returncode, 0)
        self.assertIn("Intervention Dock", res_monitor.stdout)
        self.assertIn("PENDING", res_monitor.stdout)
        self.assertIn("CANCEL", res_monitor.stdout)


if __name__ == "__main__":
    unittest.main()
