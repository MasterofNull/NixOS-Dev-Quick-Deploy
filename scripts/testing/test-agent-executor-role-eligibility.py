#!/usr/bin/env python3
"""
Phase 58A.5 regression: AGENT_TYPE_ELIGIBLE_ROLES enforced at execute_task dispatch.
Tests that ineligible role assignments are clamped to the agent_type default.
"""
import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTS = ROOT / "ai-stack/local-agents"
sys.path.insert(0, str(LOCAL_AGENTS))
spec = importlib.util.spec_from_file_location(
    "agent_executor",
    LOCAL_AGENTS / "agent_executor.py",
)
mod = importlib.util.module_from_spec(spec)
# Stub external deps before import
sys.modules.setdefault("httpx", MagicMock())
spec.loader.exec_module(mod)

AgentExecutor = mod.LocalAgentExecutor
AgentType = mod.AgentType
Task = mod.Task
AGENT_TYPE_DEFAULT_ROLE = mod.AGENT_TYPE_DEFAULT_ROLE
AGENT_TYPE_ELIGIBLE_ROLES = mod.AGENT_TYPE_ELIGIBLE_ROLES

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        print(f"  FAIL  {name}")
        FAIL += 1


async def make_executor():
    ex = AgentExecutor.__new__(AgentExecutor)
    ex.llama_endpoint = "http://localhost:8080"
    ex.enable_fallback = False
    ex.allow_degraded_local_execution = True
    ex.fallback_endpoint = None
    ex.tool_registry = MagicMock()
    ex.tool_registry.tools = {}
    ex.performance = {at: MagicMock() for at in AgentType}
    ex.performance[AgentType.AGENT].update = MagicMock()
    return ex


async def test_eligible_role_unchanged():
    """Role within eligible set passes through unchanged."""
    ex = await make_executor()
    task = Task(id="t1", objective="test", role="implementer")

    with patch.object(ex, "route_task", return_value=(True, "local")), \
         patch.object(ex, "_execute_with_tools", new_callable=AsyncMock,
                      return_value=("ok", 10)):
        result = await ex.execute_task(task, AgentType.AGENT)

    check("eligible role (implementer for AGENT) unchanged", result.role == "implementer")


async def test_ineligible_role_clamped():
    """CHAT agent requesting orchestrator role is clamped to implementer."""
    ex = await make_executor()
    task = Task(id="t2", objective="test", role="orchestrator")  # CHAT cannot be orchestrator

    with patch.object(ex, "route_task", return_value=(True, "local")), \
         patch.object(ex, "_execute_with_tools", new_callable=AsyncMock,
                      return_value=("ok", 10)):
        result = await ex.execute_task(task, AgentType.CHAT)

    default = AGENT_TYPE_DEFAULT_ROLE[AgentType.CHAT]
    check("ineligible orchestrator clamped for CHAT", result.role == default)


async def test_none_role_auto_assigned():
    """None role is auto-assigned from AGENT_TYPE_DEFAULT_ROLE."""
    ex = await make_executor()
    task = Task(id="t3", objective="test", role=None)

    with patch.object(ex, "route_task", return_value=(True, "local")), \
         patch.object(ex, "_execute_with_tools", new_callable=AsyncMock,
                      return_value=("ok", 10)):
        result = await ex.execute_task(task, AgentType.PLANNER)

    check("None role auto-assigned for PLANNER", result.role == AGENT_TYPE_DEFAULT_ROLE[AgentType.PLANNER])


async def test_embedded_role_stays_none():
    """EMBEDDED agents always produce None role (no eligible roles, no default)."""
    ex = await make_executor()
    task = Task(id="t4", objective="test", role=None)

    with patch.object(ex, "route_task", return_value=(True, "local")), \
         patch.object(ex, "_execute_with_tools", new_callable=AsyncMock,
                      return_value=("ok", 10)):
        result = await ex.execute_task(task, AgentType.EMBEDDED)

    check("EMBEDDED role stays None", result.role is None)


async def test_eligible_set_is_nonempty_for_agent_types():
    """AGENT_TYPE_ELIGIBLE_ROLES is non-empty for AGENT and PLANNER."""
    check("AGENT eligible roles non-empty", len(AGENT_TYPE_ELIGIBLE_ROLES[AgentType.AGENT]) > 0)
    check("PLANNER eligible roles non-empty", len(AGENT_TYPE_ELIGIBLE_ROLES[AgentType.PLANNER]) > 0)


async def main():
    await test_eligible_role_unchanged()
    await test_ineligible_role_clamped()
    await test_none_role_auto_assigned()
    await test_embedded_role_stays_none()
    await test_eligible_set_is_nonempty_for_agent_types()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
