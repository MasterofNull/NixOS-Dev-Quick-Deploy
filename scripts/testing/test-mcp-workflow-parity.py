#!/usr/bin/env python3
"""Focused MCP-to-AQD retrofit workflow parity proof."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "scripts/ai/mcp-bridge-hybrid.py"
SPEC = importlib.util.spec_from_file_location("mcp_bridge_workflow_parity", BRIDGE_PATH)
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def retrofit_schema() -> dict:
    for tool in bridge.TOOLS:
        if tool["name"] == "retrofit_workflow":
            return tool["inputSchema"]
    raise AssertionError("retrofit_workflow schema missing")


def main() -> int:
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(argv: list[str], cwd: str | None = None, timeout: int = 30) -> dict:
        calls.append((argv, cwd))
        return {"ok": True, "argv": argv}

    original_run_local = bridge._run_local
    original_subprocess_run = bridge.subprocess.run
    bridge._run_local = fake_run
    bridge.subprocess.run = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("subprocess must be mocked"))
    try:
        schema = retrofit_schema()
        properties = schema["properties"]
        assert properties["stack"]["enum"] == list(bridge.RETROFIT_STACK_CHOICES)
        assert "confirm_retrofit" in properties

        target = str((ROOT / "bridge workflow fixture").resolve())
        confirmation = "a" * 64
        result = json.loads(bridge._call_tool("retrofit_workflow", {
            "target_dir": target,
            "project_name": "fixture",
            "goal": "prove parity",
            "stack": "python",
            "owner": "test",
            "force": True,
            "confirm_retrofit": confirmation,
        }))
        assert result["ok"]
        argv, cwd = calls.pop()
        assert cwd == target
        assert argv == [
            bridge.AQD_BIN, "workflows", "retrofit", "--target", target,
            "--name", "fixture", "--goal", "prove parity", "--stack", "python",
            "--owner", "test", "--force", "--confirm-retrofit", confirmation,
        ]

        bridge._call_tool("retrofit_workflow", {"target_dir": target, "force": True})
        argv, cwd = calls.pop()
        assert cwd == target and "--force" in argv and "--confirm-retrofit" not in argv

        bridge._call_tool("retrofit_workflow", {"target_dir": target})
        argv, cwd = calls.pop()
        assert cwd == target and "--stack" not in argv and "--confirm-retrofit" not in argv

        for stack in ("java", "", 0, False, [], {}):
            invalid = json.loads(bridge._call_tool("retrofit_workflow", {"target_dir": target, "stack": stack}))
            assert invalid["ok"] is False and "invalid retrofit stack" in invalid["error"]
            assert not calls
    finally:
        bridge._run_local = original_run_local
        bridge.subprocess.run = original_subprocess_run

    print("AQ_QA_MCP_WORKFLOW_PARITY=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
