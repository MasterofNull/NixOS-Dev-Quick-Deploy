import asyncio
import os
import json
from tool_registry import ToolRegistry, ToolDefinition, ToolCall, SafetyPolicy, ToolCategory

async def test_safety_interception():
    print("--- Testing Safety Control Layer Interception ---")
    
    registry = ToolRegistry()
    
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

if __name__ == "__main__":
    asyncio.run(test_safety_interception())
