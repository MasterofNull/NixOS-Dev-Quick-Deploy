"""Shared single-flight runner for expensive aq-qa subprocesses."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_RUNNING_TASKS: Dict[str, "asyncio.Task[Dict[str, Any]]"] = {}
_TASKS_LOCK = asyncio.Lock()

_SYSTEM_BIN = "/run/current-system/sw/bin"
_DASHBOARD_QA_TMPDIR = "qa-runner-tmp"
_DASHBOARD_QA_PYCACHE = "qa-runner-pycache"
_DASHBOARD_QA_CARGO_TARGET = "qa-runner-cargo-target"

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
    "0.10.26",  # context compaction sandwich imports full switchboard deps
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


def _dashboard_data_dir() -> Path:
    return Path(os.environ.get("DASHBOARD_DATA_DIR") or _repo_root() / ".agents" / "dashboard")


def _runtime_path(name: str) -> Path:
    return _dashboard_data_dir() / name


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
    tmpdir = _runtime_path(_DASHBOARD_QA_TMPDIR)
    pycache_dir = _runtime_path(_DASHBOARD_QA_PYCACHE)
    cargo_target_dir = _runtime_path(_DASHBOARD_QA_CARGO_TARGET)
    for path in (tmpdir, pycache_dir, cargo_target_dir):
        path.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PATH"] = f"{Path(sys.executable).resolve().parent}:{_SYSTEM_BIN}:" + env.get("PATH", "")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env["PYTHONPYCACHEPREFIX"] = str(pycache_dir)
    env["CARGO_TARGET_DIR"] = str(cargo_target_dir)
    for name in ("TMPDIR", "TEMP", "TMP"):
        env[name] = str(tmpdir)
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


# ---------------------------------------------------------------------------
# A2 — bounded passive projection reader for the C1A provider-probe heartbeat
# (`.agent/qa/provider-probe-active.json`, schema `qa.provider-probe-active.v1`).
# Binds only to that file path and schema — never to qa-provider-probe.py
# internals or its publication barrier. Read-only; never QA pass/fail
# authority; never starts, mutates, or extends any QA/provider/evidence state.
# ---------------------------------------------------------------------------
_PROBE_ACTIVE_REL_PARTS = (".agent", "qa", "provider-probe-active.json")
_PROBE_ACTIVE_MAX_BYTES = 16384
_PROBE_FRESHNESS_MS = 5000

_PROBE_PROVIDER_IDS = frozenset({"codex", "qwen", "claude", "pi"})
_PROBE_LIFECYCLE_STATES = frozenset(
    {"idle", "starting", "running", "terminating", "reaping", "terminal"}
)
_PROBE_FAILURE_CLASSES = frozenset(
    {
        "none",
        "executable_missing",
        "spawn_failed",
        "exit_nonzero",
        "provider_reported_failure",
        "machine_output_missing",
        "machine_output_invalid",
        "deadline_exceeded",
        "output_limit_exceeded",
        "cleanup_failed",
        "interrupted",
        "probe_busy",
        "contract_invalid",
    }
)
_PROBE_ACTIVE_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "qa_invocation_id",
        "provider_id",
        "lifecycle_state",
        "elapsed_ms",
        "heartbeat_utc",
        "deadline_ms",
        "last_terminal_failure_class",
    }
)
_PROBE_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _probe_active_path() -> Path:
    return _repo_root().joinpath(*_PROBE_ACTIVE_REL_PARTS)


def _parse_probe_heartbeat_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _read_probe_active_raw() -> Optional[Dict[str, Any]]:
    """Read and structurally validate the C1A heartbeat file.

    Returns None (rejects) for any non-regular, symlinked, oversized,
    malformed, unbound (schema/enum mismatch), or future-dated object —
    "missing/stale/malformed" per the projection contract are always
    treated as non-healthy. Never inspects QA cache, evidence, or
    qa-provider-probe.py internals; the only I/O is one bounded read of
    this one file.
    """
    path = _probe_active_path()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError:
        return None
    try:
        try:
            st = os.fstat(fd)
        except OSError:
            return None
        if not stat.S_ISREG(st.st_mode):
            return None
        if st.st_size <= 0 or st.st_size > _PROBE_ACTIVE_MAX_BYTES:
            return None
        try:
            raw = os.read(fd, _PROBE_ACTIVE_MAX_BYTES + 1)
        except OSError:
            return None
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    if len(raw) > _PROBE_ACTIVE_MAX_BYTES:
        return None
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(obj, dict) or set(obj.keys()) != _PROBE_ACTIVE_REQUIRED_FIELDS:
        return None
    if obj.get("schema_version") != "qa.provider-probe-active.v1":
        return None
    invocation_id = obj.get("qa_invocation_id")
    if not isinstance(invocation_id, str) or not _PROBE_UUID_RE.match(invocation_id):
        return None
    lifecycle_state = obj.get("lifecycle_state")
    if lifecycle_state not in _PROBE_LIFECYCLE_STATES:
        return None
    provider_id = obj.get("provider_id")
    if lifecycle_state == "idle":
        if provider_id is not None:
            return None
    elif provider_id not in _PROBE_PROVIDER_IDS:
        return None
    elapsed_ms = obj.get("elapsed_ms")
    if isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, int):
        return None
    if elapsed_ms < 0 or elapsed_ms > 300000:
        return None
    if obj.get("deadline_ms") != 45000:
        return None
    last_failure_class = obj.get("last_terminal_failure_class")
    if lifecycle_state == "terminal":
        if last_failure_class not in _PROBE_FAILURE_CLASSES:
            return None
    elif last_failure_class is not None:
        return None
    heartbeat_dt = _parse_probe_heartbeat_utc(obj.get("heartbeat_utc"))
    if heartbeat_dt is None:
        return None
    if heartbeat_dt > datetime.now(timezone.utc):
        return None  # future-dated — never trusted; folded into "unavailable"
    return {
        "qa_invocation_id": invocation_id,
        "provider_id": provider_id,
        "lifecycle_state": lifecycle_state,
        "elapsed_ms": elapsed_ms,
        "last_failure_class": last_failure_class,
        "heartbeat_dt": heartbeat_dt,
    }


def _probe_dashboard_confined() -> bool:
    # Same env var and truthy-set already used for phase-0 dashboard
    # confinement elsewhere in this module; no new env var introduced.
    return os.environ.get("AQ_QA_DASHBOARD_SAFE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_provider_probe_projection() -> Dict[str, Any]:
    """Pure bounded projection of the C1A heartbeat for dashboard display.

    Returns only the fixed `provider_probe` shape (design-packet SS4.1):
    availability, provider_id, lifecycle_state, elapsed_ms,
    last_failure_class, freshness_ms, qa_invocation_id, host_execution.
    Never starts a probe, never touches the QA cache/evidence, and is
    never pass/fail authority — a stale or unavailable projection cannot
    change Phase-0 status, counts, badge, cache, or acceptance.
    """
    confined = _probe_dashboard_confined()
    raw = _read_probe_active_raw()
    if raw is None:
        return {
            "availability": "unavailable",
            "provider_id": None,
            "lifecycle_state": "unavailable",
            "elapsed_ms": None,
            "last_failure_class": None,
            "freshness_ms": None,
            "qa_invocation_id": None,
            "host_execution": "dashboard_confined_skip" if confined else "unavailable",
        }

    now = datetime.now(timezone.utc)
    freshness_ms = int((now - raw["heartbeat_dt"]).total_seconds() * 1000.0)
    if freshness_ms < 0:
        freshness_ms = 0
    availability = "current" if freshness_ms <= _PROBE_FRESHNESS_MS else "stale"

    if confined:
        host_execution = "dashboard_confined_skip"
    elif raw["lifecycle_state"] == "terminal":
        host_execution = "terminal"
    else:
        host_execution = "active"

    return {
        "availability": availability,
        "provider_id": raw["provider_id"],
        "lifecycle_state": raw["lifecycle_state"],
        "elapsed_ms": raw["elapsed_ms"],
        "last_failure_class": raw["last_failure_class"],
        "freshness_ms": freshness_ms,
        "qa_invocation_id": raw["qa_invocation_id"],
        "host_execution": host_execution,
    }
