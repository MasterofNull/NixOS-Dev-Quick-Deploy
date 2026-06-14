import asyncio
import sys
import os
from pathlib import Path

# Add ai-stack/local-agents/builtin_tools to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "ai-stack" / "local-agents"))
sys.path.insert(0, str(REPO_ROOT / "ai-stack" / "local-agents" / "builtin_tools"))

from builtin_tools.ai_coordination import get_unified_stack_health_handler

async def test_tool():
    print("Testing get_unified_stack_health_handler...")
    result = await get_unified_stack_health_handler()
    import json
    print(json.dumps(result, indent=2))
    
    if result.get("success"):
        print("\nSUCCESS: Tool returned a valid health snapshot.")
        if "rate_limiting" in result:
             rl = result["rate_limiting"]
             print(f"Rate Limiting Status: {'ON' if rl.get('config', {}).get('enabled') else 'OFF'}")
    else:
        print("\nFAILURE: Tool reported error.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_tool())
