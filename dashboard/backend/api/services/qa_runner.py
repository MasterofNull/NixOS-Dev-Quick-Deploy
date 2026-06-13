"""Shared single-flight runner for expensive aq-qa subprocesses."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_RUNNING_TASKS: Dict[str, "asyncio.Task[Dict[str, Any]]"] = {}
_TASKS_LOCK = asyncio.Lock()

_DASHBOARD_CONFINEMENT_MARKERS = (
    "Permission denied",
    "Read-only file system",
    "No usable temporary directory found",
    "ModuleNotFoundError: No module named",
)

_DASHBOARD_HOST_ONLY_PHASE0_IDS = {
    "0.2.4",  # postgres table-count probe uses psql
    "0.2.5",  # redis key-count probe uses redis-cli
    "0.5.1",  # Continue CLI user-lane probe
    "0.5.2",  # Continue config under the primary user's home
    "0.5.3",  # VSCodium extension list under the primary user's home
    "0.5.5",  # Continue prompt trimming smoke
    "0.5.6",  # Continue/editor feedback smoke
    "0.6.1",  # remote flagship CLI smoke
    "0.6.2",  # Gemini CLI live-state smoke
    "0.10.4",  # discovery-agent test imports full local-agent env
    "0.10.5",  # model catalog freshness imports full coordinator deps
    "0.10.6",  # flat PRD gate needs writable temp
    "0.10.7",  # artifact policy shells out to git
    "0.10.8",  # memory registry shells out to git
    "0.10.9",  # delegation artifact persistence needs writable temp/runtime deps
    "0.10.13",  # inference budget sidecar tests need writable temp
    "0.10.14",  # local-agent store_memory imports full local-agent env
    "0.150.1",  # candidate lifecycle manager needs writable temp
    "83.1",  # py_compile writes pyc unless PYTHONDONTWRITEBYTECODE is honored
    "83.2",
    "83.3",  # DAG integration imports full runtime deps
    "85.1",
    "85.2",
    "86.2",  # attention queue smoke needs writable temp
    "86.4",  # aq-alerts executable path under dashboard confinement
}


def _repo_root() -> Path:
    return Path(os.environ.get("REPO_ROOT") or Path(__file__).resolve().parents[4])


def _aq_qa_bin() -> str:
    repo_script = _repo_root() / "scripts" / "ai" / "aq-qa"
    if repo_script.is_file():
        return str(repo_script)
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


def _qa_command() -> list[str]:
    harness_main = _repo_root() / "scripts" / "testing" / "harness_qa" / "main.py"
    if harness_main.is_file():
        return [sys.executable, str(harness_main)]
    return [_bash_bin(), _aq_qa_bin()]


def _recount(data: Dict[str, Any]) -> None:
    tests = data.get("tests")
    if not isinstance(tests, list):
        return

    layers: dict[str, list[dict[str, Any]]] = {}
    passed = failed = skipped = 0
    for item in tests:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").upper()
        if status == "PASS":
            passed += 1
        elif status == "FAIL":
            failed += 1
        elif status == "SKIP":
            skipped += 1
        layer = item.get("layer")
        try:
            layer_key = str(int(layer))
        except (TypeError, ValueError):
            layer_key = str(layer or "?")
        layers.setdefault(layer_key, []).append(item)

    data["passed"] = passed
    data["failed"] = failed
    data["skipped"] = skipped
    data["layers"] = {k: v for k, v in sorted(layers.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 99)}


def _normalize_dashboard_confined_phase0(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mark host-only checks as SKIP when phase 0 runs inside the dashboard unit.

    The dashboard API is intentionally confined with ProtectHome, AppArmor, and a
    narrow Python/runtime environment. Phase-0 host QA remains authoritative when
    run from the shell, but the OSI card should not render expected dashboard
    confinement limits as broken AI stack services.
    """
    if str(data.get("phase")) != "0":
        return data

    normalized = 0
    for item in data.get("tests") or []:
        if not isinstance(item, dict) or item.get("status") != "FAIL":
            continue
        check_id = str(item.get("id") or "")
        description = str(item.get("description") or "")
        if check_id not in _DASHBOARD_HOST_ONLY_PHASE0_IDS:
            continue
        if not any(marker in description for marker in _DASHBOARD_CONFINEMENT_MARKERS) and check_id not in {
            "0.5.1",
            "0.5.3",
            "0.5.5",
            "0.5.6",
            "0.6.1",
            "0.6.2",
        }:
            continue
        item["status"] = "SKIP"
        item["description"] = (
            f"{description} (dashboard-confined: host-only probe; "
            "use aq-qa 0 --machine as the authoritative host check)"
        )
        normalized += 1

    if normalized:
        data["dashboard_confined_normalized"] = True
        data["dashboard_confined_skips"] = normalized
        _recount(data)
    return data


def _bash_bin() -> str:
    path = os.environ.get("BASH_BIN") or shutil.which("bash") or "/run/current-system/sw/bin/bash"
    if not path:
        raise RuntimeError("bash not found in BASH_BIN, PATH, or /run/current-system/sw/bin")
    return str(path)


async def _execute_phase(phase: str, *, timeout_s: float, cwd: Optional[Path]) -> Dict[str, Any]:
    env = dict(os.environ)
    env["PATH"] = "/run/current-system/sw/bin:" + env.get("PATH", "")
    env.setdefault("PYTHONUNBUFFERED", "1")
    if phase == "0":
        env.setdefault("AQ_QA_DASHBOARD_SAFE", "1")
    proc = await asyncio.create_subprocess_exec(
        *_qa_command(),
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
            detail = f": stderr={stderr_text[:2000]}"
        elif stdout_text:
            detail = f": stdout={stdout_text[:2000]}"
        raise RuntimeError(f"aq-qa exited {proc.returncode}{detail}")
    if not stdout_text:
        detail = f"exit={proc.returncode}"
        if stderr_text:
            detail += f" stderr={stderr_text[:2000]}"
        raise RuntimeError(f"aq-qa emitted no stdout ({detail})")

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
        try:
            data = json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            detail = f"exit={proc.returncode} stdout={stdout_text[:2000]}"
            if stderr_text:
                detail += f" stderr={stderr_text[:2000]}"
            raise RuntimeError(f"aq-qa emitted non-JSON output ({detail})") from exc

    data["_debug_stderr"] = stderr_text[:4096] if stderr_text else None
    data["_exit_code"] = proc.returncode
    return data


async def run_phase_json(
    phase: str,
    *,
    timeout_s: float,
    cwd: Optional[Path] = None,
    normalize_dashboard_confined: bool = False,
) -> Dict[str, Any]:
    """Run one phase at a time per process; concurrent callers await it."""
    async with _TASKS_LOCK:
        task = _RUNNING_TASKS.get(phase)
        if task is None or task.done():
            task = asyncio.create_task(_execute_phase(phase, timeout_s=timeout_s, cwd=cwd))
            _RUNNING_TASKS[phase] = task
    try:
        data = await task
        if normalize_dashboard_confined:
            data = json.loads(json.dumps(data))
            return _normalize_dashboard_confined_phase0(data)
        return data
    finally:
        async with _TASKS_LOCK:
            if _RUNNING_TASKS.get(phase) is task and task.done():
                _RUNNING_TASKS.pop(phase, None)
