"""Behavioral regression tests for delegated caller safety."""

import asyncio
import shutil
import subprocess
from pathlib import Path

from workflow import agents_task_handlers as handlers
from workflow_executor import WorkflowPhaseExecutor


class _Process:
    pid = 4321
    returncode = 0

    def __init__(self, timeout=False):
        self.timeout = timeout
        self.calls = 0

    async def communicate(self):
        self.calls += 1
        if self.timeout and self.calls == 1:
            await asyncio.Future()
        return b"delegated output", b""


def test_delegated_reviewer_uses_reviewer_role(monkeypatch):
    spawned = []

    async def create_process(*args, **kwargs):
        spawned.append(args)
        return _Process()

    monkeypatch.setattr(handlers.asyncio, "create_subprocess_exec", create_process)
    instance, status = asyncio.run(handlers._spawn_delegated_agent_instance(
        lane="claude", role="reviewer", task_text="review", timeout_sec=1,
    ))

    assert status == 201
    assert instance["role"] == "reviewer"
    assert spawned[0][spawned[0].index("--role") + 1] == "review"


def test_delegated_unknown_role_is_rejected_before_spawn(monkeypatch):
    async def create_process(*_args, **_kwargs):
        raise AssertionError("unknown roles must not start a subprocess")

    monkeypatch.setattr(handlers.asyncio, "create_subprocess_exec", create_process)
    instance, status = asyncio.run(handlers._spawn_delegated_agent_instance(
        lane="gemini", role="unsupported", task_text="x", timeout_sec=1,
    ))

    assert status == 400
    assert instance["status"] == "failed"


def test_timeout_kills_and_reaps_delegated_process_group(monkeypatch):
    process = _Process(timeout=True)
    killed = []

    async def create_process(*_args, **_kwargs):
        return process

    monkeypatch.setattr(handlers.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(handlers.os, "killpg", lambda pid, sig: killed.append((pid, sig)))
    instance, status = asyncio.run(handlers._spawn_delegated_agent_instance(
        lane="gemini", role="implement", task_text="x", timeout_sec=0.01,
    ))

    assert status == 504
    assert instance["status"] == "timeout"
    assert killed and killed[0][0] == process.pid
    assert process.calls == 2


class _Response:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class _Client:
    def __init__(self, body, **_kwargs):
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, *_args, **_kwargs):
        return _Response(self.body)


def test_delegate_phase_rejects_failed_and_empty_completed_responses(monkeypatch):
    executor = WorkflowPhaseExecutor("http://coordinator")
    phase = {"id": "p1"}

    for body in (
        {"status": "error", "error": "timeout"},
        {"status": "ok", "instance": {"status": "completed", "result": "  "}},
    ):
        monkeypatch.setattr(
            "workflow_executor.httpx.AsyncClient", lambda **kwargs: _Client(body, **kwargs)
        )
        try:
            asyncio.run(executor._delegate_phase_execution(phase, "objective", {}))
        except RuntimeError:
            continue
        raise AssertionError("failed or empty delegated responses must not complete a phase")


def test_fanout_uses_codex_supported_arguments(tmp_path):
    repo_root = Path(__file__).resolve().parents[4]
    scripts_dir = tmp_path / "scripts" / "ai"
    scripts_dir.mkdir(parents=True)
    fanout = scripts_dir / "delegate-fanout"
    shutil.copy2(repo_root / "scripts" / "ai" / "delegate-fanout", fanout)
    codex = scripts_dir / "delegate-to-codex"
    codex.write_text(
        """#!/usr/bin/env bash
for arg in "$@"; do
    [[ "$arg" == "--role" ]] && exit 41
done
[[ "$2" == $'Assigned role: implementer\\n\\nsmoke' ]] || exit 42
echo codex-20261003-010000-abcdef
"""
    )
    codex.chmod(0o755)
    fanout.chmod(0o755)

    result = subprocess.run(
        [str(fanout), "--prompt", "smoke", "--agents", "codex", "--role", "implement"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Spawned codex" in result.stdout
