#!/usr/bin/env python3
"""aq-rsi CLI tests: isolated ledger/queue via env, no services, no model calls."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "ai" / "aq-rsi"


def _iso(hours_ago):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


class AqRsiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.queue = t / "queue.json"
        self.env = dict(os.environ, RSI_RUNTIME_DIR=str(t), RSI_BACKLOG_FILE=str(t / "backlog.md"),
                        RSI_WORKAROUNDS_FILE=str(t / "wa.md"), PRSI_ACTION_QUEUE_PATH=str(self.queue),
                        A2A_EVENT_LOG=str(t / "events.jsonl"), REDIS_URL="redis://127.0.0.1:1/0")
        self.env.pop("PRSI_INCIDENTS_FILE", None)
        (t / "rsi-incidents.json").write_text(json.dumps({"version": 1, "incidents": {}}))

    def run_cli(self, *args):
        r = subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True,
                           env=self.env, timeout=10)
        return r.stdout, r.stderr, r.returncode

    def write_queue(self, actions):
        self.queue.write_text(json.dumps({"actions": actions}))

    @staticmethod
    def row(rid, status, **kw):
        return {"id": rid, "status": status, "risk": "high",
                "raw_action": {"source": "rsi-incidents.json", "incident_id": "inc-" + rid}, **kw}

    def test_report_fast_dedupes_and_redacts(self):
        t0 = time.monotonic()
        out1, _, rc1 = self.run_cli("report", "hook denied token=abc123", "--subject", "a")
        out2, _, rc2 = self.run_cli("report", "hook denied token=abc123", "--subject", "b")
        self.assertEqual((rc1, rc2), (0, 0))
        self.assertLess((time.monotonic() - t0) / 2, 2.0)
        self.assertEqual(json.loads(out1)["incident"], json.loads(out2)["incident"])
        ledger = json.loads((Path(self.tmp.name) / "rsi-incidents.json").read_text())
        (inc,) = ledger["incidents"].values()
        self.assertEqual(inc["count"], 2)
        self.assertNotIn("abc123", json.dumps(ledger))

    def test_report_bad_severity_exits_2(self):
        _, err, rc = self.run_cli("report", "x", "--severity", "bogus")
        self.assertEqual(rc, 2)
        self.assertIn("severity", err)

    def test_status_alert_pending_over_24h_zero_executed(self):
        self.write_queue([self.row("r1", "rsi_pending", created_at=_iso(30))])
        out, _, rc = self.run_cli("status", "--json")
        data = json.loads(out)
        self.assertEqual(rc, 1)
        self.assertEqual(data["executed"], 0)
        self.assertGreater(data["oldest_pending_age_hours"], 24)
        self.assertTrue(data["alerts"])

    def test_status_counts_lanes_skips_stalled(self):
        self.write_queue([
            self.row("r1", "rsi_awaiting_validation", rsi_attempts=1, created_at=_iso(2),
                     execution={"receipt": {"lane": "codex"}}),
            self.row("r2", "rsi_stalled", rsi_attempts=3, execution={"receipt": {"lane": "local"}}),
            self.row("r3", "rsi_pending", created_at=_iso(1),
                     execution={"result": "skipped_verifier_required"}),
        ])
        out, _, rc = self.run_cli("status", "--json")
        data = json.loads(out)
        self.assertEqual(data["executed"], 2)
        self.assertEqual(data["stalled"], 1)
        self.assertEqual(data["skipped"], {"skipped_verifier_required": 1})
        self.assertEqual(set(data["per_lane"]), {"codex", "local"})
        self.assertEqual(rc, 1)  # stalled => not healthy

    def test_status_missing_or_corrupt_incident_ledger_is_unknown(self):
        self.write_queue([self.row("r1", "rsi_awaiting_validation", rsi_attempts=1, created_at=_iso(1),
                                   execution={"receipt": {"lane": "codex"}})])
        ledger = Path(self.tmp.name) / "rsi-incidents.json"
        ledger.unlink()
        for body in (None, "{not json"):  # missing, then corrupt
            if body is not None:
                ledger.write_text(body)
            out, _, rc = self.run_cli("status", "--json")
            data = json.loads(out)
            self.assertEqual((rc, data["state"], data["healthy"]), (2, "unknown", None), body)
            self.assertIn("incident ledger", data["error"])
        ledger.write_text(json.dumps({"incidents": {}}))
        self.assertEqual(self.run_cli("status", "--json")[2], 0)

    def test_status_missing_queue_is_unknown_not_healthy(self):
        out, _, rc = self.run_cli("status", "--json")
        data = json.loads(out)
        self.assertEqual((rc, data["state"], data["healthy"]), (2, "unknown", None))

    def test_pending_delegates(self):
        self.write_queue([self.row("r1", "rsi_pending", approval={})])
        out, _, rc = self.run_cli("pending", "--count")
        self.assertEqual((rc, out.strip()), (0, "1"))

    def test_approve_bind_stores_scoped_expiring_approval(self):
        t = Path(self.tmp.name)
        (t / "rsi-incidents.json").write_text(json.dumps({"incidents": {"inc-r1": {
            "id": "inc-r1", "producer": "p", "path": "x", "authority": "a", "error": "e"}}}))
        self.write_queue([self.row("r1", "rsi_pending")])
        out, err, rc = self.run_cli("approve", "r1", "--bind", "--scope", "apply", "--ttl", "120")
        self.assertEqual(rc, 0, err)
        self.assertIn("scope=apply", out)
        rec = json.loads((t / "rsi-approvals.json").read_text())["inc-r1"]
        self.assertEqual((rec["scope"], rec["by"]), ("apply", "owner"))
        self.assertEqual(len(rec["subject_sha256"]), 64)
        _, err, rc = self.run_cli("approve", "r1", "--bind", "--ttl", "99999999")
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(self.queue.read_text())["actions"][0]["status"], "rsi_pending")

    def test_approve_prints_command_only(self):
        self.write_queue([self.row("r1", "rsi_pending")])
        for key in ("r1", "inc-r1"):
            out, _, rc = self.run_cli("approve", key)
            self.assertEqual(rc, 0)
            self.assertIn("verify --id r1 --by owner", out)
        _, _, rc = self.run_cli("approve", "nope")
        self.assertEqual(rc, 1)
        self.assertEqual(json.loads(self.queue.read_text())["actions"][0]["status"], "rsi_pending")


if __name__ == "__main__":
    unittest.main()
