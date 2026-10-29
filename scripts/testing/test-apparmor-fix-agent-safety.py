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

    def _run_agent(self, denials):
        """Run agent.main() on a temp nix file; return (rc, stdout, stderr, queued, nix_text)."""
        out, err, queued = io.StringIO(), io.StringIO(), []
        stdin = io.StringIO(json.dumps({"denials": denials}))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.nix"
            p.write_text(NIX)
            with patch.object(agent, "NIX_FILE", p), \
                 patch.object(agent, "push", lambda **k: queued.append(k) or "A1"), \
                 patch.object(agent, "_update_handoff", lambda *a, **k: None), \
                 patch.object(agent, "_seed_rag", lambda *a, **k: None), \
                 patch.object(agent, "_push_memory_fact", lambda *a, **k: None), \
                 patch.object(agent, "_emit_training_event", lambda *a, **k: None), \
                 patch.object(sys, "argv", ["x", "--profile", "x", "--input-json", "-"]), \
                 patch.object(sys, "stdin", stdin), \
                 redirect_stdout(out), redirect_stderr(err):
                rc = agent.main()
            return rc, out.getvalue(), err.getvalue(), queued, p.read_text()

    def test_mixed_batch_rejected_whole(self):
        rc, out, err, queued, nix = self._run_agent([
            {"operation": "open", "path": "/etc/ok.conf", "mask": "r"},
            {"operation": "open", "path": "/etc/${evil}", "mask": "r"}])
        self.assertNotIn(rc, (0, 2))
        self.assertNotEqual(rc, 0)
        self.assertEqual(queued, [])
        self.assertEqual(nix, NIX)
        self.assertIn("REJECTED", err)
        self.assertIn("rejected: 1 rule(s) failed validation", json.loads(out)["message"])

    def test_all_rejected_not_reported_as_covered(self):
        rc, out, err, queued, nix = self._run_agent([
            {"operation": "open", "path": "/etc/${evil}", "mask": "r"}])
        self.assertNotIn(rc, (0, 2))
        self.assertNotIn("already covered", out)
        self.assertEqual(queued, [])
        self.assertEqual(nix, NIX)

    def _approve(self, rules, nix_text):
        mod = SourceFileLoader("aqa", str(ROOT / "scripts/ai/aq-approve")).load_module()
        alert = {"id": "A1", "status": "pending", "executor": "apparmor_fix",
                 "payload": {"profile": "x", "rules_proposed": rules}}
        ran, fin = [], []
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            nix = Path(d) / "nix" / "modules" / "services" / "mcp-servers.nix"
            nix.parent.mkdir(parents=True)
            nix.write_text(nix_text)
            with patch.object(mod, "_REPO_ROOT", Path(d)), \
                 patch.object(mod, "get_by_id", lambda i: alert), \
                 patch.object(mod, "claim_for_execution", lambda i, a: (True, "", alert)), \
                 patch.object(mod, "finalize_claim", lambda i, ok, **k: fin.append((ok, k)) or True), \
                 patch.dict(mod._EXECUTOR_TABLE, {"apparmor_fix": lambda a: ran.append(a) or True}), \
                 redirect_stdout(out), redirect_stderr(err):
                rc = mod.approve_alert("A1", "t")
        return rc, out.getvalue(), ran, fin

    def test_approve_invalid_rule_in_comment_not_approved(self):
        nix = "security.apparmor.policies.\"x\" = {\n  profile = ''\n    # capability sys_admin,\n    deny /home/** wx,\n  '';\n};\n"
        rc, out, ran, fin = self._approve(["capability sys_admin,"], nix)
        self.assertNotEqual(rc, 0)
        self.assertNotIn("Approved", out)
        self.assertEqual(ran, [])
        self.assertEqual([f[0] for f in fin], [False])

    def test_approve_comment_or_other_profile_not_present(self):
        mod = SourceFileLoader("aqa2", str(ROOT / "scripts/ai/aq-approve")).load_module()
        nix = ("security.apparmor.policies.\"x\" = {\n  profile = ''\n    # /a/b r,\n    deny /home/** wx,\n  '';\n};\n"
               "security.apparmor.policies.\"y\" = {\n  profile = ''\n    /c/d r,\n  '';\n};\n")
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "nix" / "modules" / "services" / "mcp-servers.nix"
            f.parent.mkdir(parents=True)
            f.write_text(nix)
            with patch.object(mod, "_REPO_ROOT", Path(d)):
                self.assertFalse(mod._apparmor_rules_already_present("x", ["/a/b r,"]))
                self.assertFalse(mod._apparmor_rules_already_present("x", ["/c/d r,"]))
                self.assertTrue(mod._apparmor_rules_already_present("y", ["/c/d r,"]))


if __name__ == "__main__":
    unittest.main()
