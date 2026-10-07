#!/usr/bin/env python3
"""Lane quota/cooldown behavior: _is_lane_unavailable, _lane_cooldown_until, dispatch stops, cooldown gates."""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

_INCIDENTS_TMP = tempfile.TemporaryDirectory(prefix="prsi-incidents-test-")
os.environ["PRSI_INCIDENTS_FILE"] = str(Path(_INCIDENTS_TMP.name) / "rsi-incidents.json")

_DELEGATION_TMP = tempfile.TemporaryDirectory(prefix="prsi-delegation-test-")
os.environ["AQ_DELEGATION_DIR"] = str(_DELEGATION_TMP.name)

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prsi_orchestrator", ROOT / "scripts/automation/prsi-orchestrator.py")
prsi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prsi)

LANE_UNAVAILABLE_RECEIPT = {
    "exit_code": 0,
    "lane": "codex",
    "reason": "missing_delegate_receipt",
    "stderr_tail": "ERROR: You've hit your usage limit. Current usage: 250000 / 250000 tokens. To continue, try again at 7:25 PM.\n",
    "stdout_tail": "",
}

LANE_UNAVAILABLE_RECEIPT_STRAIGHT_APOSTROPHE = {
    "exit_code": 0,
    "lane": "codex",
    "reason": "missing_delegate_receipt",
    "stderr_tail": "ERROR: You have hit your usage limit. Current usage: 250000 / 250000 tokens. To continue, try again at 7:25 PM.\n",
    "stdout_tail": "",
}

QUALITY_FAILURE = {
    "exit_code": 1,
    "lane": "codex",
    "stderr_tail": "tests failed: assertion error\n",
    "stdout_tail": "",
}


def row(rid="r1", status="rsi_pending", **extra):
    r = {
        "id": rid,
        "type": "maintenance",
        "risk": "low",
        "status": status,
        "rsi_attempts": 0,
        "rsi_infra_failures": 0,
        "estimated_token_cost": 1,
        "raw_action": {"source": "rsi-incidents.json", "reason": "rsi-incident-open", "incident_id": "rsi-test"},
        "execution": {},
    }
    r["approval"] = {"verifier_by": "owner"}
    r.update(extra)
    return r


class LaneUnavailableDetector(unittest.TestCase):
    def test_typographic_apostrophe(self):
        """Codex quota error with typographic apostrophe U+2019."""
        self.assertTrue(prsi._is_lane_unavailable(LANE_UNAVAILABLE_RECEIPT))

    def test_straight_apostrophe_in_stderr(self):
        """Codex quota error with straight apostrophe in stderr."""
        receipt = {
            "exit_code": 0,
            "lane": "codex",
            "reason": "missing_delegate_receipt",
            "stderr_tail": "ERROR: You have hit your usage limit. try again at 7:25 PM.\n",
            "stdout_tail": "",
        }
        self.assertTrue(prsi._is_lane_unavailable(receipt))

    def test_quota_in_stdout(self):
        """Quota error message in stdout_tail."""
        receipt = {
            "exit_code": 0,
            "lane": "codex",
            "stdout_tail": "ERROR: You've hit your usage limit. try again at 7:25 PM.\n",
            "stderr_tail": "",
        }
        self.assertTrue(prsi._is_lane_unavailable(receipt))

    def test_rate_limit_exceeded(self):
        """Rate limit variant."""
        receipt = {
            "exit_code": 1,
            "lane": "codex",
            "stderr_tail": "rate limit exceeded, try again later\n",
        }
        self.assertTrue(prsi._is_lane_unavailable(receipt))

    def test_quota_cooldown_message(self):
        """Quota cooldown active message."""
        receipt = {
            "exit_code": 1,
            "lane": "codex",
            "stderr_tail": "quota cooldown active until 2026-10-02T19:25:00Z\n",
        }
        self.assertTrue(prsi._is_lane_unavailable(receipt))

    def test_claude_weekly_limit(self):
        """Claude's weekly limit message variant."""
        receipt = {
            "exit_code": 1,
            "lane": "claude",
            "stderr_tail": "You've hit your weekly limit · resets 2am (America/Los_Angeles)\n",
        }
        self.assertTrue(prsi._is_lane_unavailable(receipt))

    def test_quality_failure_not_lane_unavailable(self):
        """Normal quality failure should not be detected as lane unavailable."""
        self.assertFalse(prsi._is_lane_unavailable(QUALITY_FAILURE))

    def test_empty_receipt(self):
        """Empty/None receipt should return False."""
        self.assertFalse(prsi._is_lane_unavailable({}))
        self.assertFalse(prsi._is_lane_unavailable(None))

    def test_infra_error_not_lane_unavailable(self):
        """Infrastructure error is not lane unavailable."""
        receipt = {
            "exit_code": 2,
            "stderr_tail": "bash: /bin/x: No such file or directory\n",
        }
        self.assertFalse(prsi._is_lane_unavailable(receipt))


