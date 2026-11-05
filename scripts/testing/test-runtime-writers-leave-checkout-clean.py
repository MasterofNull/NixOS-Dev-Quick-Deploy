#!/usr/bin/env python3
"""P1.10 regression: scheduled/runtime producers must leave `git status` of the checkout clean.

Each case builds a throwaway git checkout holding the real lib code plus committed seeds, points the
producer at a separate state dir, runs it, and asserts (a) the checkout is still clean and (b) the
state dir received the write, seeded from the tracked file where one exists.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SEED_INCIDENT = {"version": 1, "incidents": {"seed-1": {"id": "seed-1", "status": "open", "count": 1}}}
FRONTIER_DIR = ".agents/plans/frontier-evidence-intake"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def make_checkout(tmp: Path) -> Path:
    co = tmp / "checkout"
    shutil.copytree(REPO / "scripts" / "ai" / "lib", co / "scripts" / "ai" / "lib",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (co / ".agent" / "collaboration").mkdir(parents=True)
    (co / ".agent" / "collaboration" / "rsi-incidents.json").write_text(json.dumps(SEED_INCIDENT))
    (co / ".agent" / "memory").mkdir(parents=True)
    (co / ".agent" / "memory" / "issues-backlog.md").write_text("# backlog\n")
    (co / FRONTIER_DIR).mkdir(parents=True)
    (co / FRONTIER_DIR / "BACKLOG.jsonl").write_text("")
    (co / FRONTIER_DIR / "scan-state.json").write_text(json.dumps(
        {"src": {"fingerprint": "a" * 64, "last_scan": "2020-01-01T00:00:00Z"}}))
    shutil.copy(REPO / ".gitignore", co / ".gitignore")  # real ignore rules (a2a spools etc.)
    git(co, "init", "-q")
    git(co, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(co, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed")
    return co


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("RSI_RUNTIME_DIR", "PRSI_INCIDENTS_FILE", "RSI_STATE_DIR", "FRONTIER_STATE_DIR", "REDIS_URL")}
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


def run_py(co: Path, code: str, env) -> str:
    p = subprocess.run([sys.executable, "-c", code], cwd=str(co), env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


class RuntimeWritersLeaveCheckoutClean(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.co = make_checkout(self.tmp)

    def tearDown(self):
        self._t.cleanup()

    def test_rsi_ledger_goes_to_state_dir_seeded_from_tracked(self):
        state = self.tmp / "rsi-state"
        state.mkdir()
        env = clean_env(RSI_STATE_DIR=str(state))
        run_py(self.co, (
            "import sys; sys.path.insert(0, 'scripts/ai/lib'); import rsi_lifecycle as r;"
            "r._BACKLOG = r._RUNTIME / 'unused.md';"
            "r.failure('agent','subj','prod','/p','auth','boom', severity='high', root_fix='x')"), env)
        self.assertEqual(git(self.co, "status", "--porcelain"), "")
        ledger = json.loads((state / "rsi-incidents.json").read_text())["incidents"]
        self.assertIn("seed-1", ledger)          # tracked seed carried over
        self.assertEqual(len(ledger), 2)          # plus the new incident
        self.assertEqual(json.loads((self.co / ".agent/collaboration/rsi-incidents.json").read_text()), SEED_INCIDENT)

    def test_rsi_unset_env_without_system_dir_falls_back_to_checkout(self):
        env = clean_env()
        run_py(self.co, (
            "import sys; sys.path.insert(0, 'scripts/ai/lib'); import rsi_paths;"
            "rsi_paths.DEFAULT_STATE_DIR = %r; import rsi_lifecycle as r;"
            "r.failure('agent','subj','prod','/p','auth','boom')" % str(self.tmp / "no-system-dir")), env)
        self.assertIn("rsi-incidents.json", git(self.co, "status", "--porcelain"))

    def _fails_closed(self, code, **env_extra):
        p = subprocess.run([sys.executable, "-c", code], cwd=str(self.co), env=clean_env(**env_extra),
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("StateDirError", p.stderr)
        return p.stderr

    def test_rsi_explicit_missing_state_dir_fails_closed(self):
        missing = str(self.tmp / "missing")
        err = self._fails_closed(
            "import sys; sys.path.insert(0, 'scripts/ai/lib'); import rsi_lifecycle", RSI_STATE_DIR=missing)
        self.assertIn(missing, err)
        self.assertEqual(git(self.co, "status", "--porcelain"), "")

    def test_rsi_explicit_unwritable_state_dir_fails_closed(self):
        ro = self.tmp / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            if os.access(ro, os.W_OK):
                self.skipTest("running as a user that bypasses DAC")
            self._fails_closed("import sys; sys.path.insert(0, 'scripts/ai/lib'); import rsi_lifecycle",
                               RSI_STATE_DIR=str(ro))
        finally:
            ro.chmod(0o700)

    def test_rsi_explicit_runtime_dir_and_incidents_file_fail_closed(self):
        code = "import sys; sys.path.insert(0, 'scripts/ai/lib'); import rsi_paths; rsi_paths.%s()"
        self._fails_closed(code % "runtime_dir", RSI_RUNTIME_DIR=str(self.tmp / "nope"))
        self._fails_closed(code % "incidents_path", PRSI_INCIDENTS_FILE=str(self.tmp / "nope" / "l.json"))

    def test_frontier_explicit_missing_state_dir_fails_closed(self):
        self._fails_closed(
            "import sys; sys.path.insert(0, 'scripts/ai/lib'); import frontier_backlog as fb; fb.load(fb.DEFAULT_STORE)",
            FRONTIER_STATE_DIR=str(self.tmp / "missing"))

    def test_frontier_unset_env_without_system_dir_falls_back(self):
        out = run_py(self.co, (
            "import sys; sys.path.insert(0, 'scripts/ai/lib'); import frontier_backlog as fb;"
            "fb.DEFAULT_STATE_DIR = %r; print(fb.state_dir())" % str(self.tmp / "no-system-dir")), clean_env())
        self.assertEqual(out.strip(), "None")

    def test_frontier_scan_writes_state_dir_and_overlay_is_visible(self):
        state = self.tmp / "frontier-state"
        state.mkdir()
        env = clean_env(FRONTIER_STATE_DIR=str(state))
        out = run_py(self.co, (
            "import sys, json, time; from pathlib import Path; sys.path.insert(0, 'scripts/ai/lib');"
            "import frontier_scan as fsc, frontier_backlog as fb;"
            "repo = Path('.').resolve(); sp, st = fsc.runtime_paths(repo);"
            "cat = {'sources': [{'id': 'src', 'name': 'S', 'url': 'https://example.invalid/', 'cadence': 'daily',"
            " 'pillar': 'p', 'trust_tier': 'primary'}]};"
            "res = fsc.scan_due(cat, state_path=sp, store=st, fetcher=lambda u, **k: {'text': 'changed'});"
            "print(json.dumps({'outcome': res['results'][0]['outcome'],"
            " 'visible': [r['id'] for r in fb.load(str(repo / fb.DEFAULT_STORE))]}))"), env)
        got = json.loads(out)
        self.assertEqual(got["outcome"], "candidate_filed")
        self.assertEqual(git(self.co, "status", "--porcelain"), "")
        self.assertTrue((state / "BACKLOG.jsonl").read_text().strip())
        self.assertTrue((state / "scan-state.json").exists())
        self.assertEqual(len(got["visible"]), 1)  # readers of the tracked store see the runtime candidate

    def test_frontier_triage_promotes_only_the_touched_candidate(self):
        state = self.tmp / "frontier-state"
        state.mkdir()
        env = clean_env(FRONTIER_STATE_DIR=str(state))
        run_py(self.co, (
            "import sys; from pathlib import Path; sys.path.insert(0, 'scripts/ai/lib'); import frontier_backlog as fb;"
            "ov = state = Path(%r) / 'BACKLOG.jsonl';"
            "rec = lambda i: {'id': i, 'technique': i, 'source': 's', 'claim': i, 'verdict': 'monitor', 'aqos_mapping': 'm',"
            " 'proposed_slice': 'p', 'acceptance_goal': 'a'};"
            "[fb.add(str(ov), rec(i)) for i in ('c1', 'c2')];"
            "assert fb.set_status(str(Path('.').resolve() / fb.DEFAULT_STORE), 'c1', 'deferred')['ok']" % str(state)), env)
        tracked = (self.co / FRONTIER_DIR / "BACKLOG.jsonl").read_text()
        self.assertIn('"c1"', tracked)
        self.assertNotIn('"c2"', tracked)

    def test_auto_update_run_never_touches_flake_inputs(self):
        spec_path = REPO / "scripts" / "testing" / "test-aq-auto-update.py"
        import importlib.util
        spec = importlib.util.spec_from_file_location("t_aq_auto_update", spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fx = mod.Fx(self.tmp / "au")
        git(fx.repo, "init", "-q")
        git(fx.repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(fx.repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed")
        p = fx.run("run")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(fx.status()["outcome"], "switched")
        self.assertNotIn("FLAKE_UPDATE", fx.calls())
        self.assertNotIn("PIN_WATCH", fx.calls())
        self.assertEqual(git(fx.repo, "status", "--porcelain", "--", "flake.lock"), "")


if __name__ == "__main__":
    unittest.main()
