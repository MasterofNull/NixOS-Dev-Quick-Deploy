#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Dynamically add the hybrid-coordinator module to sys.path for testing
repo_root = Path(__file__).resolve().parent.parent.parent
hybrid_coordinator_path = repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(hybrid_coordinator_path))

from agent_capability_registry import discover_agents

def test_agent_registry():
    # Clear existing host aliases to prevent test pollution from your local NixOS environment
    for key in list(os.environ.keys()):
        if key.startswith("SWITCHBOARD_REMOTE_ALIAS_"):
            del os.environ[key]

    # Mock dynamic environment discovery
    os.environ["SWITCHBOARD_REMOTE_ALIAS_CLAUDE"] = "claude-3-sonnet"
    os.environ["SWITCHBOARD_REMOTE_ALIAS_GPT"] = "gpt-4o"

    agents = discover_agents()

    # Validate Local Agent default inclusion
    assert "local-agent" in agents
    assert agents["local-agent"]["source"] == "local"

    # Validate dynamic remote agent discovery
    assert "claude" in agents
    assert agents["claude"]["model"] == "claude-3-sonnet"
    assert agents["gpt"]["model"] == "gpt-4o"

    # Validate remote agents do NOT have the 'cli' profile
    assert "cli" not in agents["claude"]["profiles"]

    print("✅ Agent capability registry tests passed!")

if __name__ == "__main__":
    test_agent_registry()
