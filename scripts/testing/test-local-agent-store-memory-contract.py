#!/usr/bin/env python3
"""Validate local-agent store_memory uses coordinator-compatible memory tiers."""

from __future__ import annotations

import importlib.util
import sys
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

    registry = module.ToolRegistry()
    module.register_ai_coordination_tools(registry)
    store_tool = registry.get_tool("store_memory")
    assert_true(store_tool is not None, "store_memory tool must be registered")

    context_schema = store_tool.parameters["properties"]["context_type"]
    assert_true(set(context_schema["enum"]) == canonical, "store_memory schema must expose canonical tiers")
    assert_true(context_schema["default"] == "semantic", "store_memory default must be semantic")
    assert_true("milestone" not in context_schema["enum"], "milestone must remain an alias, not a canonical tier")

    print("PASS: local-agent store_memory contract uses canonical memory tiers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
