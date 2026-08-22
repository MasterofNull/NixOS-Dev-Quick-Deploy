#!/usr/bin/env python3
"""Hermetic reachability contract for the local delegated agent entrypoint."""

from __future__ import annotations

import importlib.util
import asyncio
import builtins
from importlib.machinery import SourceFileLoader
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "scripts" / "ai" / "aq-agent-loop"
MANIFEST = ROOT / "config" / "local-agent-capability-manifest.json"
TOOL_REGISTRY = ROOT / "ai-stack" / "local-agents" / "tool_registry.py"


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def load_loop():
    spec = importlib.util.spec_from_loader(
        "aq_agent_loop_reachability",
        SourceFileLoader("aq_agent_loop_reachability", str(LOOP)),
    )
    check(spec is not None and spec.loader is not None, "agent loop is not importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_registry_without_safety_layer():
    """Import the registry as though its coordinator safety dependency failed."""
    module_name = "tool_registry_safety_fallback_negative"
    spec = importlib.util.spec_from_file_location(module_name, TOOL_REGISTRY)
    check(spec is not None and spec.loader is not None, "tool registry is not importable")
    module = importlib.util.module_from_spec(spec)
    original_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "workflow.safety_control_layer":
            raise ImportError("simulated coordinator safety-layer import failure")
        return original_import(name, globals, locals, fromlist, level)

    try:
        builtins.__import__ = blocked_import
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        builtins.__import__ = original_import
        sys.modules.pop(module_name, None)
    return module


def expect_mismatch(loop, names: set[str], declared: frozenset[str]) -> None:
    try:
        loop._ensure_registry_reachability(SimpleNamespace(tools={name: object() for name in names}), declared)
    except RuntimeError as exc:
        check(str(exc) == "local_agent_capability_reachability_mismatch", "mismatch did not use bounded reason")
        return
    raise AssertionError("admitted-but-unreachable capability was accepted")


def main() -> None:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    check(raw["quarantined_capabilities"]["code_execution"]["enabled"] is False, "quarantined capability was enabled")
    check(
        raw["conditional_hidden_capabilities"]["github_create_pr"]["enabled_by_default"] is False,
        "GitHub PR mutation must be hidden by default",
    )
    fallback_registry_module = load_registry_without_safety_layer()
    fallback_receipt = fallback_registry_module.SafetyControlLayer().intercept_action(
        action_type="github_create_pr", params={}, agent_id="test"
    )
    check(
        fallback_receipt.get("reason") == "safety_control_layer_unavailable",
        "missing coordinator safety layer failed open",
    )
    original_state_home = os.environ.get("XDG_STATE_HOME")
    original_commit_gate = os.environ.get("AQ_LOCAL_ALLOW_COMMIT")
    with tempfile.TemporaryDirectory(prefix="aq-local-capabilities-") as state_home:
        os.environ["XDG_STATE_HOME"] = state_home
        os.environ.pop("AQ_LOCAL_ALLOW_COMMIT", None)
        loop = load_loop()
        full_declared = loop._load_enabled_capabilities("full")
        full_registry = loop.build_registry("full")
        slim_declared = loop._load_enabled_capabilities("self-improvement")
        slim_registry = loop.build_registry("self-improvement")
        os.environ["AQ_LOCAL_ALLOW_COMMIT"] = "1"
        commit_declared = loop._load_enabled_capabilities("full")
        commit_registry = loop.build_registry("full")
    if original_state_home is None:
        os.environ.pop("XDG_STATE_HOME", None)
    else:
        os.environ["XDG_STATE_HOME"] = original_state_home
    if original_commit_gate is None:
        os.environ.pop("AQ_LOCAL_ALLOW_COMMIT", None)
    else:
        os.environ["AQ_LOCAL_ALLOW_COMMIT"] = original_commit_gate
    check(set(full_registry.tools) == set(full_declared), "full declared tools are not exactly model-visible")
    check(set(slim_registry.tools) == set(slim_declared), "self-improvement declared tools are not exactly model-visible")
    check("git_add" not in full_registry.tools and "git_commit" not in full_registry.tools, "default commit tools remained model-visible")
    check("git_add" not in slim_registry.tools and "git_commit" not in slim_registry.tools, "slim profile exposed default-hidden commit tools")
    check(set(commit_registry.tools) == set(commit_declared), "explicit existing commit gate did not match declared conditional tools")
    check({"git_add", "git_commit"} <= set(commit_registry.tools), "conditional commit tools were not surfaced by explicit gate")
    check("code_execution" not in full_registry.tools, "quarantined capability reached the local agent")
    check("github_create_pr" not in full_registry.tools, "external-account mutation remained model-visible")
    check("github_create_pr" not in slim_registry.tools, "slim profile exposed external-account mutation")
    check("github_create_pr" not in commit_registry.tools, "commit opt-in exposed external-account mutation")

    # Audit every elevated mutator that remains declared and model-visible in
    # the default review registry.  WRITE_SAFE tools retain their narrow
    # worktree/loopback contract; SYSTEM_MODIFY and DESTRUCTIVE tools require
    # both a proposal and operator confirmation.
    elevated_mutators = [
        tool for tool in full_registry.tools.values()
        if tool.safety_policy.value in {"system_modify", "destructive"}
    ]
    check(elevated_mutators, "full profile unexpectedly has no elevated mutators to audit")
    for tool in elevated_mutators:
        check(tool.requires_proposal, f"{tool.name} lacks proposal gate")
        check(tool.requires_confirmation, f"{tool.name} lacks confirmation gate")

    # A direct registry consumer cannot accidentally turn a SYSTEM_MODIFY
    # declaration into an external mutation: its handler is never reached
    # without an explicit confirmation callback.
    async def external_mutation_handler(**_kwargs):
        raise AssertionError("external mutation handler must not execute")

    with tempfile.TemporaryDirectory(prefix="aq-local-external-mutation-") as audit_dir:
        direct_registry = fallback_registry_module.ToolRegistry(
            db_path=Path(audit_dir) / "tool-audit.sqlite",
        )
        direct_tool = fallback_registry_module.ToolDefinition(
            name="external_account_mutation_test",
            description="test-only external mutation",
            parameters={"type": "object", "properties": {}},
            category=fallback_registry_module.ToolCategory.AI_COORD,
            safety_policy=fallback_registry_module.SafetyPolicy.SYSTEM_MODIFY,
            handler=external_mutation_handler,
        )
        direct_registry.register(direct_tool)
        check(direct_tool.requires_proposal, "system mutation lost proposal requirement")
        check(direct_tool.requires_confirmation, "system mutation lost confirmation requirement")
        blocked = asyncio.run(direct_registry.execute_tool_call(fallback_registry_module.ToolCall(
            id="external-mutation-negative",
            tool_name=direct_tool.name,
            arguments={},
        )))
        check(blocked.status in {"intercepted", "failed"}, "unconfirmed external mutation was not blocked")
        check(blocked.status != "completed", "unconfirmed external mutation executed")
    for declared in (full_declared, slim_declared):
        first = next(iter(declared))
        expect_mismatch(loop, set(declared) - {first}, declared)
        expect_mismatch(loop, set(declared) | {"unclaimed_test_tool"}, declared)
    print(f"PASS: local-agent capability reachability (full={len(full_declared)}, self-improvement={len(slim_declared)})")


if __name__ == "__main__":
    main()
