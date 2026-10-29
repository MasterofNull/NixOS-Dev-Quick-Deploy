#!/usr/bin/env python3
"""Tests for scripts/governance/check-activation-manifest.py using temp repos."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts/governance/check-activation-manifest.py"
sys.path.insert(0, str(ROOT / "scripts/governance/lib"))
from clean_git_env import clean_git_env  # noqa: E402

OPTIONS_NIX = "{ options.services.aiFoo = { enable = lib.mkEnableOption \"foo\"; }; }\n"
MODULE_NIX = "{ config = { services.aiFoo.enable = true; }; }\n"


def sh(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env=clean_git_env())


def entry(**kw):
    e = {"feature": "foo", "entrypoint": "scripts/ai/aq-foo", "live_caller": "scripts/ai/caller.sh",
         "enable": None, "health_signal": "scripts/ai/health.py:foo_health", "deferral": None}
    e.update(kw)
    return e


class Case(unittest.TestCase):
    def make_repo(self, features, files=None, new_files=None):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        base_files = {
            "scripts/ai/aq-foo": "#!/bin/sh\n",
            "scripts/ai/caller.sh": "aq-foo run\n",
            "scripts/ai/health.py": "def foo_health(): pass\n",
            "nix/modules/core/options.nix": OPTIONS_NIX,
            "nix/profiles/p.nix": "{ }\n",
            "config/activation-manifest.json": json.dumps({"schema_version": 1, "features": features}),
        }
        base_files.update(files or {})
        for rel, text in base_files.items():
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        sh(tmp, "init", "-q", "-b", "main")
        sh(tmp, "config", "user.email", "t@example.invalid")
        sh(tmp, "config", "user.name", "t")
        sh(tmp, "add", "-A")
        sh(tmp, "commit", "-q", "-m", "base")
        for rel, text in (new_files or {}).items():
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
            sh(tmp, "add", rel)
        return tmp

    def run_check(self, repo, *extra):
        r = subprocess.run([sys.executable, str(CHECKER), "--repo-root", str(repo), *extra],
                           capture_output=True, text=True, env=clean_git_env())
        return r.returncode, r.stdout

    def test_fully_wired_passes(self):
        repo = self.make_repo([entry(enable="services.aiFoo.enable")],
                              files={"nix/profiles/p.nix": MODULE_NIX})
        rc, out = self.run_check(repo, "--staged")
        self.assertEqual(rc, 0, out)

    def test_new_aq_script_without_entry_fails(self):
        repo = self.make_repo([entry()], new_files={"scripts/ai/aq-bar": "#!/bin/sh\n"})
        rc, out = self.run_check(repo, "--staged")
        self.assertEqual(rc, 1, out)
        self.assertIn("scripts/ai/aq-bar", out)

    def test_new_systemd_unit_without_entry_fails(self):
        repo = self.make_repo([entry()], new_files={
            "nix/modules/other.nix": "{ systemd.services.aq-baz = { }; }\n"})
        rc, out = self.run_check(repo, "--staged")
        self.assertEqual(rc, 1, out)
        self.assertIn("aq-baz", out)

    def test_live_caller_not_referencing_fails(self):
        repo = self.make_repo([entry()], files={"scripts/ai/caller.sh": "nothing here\n"})
        rc, out = self.run_check(repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("does not reference", out)

    def test_enable_unset_without_deferral_fails(self):
        repo = self.make_repo([entry(enable="services.aiFoo.enable")])
        rc, out = self.run_check(repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("set to true nowhere", out)

    def test_enable_set_only_in_declaring_module_fails(self):
        repo = self.make_repo([entry(enable="services.aiFoo.enable")],
                              files={"nix/modules/core/options.nix": OPTIONS_NIX + MODULE_NIX})
        rc, _ = self.run_check(repo)
        self.assertEqual(rc, 1)

    def test_missing_health_symbol_fails(self):
        repo = self.make_repo([entry(health_signal="scripts/ai/health.py:nope")])
        rc, out = self.run_check(repo)
        self.assertEqual(rc, 1, out)
        self.assertIn("health_signal symbol", out)

    def test_deferred_entry_passes(self):
        d = {"date": date.today().isoformat(), "reason": "no caller yet", "tracking": "backlog"}
        repo = self.make_repo([entry(enable="services.aiFoo.enable", deferral=d)],
                              files={"scripts/ai/caller.sh": "nothing\n"})
        rc, out = self.run_check(repo)
        self.assertEqual(rc, 0, out)

    def test_stale_deferral_warns_only(self):
        old = (date.today() - timedelta(days=200)).isoformat()
        d = {"date": old, "reason": "waiting", "tracking": "backlog"}
        repo = self.make_repo([entry(enable="services.aiFoo.enable", deferral=d)])
        rc, out = self.run_check(repo)
        self.assertEqual(rc, 0, out)
        self.assertIn("WARN", out)

    def test_invalid_deferral_fails(self):
        repo = self.make_repo([entry(deferral={"date": "yesterday", "reason": ""})])
        rc, _ = self.run_check(repo)
        self.assertEqual(rc, 1)

    def test_new_script_with_entry_passes(self):
        repo = self.make_repo([entry(entrypoint="scripts/ai/aq-bar", live_caller="scripts/ai/caller.sh")],
                              files={"scripts/ai/caller.sh": "aq-bar\n"},
                              new_files={"scripts/ai/aq-bar": "#!/bin/sh\n"})
        rc, out = self.run_check(repo, "--staged")
        self.assertEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
