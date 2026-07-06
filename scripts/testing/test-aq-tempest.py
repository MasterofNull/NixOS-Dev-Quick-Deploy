#!/usr/bin/env python3
"""Regression checks for the safe T3MP3ST intake facade."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CMD = ROOT / "scripts" / "ai" / "aq-tempest"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CMD), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def run_json(*args: str) -> dict:
    return json.loads(run(*args, "--json").stdout)


def main() -> int:
    status = run_json("status")
    assert status["id"] == "t3mp3st"
    assert status["state"] == "blocked-security-intake"
    assert status["active_execution"] == "blocked"
    assert status["prd"] == ".agent/PROJECT-T3MP3ST-CAPABILITY-INTAKE-PRD.md"
    assert "dual-use-offensive-security" in status["risk_flags"]
    assert "network-active-scanning" in status["risk_flags"]
    assert status["permissions"]["network"] == "blocked-until-scope-gated"
    assert status["unsafe_tool_count"] == 0

    gates = run_json("gates")
    joined_gates = "\n".join(gates["required_gates"]).lower()
    assert "scope receipts" in joined_gates
    assert "human approval" in joined_gates
    assert "mcp/tool admission deny-by-default" in joined_gates
    assert "dashboard or aq-report" in joined_gates

    audit = run_json("audit")
    assert audit["report"]["id"] == "t3mp3st"
    assert audit["report"]["admission"] in {"needs-review", "review-recommended", "blocked"}

    for command in ("install", "run", "server", "mcp", "scan", "exploit", "mission", "war-room"):
        proc = run(command, check=False)
        assert proc.returncode == 2, command
        assert "blocked-security-intake" in proc.stderr
        assert "active execution is disabled" in proc.stderr

    print("PASS: aq-tempest safe intake facade checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
