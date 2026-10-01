#!/usr/bin/env python3
"""Tests for aq-rsi-pending script and RSI dispatch copy-back mechanism."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
AQ_RSI_PENDING = SCRIPTS_DIR / "ai" / "aq-rsi-pending"


class TestAqRsiPending(unittest.TestCase):
    """Tests for aq-rsi-pending script."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Create queue and incidents files
        self.queue_file = self.temp_path / "action-queue.json"
        self.incidents_file = self.temp_path / "rsi-incidents.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_queue(self, actions):
        """Write test queue file."""
        self.queue_file.write_text(json.dumps({"actions": actions}))

    def write_incidents(self, incidents):
        """Write test incidents file."""
        self.incidents_file.write_text(json.dumps({"incidents": incidents, "version": 1}))

    def run_aq_rsi_pending(self, args=()):
        """Run aq-rsi-pending and return (stdout, stderr, returncode)."""
        env = os.environ.copy()
        env["PRSI_ACTION_QUEUE_PATH"] = str(self.queue_file)
        env["PRSI_INCIDENTS_FILE"] = str(self.incidents_file)
        result = subprocess.run(
            [sys.executable, str(AQ_RSI_PENDING)] + list(args),
            capture_output=True,
            text=True,
            env=env,
            timeout=5
        )
        return result.stdout, result.stderr, result.returncode

    def test_high_risk_unsigned_row_listed(self):
        """High-risk unsigned row should be listed."""
        incident = {
            "test-incident-1": {
                "severity": "high",
                "agent": "test-agent",
                "error": "Test error message for incident 1"
            }
        }
        self.write_incidents(incident)

        actions = [
            {
                "id": "row-1",
                "risk": "high",
                "status": "rsi_pending",
                "raw_action": {
                    "source": "rsi-incidents.json",
                    "incident_id": "test-incident-1"
                },
                "approval": {}
            }
        ]
        self.write_queue(actions)

        stdout, stderr, returncode = self.run_aq_rsi_pending()
        self.assertEqual(returncode, 0)
        self.assertIn("row-1", stdout)
        self.assertIn("severity=high", stdout)

    def test_signed_row_not_listed(self):
        """Row with verifier_by set should not be listed."""
        incident = {
            "test-incident-2": {
                "severity": "high",
                "agent": "test-agent",
                "error": "Test error"
            }
        }
        self.write_incidents(incident)

        actions = [
            {
                "id": "row-2",
                "risk": "high",
                "status": "rsi_pending",
                "raw_action": {
                    "source": "rsi-incidents.json",
                    "incident_id": "test-incident-2"
                },
                "approval": {
                    "verifier_by": "owner"
                }
            }
        ]
        self.write_queue(actions)

        stdout, stderr, returncode = self.run_aq_rsi_pending()
        self.assertEqual(returncode, 0)
        self.assertNotIn("row-2", stdout)

    def test_non_rsi_row_ignored(self):
        """Non-RSI rows should be ignored."""
        actions = [
            {
                "id": "row-3",
                "risk": "high",
                "status": "approved",
                "raw_action": {
                    "source": "prsi-queue",  # Not rsi-incidents.json
                    "type": "knowledge"
                },
                "approval": {}
            }
        ]
        self.write_queue(actions)

        stdout, stderr, returncode = self.run_aq_rsi_pending()
        self.assertEqual(returncode, 0)
        self.assertNotIn("row-3", stdout)

    def test_low_risk_row_ignored(self):
        """Low-risk rows should be ignored even if unsigned."""
        incident = {
            "test-incident-3": {
                "severity": "low",
                "agent": "test-agent",
                "error": "Test error"
            }
        }
        self.write_incidents(incident)

        actions = [
            {
                "id": "row-4",
                "risk": "low",
                "status": "rsi_pending",
                "raw_action": {
                    "source": "rsi-incidents.json",
                    "incident_id": "test-incident-3"
                },
                "approval": {}
            }
        ]
        self.write_queue(actions)

        stdout, stderr, returncode = self.run_aq_rsi_pending()
        self.assertEqual(returncode, 0)
        self.assertNotIn("row-4", stdout)

    def test_count_flag(self):
        """--count flag should print only the count."""
        incident = {
            "test-incident-4": {
                "severity": "high",
                "agent": "test-agent",
                "error": "Test error"
            },
            "test-incident-5": {
                "severity": "high",
                "agent": "test-agent",
                "error": "Another error"
            }
        }
        self.write_incidents(incident)

        actions = [
            {
                "id": "row-5",
                "risk": "high",
                "status": "rsi_pending",
                "raw_action": {
                    "source": "rsi-incidents.json",
                    "incident_id": "test-incident-4"
                },
                "approval": {}
            },
            {
                "id": "row-6",
                "risk": "high",
                "status": "rsi_failed",
                "raw_action": {
                    "source": "rsi-incidents.json",
                    "incident_id": "test-incident-5"
                },
                "approval": {}
            }
        ]
        self.write_queue(actions)

        stdout, stderr, returncode = self.run_aq_rsi_pending(["--count"])
        self.assertEqual(returncode, 0)
        self.assertEqual(stdout.strip(), "2")

    def test_json_flag(self):
        """--json flag should print machine-readable output."""
        incident = {
            "test-incident-6": {
                "severity": "high",
                "agent": "test-agent",
                "error": "Test error message"
            }
        }
        self.write_incidents(incident)

        actions = [
            {
                "id": "row-7",
                "risk": "high",
                "status": "rsi_pending",
                "raw_action": {
                    "source": "rsi-incidents.json",
                    "incident_id": "test-incident-6"
                },
                "approval": {}
            }
        ]
        self.write_queue(actions)

        stdout, stderr, returncode = self.run_aq_rsi_pending(["--json"])
        self.assertEqual(returncode, 0)
        data = json.loads(stdout)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "row-7")
        self.assertEqual(data[0]["severity"], "high")

    def test_unreadable_queue_exits_2(self):
        """Unreadable queue should exit 2."""
        # Don't create the queue file at all
        stdout, stderr, returncode = self.run_aq_rsi_pending()
        self.assertEqual(returncode, 2)
        self.assertIn("not found", stderr.lower())

    def test_empty_queue(self):
        """Empty queue should not error."""
        self.write_queue([])

        stdout, stderr, returncode = self.run_aq_rsi_pending()
        self.assertEqual(returncode, 0)

    def test_count_with_zero_pending(self):
        """--count with no pending items should print 0."""
        self.write_queue([])
        self.write_incidents({})

        stdout, stderr, returncode = self.run_aq_rsi_pending(["--count"])
        self.assertEqual(returncode, 0)
        self.assertEqual(stdout.strip(), "0")


