#!/usr/bin/env python3
"""Offline regression checks for local-agent degraded execution paths."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "local-agents"))

from agent_executor import AgentType, LocalAgentExecutor, Task, TaskStatus
from task_router import AgentTarget, TaskRouter


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def test_executor_offline_degrades_flagship() -> None:
    executor = LocalAgentExecutor(
        enable_fallback=True,
        fallback_endpoint="http://127.0.0.1:65535",
        offline_mode=True,
        allow_degraded_local_execution=True,
    )

    async def fake_local_execute(task: Task, agent_type: AgentType, max_tool_calls: int) -> str:
        return "local-offline-result"

    executor._execute_with_tools = fake_local_execute  # type: ignore[method-assign]

    task = Task(
        id="offline-flagship",
        objective="Solve a flagship-only task while offline",
        complexity=0.95,
        quality_critical=True,
        requires_flagship=True,
    )

    result = await executor.execute_task(task)
    assert_true(result.status == TaskStatus.COMPLETED, "offline degraded task should complete locally")
    assert_true(result.result == "local-offline-result", "offline degraded task should keep local result")
    assert_true(result.assigned_agent == "local-agent", "offline degraded task should stay on local agent")
    assert_true(
        result.degraded_reason is not None and "degrad" in result.degraded_reason.lower(),
        "offline degraded task should record degraded reason",
    )


async def test_executor_failed_remote_probe_stays_local() -> None:
    executor = LocalAgentExecutor(
        enable_fallback=True,
        fallback_endpoint="http://127.0.0.1:65535",
        offline_mode=False,
        allow_degraded_local_execution=True,
        remote_probe_timeout_seconds=0.01,
    )

    async def fake_local_execute(task: Task, agent_type: AgentType, max_tool_calls: int) -> str:
        return "local-probe-fallback"

    executor._execute_with_tools = fake_local_execute  # type: ignore[method-assign]

    task = Task(
        id="remote-unavailable",
        objective="Produce a quality critical answer without remote reachability",
        complexity=0.9,
        quality_critical=True,
    )

    result = await executor.execute_task(task)
    assert_true(result.status == TaskStatus.COMPLETED, "unreachable remote should degrade to local completion")
    assert_true(result.result == "local-probe-fallback", "unreachable remote should use local execution result")
    assert_true(
        result.degraded_reason is not None and "remote fallback unavailable" in result.degraded_reason.lower(),
        "remote probe failure should be visible in degraded reason",
    )


def test_router_offline_degrades_remote_targets() -> None:
    router = TaskRouter(
        offline_mode=True,
        remote_available=False,
        allow_degraded_local=True,
    )

    flagship = router.route(
        objective="Need flagship output",
        complexity=0.9,
        quality_critical=True,
        requires_flagship=True,
    )
    assert_true(flagship.target == AgentTarget.LOCAL_AGENT, "offline flagship route should degrade to local")
    assert_true("unavailable" in flagship.reason.lower(), "offline flagship route should explain degraded reason")

    complex_remote = router.route(
        objective="Design a complex system",
        complexity=0.85,
        quality_critical=True,
    )
    assert_true(complex_remote.target == AgentTarget.LOCAL_AGENT, "offline quality-critical route should degrade to local")
    assert_true(complex_remote.fallback is None, "offline degraded route should not advertise remote fallback")


async def main() -> int:
    await test_executor_offline_degrades_flagship()
    await test_executor_failed_remote_probe_stays_local()
    test_router_offline_degrades_remote_targets()
    print("PASS: local-agent offline resilience regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
