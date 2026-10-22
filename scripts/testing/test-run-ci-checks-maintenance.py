#!/usr/bin/env python3
"""Test run-ci-checks.sh --maintenance behavior (W6-S7).

Verifies:
1. --maintenance runs all checks and sets mode to 'all'.
2. Missing tools under CI=true produce FAIL in normal mode, but WARN under --maintenance mode.
"""
import os
import subprocess
import sys
import tempfile
import json

def test_maintenance_flag_missing_tool_surfaces_warn():
    # Setup temporary manifest
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = os.path.join(tmpdir, "ci-checks.json")
        manifest_data = {
            "checks": [
                {
                    "id": "nonexistent-tool-check",
                    "paths": ["**/*"],
                    "needs": ["nonexistent_binary_xyz_12345"],
                    "cmd": "true"
                }
            ]
        }
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        runner = os.path.abspath("scripts/governance/run-ci-checks.sh")

        # Test 1: CI=true, normal --all mode -> FAIL on missing tool
        env_ci = os.environ.copy()
        env_ci["CI"] = "true"
        env_ci["CI_CHECKS_MANIFEST"] = manifest_path
        p1 = subprocess.run([runner, "--all"], capture_output=True, text=True, env=env_ci)
        assert p1.returncode != 0, f"Expected non-zero exit code under CI=true, got {p1.returncode}"
        assert "[FAIL] nonexistent-tool-check: missing tool" in p1.stdout, f"Expected FAIL in output, got: {p1.stdout}"

        # Test 2: CI=true, --maintenance mode -> WARN on missing tool, exit code 0
        p2 = subprocess.run([runner, "--maintenance"], capture_output=True, text=True, env=env_ci)
        assert p2.returncode == 0, f"Expected 0 exit code under --maintenance, got {p2.returncode}. Output:\n{p2.stdout}\n{p2.stderr}"
        assert "[WARN] nonexistent-tool-check: missing tool" in p2.stdout, f"Expected WARN in output, got: {p2.stdout}"

    print("PASS: test_maintenance_flag_missing_tool_surfaces_warn")

if __name__ == "__main__":
    test_maintenance_flag_missing_tool_surfaces_warn()
