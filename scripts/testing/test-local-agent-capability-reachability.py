#!/usr/bin/env python3
"""Hermetic reachability contract for the local delegated agent entrypoint."""

from __future__ import annotations

import importlib.util
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
    for declared in (full_declared, slim_declared):
        first = next(iter(declared))
        expect_mismatch(loop, set(declared) - {first}, declared)
        expect_mismatch(loop, set(declared) | {"unclaimed_test_tool"}, declared)
    print(f"PASS: local-agent capability reachability (full={len(full_declared)}, self-improvement={len(slim_declared)})")


if __name__ == "__main__":
    main()
