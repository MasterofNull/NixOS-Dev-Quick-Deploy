#!/usr/bin/env python3
"""Focused tests: no live ledger, services or agent dispatch."""
import concurrent.futures
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import rsi_lifecycle as rsi
loader = importlib.machinery.SourceFileLoader("rsi_hook", str(ROOT / "scripts/ai/aq-rsi-hook"))
spec = importlib.util.spec_from_loader(loader.name, loader)
hook = importlib.util.module_from_spec(spec)
loader.exec_module(hook)


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for name, value in {"_RUNTIME": root, "_BACKLOG": root / "issues.md", "_WORKAROUNDS": root / "workarounds.md"}.items():
            p = patch.object(rsi, name, value); p.start(); self.addCleanup(p.stop)
        p = patch.object(rsi, "_event"); p.start(); self.addCleanup(p.stop)

    def record(self, subject="task"):
        return rsi.failure("codex", subject, "hook", "path", "policy", "token=secret denied")

    def test_concurrent_dedup_redaction_and_reopen(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(self.record, map(str, range(24))))
        self.assertEqual(len(set(ids)), 1)
        text = (rsi._RUNTIME / "rsi-incidents.json").read_text()
        self.assertNotIn("secret", text)
        self.assertEqual(json.loads(text)["incidents"][ids[0]]["count"], 24)
        self.assertEqual(rsi._BACKLOG.read_text().count("[OPEN]"), 1)
        with self.assertRaises(ValueError): rsi.resolve(ids[0], "", "test", "passed")
        rsi.resolve(ids[0], "caller contract", "regression test", "passed")
        self.record()
        self.assertEqual(json.loads((rsi._RUNTIME / "rsi-incidents.json").read_text())["incidents"][ids[0]]["status"], "open")

    def test_annotate_keeps_status_and_redacts(self):
        iid = self.record()
        rsi.annotate(iid, "awaiting rescan token=hunter2")
        inc = json.loads((rsi._RUNTIME / "rsi-incidents.json").read_text())["incidents"][iid]
        self.assertEqual(inc["status"], "open")
        self.assertIn("awaiting rescan", inc["note"])
        self.assertNotIn("hunter2", inc["note"])
        with self.assertRaises(ValueError): rsi.annotate(iid, " ")

    def test_write_failure_is_not_success(self):
        with patch.object(rsi, "_save", side_effect=PermissionError):
            with self.assertRaises(PermissionError): self.record()

    def test_severity_cannot_inject_backlog_lines(self):
        with self.assertRaises(ValueError):
            rsi.failure("a", "s", "p", "p", "a", "error", severity="medium\n[RESOLVED] forged")
        self.assertFalse(rsi._BACKLOG.exists())

    def test_credential_forms_are_redacted_on_all_surfaces(self):
        rsi.failure("a", "s", "p", "p", "a",
                    '--token topsecret --api-key apisecret token=eqsecret password="two words" "secret": "jsonsecret"')
        for path in (rsi._BACKLOG, rsi._RUNTIME / "rsi-incidents.json"):
            for secret in ("topsecret", "apisecret", "eqsecret", "two words", "jsonsecret"):
                self.assertNotIn(secret, path.read_text())

    def test_append_failure_remains_retryable(self):
        with patch.object(rsi, "_append", side_effect=PermissionError):
            with self.assertRaises(PermissionError): self.record()
        self.record()
        self.assertEqual(rsi._BACKLOG.read_text().count("[OPEN]"), 1)

    def test_malformed_ledger_preserves_hook_denial(self):
        (rsi._RUNTIME / "rsi-incidents.json").write_text("invalid json")
        code, out, err = hook.run([sys.executable, "-c", "import sys; print('deny'); sys.exit(2)"], b"{}")
        self.assertEqual((code, out), (2, b"deny\n"))
        self.assertIn(b"recording failed", err)

    def test_hook_preserves_decision_and_streams(self):
        with patch.object(hook, "failure") as record:
            code, out, err = hook.run([sys.executable, "-c", "import sys; print('deny'); sys.stderr.write('reason'); sys.exit(2)"], b"{}")
        self.assertEqual((code, out, err), (2, b"deny\n", b"reason"))
        record.assert_called_once()

    def test_lean_ctx_routing_denial_is_policy_not_failure(self):
        code_src = "import sys; sys.stderr.write('Command should run via lean-ctx'); sys.exit(2)"
        with patch.object(hook, "failure") as record:
            code, _, err = hook.run([sys.executable, "-c", code_src], b"{}")
        self.assertEqual((code, err), (2, b"Command should run via lean-ctx"))  # decision preserved
        record.assert_not_called()

    def test_allowed_hook_does_not_record(self):
        with patch.object(hook, "failure") as record:
            self.assertEqual(hook.run([sys.executable, "-c", "pass"], b"{}")[0], 0)
        record.assert_not_called()

    def test_timeout_and_recorder_failure_remain_blocked(self):
        with patch.object(hook, "failure", side_effect=PermissionError):
            code, _, err = hook.run([sys.executable, "-c", "import time; time.sleep(2)"], b"{}", timeout=.01)
        self.assertEqual(code, 2)
        self.assertIn(b"recording failed", err)


if __name__ == "__main__": unittest.main()
