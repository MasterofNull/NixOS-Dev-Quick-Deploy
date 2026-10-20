#!/usr/bin/env python3
"""
Unit and regression tests for aq-human-intervention.
Tests pause, resume, skip, edit, and cancel commands.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERVENTION_CLI = REPO_ROOT / "scripts/ai/aq-human-intervention"

class TestHumanIntervention(unittest.TestCase):

    def setUp(self):
        self.control_dir = REPO_ROOT / ".agents" / "delegation" / "control"
        self.control_dir.mkdir(parents=True, exist_ok=True)
        self.test_task_id = "test-task-intervention-123"
        self.queue_file = self.control_dir / f"{self.test_task_id}.jsonl"

    def tearDown(self):
        if self.queue_file.exists():
            try:
                self.queue_file.unlink()
            except Exception:
                pass

    def run_cli(self, args):
        cmd = [str(INTERVENTION_CLI), "--task-id", self.test_task_id] + args
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_pause_and_resume(self):
        res1 = self.run_cli(["pause", "--reason", "Inspect intermediate state"])
        self.assertEqual(res1.returncode, 0)
        self.assertIn("PAUSED", res1.stdout)

        res2 = self.run_cli(["resume", "--instruction", "State verified; proceed"])
        self.assertEqual(res2.returncode, 0)
        self.assertIn("RESUMED", res2.stdout)

        lines = [json.loads(l) for l in self.queue_file.read_text().splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["kind"], "pause")
        self.assertEqual(lines[1]["kind"], "resume")

    def test_skip(self):
        res = self.run_cli(["skip", "--step-name", "flaky-external-fetch"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("SKIPPED", res.stdout)

        lines = [json.loads(l) for l in self.queue_file.read_text().splitlines() if l.strip()]
        self.assertEqual(lines[-1]["kind"], "skip")
        self.assertIn("flaky-external-fetch", lines[-1]["text"])

    def test_edit_intent(self):
        res = self.run_cli(["edit", "Focus on memory safety instead of speed optimization"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("INTENT UPDATED", res.stdout)

        lines = [json.loads(l) for l in self.queue_file.read_text().splitlines() if l.strip()]
        self.assertEqual(lines[-1]["kind"], "edit_intent")
        self.assertIn("Focus on memory safety", lines[-1]["text"])

    def test_cancel(self):
        res = self.run_cli(["cancel", "--reason", "Operator emergency stop"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("CANCELLED", res.stdout)

        lines = [json.loads(l) for l in self.queue_file.read_text().splitlines() if l.strip()]
        self.assertEqual(lines[-1]["kind"], "cancel")

if __name__ == "__main__":
    unittest.main()
