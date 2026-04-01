"""Dashboard configuration and control-plane inventory endpoints."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import aiohttp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import service_endpoints

router = APIRouter()
logger = logging.getLogger(__name__)

_CONFIG: Dict[str, Any] = {
    "rate_limit": 60,
    "checkpoint_interval": 100,
    "backpressure_threshold_mb": 100,
    "log_level": "INFO",
}


class ConfigPayload(BaseModel):
    rate_limit: int = 60
    checkpoint_interval: int = 100
    backpressure_threshold_mb: int = 100
    log_level: str = "INFO"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _workflow_blueprints_path() -> Path:
    return _repo_root() / "config" / "workflow-blueprints.json"


def _load_secret_from_file(env_var: str) -> str:
    secret_path = os.getenv(env_var, "").strip()
    if not secret_path:
        return ""
    try:
        return Path(secret_path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _hybrid_headers() -> Dict[str, str]:
    api_key = os.getenv("HYBRID_API_KEY", "").strip() or _load_secret_from_file("HYBRID_API_KEY_FILE")
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


async def _fetch_hybrid_health() -> Dict[str, Any]:
    url = f"{service_endpoints.HYBRID_URL}/health"
    timeout = aiohttp.ClientTimeout(total=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=_hybrid_headers()) as response:
                if response.status != 200:
                    logger.warning("Hybrid health probe returned %s for %s", response.status, url)
                    return {}
                return await response.json()
    except Exception as exc:
        logger.warning("Failed fetching hybrid health for dashboard config inventory: %s", exc)
        return {}


def _load_workflow_blueprints() -> List[Dict[str, Any]]:
    blueprint_path = _workflow_blueprints_path()
    try:
        payload = json.loads(blueprint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed loading workflow blueprints from %s: %s", blueprint_path, exc)
        return []

    blueprints = payload.get("blueprints")
    if not isinstance(blueprints, list):
        return []

    summarized: List[Dict[str, Any]] = []
    for entry in blueprints:
        if not isinstance(entry, dict):
            continue
        policy = entry.get("orchestration_policy") or {}
        summarized.append(
            {
                "workflow_id": str(entry.get("id") or ""),
                "name": str(entry.get("name") or entry.get("id") or "unnamed"),
                "runtime_editable": False,
                "redeploy_required": True,
                "orchestration_policy": {
                    "primary_lane": policy.get("primary_lane"),
                    "reviewer_lane": policy.get("reviewer_lane"),
                    "escalation_lane": policy.get("escalation_lane"),
                    "collaborator_lanes": list(policy.get("collaborator_lanes") or []),
                    "allow_parallel_subagents": bool(policy.get("allow_parallel_subagents", False)),
                    "max_parallel_subagents": int(policy.get("max_parallel_subagents", 1) or 1),
                },
            }
        )
    return summarized


async def _build_config_snapshot() -> Dict[str, Any]:
    hybrid_health = await _fetch_hybrid_health()
    harness_state = dict(hybrid_health.get("ai_harness") or {})
    workflow_blueprints = _load_workflow_blueprints()

    return {
        "rate_limit": _CONFIG["rate_limit"],
        "checkpoint_interval": _CONFIG["checkpoint_interval"],
        "backpressure_threshold_mb": _CONFIG["backpressure_threshold_mb"],
        "log_level": _CONFIG["log_level"],
        "dashboard_runtime": dict(_CONFIG),
        "harness_runtime": {
            "source": f"{service_endpoints.HYBRID_URL}/health",
            "runtime_editable": False,
            "redeploy_required": False,
            "settings": harness_state,
        },
        "workflow_blueprints": workflow_blueprints,
        "control_plane_inventory": {
            "dashboard_runtime_controls": [
                {
                    "surface": "/api/config",
                    "scope": "dashboard-api only",
                    "runtime_editable": True,
                    "redeploy_required": False,
                    "fields": sorted(_CONFIG.keys()),
                }
            ],
            "live_runtime_sources": [
                {
                    "surface": "/health ai_harness",
                    "scope": "hybrid coordinator live runtime",
                    "runtime_editable": False,
                    "redeploy_required": False,
                }
            ],
            "redeploy_required_sources": [
                {
                    "surface": "config/workflow-blueprints.json",
                    "scope": "workflow orchestration policy",
                    "runtime_editable": False,
                    "redeploy_required": True,
                }
            ],
            "known_gaps": [
                {
                    "surface": "/api/config",
                    "status": "misleading",
                    "detail": "Legacy dashboard config writes only dashboard-local runtime values, not hybrid harness or Nix settings.",
                },
                {
                    "surface": "/api/actions",
                    "status": "separate-config",
                    "detail": "Action catalog is loaded from ~/.local/share/nixos-system-dashboard/config.json instead of the hybrid coordinator control plane.",
                },
                {
                    "surface": "/api/collaboration and /api/workflows",
                    "status": "miswired",
                    "detail": "These routes expose standalone libraries instead of the live hybrid coordinator workflow/session state.",
                },
            ],
        },
        "legacy_notice": (
            "Dashboard runtime controls are local to the dashboard API. "
            "AI harness flags are read from the live hybrid coordinator, and workflow blueprint "
            "sub-agent policy changes require editing config/workflow-blueprints.json followed by redeploy or restart."
        ),
    }


@router.get("")
async def get_runtime_config() -> Dict[str, Any]:
    """Return dashboard runtime config plus live harness control-plane inventory."""
    return await _build_config_snapshot()


@router.post("")
async def update_runtime_config(payload: ConfigPayload) -> Dict[str, Any]:
    """Update dashboard-local runtime configuration only."""
    _CONFIG.update(payload.model_dump())
    snapshot = await _build_config_snapshot()
    snapshot.update(
        {
            "status": "ok",
            "scope": "dashboard-runtime-only",
            "restarted": [],
            "warning": (
                "This endpoint updates dashboard-local runtime settings only. "
                "AI harness and workflow blueprint settings are not changed here."
            ),
        }
    )
    return snapshot


@router.get("/{file_name}")
async def get_config(file_name: str) -> Dict[str, Any]:
    """Get a supported config file content preview."""
    try:
        if file_name != "workflow-blueprints.json":
            raise HTTPException(status_code=404, detail="Unsupported config file")
        path = _workflow_blueprints_path()
        return {
            "file_name": file_name,
            "path": str(path),
            "content": path.read_text(encoding="utf-8"),
            "redeploy_required": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{file_name}")
async def update_config(file_name: str, content: str) -> Dict[str, Any]:
    """Reject unsupported dashboard file writes instead of pretending success."""
    raise HTTPException(
        status_code=501,
        detail=(
            f"Dashboard API does not support editing {file_name} yet. "
            "Use declarative repo changes for Nix or workflow blueprint updates."
        ),
    )
