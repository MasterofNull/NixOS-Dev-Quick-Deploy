#!/usr/bin/env python3
"""Gemini lane refuses non-Gemini model ids; roster/fallback ids come from model-coordinator."""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELEGATE = ROOT / "scripts/ai/delegate-to-gemini"
CONFIG = ROOT / "config/model-coordinator.json"


class GeminiModelGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / "calls.log"
        stub = self.dir / "gemini"
        stub.write_text(f"#!/usr/bin/env bash\necho \"$@\" >> {self.log}\necho OK\n")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        self.stub = stub

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def delegate(self, model: str):
        deleg = self.dir / "deleg"
        deleg.mkdir(exist_ok=True)
        env = dict(os.environ, GEMINI_BIN=str(self.stub), AQ_DELEGATION_DIR=str(deleg))
        return subprocess.run([str(DELEGATE), "--role", "review", "--mode", "plan", "--wait",
                               "--model", model, "--prompt", "hi"],
                              capture_output=True, text=True, timeout=60, env=env, cwd=self.dir)

    def test_non_gemini_models_are_refused_before_any_call(self):
        for model in ("claude-opus-5-5-high", "claude-sonnet-5-5-low", "gpt-oss-120b-medium", "Claude-Opus-5-5"):
            with self.subTest(model=model):
                r = self.delegate(model)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("GEMINI_LANE_NON_GEMINI_MODEL", r.stderr)
                self.assertFalse(self.log.exists(), "CLI must not be invoked for a refused model")

    def test_gemini_models_pass_the_guard(self):
        r = self.delegate("gemini-4-hydrogen-low")
        self.assertNotIn("GEMINI_LANE_NON_GEMINI_MODEL", r.stdout + r.stderr)
        self.assertTrue(self.log.exists())
        self.assertIn("--model gemini-4-hydrogen-low", self.log.read_text())

    def test_coordinator_gemini_lane_is_consistent(self):
        lane = json.loads(CONFIG.read_text())["tiers"]["google"]["gemini_lane"]
        self.assertEqual(lane["required_id_prefix"], "gemini-")
        roster = lane["roster"]
        self.assertTrue(roster)
        for mid, entry in roster.items():
            self.assertTrue(mid.startswith("gemini-"), mid)
            self.assertTrue(entry["capabilities"] and entry["best_use"] and entry["role"], mid)
        for key in ("default", "fallback", "baseline_fallback"):
            self.assertTrue(lane[key].startswith("gemini-"), key)
        self.assertIn(lane["baseline_fallback"], roster)


if __name__ == "__main__":
    unittest.main(verbosity=2)
