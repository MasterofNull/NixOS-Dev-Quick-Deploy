"""Phase 73 checks — Progressive Tool Disclosure Parity (Phase A).

73.1  TOOL_CATALOG size: local_agent_runtime.py exports TOOL_CATALOG with >= 17 entries
73.2  Catalog completeness: all 14 AI coordination tools + 3 base tools present
73.3  _dispatch_tool coverage: every catalog entry has a dispatch case (or graceful fallback)
73.4  _select_tools_for_task: returns 4-5 tools, token cost <= 400 across test cases
73.5  Token budget: slim schemas keep ALL selection scenarios under 400 tokens
73.6  TOOL_SCHEMAS completeness: all 17 tools present in ultra-minimal form, total <= 800 tokens
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from ..core.context import RunContext
from ..core.result import CheckResult, passed, failed, skipped

_REPO = Path(__file__).resolve().parents[4]
_RUNTIME_PATH = _REPO / "ai-stack" / "agents" / "runtimes"

# The 14 AI coordination tool names defined in ai_coordination.py
_AI_COORD_TOOLS = {
    "get_hint", "delegate_to_remote", "query_context", "store_memory",
    "get_workflow_status", "run_opencode", "harness_health", "get_prsi_pending",
    "prsi_orchestrate", "recommend_agent_for_task", "query_aidb",
    "get_working_memory", "mesh_discovery", "collective_memory_search",
}
# The 3 base tool names
_BASE_TOOLS = {"route_search", "recall_memory", "run_harness_cli"}
_ALL_EXPECTED = _AI_COORD_TOOLS | _BASE_TOOLS

# Tools with graceful fallback (not true dispatch gaps)
_GRACEFUL_FALLBACK = {"run_opencode"}


def _load_runtime() -> tuple[Any, Any] | None:
    """Import TOOL_CATALOG and _select_tools_for_task with required env vars set."""
    runtime_dir = str(_RUNTIME_PATH)
    if runtime_dir not in sys.path:
        sys.path.insert(0, runtime_dir)
    # Inject required module-level env vars
    for key, val in [
        ("AGENT_ID", "aq-qa-73"),
        ("AGENT_ROLE", "coordinator"),
        ("AGENT_SYSTEM_PROMPT", "qa-probe"),
        ("AGENT_TASK", "qa probe task"),
    ]:
        os.environ.setdefault(key, val)
    try:
        # Force fresh import in case module was previously imported without env vars
        if "local_agent_runtime" in sys.modules:
            mod = sys.modules["local_agent_runtime"]
        else:
            import importlib
            mod = importlib.import_module("local_agent_runtime")
        catalog = getattr(mod, "TOOL_CATALOG", None)
        selector = getattr(mod, "_select_tools_for_task", None)
        return catalog, selector
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 73.1 — TOOL_CATALOG size >= 17
# ---------------------------------------------------------------------------

def _check_73_1(_ctx: RunContext) -> CheckResult:
    """Verify TOOL_CATALOG exports >= 17 entries."""
    result = _load_runtime()
    if result is None:
        return failed(3, "73.1", "TOOL_CATALOG size", "failed to import local_agent_runtime", phase="73")

    catalog, _ = result
    if catalog is None:
        return failed(3, "73.1", "TOOL_CATALOG size", "TOOL_CATALOG not exported", phase="73")

    count = len(catalog)
    if count < 17:
        return failed(3, "73.1", "TOOL_CATALOG size",
                      f"expected >= 17, got {count}", phase="73")
    return passed(3, "73.1", f"TOOL_CATALOG has {count} entries (>= 17)", phase="73")


# ---------------------------------------------------------------------------
# 73.2 — All 17 expected tools present in catalog
# ---------------------------------------------------------------------------

def _check_73_2(_ctx: RunContext) -> CheckResult:
    """Verify all 14 AI coordination tools + 3 base tools are in TOOL_CATALOG."""
    result = _load_runtime()
    if result is None:
        return failed(3, "73.2", "catalog completeness", "failed to import runtime", phase="73")

    catalog, _ = result
    if catalog is None:
        return failed(3, "73.2", "catalog completeness", "TOOL_CATALOG not exported", phase="73")

    catalog_keys = set(catalog.keys())
    missing = _ALL_EXPECTED - catalog_keys
    extra = catalog_keys - _ALL_EXPECTED
    if missing:
        return failed(3, "73.2", "catalog completeness",
                      f"missing tools: {sorted(missing)}", phase="73")

    note = f"all 17 tools present"
    if extra:
        note += f"; {len(extra)} additional: {sorted(extra)}"
    return passed(3, "73.2", note, phase="73")


# ---------------------------------------------------------------------------
# 73.3 — _dispatch_tool coverage
# ---------------------------------------------------------------------------

def _check_73_3(_ctx: RunContext) -> CheckResult:
    """Verify _dispatch_tool() in local_agent_runtime.py has a case for each catalog entry."""
    runtime_file = _RUNTIME_PATH / "local_agent_runtime.py"
    if not runtime_file.exists():
        return skipped(3, "73.3", "_dispatch_tool coverage", "local_agent_runtime.py not found", phase="73")

    text = runtime_file.read_text(encoding="utf-8")
    # Locate _dispatch_tool function body
    if "_dispatch_tool" not in text:
        return failed(3, "73.3", "_dispatch_tool coverage", "_dispatch_tool not found in file", phase="73")

    missing_dispatch = []
    for tool_name in _ALL_EXPECTED:
        if tool_name in _GRACEFUL_FALLBACK:
            continue  # graceful fallback counts as covered
        # Check for `name == "tool_name"` pattern
        if f'name == "{tool_name}"' not in text:
            missing_dispatch.append(tool_name)

    if missing_dispatch:
        return failed(3, "73.3", "_dispatch_tool coverage",
                      f"no dispatch case for: {sorted(missing_dispatch)}", phase="73")

    return passed(3, "73.3",
                  f"_dispatch_tool has cases for all {len(_ALL_EXPECTED)} tools "
                  f"({len(_GRACEFUL_FALLBACK)} graceful fallback)", phase="73")


# ---------------------------------------------------------------------------
# 73.4 — _select_tools_for_task returns 4-5 tools
# ---------------------------------------------------------------------------

def _check_73_4(_ctx: RunContext) -> CheckResult:
    """Verify _select_tools_for_task returns 4-5 tools across representative task inputs."""
    result = _load_runtime()
    if result is None:
        return failed(3, "73.4", "_select_tools_for_task count", "failed to import runtime", phase="73")

    _, selector = result
    if selector is None:
        return failed(3, "73.4", "_select_tools_for_task count",
                      "_select_tools_for_task not exported", phase="73")

    test_cases = [
        "search for error patterns in aidb",
        "remember this solution for the async bug",
        "check health status of all services",
        "what is the current state of things",
        "get a hint for fixing the coordinator",
    ]
    violations = []
    for task in test_cases:
        sel = selector(task)
        count = len(sel)
        if not (4 <= count <= 5):
            violations.append(f"'{task[:30]}' -> {count} tools (expected 4-5)")

    if violations:
        return failed(3, "73.4", "_select_tools_for_task count",
                      "; ".join(violations), phase="73")

    return passed(3, "73.4",
                  f"_select_tools_for_task returns 4-5 tools for all {len(test_cases)} test cases",
                  phase="73")


# ---------------------------------------------------------------------------
# 73.5 — Token budget: all selections <= 400 tokens
# ---------------------------------------------------------------------------

def _check_73_5(_ctx: RunContext) -> CheckResult:
    """Verify slim schemas keep all selection scenarios under 400 tokens."""
    result = _load_runtime()
    if result is None:
        return failed(3, "73.5", "token budget", "failed to import runtime", phase="73")

    _, selector = result
    if selector is None:
        return failed(3, "73.5", "token budget", "_select_tools_for_task not exported", phase="73")

    test_cases = [
        "search for error patterns in aidb",
        "remember this solution for the async bug",
        "check health status of all services",
        "discover agents in the mesh and delegate to remote",
        "what is the current state of things",
        "get a hint for fixing the coordinator",
        "store the result in memory for this session",
        "what is the workflow status for abc123",
    ]
    violations = []
    max_tok = 0.0
    for task in test_cases:
        sel = selector(task)
        tok = len(json.dumps(sel)) / 4
        if tok > max_tok:
            max_tok = tok
        if tok > 400:
            violations.append(f"'{task[:30]}' -> {tok:.0f} tok (> 400)")

    if violations:
        return failed(3, "73.5", "token budget",
                      f"over-budget: {'; '.join(violations)}", phase="73")

    return passed(3, "73.5",
                  f"max token cost {max_tok:.0f} across {len(test_cases)} cases (budget: 400)",
                  phase="73")


# ---------------------------------------------------------------------------
# 73.6 — TOOL_SCHEMAS legacy alias still exports 3-tool base set
# ---------------------------------------------------------------------------

def _check_73_6(_ctx: RunContext) -> CheckResult:
    """Verify TOOL_SCHEMAS exports all 17 catalog tools for external callers.

    The linter optimised TOOL_SCHEMAS to an ultra-minimal 17-tool list using _T() helper
    (all tools, ≤800 tokens total). This is better than the 3-tool alias originally planned.
    The check verifies that all expected tool names are present.
    """
    if "local_agent_runtime" not in sys.modules:
        result = _load_runtime()
        if result is None:
            return failed(3, "73.6", "TOOL_SCHEMAS completeness", "failed to import runtime", phase="73")

    mod = sys.modules.get("local_agent_runtime")
    if mod is None:
        return failed(3, "73.6", "TOOL_SCHEMAS completeness", "module not loaded", phase="73")

    schemas = getattr(mod, "TOOL_SCHEMAS", None)
    if schemas is None:
        return failed(3, "73.6", "TOOL_SCHEMAS completeness", "TOOL_SCHEMAS not exported", phase="73")

    names = {s.get("function", {}).get("name") for s in schemas}
    missing = _ALL_EXPECTED - names
    if missing:
        return failed(3, "73.6", "TOOL_SCHEMAS completeness",
                      f"missing tools: {sorted(missing)}", phase="73")

    # Also verify total token cost stays under 800 (ultra-minimal design goal)
    tok = len(json.dumps(schemas)) / 4
    if tok > 800:
        return failed(3, "73.6", "TOOL_SCHEMAS completeness",
                      f"token cost {tok:.0f} exceeds 800-token design goal", phase="73")

    return passed(3, "73.6",
                  f"TOOL_SCHEMAS has all {len(names)} tools, token cost {tok:.0f} (<= 800)",
                  phase="73")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(ctx: RunContext) -> list[CheckResult]:
    return [
        _check_73_1(ctx),
        _check_73_2(ctx),
        _check_73_3(ctx),
        _check_73_4(ctx),
        _check_73_5(ctx),
        _check_73_6(ctx),
    ]
