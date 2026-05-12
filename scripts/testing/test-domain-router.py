#!/usr/bin/env python3
import sys
from pathlib import Path

# Dynamically add the hybrid-coordinator module to sys.path for testing
repo_root = Path(__file__).resolve().parent.parent.parent
hybrid_coordinator_path = repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(hybrid_coordinator_path))

from domain_router import classify_domain, route_to_team

def test_domain_router():
    # Test Domain Classification
    assert classify_domain("Please update the flake.nix module") == "nixos"
    assert classify_domain("Write an async FastAPI endpoint") == "python"
    assert classify_domain("Audit this code for vulnerabilities") == "security"
    assert classify_domain("Make the background blue", hint="design") == "design"
    assert classify_domain("Generic task with no keywords") == "general"

    # Test Team Routing
    assert "architect:remote-reasoning" in route_to_team("nixos")
    assert "impeccable:team_via_/agent/intake?domain=design" in route_to_team("design")
    assert "default:local-agent" in route_to_team("general")

    print("✅ Domain router tests passed!")

if __name__ == "__main__":
    test_domain_router()
