"""Systemd unit discovery helpers for AI stack monitoring."""
from __future__ import annotations

import subprocess
import time
from typing import List

DEFAULT_AI_STACK_UNITS: List[str] = [
    "ai-aidb",
    "ai-hybrid-coordinator",
    "ai-ralph-wiggum",
    "ai-auth-selftest",
    "ai-otel-collector",
    "llama-cpp",
    "qdrant",
    "redis-mcp",
    "postgresql",
]

DASHBOARD_UNITS: List[str] = [
    "command-center-dashboard-api",
    "command-center-dashboard-frontend",
]

NON_RUNTIME_AI_UNITS = {
    "ai-auth-selftest",
    "ai-pgvector-bootstrap",
}

_CACHE_TTL_SECONDS = 15
_CACHE_UNITS: List[str] = []
_CACHE_EXPIRES_AT = 0.0


def _normalize_service_names(raw_units: List[str]) -> List[str]:
    names = []
    for unit in raw_units:
        clean = unit.strip()
        if not clean.endswith(".service"):
            continue
        names.append(clean[:-8])
    return sorted(set(names))


def _discover_from_show() -> List[str]:
    cmd = [
        "systemctl",
        "show",
        "ai-stack.target",
        "--property=Wants",
        "--property=Requires",
        "--value",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []
    raw = (result.stdout or "").replace("\n", " ").split()
    return _normalize_service_names(raw)


def _discover_from_dependencies() -> List[str]:
    cmd = [
        "systemctl",
        "list-dependencies",
        "ai-stack.target",
        "--plain",
        "--no-pager",
        "--full",
        "--type=service",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []

    raw_units: List[str] = []
    for line in (result.stdout or "").splitlines():
        token = line.strip().lstrip("+-* ").strip()
        if token:
            raw_units.append(token)
    return _normalize_service_names(raw_units)


def get_ai_stack_units() -> List[str]:
    """Return AI stack units discovered from ai-stack.target with TTL caching."""
    global _CACHE_UNITS, _CACHE_EXPIRES_AT
    now = time.time()
    if _CACHE_UNITS and now < _CACHE_EXPIRES_AT:
        return list(_CACHE_UNITS)

    discovered = _discover_from_show() or _discover_from_dependencies()
    units = discovered or list(DEFAULT_AI_STACK_UNITS)
    _CACHE_UNITS = units
    _CACHE_EXPIRES_AT = now + _CACHE_TTL_SECONDS
    return list(units)


def get_monitored_units(include_dashboard: bool = True) -> List[str]:
    units = get_ai_stack_units()
    if include_dashboard:
        units = sorted(set(units + DASHBOARD_UNITS))
    return units


def get_ai_runtime_units() -> List[str]:
    """Return AI units expected to be long-running runtime services."""
    return [u for u in get_ai_stack_units() if u not in NON_RUNTIME_AI_UNITS]
