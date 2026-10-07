#!/usr/bin/env python3
"""Infra-failure classifier, no-attempt-consumption dispatch, and rsi-requeue. Offline; temp queue only."""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_INCIDENTS_TMP = tempfile.TemporaryDirectory(prefix="prsi-incidents-test-")
os.environ["PRSI_INCIDENTS_FILE"] = str(Path(_INCIDENTS_TMP.name) / "rsi-incidents.json")

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prsi_requeue", ROOT / "scripts/automation/prsi-orchestrator.py")
prsi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prsi)

INFRA = {"exit_code": 1, "lane": "codex", "stderr_tail": "touch: cannot touch '/x/registry.jsonl': Read-only file system\n"}
QUALITY = {"exit_code": 1, "lane": "codex", "stderr_tail": "tests failed: assertion error\n"}


def row(rid="r1", status="rsi_pending", approved=True, receipt=None, **extra):
    r = {"id": rid, "type": "maintenance", "risk": "low", "status": status, "rsi_attempts": 0,
         "estimated_token_cost": 1,
         "raw_action": {"source": "rsi-incidents.json", "reason": "rsi-incident-open", "incident_id": "rsi-test"},
         "execution": {"receipt": receipt} if receipt else {}}
    if approved:
        r["approval"] = {"verifier_by": "owner"}
    r.update(extra)
    return r


class Classifier(unittest.TestCase):
    def test_classifier(self):
        c = prsi._is_infra_failure
        self.assertTrue(c(INFRA))
        for tail in ("bash: x: Permission denied", "EROFS: nope", "EACCES", "foo: command not found",
                     "env: 'codex': No such file or directory",
                     "delegate-to-codex: line 3: /bin/x: No such file or directory"):
            self.assertTrue(c({"exit_code": 2, "stderr_tail": tail}), tail)
        self.assertFalse(c({**INFRA, "exit_code": 0}))
        self.assertFalse(c(QUALITY))
        self.assertFalse(c({"exit_code": 1, "stderr_tail": "open data.txt: No such file or directory"}))
        self.assertFalse(c({"exit_code": 1, "reason": "delegate_timeout", "stderr_tail": "Permission denied"}))
        self.assertFalse(c(None))
        self.assertFalse(c({"lane": "codex", "reason": "delegate_timeout"}))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ("QUEUE_PATH", "PRSI_STATE_PATH", "PRSI_POLICY_FILE", "ACTIONS_LOG_PATH", "_RSI_DISPATCH_LOCK"):
            self.enterContext(patch.object(prsi, name, self.root / name))

    def run_cmd(self, argv, fn):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = fn(prsi.build_parser().parse_args(argv))
        return code, json.loads(out.getvalue())

    def rows(self):
        return {r["id"]: r for r in prsi._load_queue()["actions"]}


class Requeue(Base):
    def test_requeue(self):
        good = row("good", "rsi_stalled", receipt=INFRA, rsi_attempts=3)
        exhausted = row("exh", "rsi_stalled", receipt=QUALITY, rsi_attempts=1, rsi_infra_failures=6)
        exhausted["execution"]["reason"] = "infra_failures_exhausted"
        quality = row("q", "rsi_stalled", receipt=QUALITY, rsi_attempts=3)
        unapproved = row("u", "rsi_stalled", approved=False, receipt=INFRA)
        pending = row("p", "rsi_pending")
        prsi._save_queue({"actions": [good, exhausted, quality, unapproved, pending]})

        _, out = self.run_cmd(["rsi-requeue", "--dry-run"], prsi.cmd_rsi_requeue)
        self.assertEqual(sorted(out["requeued"]), ["exh", "good"])
        self.assertEqual(self.rows()["good"]["status"], "rsi_stalled")  # nothing written

        code, out = self.run_cmd(["rsi-requeue", "--id", "good", "--id", "q", "--id", "u", "--id", "nope"], prsi.cmd_rsi_requeue)
        self.assertEqual(code, 0)
        self.assertEqual(out["requeued"], ["good"])
        self.assertEqual(out["skipped"], {"q": "not_infra_failure", "u": "not_owner_approved", "nope": "not_found"})
        rows = self.rows()
        g = rows["good"]
        self.assertEqual((g["status"], g["rsi_attempts"], g["rsi_infra_failures"]), ("rsi_pending", 0, 0))
        self.assertEqual(g["approval"], {"verifier_by": "owner"})
        h = g["execution"]["requeue_history"][0]
        self.assertEqual((h["prior_status"], h["prior_attempts"], h["reason"]), ("rsi_stalled", 3, "infra_failure"))
        self.assertEqual(rows["q"]["status"], "rsi_stalled")
        self.assertEqual(rows["exh"]["status"], "rsi_stalled")

        self.run_cmd(["rsi-requeue"], prsi.cmd_rsi_requeue)
        self.assertEqual(self.rows()["exh"]["status"], "rsi_pending")


class Dispatch(Base):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(prsi, "cmd_sync", return_value=0))
        self.enterContext(patch.object(prsi, "_rsi_open_incident_ids", return_value=(True, {"rsi-test"})))
        self.enterContext(patch.object(prsi, "_rsi_dispatch_preflight", return_value=(True, "isolated_worktree_required")))

    def dispatch(self, receipt):
        with patch.object(prsi, "_run_rsi_delegate", return_value=("rsi_failed", receipt)):
            return self.run_cmd(["rsi-dispatch", "--execute"], prsi.cmd_rsi_dispatch)

    def test_infra_failure_refunds_attempt_and_stalls_after_six(self):
        prsi._save_queue({"actions": [row()]})
        for i in range(1, 6):
            self.dispatch(INFRA)
            r = self.rows()["r1"]
            self.assertEqual((r["status"], r["rsi_attempts"], r["rsi_infra_failures"]), ("rsi_pending", 0, i))
            self.assertEqual(r["execution"]["result"], "infra_error")
            self.assertEqual(r["execution"]["receipt"]["exit_code"], 1)
        self.dispatch(INFRA)
        r = self.rows()["r1"]
        self.assertEqual((r["status"], r["execution"]["reason"]), ("rsi_stalled", "infra_failures_exhausted"))
        self.assertEqual(r["rsi_attempts"], 0)

    def test_quality_failure_still_consumes_attempt(self):
        prsi._save_queue({"actions": [row()]})
        self.dispatch(QUALITY)
        r = self.rows()["r1"]
        self.assertEqual((r["status"], r["rsi_attempts"], r["rsi_infra_failures"]), ("rsi_failed", 1, 0))


if __name__ == "__main__":
    unittest.main()
