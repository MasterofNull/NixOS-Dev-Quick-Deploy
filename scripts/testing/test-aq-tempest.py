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
    assert status["state"] == "ready-scope-gated"
    assert status["active_execution"] == "scope-gated-runtime-pending"
    assert status["prd"] == ".agent/PROJECT-T3MP3ST-CAPABILITY-INTAKE-PRD.md"
    assert "dual-use-offensive-security" in status["risk_flags"]
    assert "network-active-scanning" in status["risk_flags"]
    assert status["permissions"]["network"] == "scope-gated-local-only"
    assert status["unsafe_tool_count"] == 0
    assert status["scope_receipts"] == ".agent/security-scope-receipts"

    gates = run_json("gates")
    joined_gates = "\n".join(gates["required_gates"]).lower()
    assert "scope receipts" in joined_gates
    assert "human approval" in joined_gates
    assert "mcp/tool admission deny-by-default" in joined_gates
    assert "dashboard or aq-report" in joined_gates

    audit = run_json("audit")
    assert audit["report"]["id"] == "t3mp3st"
    assert audit["report"]["admission"] == "accepted-with-mitigations"
    assert audit["report"]["pinned_version"] == "ae32cf505174a422c55d7ca970f5f23816218f38"

    scope = run_json(
        "scope-create",
        "--name",
        "test-localhost",
        "--targets",
        "127.0.0.1,10.0.0.0/24",
        "--approved-by",
        "test-operator",
        "--purpose",
        "regression test",
        "--expires-at",
        "2099-01-01T00:00:00Z",
    )
    assert scope["ok"] is True
    checked = run_json("scope-check", "test-localhost")
    assert checked["ok"] is True
    refused = run(
        "scope-create",
        "--name",
        "public",
        "--targets",
        "8.8.8.8",
        "--approved-by",
        "test-operator",
        "--purpose",
        "regression test",
        "--expires-at",
        "2099-01-01T00:00:00Z",
        check=False,
    )
    assert refused.returncode == 2
    assert "refusing public" in refused.stderr

    for command in ("install", "run", "server", "mcp", "scan", "exploit", "mission", "war-room"):
        proc = run(command, check=False)
        assert proc.returncode == 2, command
        assert "requires a valid local scope receipt" in proc.stderr
    scoped = run("scan", "--scope", "test-localhost", check=False)
    assert scoped.returncode == 3
    assert "runtime is not attached yet" in scoped.stderr
    receipt = ROOT / ".agent" / "security-scope-receipts" / "test-localhost.json"
    if receipt.exists():
        receipt.unlink()

    print("PASS: aq-tempest safe intake facade checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
