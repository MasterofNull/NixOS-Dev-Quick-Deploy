#!/usr/bin/env python3
"""Unit and isolation tests for mcp-rea-sandboxed launcher (W1-S2)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAUNCHER = REPO_ROOT / "scripts" / "ai" / "mcp-rea-sandboxed"


class TestReaSandbox(unittest.TestCase):
    def test_launcher_executable_exists(self):
        self.assertTrue(LAUNCHER.exists(), f"Launcher does not exist at {LAUNCHER}")
        self.assertTrue(os.access(LAUNCHER, os.X_OK), "Launcher is not executable")

    def test_refuses_when_candidate_state_not_enabled(self):
        # Currently rea-reverse-engineering is in state 'proposed' (pre-W1-S3 activation)
        proc = subprocess.run(
            [str(LAUNCHER), "--", "echo", "should_fail"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(proc.returncode, 2, f"Expected admission failure return code 2, got: {proc.returncode}")
        self.assertIn("REJECT", proc.stderr)

    def test_admission_passes_when_enabled(self):
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as tmp_cand, \
             tempfile.NamedTemporaryFile("w+", encoding="utf-8") as tmp_cat:
            cand_data = {
                "candidates": [
                    {"id": "rea-reverse-engineering", "state": "enabled"}
                ]
            }
            cat_data = {"capabilities": {"rea-reverse-engineering": {"status": "enabled"}}}
            json.dump(cand_data, tmp_cand)
            json.dump(cat_data, tmp_cat)
            tmp_cand.flush()
            tmp_cat.flush()

            verify_script = f"""
import json, sys
candidate_doc = json.loads(open("{tmp_cand.name}").read())
catalog_doc = json.loads(open("{tmp_cat.name}").read())
candidate = next((item for item in candidate_doc.get("candidates", []) if item.get("id") == "rea-reverse-engineering"), None)
if not candidate or candidate.get("state") not in ("accepted", "enabled"):
    sys.exit(2)
sys.exit(0)
"""
            res = subprocess.run(["python3", "-c", verify_script])
            self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
