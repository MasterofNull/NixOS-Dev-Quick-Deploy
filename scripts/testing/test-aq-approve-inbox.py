#!/usr/bin/env python3
"""Regression test for aq-approve approval inbox (temp files only)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CLI = REPO / "scripts" / "ai" / "aq-approve"


def inc(i, status, sev="high"):
    return {"id": i, "status": status, "severity": sev, "agent": "t", "error": f"err {i}", "path": "p"}


class T(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        rsi = {"id": "row1", "status": "rsi_pending", "risk": "high", "approval": {},
               "raw_action": {"source": "rsi-incidents.json", "incident_id": "inc1"}}
        ver = {"id": "row2", "status": "rsi_pending", "risk": "high", "approval": {"verifier_by": "owner"},
               "raw_action": {"source": "rsi-incidents.json", "incident_id": "inc3"}}
        plain = {"id": "row3", "status": "pending_approval", "risk": "medium", "action": "prefer_local",
                 "raw_action": {"type": "routing"}}
        (self.d / "q.json").write_text(json.dumps({"actions": [rsi, ver, plain]}))
        self.ledger = {"incidents": {"inc1": inc("inc1", "open"), "inc2": inc("inc2", "open", "low"),
                                     "inc3": inc("inc3", "resolved")}}
        (self.d / "led.json").write_text(json.dumps(self.ledger))
        (self.d / "attn").mkdir()
        self.env = dict(os.environ, PRSI_ACTION_QUEUE_PATH=str(self.d / "q.json"),
                        PRSI_INCIDENTS_FILE=str(self.d / "led.json"),
                        ATTENTION_QUEUE_DIR=str(self.d / "attn"),
                        ATTENTION_MIRROR_PATH=str(self.d / "mirror.json"),
                        AQ_APPROVAL_INBOX_DIR=str(self.d / "inbox"),
                        PRSI_ACTIONS_LOG_PATH=str(self.d / "actions.jsonl"))

    def run_cli(self, *a, cwd="/"):
        return subprocess.run([sys.executable, str(CLI), *a], capture_output=True, text=True,
                              env=self.env, cwd=cwd, timeout=90)

    def listing(self):
        return json.loads(self.run_cli("--json").stdout)

    def test_all(self):
        out = self.run_cli()
        self.assertEqual(out.returncode, 0, out.stderr)
        lines = out.stdout.splitlines()
        self.assertTrue(lines[0].startswith("Approval inbox [tag "))
        self.assertIn("Needs approval (2)", out.stdout)
        self.assertIn("Deferred (1)", out.stdout)
        self.assertLess(out.stdout.index("1. [high]"), out.stdout.index("Deferred"))
        j = self.listing()
        self.assertEqual([i["key"] for i in j["items"]], ["prsi:row1", "prsi:row3", "rsi:inc2"])
        self.assertEqual([i["section"] for i in j["items"]], ["approval", "approval", "deferred"])
        tag = j["tag"]
        self.assertEqual(self.listing()["tag"], tag)
        self.assertEqual(self.run_cli("--summary").stdout.strip(),
                         "Approval inbox: 2 need approval, 1 deferred (aq-approve)")

        # stale tag -> exit 3, nothing written
        r = self.run_cli("approve", "1", "--tag", "deadbeef")
        self.assertEqual(r.returncode, 3)
        self.assertIn("Inbox changed since tag deadbeef", r.stdout)
        self.assertFalse((self.d / "inbox").exists())
        q = json.loads((self.d / "q.json").read_text())
        self.assertFalse(q["actions"][0]["approval"].get("verifier_by"))

        # approve deferred refused
        r = self.run_cli("approve", "3", "--tag", tag)
        self.assertEqual(r.returncode, 2)
        self.assertIn("nothing to approve", r.stdout)

        # dismiss deferred: hidden, ledger unchanged, tag changes
        r = self.run_cli("dismiss", "3", "--tag", tag, "--door", "chat", "--note", "later")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        j2 = self.listing()
        self.assertNotEqual(j2["tag"], tag)
        self.assertEqual(len(j2["items"]), 2)
        self.assertEqual(json.loads((self.d / "led.json").read_text()), self.ledger)
        dis = json.loads((self.d / "inbox" / "approval-inbox.json").read_text())["dismissed"]
        self.assertEqual(dis["rsi:inc2"]["door"], "chat")

        # approve 1 on RSI row
        r = self.run_cli("approve", "1", "--tag", j2["tag"], "--door", "chat", "--note", "ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        q = json.loads((self.d / "q.json").read_text())
        self.assertEqual(q["actions"][0]["approval"]["verifier_by"], "owner")
        recs = [json.loads(l) for l in (self.d / "inbox" / "approval-inbox-audit.jsonl").read_text().splitlines()]
        self.assertEqual([x["action"] for x in recs], ["approve", "dismiss", "approve"])
        self.assertEqual(recs[2]["door"], "chat")
        self.assertEqual(recs[2]["key"], "prsi:row1")
        # signed-off incident is in repair, not deferred (live 2026-10-02 regression)
        j3 = json.loads(self.run_cli("--json").stdout)
        self.assertNotIn("rsi:inc1", [i["key"] for i in j3["items"]])

    def test_empty_and_legacy(self):
        (self.d / "q.json").write_text(json.dumps({"actions": []}))
        (self.d / "led.json").write_text(json.dumps({"incidents": {}}))
        self.assertEqual(self.run_cli("--summary").stdout.strip(), "Approval inbox: empty")
        r = self.run_cli("--help")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Usage: aq-approve [--actor LABEL] <alert-id>", r.stdout)
        r = self.run_cli("attn-nonexist")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not found", r.stderr)


if __name__ == "__main__":
    unittest.main()
