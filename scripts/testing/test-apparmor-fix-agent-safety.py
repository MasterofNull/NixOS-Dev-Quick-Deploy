#!/usr/bin/env python3
"""Safety regressions: AppArmor rule allowlist, write-time re-validation,
failure reporting, and aq-approve rendering. Uses temp files only."""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
import apparmor_rules  # noqa: E402

_spec = importlib.util.spec_from_file_location("afa", ROOT / "scripts/automation/apparmor-fix-agent.py")
agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agent)

NIX = "profile = ''\n    /bin/sh ix,\n    deny /home/** wx,\n  '';\n"
BAD = [
    "/a r,\n/b rw,", "${pkgs.x} r,", "/x/${pkgs.x} r,", "/x rw, # c", "/x`id` r,",
    "/a/../etc/shadow r,", "/x\"y\" r,", "/x\x00 r,", "/x r,{", "/x rwx,", "capability sys_admin,",
    "/x/{a,b} r,", "ptrace read peer=a b,", "/x ''r,",
]
GOOD = [
    "            /proc/@{pids}/cmdline r,", "/dev/shm/sem.* rwk,", "/nix/store/**/bin/x ix,",
    "ptrace read peer=unconfined,", "signal (term kill) peer=unconfined,", "/ r,",
]


class T(unittest.TestCase):
    def test_validator(self):
        for r in BAD:
            self.assertIsNotNone(apparmor_rules.rule_error(r), r)
        for r in GOOD:
            self.assertIsNone(apparmor_rules.rule_error(r), r)

    def test_generated_rules_valid(self):
        for args in [("open", "/etc/foo.conf", "r"), ("exec", "/nix/store/abc-x/bin/y", "x"),
                     ("open", "/proc/123/stat", "r"), ("ptrace", "", "read", "unconfined"),
                     ("signal", "", "term", "unconfined")]:
            rule, cmt = agent._make_rule(*args)
            self.assertIsNone(apparmor_rules.rule_error(rule), rule)
            self.assertIsNone(apparmor_rules.comment_error(cmt), cmt)

    def _with_nix(self, fn):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.nix"
            p.write_text(NIX)
            with patch.object(agent, "NIX_FILE", p):
                fn(p)

    def test_write_rejects_injection_and_leaves_file(self):
        def run(p):
            for r in BAD:
                with redirect_stderr(io.StringIO()):
                    self.assertFalse(agent._insert_rules_for_profile("x", [(r, "c")]), r)
                self.assertEqual(p.read_text(), NIX)
            with redirect_stderr(io.StringIO()):
                self.assertFalse(agent._insert_rules_for_profile("x", [("/ok r,", "c ${x}")]))
                self.assertFalse(agent._insert_rules_for_profile("x", [("/ok r,", "ok"), ("${a} r,", "c")]))
            self.assertEqual(p.read_text(), NIX)
            self.assertTrue(agent._insert_rules_for_profile("x", [("            /ok/file r,", "ok")]))
            self.assertIn("/ok/file r,", p.read_text())
        self._with_nix(run)

    def _commit_staged(self, alert, nix_ok=True):
        out, err = io.StringIO(), io.StringIO()
        resolved = []
        with patch.object(agent, "get_by_id", lambda i: alert), \
             patch.object(agent, "resolve", lambda *a, **k: resolved.append(a)), \
             patch.object(agent, "_insert_rules_for_profile", wraps=agent._insert_rules_for_profile) as ins, \
             patch.object(sys, "argv", ["x", "--commit-staged", "--alert-id", "A1"]), \
             patch("subprocess.run", side_effect=AssertionError("no git/subprocess allowed")), \
             redirect_stdout(out), redirect_stderr(err):
            rc = agent.main()
        return rc, out.getvalue(), resolved

    def test_commit_staged_failure_not_approved(self):
        def run(p):
            rc, out, resolved = self._commit_staged(
                {"payload": {"profile": "x", "rules_proposed": ["/a r,\n/b rw,"]}})
            self.assertNotEqual(rc, 0)
            self.assertNotIn("committed", out)
            self.assertEqual(resolved, [])
            self.assertEqual(p.read_text(), NIX)
            rc, out, resolved = self._commit_staged(None)  # no alert
            self.assertNotEqual(rc, 0)
            self.assertEqual(resolved, [])
            # write failure (unwritable path) with a valid rule
            with patch.object(agent, "NIX_FILE", p.parent / "missing.nix"):
                rc, out, resolved = self._commit_staged(
                    {"payload": {"profile": "x", "rules_proposed": ["/a r,"]}})
            self.assertNotEqual(rc, 0)
            self.assertEqual(resolved, [])
        self._with_nix(run)

    def test_commit_staged_success_writes_without_git(self):
        def run(p):
            rc, out, resolved = self._commit_staged(
                {"payload": {"profile": "x", "rules_proposed": ["            /a/b r,"]}})
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out)["status"], "applied_uncommitted")
            self.assertEqual(len(resolved), 1)
            self.assertIn("/a/b r,", p.read_text())
        self._with_nix(run)

    def test_aq_approve_renders_rules(self):
        mod = SourceFileLoader("aqa", str(ROOT / "scripts/ai/aq-approve")).load_module()
        alert = {"executor": "apparmor_fix", "payload": {
            "profile": "p", "rules_proposed": ["            /a/b r,", "${pkgs.x} r,"]}}
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod._print_apparmor_rules(alert)
        o = buf.getvalue()
        self.assertIn("/a/b r,", o)
        self.assertIn("${pkgs.x} r,", o)
        self.assertIn("REJECTED", o)
        self.assertFalse(mod._handle_apparmor_fix({"id": "z", "payload": alert["payload"]}))


if __name__ == "__main__":
    unittest.main()
