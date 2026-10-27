#!/usr/bin/env python3
"""
test-coverage-gate.py — SOTA Test Coverage Enforcement Gate verification.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts/governance/tier0.d/check-test-coverage.sh"


def test_coverage_gate():
    assert SCRIPT.is_file(), f"Missing script: {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), f"Script not executable: {SCRIPT}"

    res = subprocess.run([str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, f"check-test-coverage failed: {res.stderr}"
    assert "[tier0.d/check-test-coverage] PASS" in res.stdout
    print("PASS: check-test-coverage gate execution validated")


def main():
    test_coverage_gate()
    print("ALL COVERAGE GATE TESTS PASSED")


if __name__ == "__main__":
    main()
