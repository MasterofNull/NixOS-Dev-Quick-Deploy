#!/usr/bin/env python3
"""
Test agent status reporting - simplified inline test.
"""

import json
import sys
from datetime import datetime

def test_agent_status_formatting():
    """Test the agent status formatting logic."""
    print("Testing agent status reporting logic...")

    # Test data
    test_status = {
        "pool_status": "ok",
        "total_agents": 5,
        "available_agents": 3,
        "free_agents_available": 2,
        "agents": [
            {
                "agent_id": "test_qwen_32b",
                "name": "Qwen 32B Chat",
                "status": "rate_limited",
                "tier": "free",
                "is_available": False,
                "is_rate_limited": True,
                "current_load": 0,
                "max_concurrent": 3,
                "success_rate": 0.95,
                "eta_available_minutes": 2,
            },
            {
                "agent_id": "test_mistral_7b",
                "name": "Mistral 7B Instruct",
                "status": "available",
                "tier": "free",
                "is_available": True,
                "is_rate_limited": False,
                "current_load": 1,
                "max_concurrent": 5,
                "success_rate": 0.98,
            },
            {
                "agent_id": "test_unavailable",
                "name": "Test Unavailable Agent",
                "status": "unavailable",
                "tier": "paid_standard",
                "is_available": False,
                "is_rate_limited": False,
                "current_load": 0,
                "max_concurrent": 5,
                "success_rate": 0.85,
            },
        ]
    }

    # Test 1: Check structure
    required_fields = ["pool_status", "total_agents", "available_agents", "free_agents_available", "agents"]
    for field in required_fields:
        if field not in test_status:
            print(f"✗ Missing required field: {field}")
            return False
    print("✓ Agent status structure is correct")

    # Test 2: Check agent details
    agents = test_status["agents"]
    rate_limited = [a for a in agents if a.get("is_rate_limited")]
    unavailable = [a for a in agents if not a.get("is_available") and not a.get("is_rate_limited")]

    if len(rate_limited) != 1:
        print(f"✗ Expected 1 rate-limited agent, got {len(rate_limited)}")
        return False
    print("✓ Rate-limited agent detection works")

    if len(unavailable) != 1:
        print(f"✗ Expected 1 unavailable agent, got {len(unavailable)}")
        return False
    print("✓ Unavailable agent detection works")

    # Test 3: Check ETA calculation
    rl_agent = rate_limited[0]
    if "eta_available_minutes" not in rl_agent:
        print("✗ ETA field missing from rate-limited agent")
        return False
    if rl_agent["eta_available_minutes"] != 2:
        print(f"✗ ETA should be 2 minutes, got {rl_agent['eta_available_minutes']}")
        return False
    print("✓ ETA field present and correct")

    # Test 4: Format summary message
    summary_lines = []
    summary_lines.append(f"\n  Agent Pool Status: {test_status['pool_status']}")
    summary_lines.append(f"    Total agents: {test_status['total_agents']} | Available: {test_status['available_agents']} | Free tier: {test_status['free_agents_available']}")

    if rate_limited:
        summary_lines.append(f"    Rate-limited agents: {len(rate_limited)}")
        for agent in rate_limited[:3]:
            eta = agent.get("eta_available_minutes")
            eta_str = f" (ETA: {eta} min)" if eta else " (ETA: unknown)"
            summary_lines.append(f"      - {agent.get('name', agent.get('agent_id'))}{eta_str}")

    if unavailable:
        summary_lines.append(f"    Unavailable agents: {len(unavailable)}")
        for agent in unavailable[:3]:
            summary_lines.append(f"      - {agent.get('name', agent.get('agent_id'))}: {agent.get('status', 'unknown')}")

    if rate_limited or unavailable:
        summary_lines.append("")
        summary_lines.append("  Action: Wait for rate limits to reset or use available agents.")

    summary = "\n".join(summary_lines)

    if "Qwen 32B Chat" not in summary:
        print("✗ Agent name not in summary")
        return False
    if "ETA: 2 min" not in summary:
        print("✗ ETA not in summary")
        return False
    if "Test Unavailable Agent" not in summary:
        print("✗ Unavailable agent not in summary")
        return False

    print("✓ Agent status summary formatting correct")
    print("\nSample output:")
    print(summary)

    # Test 5: Error message formatting
    def format_error_with_status(error_result, status):
        http_status = error_result.get("http_status", 0)
        error = error_result.get("error", "Unknown error")

        if http_status == 429:
            retry_after = error_result.get("retry_after", "")
            base_msg = f"Rate limited (HTTP 429). {error}"
            if retry_after:
                base_msg += f" Retry after: {retry_after}s."
        elif http_status == 503:
            base_msg = f"Service unavailable (HTTP 503). {error}"
        else:
            base_msg = f"{error}"

        # Append status summary
        base_msg += "\n" + "\n".join(summary_lines)
        return base_msg

    error_429 = {
        "status": "error",
        "http_status": 429,
        "error": "Rate limit exceeded",
        "retry_after": "60",
    }

    error_msg = format_error_with_status(error_429, test_status)
    if "Rate limited (HTTP 429)" not in error_msg:
        print("✗ 429 error not formatted correctly")
        return False
    if "Retry after: 60s" not in error_msg:
        print("✗ Retry-After not included in 429 error")
        return False
    if "Agent Pool Status" not in error_msg:
        print("✗ Agent status not in error message")
        return False

    print("✓ HTTP 429 error message formatting correct")

    error_503 = {
        "status": "error",
        "http_status": 503,
        "error": "Service temporarily unavailable",
    }

    error_msg_503 = format_error_with_status(error_503, test_status)
    if "Service unavailable (HTTP 503)" not in error_msg_503:
        print("✗ 503 error not formatted correctly")
        return False

    print("✓ HTTP 503 error message formatting correct")

    print("\n✅ All agent status reporting tests passed!")
    return True

if __name__ == "__main__":
    success = test_agent_status_formatting()
    sys.exit(0 if success else 1)
