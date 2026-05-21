#!/usr/bin/env python3
"""Validate effective security metadata for local-agent tool registry entries."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTS = ROOT / "ai-stack" / "local-agents"
BUILTINS = LOCAL_AGENTS / "builtin_tools"
sys.path.insert(0, str(LOCAL_AGENTS))
sys.path.insert(0, str(BUILTINS))

from tool_registry import SafetyPolicy, ToolCategory, ToolDefinition, ToolRegistry  # noqa: E402
import shell_tools  # noqa: E402
import file_operations  # noqa: E402
import git_tools  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_profiles() -> set[str]:
    import json
    data = json.loads((ROOT / "config" / "runtime-isolation-profiles.json").read_text(encoding="utf-8"))
    return set((data.get("profiles") or {}).keys())


def register_available_tools() -> ToolRegistry:
    registry = ToolRegistry(db_path=Path("/tmp/nixos-ai-tool-registry-test.db"))
    shell_tools.register_shell_tools(registry)
    file_operations.register_file_tools(registry)
    git_tools.register_git_tools(registry)
    return registry


def main() -> int:
    known_profiles = load_profiles()
    registry = register_available_tools()
    tools = registry.list_tools(enabled_only=True)
    assert_true(len(tools) >= 10, "expected built-in local-agent tools to register")

    required_fields = [
        "sandbox_profile",
        "resource_roots",
        "timeout_seconds",
        "output_cap_bytes",
        "artifact_retention",
        "secret_policy",
        "network_policy",
    ]
    for tool in tools:
        data = tool.to_dict()
        for field in required_fields:
            assert_true(data.get(field) not in (None, "", [], 0), f"{tool.name} missing {field}")
        assert_true(tool.sandbox_profile in known_profiles, f"{tool.name} unknown sandbox profile {tool.sandbox_profile}")
        assert_true(tool.network_policy in {"none", "loopback"}, f"{tool.name} has unsafe network policy {tool.network_policy}")
        if tool.safety_policy == SafetyPolicy.READ_ONLY:
            assert_true(tool.network_policy == "none", f"read-only tool {tool.name} must default to no network")

    # New/third-party tool declarations also get conservative effective defaults.
    async def noop() -> dict:
        return {"ok": True}

    custom = ToolDefinition(
        name="custom_readonly",
        description="custom test tool",
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.FILE_OPS,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=noop,
    )
    assert_true(custom.sandbox_profile == "readonly-strict", "default readonly sandbox profile drifted")
    assert_true(custom.network_policy == "none", "default readonly network policy drifted")

    summary = registry.get_security_metadata_summary()
    assert_true(summary["complete"] is True, f"registry metadata incomplete: {summary}")
    assert_true(summary["missing_count"] == 0, f"registry metadata missing: {summary}")

    print(f"PASS: {len(tools)} local-agent tools have effective sandbox/security metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
