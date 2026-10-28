#!/usr/bin/env python3
"""
test-property-security-primitives.py — SOTA Property-Based Security Gate verification.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts/governance/tier0.d/check-property-security-primitives.sh"


def test_property_security_gate():
    assert SCRIPT.is_file(), f"Missing script: {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), f"Script not executable: {SCRIPT}"

    res = subprocess.run([str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, f"check-property-security-primitives failed: {res.stderr}"
    assert "[tier0.d/check-property-security-primitives] PASS" in res.stdout
    print("PASS: check-property-security-primitives gate execution validated")


def main():
    test_property_security_gate()
    print("ALL PROPERTY SECURITY GATE TESTS PASSED")


if __name__ == "__main__":
    main()
