#!/usr/bin/env python3
"""Validate local-agent store_memory uses coordinator-compatible memory tiers."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTS = ROOT / "ai-stack" / "local-agents"
AI_COORDINATION = LOCAL_AGENTS / "builtin_tools" / "ai_coordination.py"


def load_module():
    sys.path.insert(0, str(LOCAL_AGENTS))
    spec = importlib.util.spec_from_file_location("ai_coordination_contract", AI_COORDINATION)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {AI_COORDINATION}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    module = load_module()
    source = AI_COORDINATION.read_text(encoding="utf-8")
    auth_source = (ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "middleware" / "auth.py").read_text(
        encoding="utf-8",
    )

    canonical = {
        "episodic",
        "semantic",
        "procedural",
        "working",
        "error_solutions",
        "interaction_history",
    }
    assert_true(set(module.MEMORY_TYPES) == canonical, "local memory type set must match coordinator tiers")

    aliases = {
        "note": "semantic",
        "observation": "episodic",
        "milestone": "episodic",
        "decision": "procedural",
        "error": "error_solutions",
        "interaction": "interaction_history",
        "": "semantic",
    }
    for raw, expected in aliases.items():
        actual = module.normalize_store_memory_type(raw)
        assert_true(actual == expected, f"alias {raw!r} normalized to {actual!r}, expected {expected!r}")

    with tempfile.TemporaryDirectory() as state_dir:
        old_state_home = os.environ.get("XDG_STATE_HOME")
        os.environ["XDG_STATE_HOME"] = state_dir
        try:
            registry = module.ToolRegistry()
            assert_true(
                str(registry.db_path).startswith(state_dir),
                "ToolRegistry default audit DB must honor XDG_STATE_HOME",
            )
            module.register_ai_coordination_tools(registry)
            store_tool = registry.get_tool("store_memory")
        finally:
            if old_state_home is None:
                os.environ.pop("XDG_STATE_HOME", None)
            else:
                os.environ["XDG_STATE_HOME"] = old_state_home
    assert_true(store_tool is not None, "store_memory tool must be registered")

    context_schema = store_tool.parameters["properties"]["context_type"]
    assert_true(set(context_schema["enum"]) == canonical, "store_memory schema must expose canonical tiers")
    assert_true(context_schema["default"] == "semantic", "store_memory default must be semantic")
    assert_true("milestone" not in context_schema["enum"], "milestone must remain an alias, not a canonical tier")

    assert_true("import os" in source, "run_opencode_handler must import os for env resolution")
    assert_true(
        "/control/ai-coordinator/delegate" in source,
        "delegate_to_remote must use the coordinator delegate endpoint, not /query",
    )
    assert_true(
        "/memory/recall" in source and "Context memory integration not yet implemented" not in source,
        "query_context must call memory recall instead of returning a stub",
    )
    assert_true(
        "/workflow/orchestrate/" in source and "/workflow/status/" not in source,
        "get_workflow_status must use the registered workflow orchestrate endpoint",
    )
    assert_true(
        '.post(f"{HYBRID_COORDINATOR_URL}/federated/recommend"' not in source,
        "recommend_agent_for_task must not call the nonexistent federated recommend route",
    )
    assert_true(
        '"/control/prsi/"' in auth_source,
        "PRSI local-agent tools require /control/prsi/ loopback authorization",
    )

    print("PASS: local-agent store_memory contract uses canonical memory tiers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