class TestCopyBackLogic(unittest.TestCase):
    """Unit tests for the copy-back logic used in cmd_rsi_dispatch."""

    def test_copy_back_execution_results_to_original_rows(self):
        """Test that execution results are correctly copied back to original rows."""
        # Simulate the eligible rows before _select_actions_for_execution
        eligible = [
            {
                "id": "row-1",
                "type": "knowledge",
                "risk": "high",
                "approval": {}
            },
            {
                "id": "row-2",
                "type": "routing",
                "risk": "medium",
                "approval": {}
            }
        ]

        # Simulate the selection copies returned by _reserve_actions_for_execution
        # with execution results set by _select_actions_for_execution
        selection = [
            {
                **eligible[0],
                "status": "approved",
                "execution": {"result": "skipped_missing_independent_verifier"}
            },
            {
                **eligible[1],
                "status": "approved",
                "execution": {"result": "selected"}
            }
        ]

        # Apply the copy-back logic from cmd_rsi_dispatch
        skipped_reasons = {}
        for sel_row in selection:
            row_id = sel_row.get("id")
            exec_result = sel_row.get("execution", {}).get("result")
            if exec_result:
                for orig_row in eligible:
                    if orig_row.get("id") == row_id:
                        orig_row.setdefault("execution", {})["result"] = exec_result
                        if exec_result.startswith("skipped_"):
                            skipped_reasons[exec_result] = skipped_reasons.get(exec_result, 0) + 1
                        break

        # Verify the results
        self.assertIn("execution", eligible[0])
        self.assertEqual(
            eligible[0]["execution"]["result"],
            "skipped_missing_independent_verifier"
        )
        self.assertIn("execution", eligible[1])
        self.assertEqual(eligible[1]["execution"]["result"], "selected")

        # Verify skipped reasons were collected
        self.assertEqual(skipped_reasons["skipped_missing_independent_verifier"], 1)

    def test_multiple_skipped_reasons_counted(self):
        """Test that multiple different skip reasons are counted correctly."""
        eligible = [
            {"id": f"row-{i}", "type": "knowledge", "risk": "high", "approval": {}}
            for i in range(3)
        ]

        skip_results = [
            "skipped_missing_independent_verifier",
            "skipped_missing_independent_verifier",
            "skipped_budget_cap"
        ]

        selection = [
            {**row, "status": "approved", "execution": {"result": result}}
            for row, result in zip(eligible, skip_results)
        ]

        skipped_reasons = {}
        for sel_row in selection:
            row_id = sel_row.get("id")
            exec_result = sel_row.get("execution", {}).get("result")
            if exec_result:
                for orig_row in eligible:
                    if orig_row.get("id") == row_id:
                        orig_row.setdefault("execution", {})["result"] = exec_result
                        if exec_result.startswith("skipped_"):
                            skipped_reasons[exec_result] = skipped_reasons.get(exec_result, 0) + 1
                        break

        self.assertEqual(skipped_reasons["skipped_missing_independent_verifier"], 2)
        self.assertEqual(skipped_reasons["skipped_budget_cap"], 1)


def run_tests():
    """Run all tests and print summary."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestAqRsiPending))
    suite.addTests(loader.loadTestsFromTestCase(TestCopyBackLogic))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    passed = total - failed
    print(f"\n{passed}/{total} tests passed")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
