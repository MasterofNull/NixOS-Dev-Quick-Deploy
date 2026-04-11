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


def _agent_discovery_manifest_path() -> Path:
    return _repo_root() / "config" / "ai-stack-agent-discovery.json"


def _harness_first_policy_path() -> Path:
    return _repo_root() / "config" / "harness-first-policy.json"


def _harness_runbook_path() -> Path:
    return _repo_root() / "docs" / "harness-first" / "HARNESS-FIRST-RUNBOOK.md"


def _harness_evidence_template_path() -> Path:
    return _repo_root() / "docs" / "harness-first" / "HARNESS-FIRST-EVIDENCE-TEMPLATE.md"


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


def _load_agent_discovery_manifest() -> Dict[str, Any]:
    manifest_path = _agent_discovery_manifest_path()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed loading agent discovery manifest from %s: %s", manifest_path, exc)
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_harness_first_policy() -> Dict[str, Any]:
    policy_path = _harness_first_policy_path()
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed loading harness-first policy from %s: %s", policy_path, exc)
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_markdown_excerpt(path: Path, max_lines: int = 24) -> List[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Failed loading markdown excerpt from %s: %s", path, exc)
        return []
    excerpt = [line.rstrip() for line in lines[:max_lines]]
    return [line for line in excerpt if line.strip()]


def _bool_env(name: str, default: bool) -> bool:
    value = str(os.getenv(name, str(default).lower())).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _frontdoor_profile(name: str, fallback: str) -> str:
    return str(os.getenv(name, fallback) or fallback).strip()


def _build_frontdoor_routing_snapshot() -> Dict[str, Any]:
    aliases = [
        {"route": "default", "profile": _frontdoor_profile("AI_LOCAL_FRONTDOOR_DEFAULT_PROFILE", "default")},
        {"route": "Explore", "profile": _frontdoor_profile("AI_LOCAL_FRONTDOOR_EXPLORE_PROFILE", "default")},
        {"route": "Plan", "profile": _frontdoor_profile("AI_LOCAL_FRONTDOOR_PLAN_PROFILE", "default")},
        {
            "route": "Implementation",
            "profile": _frontdoor_profile("AI_LOCAL_FRONTDOOR_IMPLEMENTATION_PROFILE", "remote-coding"),
        },
        {
            "route": "Reasoning",
            "profile": _frontdoor_profile("AI_LOCAL_FRONTDOOR_REASONING_PROFILE", "remote-reasoning"),
        },
        {
            "route": "ToolCalling",
            "profile": _frontdoor_profile("AI_LOCAL_FRONTDOOR_TOOL_CALLING_PROFILE", "local-tool-calling"),
        },
        {"route": "Continuation", "profile": _frontdoor_profile("AI_LOCAL_FRONTDOOR_CONTINUATION_PROFILE", "default")},
    ]
    return {
        "enabled": _bool_env("AI_LOCAL_FRONTDOOR_ROUTING_ENABLE", True),
        "runtime_editable": False,
        "redeploy_required": True,
        "source": "AI_LOCAL_FRONTDOOR_* env vars (declarative service defaults)",
        "aliases": aliases,
    }


async def _build_config_snapshot() -> Dict[str, Any]:
    hybrid_health = await _fetch_hybrid_health()
    harness_state = dict(hybrid_health.get("ai_harness") or {})
    workflow_blueprints = _load_workflow_blueprints()
    discovery_manifest = _load_agent_discovery_manifest()
    harness_policy = _load_harness_first_policy()
    primary_contact = dict(discovery_manifest.get("primary_contact") or {})
    frontdoor_routing = _build_frontdoor_routing_snapshot()
    workflow_loop = list(primary_contact.get("workflow_loop") or [])
    bootstrap_commands = list(primary_contact.get("bootstrap") or [])
    policy_required_commands = list(harness_policy.get("required_commands") or [])
    policy_required_sections = list(harness_policy.get("required_sections") or [])
    policy_required_evidence = list(harness_policy.get("required_evidence_sections") or [])

    docs_sources = [
        {
            "label": "Harness-First Runbook",
            "path": str(_harness_runbook_path()),
            "preview_lines": _load_markdown_excerpt(_harness_runbook_path()),
            "redeploy_required": False,
        },
        {
            "label": "Harness Evidence Template",
            "path": str(_harness_evidence_template_path()),
            "preview_lines": _load_markdown_excerpt(_harness_evidence_template_path()),
            "redeploy_required": False,
        },
        {
            "label": "Harness-First Policy",
            "path": str(_harness_first_policy_path()),
            "preview_lines": [],
            "redeploy_required": True,
        },
        {
            "label": "Agent Discovery Manifest",
            "path": str(_agent_discovery_manifest_path()),
            "preview_lines": [],
            "redeploy_required": True,
        },
        {
            "label": "Workflow Blueprints",
            "path": str(_workflow_blueprints_path()),
            "preview_lines": [],
            "redeploy_required": True,
        },
    ]

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
        "frontdoor_routing": frontdoor_routing,
        "primary_contact": {
            "human_frontdoor": primary_contact.get("human_frontdoor") or "local-orchestrator",
            "bootstrap": bootstrap_commands,
            "workflow_loop": workflow_loop,
            "routing_aliases": dict(primary_contact.get("routing_aliases") or {}),
            "source": str(_agent_discovery_manifest_path()),
        },
        "harness_workflow": {
            "workflow_loop": workflow_loop,
            "bootstrap_commands": bootstrap_commands,
            "required_commands": policy_required_commands,
            "required_sections": policy_required_sections,
            "required_evidence_sections": policy_required_evidence,
            "runbook": harness_policy.get("runbook") or str(_harness_runbook_path()),
            "evidence_template": harness_policy.get("evidence_template") or str(_harness_evidence_template_path()),
            "source": str(_harness_first_policy_path()),
        },
        "documentation_sources": docs_sources,
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
                },
                {
                    "surface": "AI_LOCAL_FRONTDOOR_*",
                    "scope": "local harness first-layer route aliases",
                    "runtime_editable": False,
                    "redeploy_required": True,
                },
                {
                    "surface": "config/harness-first-policy.json",
                    "scope": "canonical harness workflow contract and evidence requirements",
                    "runtime_editable": False,
                    "redeploy_required": True,
                }
            ],
            "redeploy_required_sources": [
                {
                    "surface": "config/workflow-blueprints.json",
                    "scope": "workflow orchestration policy",
                    "runtime_editable": False,
                    "redeploy_required": True,
                },
                {
                    "surface": "config/ai-stack-agent-discovery.json",
                    "scope": "primary human contact surface and agent bootstrap manifest",
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
                {
                    "surface": "dashboard front-door controls",
                    "status": "observe-only",
                    "detail": "The dashboard now shows local front-door routing and primary contact surfaces, but changing them still requires declarative config plus restart/redeploy.",
                },
            ],
        },
        "legacy_notice": (
            "Dashboard runtime controls are local to the dashboard API. "
            "AI harness flags and first-layer route aliases are read from the live hybrid coordinator or declarative env, "
            "and workflow blueprint or primary-contact changes require editing repo config followed by redeploy or restart."
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
        supported_paths = {
            "workflow-blueprints.json": (_workflow_blueprints_path(), True),
            "ai-stack-agent-discovery.json": (_agent_discovery_manifest_path(), True),
            "harness-first-policy.json": (_harness_first_policy_path(), True),
            "HARNESS-FIRST-RUNBOOK.md": (_harness_runbook_path(), False),
            "HARNESS-FIRST-EVIDENCE-TEMPLATE.md": (_harness_evidence_template_path(), False),
        }
        if file_name not in supported_paths:
            raise HTTPException(status_code=404, detail="Unsupported config file")
        path, redeploy_required = supported_paths[file_name]
        return {
            "file_name": file_name,
            "path": str(path),
            "content": path.read_text(encoding="utf-8"),
            "redeploy_required": redeploy_required,
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
