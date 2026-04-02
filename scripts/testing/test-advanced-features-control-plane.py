#!/usr/bin/env python3
"""Static control-plane regression for advanced_features coordinator wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "server.py"
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"
MCP_HANDLERS = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "mcp_handlers.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    server_text = SERVER.read_text(encoding="utf-8")
    http_text = HTTP_SERVER.read_text(encoding="utf-8")
    mcp_text = MCP_HANDLERS.read_text(encoding="utf-8")

    assert_true("import advanced_features" in server_text, "server should import advanced_features")
    assert_true("advanced_features.init(" in server_text, "server should initialize advanced_features")

    for tool_name in [
        "get_advanced_features_readiness",
        "get_agent_quality_profiles",
        "select_failover_remote_agent",
        "get_agent_benchmarks",
        "optimize_prompt_template",
        "generate_dynamic_prompt",
        "record_prompt_variant_outcome",
        "get_prompt_ab_stats",
        "select_context_tier",
        "get_tier_selection_stats",
        "analyze_failure_patterns",
        "get_capability_gap_stats",
        "record_learning_signal",
        "get_learning_recommendations",
        "get_advanced_learning_stats",
    ]:
        assert_true(f'name="{tool_name}"' in mcp_text, f"MCP handlers should expose {tool_name}")
        assert_true(f'elif name == "{tool_name}"' in mcp_text, f"MCP handlers should dispatch {tool_name}")

    for route in [
        "/control/ai-coordinator/advanced-features/readiness",
        "/control/ai-coordinator/advanced-features/offloading/quality-profiles",
        "/control/ai-coordinator/advanced-features/offloading/failover-select",
        "/control/ai-coordinator/advanced-features/offloading/benchmarks",
        "/control/ai-coordinator/advanced-features/prompt/optimize",
        "/control/ai-coordinator/advanced-features/prompt/dynamic",
        "/control/ai-coordinator/advanced-features/prompt/ab-stats",
        "/control/ai-coordinator/advanced-features/prompt/ab-record",
        "/control/ai-coordinator/advanced-features/context/tier-select",
        "/control/ai-coordinator/advanced-features/context/tier-stats",
        "/control/ai-coordinator/advanced-features/capability-gap/failure-patterns",
        "/control/ai-coordinator/advanced-features/capability-gap/stats",
        "/control/ai-coordinator/advanced-features/learning/signal",
        "/control/ai-coordinator/advanced-features/learning/recommendations",
        "/control/ai-coordinator/advanced-features/learning/stats",
    ]:
        assert_true(route in http_text, f"http server should register {route}")

    print("PASS: advanced features control plane wiring present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
