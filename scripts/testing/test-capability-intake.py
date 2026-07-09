#!/usr/bin/env python3
"""Regression checks for aq-capability-intake."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CMD = REPO_ROOT / "scripts" / "ai" / "aq-capability-intake"


def run_json(*args: str) -> dict:
    proc = subprocess.run(
        [str(CMD), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    listing = run_json("list", "--json")
    ids = {item["id"] for item in listing}
    assert "playwright-mcp" in ids
    assert "semgrep-mcp" in ids
    assert "mcp-admission-controller" in ids
    assert "t3mp3st" in ids

    all_report = run_json("audit", "--all", "--json")
    reports = {item["id"]: item for item in all_report["reports"]}
    assert reports["playwright-mcp"]["admission"] == "accepted-with-mitigations"
    assert "unpinned-version" not in reports["playwright-mcp"]["risk_flags"]
    assert "dynamic-installer:npx" in reports["playwright-mcp"]["risk_flags"]
    assert reports["semgrep-mcp"]["admission"] == "accepted-with-mitigations"
    assert "unpinned-version" not in reports["semgrep-mcp"]["risk_flags"]
    assert reports["mcp-admission-controller"]["admission"] == "accepted-with-mitigations"
    assert reports["mcp-admission-controller"]["state"] == "enabled"
    assert reports["github-mcp-readonly"]["admission"] == "accepted-with-mitigations"
    assert reports["github-mcp-readonly"]["state"] == "enabled"
    assert reports["github-mcp-readonly"]["unsafe_tool_count"] == 0
    assert reports["t3mp3st"]["state"] == "blocked-security-intake"
    assert reports["t3mp3st"]["admission"] in {"needs-review", "review-recommended", "blocked"}
    assert "dual-use-offensive-security" in reports["t3mp3st"]["risk_flags"]
    assert "network-active-scanning" in reports["t3mp3st"]["risk_flags"]
    assert reports["t3mp3st"]["unsafe_tool_count"] == 0

    one_report = run_json("audit", "semgrep-mcp", "--json")
    assert len(one_report["reports"]) == 1
    assert one_report["reports"][0]["id"] == "semgrep-mcp"

    print("PASS: capability intake checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
