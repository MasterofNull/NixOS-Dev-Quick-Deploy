#!/usr/bin/env python3
"""Regression checks for the system capability catalog SSOT."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "config" / "system-capability-catalog.json"
CMD = ROOT / "scripts" / "ai" / "aq-capability-catalog"


def run(*args: str) -> str:
    proc = subprocess.run(
        [str(CMD), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return proc.stdout


def main() -> int:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in payload["entries"]}

    for required in (
        "capability-intake",
        "auto-skill-selection",
        "tooling-manifest",
        "local-agent-delegation",
        "playwright-mcp",
        "semgrep-mcp",
        "github-mcp-readonly",
        "t3mp3st-intake",
        "understand-anything",
        "local-surface-research",
        "osint-research-store",
        "aidb-rag-stores",
    ):
        assert required in entries, f"missing catalog entry: {required}"

    for external_id in ("playwright-mcp", "semgrep-mcp", "github-mcp-readonly"):
        security = entries[external_id]["security"]
        assert security["intake_candidate_id"], f"{external_id} missing intake candidate link"
        assert security["risk"] == "high", f"{external_id} should stay high-risk gated"

    assert "local-agent" in entries["local-agent-delegation"]["agent_access"]
    assert entries["t3mp3st-intake"]["state"] == "enabled"
    assert entries["t3mp3st-intake"]["security"]["admission"] == "metadata-only-blocked-external-dual-use"
    assert entries["understand-anything"]["security"]["intake_candidate_id"] == "code-intelligence-graph-layer"
    assert "validate-batches" in entries["understand-anything"]["security"]["required_gate"]
    assert entries["local-surface-research"]["state"] == "enabled"
    assert "aq-local-surface-scan" in " ".join(entries["local-surface-research"]["primary_refs"])
    assert "osint-intelligence" in entries["osint-research-store"]["data_stores"]

    validate_out = run("validate")
    assert "PASS:" in validate_out
    check_out = run("check-doc")
    assert "PASS:" in check_out

    print("PASS: system capability catalog checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
