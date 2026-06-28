#!/usr/bin/env python3
"""Regression checks for automatic local skill selection."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CMD = ROOT / "scripts" / "ai" / "aq-skill-auto"


def run_auto(task: str, *extra: str) -> dict:
    proc = subprocess.run(
        [str(CMD), task, "--json", *extra],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(proc.stdout)


def names(payload: dict) -> set[str]:
    return set(payload["reference_skills"])


def main() -> int:
    plugin_payload = run_auto("review and import a new MCP plugin with security checks", "--agent", "codex")
    assert "capability-intake" in names(plugin_payload)
    assert names(plugin_payload) & {"mcp-server", "mcp-builder", "security-scanner"}

    dashboard_payload = run_auto("test dashboard visual behavior with browser automation", "--agent", "codex")
    assert names(dashboard_payload) & {"webapp-testing", "understand-anything", "frontend-design"}

    nix_payload = run_auto("debug NixOS service module deployment failure", "--agent", "local")
    assert len(nix_payload["reference_skills"]) <= 2
    assert names(nix_payload) & {"nixos-system", "nixos-deployment", "debug-workflow"}

    loop_payload = run_auto("recursive self improvement loop should select and test skills", "--agent", "codex", "--test")
    assert "self-improvement" in names(loop_payload)
    assert loop_payload["reference_checks"]["ok"] is True
    assert loop_payload["validation"]

    print("PASS: automatic skill selection checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
