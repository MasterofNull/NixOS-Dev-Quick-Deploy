#!/usr/bin/env python3
"""
test-phase4-observability.py — Validation for Phase 4 of P.A.E.A.
"""

import unittest
from pathlib import Path
import subprocess
import time

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

class TestPhase4(unittest.TestCase):
    def test_tui_startup(self):
        # We can't easily test a TUI with Live in a script, 
        # but we can check if it has syntax errors and imports correctly.
        proc = subprocess.Popen(
            [str(REPO_ROOT / "scripts" / "ai" / "aq-tui-dashboard")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(2)
        poll = proc.poll()
        if poll is not None:
            # If it exited, check if it was an error
            if poll != 0:
                stdout, stderr = proc.communicate()
                self.fail(f"TUI exited with error: {stderr}")
        else:
            # It's running, so it probably works
            proc.terminate()
            proc.wait()

    def test_dashboard_html_mod(self):
        html = (REPO_ROOT / "dashboard.html").read_text()
        self.assertIn('id="panel-fleet"', html)
        self.assertIn('id="tab-fleet"', html)
        
    def test_dashboard_js_mod(self):
        js = (REPO_ROOT / "assets" / "dashboard.js").read_text()
        self.assertIn("function loadFleet()", js)
        self.assertIn("function initFleetDAG(data)", js)

if __name__ == "__main__":
    unittest.main()
