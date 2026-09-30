#!/usr/bin/env python3
"""Regression checks for aq-capabilities — AQ-OS Capability Manifest & Readiness CLI.

Validates ST-3 (.agents/plans/factory-shared-toolchain/DESIGN.md):
- Manifest as declaration/record (append-live)
- Readiness check (WARNs on missing, never restricts runtime access)
- Strict mode check (exits 1 on missing when --strict is passed)
- Capability overview integration (tools, skills, workflows, roles, commands)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "ai" / "aq-capabilities"


def run_cmd(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_list_and_json() -> None:
    res = run_cmd("list", "--json")
    assert res.returncode == 0, f"aq-capabilities list failed: {res.stderr}"
    data = json.loads(res.stdout)
    assert "tools" in data
    assert len(data["tools"]) >= 8
    tool_names = {t["name"] for t in data["tools"]}
    assert {"playwright", "tmux", "watch", "ripgrep", "jq", "git"}.issubset(tool_names)
    print("PASS: test_list_and_json")


def test_check_preflight_non_blocking() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_manifest = Path(tmpdir) / "capabilities.json"
        # Seed manifest with an intentionally missing tool
        payload = {
            "schema_version": "1.0.0",
            "project": "test-proj",
            "declared_tools": [
                {"name": "nonexistent-tool-xyz-12345", "package": "nonexistent-pkg", "category": "custom"}
            ],
        }
        tmp_manifest.write_text(json.dumps(payload))

        # Non-strict mode MUST return 0 (WARN only, never gates access)
        res = run_cmd("--manifest", str(tmp_manifest), "check")
        assert res.returncode == 0, f"Expected non-blocking 0 exit, got {res.returncode}"
        assert "WARN: declared tool 'nonexistent-tool-xyz-12345'" in res.stdout

        # Strict mode MUST return 1
        res_strict = run_cmd("--manifest", str(tmp_manifest), "check", "--strict")
        assert res_strict.returncode == 1, f"Expected strict mode failure 1, got {res_strict.returncode}"
    print("PASS: test_check_preflight_non_blocking")


def test_add_live_tool() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_manifest = Path(tmpdir) / "capabilities.json"

        # Add a new tool
        res = run_cmd("--manifest", str(tmp_manifest), "add", "python313", "--name", "python", "--category", "runtime", "--required")
        assert res.returncode == 0, f"add failed: {res.stderr}"

        # Verify it was written
        assert tmp_manifest.is_file()
        data = json.loads(tmp_manifest.read_text())
        tools = data.get("declared_tools", [])
        assert any(t["name"] == "python" and t["package"] == "python313" for t in tools)
    print("PASS: test_add_live_tool")


def test_overview() -> None:
    res = run_cmd("overview", "--json")
    assert res.returncode == 0, f"overview failed: {res.stderr}"
    data = json.loads(res.stdout)
    assert data["status"] == "ready"
    caps = data["capabilities"]
    assert caps["skills"]["count"] >= 50
    assert caps["roles"]["count"] >= 5
    assert caps["tools"]["count"] >= 8
    print("PASS: test_overview")


def test_contribute() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_manifest = Path(tmpdir) / "capabilities.json"
        res = run_cmd("--manifest", str(tmp_manifest), "contribute", "hello", "--justification", "Minimal test tool", "--json")
        assert res.returncode == 0, f"contribute failed: {res.stderr}"
        data = json.loads(res.stdout)
        assert data["status"] == "proposed"
        assert data["package"] == "hello"
        assert "aq-tool hello" in data["live_command"]
        proposal_file = ROOT / data["proposal_file"]
        assert proposal_file.is_file()
        # Clean up temporary test proposal
        proposal_file.unlink()
    print("PASS: test_contribute")


def main() -> int:
    test_list_and_json()
    test_check_preflight_non_blocking()
    test_add_live_tool()
    test_contribute()
    test_overview()
    print("ALL aq-capabilities tests passed successfully!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
