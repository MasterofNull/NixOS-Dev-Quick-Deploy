#!/usr/bin/env python3
"""Lifecycle + admission-control checks for delegate-to-claude (stub provider)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DelegateClaudeLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        lib = self.repo / "scripts/ai/lib"
        lib.mkdir(parents=True)
        (self.repo / "config").mkdir()
        (self.repo / ".agents/delegation/outputs").mkdir(parents=True)
        self.wrapper = self.repo / "scripts/ai/delegate-to-claude"
        shutil.copy2(ROOT / "scripts/ai/delegate-to-claude", self.wrapper)
        shutil.copy2(ROOT / "scripts/ai/lib/claude-background-worker.sh", lib)
        shutil.copy2(ROOT / "config/model-coordinator.json", self.repo / "config")
        (lib / "audit-write.sh").write_text(
            "audit_event_start() { :; }\naudit_event_end() { :; }\naudit_save_session() { :; }\n")
        (lib / "harness-grounding.sh").write_text("harness_grounding() { :; }\n")
        (lib / "audit-post.sh").write_text("exit 0\n")
        self.fake = Path(self.temp.name) / "claude"
        self.fake.write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys, time\n"
            "time.sleep(float(os.environ.get('FAKE_SLEEP', '0')))\n"
            "print('STUB_OUTPUT')\n"
            "sys.exit(int(os.environ.get('FAKE_EXIT', '0')))\n")
        self.fake.chmod(0o755)
        self.env = {
            **os.environ,
            "CLAUDE_BIN": str(self.fake),
            "HOME": self.temp.name,
            "DELEGATE_CLAUDE_HEARTBEAT_S": "1",
        }
        self.procs: list[subprocess.Popen] = []

    def tearDown(self) -> None:
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
        self.temp.cleanup()

    def run_wrapper(self, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.wrapper), *args], cwd=self.repo, env={**self.env, **env},
            text=True, capture_output=True, timeout=30, check=False)

    def spawn(self, *args: str, **env: str) -> subprocess.Popen:
        p = subprocess.Popen(
            [str(self.wrapper), *args], cwd=self.repo, env={**self.env, **env},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.procs.append(p)
        return p

    def registry(self) -> list[dict]:
        path = self.repo / ".agents/delegation/registry.jsonl"
        if not path.exists():
            return []
        return [json.loads(x) for x in path.read_text().splitlines() if x]

    def wait_for(self, pred, timeout: float = 10.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if pred():
                return True
            time.sleep(0.1)
        return False

    # -- defect 1: terminal reconciliation ---------------------------------
    def test_provider_failure_records_terminal_failed_with_exit_code(self) -> None:
        r = self.run_wrapper("--wait", "--prompt", "x", FAKE_EXIT="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self.registry()[-1]
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["exit_code"], 1)
        self.assertTrue(row.get("finished_at"))
        self.assertIn("STUB_OUTPUT", r.stdout)

    def test_success_records_done_exit_zero(self) -> None:
        r = self.run_wrapper("--wait", "--prompt", "x")
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self.registry()[-1]
        self.assertEqual((row["status"], row["exit_code"]), ("done", 0))

    def test_pid_and_heartbeat_recorded_while_running(self) -> None:
        p = self.spawn("--wait", "--prompt", "x", FAKE_SLEEP="4")
        self.assertTrue(self.wait_for(lambda: self.registry() and self.registry()[-1].get("pid")))
        row = self.registry()[-1]
        self.assertEqual(row["status"], "running")
        self.assertIsInstance(row["pid"], int)
        first = row["heartbeat_at"]
        self.assertTrue(self.wait_for(lambda: self.registry()[-1].get("heartbeat_at") != first, 6))
        p.communicate(timeout=20)
        self.assertEqual(self.registry()[-1]["status"], "done")

    def test_killed_wrapper_still_reconciles_terminal(self) -> None:
        p = self.spawn("--wait", "--prompt", "x", FAKE_SLEEP="30")
        self.assertTrue(self.wait_for(lambda: self.registry() and self.registry()[-1].get("pid")))
        pid = self.registry()[-1]["pid"]
        p.terminate()
        p.communicate(timeout=20)
        row = self.registry()[-1]
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["exit_code"], 143)
        try:
            os.kill(pid, 9)
        except OSError:
            pass

    def test_background_failure_records_terminal(self) -> None:
        r = self.run_wrapper("--prompt", "x", FAKE_EXIT="3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.wait_for(lambda: self.registry()[-1]["status"] != "running"))
        row = self.registry()[-1]
        self.assertEqual((row["status"], row["exit_code"]), ("failed", 3))

    # -- defect 2: admission control ---------------------------------------
    def test_daily_cap_refuses_with_exit_3_and_force_overrides(self) -> None:
        env = {"DELEGATE_CLAUDE_DAILY_DISPATCH_CAP": "2"}
        for _ in range(2):
            self.assertEqual(self.run_wrapper("--wait", "--prompt", "x", **env).returncode, 0)
        r = self.run_wrapper("--wait", "--prompt", "x", **env)
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("cap", r.stderr)
        self.assertEqual(len(self.registry()), 2)  # refusal leaves no ghost row
        self.assertEqual(self.run_wrapper("--budget-check-only", **env).returncode, 3)
        forced = self.run_wrapper("--wait", "--prompt", "x", "--force-budget", **env)
        self.assertEqual(forced.returncode, 0, forced.stderr)

    def test_parallel_limit_and_reviewer_floor(self) -> None:
        env = {"DELEGATE_CLAUDE_MAX_PARALLEL": "2", "FAKE_SLEEP": "6"}
        a = self.spawn("--wait", "--prompt", "impl-a", **env)
        self.assertTrue(self.wait_for(lambda: len(self.registry()) == 1))
        # second implementer: only the reserved review slot remains -> refused
        r = self.run_wrapper("--wait", "--prompt", "impl-b", **env)
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("slot", r.stderr)
        self.assertEqual(len(self.registry()), 1)
        # reviewer is admitted into the reserved slot
        b = self.spawn("--wait", "--role", "review", "--prompt", "rev", **env)
        self.assertTrue(self.wait_for(lambda: len(self.registry()) == 2))
        # all slots now full: even a reviewer is refused
        r2 = self.run_wrapper("--wait", "--role", "review", "--prompt", "rev2", **env)
        self.assertEqual(r2.returncode, 3, r2.stderr)
        a.communicate(timeout=30)
        b.communicate(timeout=30)
        self.assertTrue(all(x["status"] == "done" for x in self.registry()))
        # slots released after completion
        self.assertEqual(self.run_wrapper("--wait", "--prompt", "again").returncode, 0)


if __name__ == "__main__":
    unittest.main()
