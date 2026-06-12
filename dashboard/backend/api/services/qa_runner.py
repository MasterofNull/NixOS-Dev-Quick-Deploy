"""Shared single-flight runner for expensive aq-qa subprocesses."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

_RUNNING_TASKS: Dict[str, "asyncio.Task[Dict[str, Any]]"] = {}
_TASKS_LOCK = asyncio.Lock()


def _aq_qa_bin() -> str:
    path = (
        shutil.which("aq-qa")
        or (
            os.path.isfile("/run/current-system/sw/bin/aq-qa")
            and "/run/current-system/sw/bin/aq-qa"
        )
    )
    if not path:
        raise RuntimeError("aq-qa not found in PATH or /run/current-system/sw/bin")
    return str(path)


async def _execute_phase(phase: str, *, timeout_s: float, cwd: Optional[Path]) -> Dict[str, Any]:
    env = dict(os.environ)
    env["PATH"] = "/run/current-system/sw/bin:" + env.get("PATH", "")
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = await asyncio.create_subprocess_exec(
        _aq_qa_bin(),
        phase,
        "--json",
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError(f"aq-qa timed out after {int(timeout_s)}s")

    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip() if stderr else ""
    if proc.returncode not in (0, 1):
        detail = ""
        if stderr_text:
            detail = f": stderr={stderr_text[:300]}"
        elif stdout_text:
            detail = f": stdout={stdout_text[:300]}"
        raise RuntimeError(f"aq-qa exited {proc.returncode}{detail}")

    data: Dict[str, Any] = {}
    for line in reversed(stdout_text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if not data:
        data = json.loads(stdout_text)

    data["_debug_stderr"] = stderr_text[:4096] if stderr_text else None
    data["_exit_code"] = proc.returncode
    return data


async def run_phase_json(phase: str, *, timeout_s: float, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Run one phase at a time per process; concurrent callers await it."""
    async with _TASKS_LOCK:
        task = _RUNNING_TASKS.get(phase)
        if task is None or task.done():
            task = asyncio.create_task(_execute_phase(phase, timeout_s=timeout_s, cwd=cwd))
            _RUNNING_TASKS[phase] = task
    try:
        return await task
    finally:
        async with _TASKS_LOCK:
            if _RUNNING_TASKS.get(phase) is task and task.done():
                _RUNNING_TASKS.pop(phase, None)