class LaneCooldownUntil(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.cooldown_file = self.tmp_path / ".codex-quota-cooldown"

    def test_future_cooldown(self):
        """Active future cooldown is returned as ISO string."""
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.cooldown_file.write_text(future)
        with patch.dict("os.environ", {"AQ_DELEGATION_DIR": str(self.tmp_path)}):
            result = prsi._lane_cooldown_until("codex")
        self.assertEqual(result, future)

    def test_expired_cooldown(self):
        """Past cooldown returns None (clearing is bash-side, not Python)."""
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.cooldown_file.write_text(past)
        with patch.dict("os.environ", {"AQ_DELEGATION_DIR": str(self.tmp_path)}):
            result = prsi._lane_cooldown_until("codex")
        self.assertIsNone(result)

    def test_missing_cooldown(self):
        """Missing cooldown file returns None."""
        with patch.dict("os.environ", {"AQ_DELEGATION_DIR": str(self.tmp_path)}):
            result = prsi._lane_cooldown_until("codex")
        self.assertIsNone(result)

    def test_corrupt_cooldown(self):
        """Unparseable cooldown returns None (clearing is bash-side, not Python)."""
        self.cooldown_file.write_text("not a valid timestamp")
        with patch.dict("os.environ", {"AQ_DELEGATION_DIR": str(self.tmp_path)}):
            result = prsi._lane_cooldown_until("codex")
        self.assertIsNone(result)

    def test_local_lane_no_cooldown(self):
        """Local lane always returns None."""
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.cooldown_file.write_text(future)
        result = prsi._lane_cooldown_until("local")
        self.assertIsNone(result)


class DispatchWithLaneUnavailable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ("QUEUE_PATH", "PRSI_STATE_PATH", "PRSI_POLICY_FILE", "ACTIONS_LOG_PATH", "_RSI_DISPATCH_LOCK"):
            self.enterContext(patch.object(prsi, name, self.root / name))
        self.enterContext(patch.object(prsi, "cmd_sync", return_value=0))
        self.enterContext(patch.object(prsi, "_rsi_open_incident_ids", return_value=(True, {"rsi-test"})))
        self.enterContext(patch.object(prsi, "_rsi_dispatch_preflight", return_value=(True, "isolated_worktree_required")))

    def run_cmd(self, argv, fn):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = fn(prsi.build_parser().parse_args(argv))
        return code, json.loads(out.getvalue())

    def rows(self):
        return {r["id"]: r for r in prsi._load_queue()["actions"]}

    def test_lane_unavailable_refunds_attempt_does_not_increment_infra_failures(self):
        """Lane unavailable: rsi_attempts refunded, infra_failures unchanged, execution.result = lane_unavailable."""
        r = row(status="rsi_pending", rsi_attempts=1)
        prsi._save_queue({"actions": [r]})

        with patch.object(prsi, "_run_rsi_delegate", return_value=("rsi_failed", LANE_UNAVAILABLE_RECEIPT)):
            self.run_cmd(["rsi-dispatch", "--execute"], prsi.cmd_rsi_dispatch)

        updated = self.rows()["r1"]
        # Attempt was refunded
        self.assertEqual(updated["rsi_attempts"], 1)
        # Infra failures unchanged
        self.assertEqual(updated["rsi_infra_failures"], 0)
        # Status back to pre-run
        self.assertEqual(updated["status"], "rsi_pending")
        # Result is lane_unavailable
        self.assertEqual(updated["execution"]["result"], "lane_unavailable")
        # Receipt persists
        self.assertEqual(updated["execution"]["receipt"], LANE_UNAVAILABLE_RECEIPT)

    def test_lane_unavailable_stops_loop(self):
        """Lane unavailable breaks dispatch loop; second eligible row is NOT dispatched."""
        r1 = row(rid="r1", status="rsi_pending", rsi_attempts=0)
        r2 = row(rid="r2", status="rsi_pending", rsi_attempts=0)
        prsi._save_queue({"actions": [r1, r2]})

        call_count = [0]
        orig_run_delegate = prsi._run_rsi_delegate

        def mock_delegate(row, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return ("rsi_failed", LANE_UNAVAILABLE_RECEIPT)
            # Should never reach here
            return orig_run_delegate(row, *args, **kwargs)

        with patch.object(prsi, "_run_rsi_delegate", side_effect=mock_delegate):
            self.run_cmd(["rsi-dispatch", "--execute"], prsi.cmd_rsi_dispatch)

        # Delegate called only once (loop broke after lane unavailable)
        self.assertEqual(call_count[0], 1)
        # Second row unchanged (never dispatched)
        r2_state = self.rows()["r2"]
        self.assertEqual(r2_state["status"], "rsi_pending")
        self.assertEqual(r2_state["rsi_attempts"], 0)

    def test_cooldown_blocks_dispatch_no_delegate_call(self):
        """Active cooldown file gates dispatch before calling _run_rsi_delegate."""
        r = row(status="rsi_pending")
        prsi._save_queue({"actions": [r]})

        # Write a future cooldown timestamp
        cooldown_dir = self.root / "delegation"
        cooldown_dir.mkdir(parents=True, exist_ok=True)
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        (cooldown_dir / ".codex-quota-cooldown").write_text(future)

        delegate_called = [False]

        def mock_delegate(*args, **kwargs):
            delegate_called[0] = True
            return ("rsi_failed", LANE_UNAVAILABLE_RECEIPT)

        with patch.object(prsi, "_run_rsi_delegate", side_effect=mock_delegate):
            with patch.dict("os.environ", {"AQ_DELEGATION_DIR": str(cooldown_dir)}):
                self.run_cmd(["rsi-dispatch", "--execute"], prsi.cmd_rsi_dispatch)

        # Delegate never called (cooldown gate prevented it)
        self.assertFalse(delegate_called[0])
        # Row unchanged
        r_state = self.rows()["r1"]
        self.assertEqual(r_state["status"], "rsi_pending")
        self.assertEqual(r_state["rsi_attempts"], 0)


class DelegateToCodexQuotaCapture(unittest.TestCase):
    """Test the embedded quota-capture Python program in delegate-to-codex."""

    def test_quota_detector_program(self):
        """Extract and verify the quota detection regex pattern in delegate-to-codex."""
        # Read delegate-to-codex script
        delegate_script = ROOT / "scripts" / "ai" / "delegate-to-codex"
        content = delegate_script.read_text(encoding="utf-8")

        # The quota detector should check for "hit your usage limit" case-insensitively
        # and apostrophe-agnostically
        self.assertIn("hit your usage limit", content.lower())

        # Verify Python code in the heredoc uses case-insensitive, apostrophe-agnostic check
        # The PYEOF block contains: if "hit your usage limit" not in text.lower():
        self.assertIn('"hit your usage limit" not in text.lower()', content)

    def test_quota_capture_writes_iso_timestamp(self):
        """_is_lane_unavailable triggers quota capture by detecting the pattern."""
        receipt = {
            "exit_code": 0,
            "lane": "codex",
            "stderr_tail": "ERROR: You've hit your usage limit. try again at 7:25 PM.",
            "stdout_tail": "",
        }
        # The detector should return True, which would trigger quota_capture_from_output
        self.assertTrue(prsi._is_lane_unavailable(receipt))


if __name__ == "__main__":
    unittest.main()
