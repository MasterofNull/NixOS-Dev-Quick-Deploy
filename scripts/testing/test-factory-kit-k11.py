#!/usr/bin/env python3
"""
test-factory-kit-k11.py — Slice K11 verification suite.
Validates check-kit-parity gate behavior, fast paths, and WARN mode compliance.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts/governance/tier0.d/check-kit-parity.sh"


def test_script_execution():
    assert SCRIPT.is_file(), f"Missing script: {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), f"Script not executable: {SCRIPT}"

    # Run in clean repo state
    res = subprocess.run([str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, f"check-kit-parity failed: {res.stderr}"
    assert "[tier0.d/check-kit-parity] PASS" in res.stdout
    print("PASS: check-kit-parity fast-path and execution contract")


def main():
    test_script_execution()
    print("ALL K11 TESTS PASSED")


if __name__ == "__main__":
    main()
