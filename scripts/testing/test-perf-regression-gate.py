#!/usr/bin/env python3
"""
test-perf-regression-gate.py — SOTA Performance Regression Gate verification.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts/governance/tier0.d/check-perf-regression.sh"


def test_gate_execution():
    assert SCRIPT.is_file(), f"Missing script: {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), f"Script not executable: {SCRIPT}"

    res = subprocess.run([str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, f"check-perf-regression failed: {res.stderr}"
    assert "[tier0.d/check-perf-regression] PASS" in res.stdout
    print("PASS: check-perf-regression gate fast-path validated")


def main():
    test_gate_execution()
    print("ALL PERF REGRESSION GATE TESTS PASSED")


if __name__ == "__main__":
    main()
