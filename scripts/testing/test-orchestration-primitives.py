#!/usr/bin/env python3
"""Focused regression coverage for orchestration foundation primitives."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_module(relative_path: str, name: str):
    module_path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def test_agent_hq_session_lifecycle() -> None:
    module = load_module("ai-stack/orchestration/agent_hq.py", "agent_hq")

    async def executor(session_id, task, agent):
        return {"session_id": session_id, "task_id": task.task_id, "agent_id": agent.agent_id}

    with tempfile.TemporaryDirectory(prefix="agent-hq-") as tmpdir:
        hq = module.AgentHQ(persistence_dir=Path(tmpdir), executor_fn=executor)
        agent = hq.register_agent("codex", {"review", "integration"})
        session = hq.create_session("resume orchestration", {"phase": "4.2"})
        task = await hq.submit_task(
            session.session_id,
            "review pending work",
            required_capabilities={"review"},
        )
        assert task is not None
        assert await hq.start_session(session.session_id) is True
        await asyncio.sleep(0.2)
        status = hq.get_session_status(session.session_id)
        assert status["tasks"]["completed"] == 1
        checkpoint = hq.create_checkpoint(session.session_id, "post-review")
        assert checkpoint is not None
        assert hq.save_session(session.session_id) is True
        restored = hq.load_session(session.session_id)
        assert restored is not None
        assert agent.agent_id in restored.agents
        assert hq.restore_checkpoint(session.session_id, checkpoint.checkpoint_id) is True


async def test_delegation_api_queue_and_feedback() -> None:
    module = load_module("ai-stack/orchestration/delegation_api.py", "delegation_api")

    async def executor(agent_id, request):
        await asyncio.sleep(0.05)
        return {"agent_id": agent_id, "task": request.task_description}

    api = module.DelegationAPI(executor_fn=executor)
    api.register_agent(
        "agent-a",
        "Analyzer",
        capabilities={"analysis"},
        capability_levels={"analysis": 0.9},
        max_concurrent=1,
    )
    api.register_agent(
        "agent-b",
        "Builder",
        capabilities={"coding"},
        capability_levels={"coding": 0.8},
        max_concurrent=1,
    )

    first = await api.delegate("analyze freeze", {"analysis"}, wait=False)
    assert first.assigned_agent == "agent-a"

    queued = await api.delegate("queued analysis", {"analysis"}, timeout_seconds=1.0, wait=False)
    assert queued.status == module.DelegationStatus.PENDING
    assert queued.reject_reason == module.RejectionReason.NO_AVAILABLE_AGENTS

    await asyncio.sleep(0.2)
    final = api.get_delegation_status(queued.request_id)
    assert final is not None
    assert final.status == module.DelegationStatus.COMPLETED
    assert api.feedback.get_agent_success_rate("agent-a") == 1.0


async def test_workspace_isolation_conflict_detection() -> None:
    module = load_module("ai-stack/orchestration/workspace_isolation.py", "workspace_isolation")

    with tempfile.TemporaryDirectory(prefix="workspace-source-") as src_tmp, tempfile.TemporaryDirectory(prefix="workspace-base-") as base_tmp:
        source = Path(src_tmp)
        (source / "shared.txt").write_text("seed", encoding="utf-8")

        manager = module.WorkspaceManager(base_dir=Path(base_tmp), default_mode=module.IsolationMode.COPY)
        ws_a = await manager.create_workspace("agent-a", "session-1", source_path=source)
        ws_b = await manager.create_workspace("agent-b", "session-1", source_path=source)

        assert "shared.txt" in manager.get_workspace_files(ws_a.workspace_id)
        assert manager.write_file(ws_a.workspace_id, "shared.txt", "alpha") is True
        assert manager.write_file(ws_b.workspace_id, "shared.txt", "beta") is True

        conflicts = manager.detect_conflicts("session-1")
        assert len(conflicts) == 1
        resolved = await manager.resolve_conflicts(conflicts, module.ConflictStrategy.LATEST_WINS)
        assert resolved[0].resolution == "latest_wins"

        assert await manager.merge_to_source(ws_a.workspace_id) is True
        assert await manager.cleanup_session_workspaces("session-1") == 2


def main() -> int:
    asyncio.run(test_agent_hq_session_lifecycle())
    asyncio.run(test_delegation_api_queue_and_feedback())
    asyncio.run(test_workspace_isolation_conflict_detection())
    print("PASS: orchestration foundation primitives are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
