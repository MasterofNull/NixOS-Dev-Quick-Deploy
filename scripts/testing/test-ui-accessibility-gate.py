#!/usr/bin/env python3
"""
test-ui-accessibility-gate.py — SOTA UI Accessibility Gate verification.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts/governance/tier0.d/check-ui-accessibility.sh"


def test_ui_accessibility_gate():
    assert SCRIPT.is_file(), f"Missing script: {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), f"Script not executable: {SCRIPT}"

    res = subprocess.run([str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, f"check-ui-accessibility failed: {res.stderr}"
    assert "[tier0.d/check-ui-accessibility] PASS" in res.stdout
    print("PASS: check-ui-accessibility gate execution validated")


def main():
    test_ui_accessibility_gate()
    print("ALL UI ACCESSIBILITY GATE TESTS PASSED")


if __name__ == "__main__":
    main()
