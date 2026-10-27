#!/usr/bin/env python3
"""
test-supply-chain-provenance-gate.py — SOTA Supply Chain SBOM & SLSA Gate verification.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts/governance/tier0.d/check-supply-chain-provenance.sh"


def test_supply_chain_gate():
    assert SCRIPT.is_file(), f"Missing script: {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), f"Script not executable: {SCRIPT}"

    res = subprocess.run([str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, f"check-supply-chain-provenance failed: {res.stderr}"
    assert "[tier0.d/check-supply-chain-provenance] PASS" in res.stdout
    print("PASS: check-supply-chain-provenance gate execution validated")


def main():
    test_supply_chain_gate()
    print("ALL SUPPLY CHAIN PROVENANCE GATE TESTS PASSED")


if __name__ == "__main__":
    main()
