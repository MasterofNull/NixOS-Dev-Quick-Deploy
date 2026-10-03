#!/usr/bin/env python3
"""Offline RSI lane and abandoned-dispatch regression tests; no real delegates."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prsi_lane", ROOT / "scripts/automation/prsi-orchestrator.py")
prsi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prsi)


def completion(lane, suffix="abcdef"):
    return f"[delegate-to-{lane}] Task {lane}-20260930-123456-{suffix} completed.\n"


def row(age=0, status="rsi_pending"):
    return {"id": "lane-test", "type": "maintenance", "risk": "low", "status": status,
            "rsi_attempts": 1, "estimated_token_cost": 1,
            "raw_action": {"source": "rsi-incidents.json", "reason": "rsi-incident-open", "incident_id": "rsi-test"},
            "execution": {"last_run_at": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
                          "receipt": {"lane": "codex"}}}


class LaneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ("QUEUE_PATH", "PRSI_STATE_PATH", "PRSI_POLICY_FILE", "ACTIONS_LOG_PATH", "_RSI_DISPATCH_LOCK"):
            self.enterContext(patch.object(prsi, name, self.root / name))
        # Only ledger sync and infrastructure preflight are stubbed. Dispatch
        # selection still exercises the real policy and budget reservation gates.
        self.enterContext(patch.object(prsi, "cmd_sync", return_value=0))
        self.enterContext(patch.object(prsi, "_rsi_open_incident_ids", return_value=(True, {"rsi-test"})))
        self.preflight = self.enterContext(patch.object(prsi, "_rsi_dispatch_preflight", return_value=(True, "isolated_worktree_required")))

    def dispatch(self, flags=(), rows=None):
        prsi._save_queue({"actions": [row()] if rows is None else rows})
        args = prsi.build_parser().parse_args(["rsi-dispatch", *flags])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = prsi.cmd_rsi_dispatch(args)
        return code, json.loads(output.getvalue()), prsi._load_queue()["actions"]

    def test_lane_selection_and_execution_receipt(self):
        for policy, flags, expected in [({}, [], "codex"), ({}, ["--lane", "local"], "local"),
                                         ({}, ["--lane", "claude"], "claude"),
                                         ({}, ["--lane", "antigravity"], "antigravity"),
                                         ({"rsi": {"repair_lane": "local"}}, [], "local"),
                                         ({"rsi": {"repair_lane": "claude"}}, [], "claude"),
                                         ({"rsi": {"repair_lane": "antigravity"}}, [], "antigravity"),
                                         ({"rsi": {"repair_lane": "local"}}, ["--lane", "codex"], "codex")]:
            with self.subTest(policy=policy, flags=flags):
                prsi.PRSI_POLICY_FILE.write_text(json.dumps(policy))
                proc = Mock(returncode=0)
                proc.communicate.return_value = (completion(expected), "")
                with patch.object(prsi.subprocess, "Popen", return_value=proc) as popen:
                    code, output, rows = self.dispatch(["--execute", *flags])
                self.assertEqual(code, 0)
                self.assertEqual(output["lane"], expected)
                self.assertEqual(output["executed"], 1)
                self.assertEqual(rows[0]["status"], "rsi_awaiting_validation")
                self.assertEqual(rows[0]["execution"]["receipt"]["lane"], expected)
                self.preflight.assert_called_with(expected)
                argv = popen.call_args.args[0]
                if expected == "codex":
                    expected_args = ["--wait", "--mode", "edit"]
                elif expected == "claude":
                    expected_args = ["--wait", "--role", "implementer"]
                elif expected == "antigravity":
                    expected_args = ["--wait", "--timeout", "600", "--role", "implementer"]
                else:
                    expected_args = ["--mode", "agent", "--wait", "--timeout", "600", "--role", "implementer"]
                self.assertEqual(argv, [str(prsi.AI_SCRIPT_DIR / f"delegate-to-{expected}"),
                                        *expected_args, "--prompt", prsi._rsi_task_prompt(row(), False)])
                self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_strict_lane_receipts(self):
        for lane in ("codex", "local", "antigravity"):
            other = "local" if lane == "codex" else "codex"
            cases = [(completion(lane), "", 0, True), (completion(other), "", 0, False),
                     ("", completion(lane), 0, False), (completion(lane), "", 1, False),
                     ("prefix " + completion(lane), "", 0, False),
                     (completion(lane).rstrip() + " extra\n", "", 0, False),
                     (completion(lane, "abc"), "", 0, False), ("Task completed.\n", "", 0, False),
                     (completion(lane, "abcdefxxxxxx"), "", 0, False)]
            for stdout, stderr, code, accepted in cases:
                with self.subTest(lane=lane, stdout=stdout, stderr=stderr, code=code):
                    proc = Mock(returncode=code)
                    proc.communicate.return_value = stdout, stderr
                    with patch.object(prsi.subprocess, "Popen", return_value=proc):
                        result, receipt = prsi._run_rsi_delegate(row(), 30, False, lane)
                    self.assertEqual(result, "rsi_awaiting_validation" if accepted else "rsi_failed")
                    self.assertEqual(receipt["lane"], lane)
                    if not accepted and code == 0:
                        self.assertEqual(receipt["reason"], "missing_delegate_receipt")

    def test_timeout_kills_process_group(self):
        for lane in ("codex", "local"):
            proc = Mock(pid=12345)
            proc.communicate.side_effect = [prsi.subprocess.TimeoutExpired("fake", 60),
                                             prsi.subprocess.TimeoutExpired("fake", 10), ("", "")]
            with patch.object(prsi.subprocess, "Popen", return_value=proc), patch.object(prsi.os, "killpg") as kill:
                result, receipt = prsi._run_rsi_delegate(row(), 30, False, lane)
            self.assertEqual(result, "rsi_stalled")
            self.assertEqual(receipt, {"lane": lane, "reason": "delegate_timeout"})
            self.assertEqual([c.args for c in kill.call_args_list],
                             [(12345, prsi.signal.SIGTERM), (12345, prsi.signal.SIGKILL)])

    def test_stale_running_reconciled_at_dispatch_start(self):
        stale, recent, pending, foreign = row(700, "rsi_running"), row(650, "rsi_running"), row(700), row(700, "rsi_running")
        foreign["raw_action"]["source"] = "other"
        with patch.object(prsi.subprocess, "Popen", side_effect=AssertionError("real delegate forbidden")):
            code, output, rows = self.dispatch(rows=[stale, recent, pending, foreign])
        self.assertEqual(code, 0)
        self.assertEqual(output["lane"], "codex")
        self.assertEqual([r["status"] for r in rows], ["rsi_failed", "rsi_running", "rsi_pending", "rsi_running"])
        self.assertEqual(rows[0]["execution"]["receipt"], {"lane": "codex", "reason": "stale_running"})
        self.assertEqual(rows[0]["rsi_attempts"], 1)
        _, _, rows = self.dispatch(["--timeout-seconds", "30"], [row(91, "rsi_running")])
        self.assertEqual(rows[0]["status"], "rsi_failed")
        exhausted = row(700, "rsi_running")
        exhausted["rsi_attempts"] = 3
        _, _, rows = self.dispatch(rows=[exhausted])
        self.assertEqual(rows[0]["status"], "rsi_stalled")
        self.assertEqual(rows[0]["execution"]["receipt"]["reason"], "stale_running")

    def test_invalid_policy_lane_fails_before_launch(self):
        prsi.PRSI_POLICY_FILE.write_text(json.dumps({"rsi": {"repair_lane": "../invalid"}}))
        code, output, _ = self.dispatch(["--execute"])
        self.assertEqual(code, 1)
        self.assertEqual(output["message"], "invalid_repair_lane")
    def test_multi_lane_cooldown_fallback(self):
        policy = {"rsi": {"repair_lanes": ["codex", "claude", "antigravity", "local"]}}
        prsi.PRSI_POLICY_FILE.write_text(json.dumps(policy))
        delegation_dir = self.root / "delegation"
        delegation_dir.mkdir(parents=True, exist_ok=True)
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. codex on cooldown -> falls back to claude
        (delegation_dir / ".codex-quota-cooldown").write_text(future)
        proc = Mock(returncode=0)
        proc.communicate.return_value = (completion("claude"), "")
        with patch.dict("os.environ", {"AQ_DELEGATION_DIR": str(delegation_dir)}), \
             patch.object(prsi.subprocess, "Popen", return_value=proc):
            code, output, rows = self.dispatch(["--execute"])
        self.assertEqual(code, 0)
        self.assertEqual(output["lane"], "claude")
        self.assertEqual(rows[0]["execution"]["receipt"]["lane"], "claude")
        self.assertEqual(rows[0]["execution"]["receipt"]["substituted_from"], "codex")

        # 2. codex and claude on cooldown -> falls back to antigravity
        (delegation_dir / ".claude-quota-cooldown").write_text(future)
        proc.communicate.return_value = (completion("antigravity"), "")
        with patch.dict("os.environ", {"AQ_DELEGATION_DIR": str(delegation_dir)}), \
             patch.object(prsi.subprocess, "Popen", return_value=proc):
            code, output, rows = self.dispatch(["--execute"])
        self.assertEqual(code, 0)
        self.assertEqual(output["lane"], "antigravity")
        self.assertEqual(rows[0]["execution"]["receipt"]["lane"], "antigravity")
        self.assertEqual(rows[0]["execution"]["receipt"]["substituted_from"], "codex")

        # 3. codex, claude, and antigravity on cooldown -> falls back to local
        (delegation_dir / ".antigravity-quota-cooldown").write_text(future)
        proc.communicate.return_value = (completion("local"), "")
        with patch.dict("os.environ", {"AQ_DELEGATION_DIR": str(delegation_dir)}), \
             patch.object(prsi.subprocess, "Popen", return_value=proc):
            code, output, rows = self.dispatch(["--execute"])
        self.assertEqual(code, 0)
        self.assertEqual(output["lane"], "local")
        self.assertEqual(rows[0]["execution"]["receipt"]["lane"], "local")
        self.assertEqual(rows[0]["execution"]["receipt"]["substituted_from"], "codex")


if __name__ == "__main__":
    unittest.main(verbosity=2)
