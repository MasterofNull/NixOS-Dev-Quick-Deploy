#!/usr/bin/env python3
"""Delegate failure classification + audit-pollution guard. Offline; no coordinator import."""
import ast
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "ai-stack/mcp-servers/hybrid-coordinator/core/status_service.py"
HTTP = ROOT / "ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py"
AUDIT = ROOT / "scripts/ai/lib/audit-write.sh"


def load_classifier():
    # status_service needs runtime-only PYTHONPATH wiring to import, so exec just the pure function.
    tree = ast.parse(STATUS.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_classify_failure_reason")
    ns = {"re": re}
    exec(compile(ast.Module([fn], []), str(STATUS), "exec"), ns)
    return ns["_classify_failure_reason"]


class Classification(unittest.TestCase):
    def test_real_categories_not_unknown(self):
        c = load_classifier()
        cases = {
            "worktree_handback_failed": "worktree_handback_failed",
            "codex usage limit reached, try again later": "quota_exceeded",
            "HTTP 429 too many requests": "quota_exceeded",
            "run cancelled by operator": "cancelled",
            "OSError [Errno 30] Read-only file system": "sandbox_denied",
            "delegate_timeout after 600s": "timeout",
            "http_status_502": "http_502",
            "failed mode=agent: Diagnose RSI incident 74724f": "agent_task_failed",
            "llama.cpp returned empty answer": "model_error",
            "": "empty_response",
            "some never-seen message": "unknown",
        }
        for msg, want in cases.items():
            self.assertEqual(c(msg), want, msg)

    def test_events_writer_uses_single_classifier(self):
        src = HTTP.read_text()
        self.assertIn("from core.status_service import _classify_failure_reason", src)
        self.assertNotIn("def _classify_failure_reason", src)


class AuditPollutionGuard(unittest.TestCase):
    def post(self, disable):
        with tempfile.TemporaryDirectory() as t:
            bindir = Path(t) / "bin"
            bindir.mkdir()
            log = Path(t) / "curl.log"
            (bindir / "curl").write_text(f'#!/bin/sh\necho called >> "{log}"\n')
            (bindir / "curl").chmod(0o755)
            env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}
            env.pop("AQ_AUDIT_DISABLE", None)
            if disable:
                env["AQ_AUDIT_DISABLE"] = "1"
            subprocess.run(["bash", "-c", f'source "{AUDIT}"; audit_event_end local task-x error 1 boom auto'],
                           env=env, check=True, capture_output=True)
            return log.exists()

    def test_disable_flag_prevents_post(self):
        self.assertTrue(self.post(disable=False))
        self.assertFalse(self.post(disable=True))

    def test_artifact_fixture_isolates_run_event_spool(self):
        text = (ROOT / "scripts/testing/test-local-delegation-artifact.py").read_text()
        self.assertIn('os.environ["AQ_AGENT_RUN_EVENTS_PATH"]', text)

    def test_worktree_isolation_fixture_disables_audit(self):
        self.assertIn('"AQ_AUDIT_DISABLE": "1"', (ROOT / "scripts/testing/test-worktree-isolation.py").read_text())


if __name__ == "__main__":
    unittest.main()
