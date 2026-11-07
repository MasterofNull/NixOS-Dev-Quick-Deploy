#!/usr/bin/env python3
"""Smoke test for destructive-tool interception in the safety control layer."""

import asyncio
import os
import json
import tempfile
import sys
from pathlib import Path

# tool_registry lives in ai-stack/local-agents (on PYTHONPATH in the deployed units).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-stack" / "local-agents"))
from tool_registry import ToolRegistry, ToolDefinition, ToolCall, SafetyPolicy, ToolCategory

async def test_safety_interception():
    print("--- Testing Safety Control Layer Interception ---")

    # The safety layer writes proposals under a cwd-relative .agent/proposals; keep that in a temp dir.
    with tempfile.TemporaryDirectory(prefix="safety-layer-test-") as tmp:
        previous_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            await _run_interception_check(Path(tmp) / "tool_audit.db")
        finally:
            os.chdir(previous_cwd)


async def _run_interception_check(db_path):
    registry = ToolRegistry(db_path=db_path)
    
    # Register a "dangerous" tool
    async def destructive_handler(cmd: str):
        return f"Executed {cmd}"
        
    tool = ToolDefinition(
        name="destructive_tool",
        description="A dangerous tool",
        parameters={"type": "object", "properties": {"cmd": {"type": "string"}}},
        category=ToolCategory.SHELL,
        safety_policy=SafetyPolicy.DESTRUCTIVE, # Should trigger interception
        handler=destructive_handler
    )
    registry.register(tool)
    
    # Attempt to call it
    call = ToolCall(
        id="test-intercept",
        tool_name="destructive_tool",
        arguments={"cmd": "rm -rf /"},
        model_id="test-agent"
    )
    
    print(f"Executing {call.tool_name}...")
    result = await registry.execute_tool_call(call)
    
    print(f"Status: {result.status}")
    print(f"Result: {json.dumps(result.result, indent=2)}")
    
    if result.status == "intercepted":
        print("\nSUCCESS: Action was intercepted and turned into a proposal.")
    else:
        print("\nFAILURE: Action was NOT intercepted.")
        raise SystemExit(1)

if __name__ == "__main__":
    asyncio.run(test_safety_interception())
