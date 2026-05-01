"""
AI coordinator, parity, skill, autoresearch, and research HTTP handlers.

Covers:
  - GET  /parity/scorecard
  - GET  /control/ai-coordinator/status
  - GET  /control/ai-coordinator/lessons
  - POST /control/ai-coordinator/lessons/review
  - GET  /control/ai-coordinator/evaluations
  - GET  /control/ai-coordinator/evaluations/trends
  - GET  /control/ai-coordinator/skills
  - POST /control/ai-coordinator/delegate
  - GET  /control/ai-coordinator/delegate/status/{task_id}
  - GET  /control/skills/usage
  - GET  /control/skills/recommendations
  - GET  /control/autoresearch/status
  - POST /control/autoresearch/run
  - POST /research/web/fetch
  - POST /research/web/browser-fetch
  - POST /research/workflows/curated-fetch

Extracted from http_server.py (Phase 12.4 decomposition).
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
from aiohttp import web

# Match http_server.py path bootstrap so this module can import from
# sibling capability/efficiency helpers when loaded under systemd.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "observability"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "offloading"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "efficiency"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "progressive-disclosure"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "capability-gap"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "real-time-learning"))

from agent_pool_manager import RemoteAgent
from config import Config
from metrics import (
    CAPABILITY_GAP_DETECTIONS,
    DELEGATED_PROMPT_TOKENS_AFTER,
    DELEGATED_PROMPT_TOKENS_BEFORE,
    DELEGATED_PROMPT_TOKEN_SAVINGS,
    DELEGATED_QUALITY_EVENTS,
    DELEGATED_QUALITY_SCORE,
    META_LEARNING_ADAPTATIONS,
    PROGRESSIVE_CONTEXT_LOADS,
    REAL_TIME_LEARNING_EVENTS,
)
from ai_coordinator import (
    build_messages as _ai_coordinator_build_messages,
    build_reasoning_finalization_messages as _ai_coordinator_build_reasoning_finalization_messages,
    build_tool_call_finalization_messages as _ai_coordinator_build_tool_call_finalization_messages,
    build_empty_content_retry_messages as _ai_coordinator_build_empty_content_retry_messages,
    default_runtime_id_for_profile as _ai_coordinator_default_runtime_id_for_profile,
    local_fallback_profile as _ai_coordinator_local_fallback_profile,
    route_by_complexity as _ai_coordinator_route_by_complexity,
)
from delegation_feedback import (
    build_recovered_artifact,
    classify_delegated_response,
    record_delegation_feedback,
)
from delegation_handlers import (
    _REMOTE_AVAIL_TTL_S,
    _apply_progressive_context,
    _apply_remote_runtime_status,
    _assess_delegated_response_quality,
    _build_delegation_fallback_chain,
    _extract_delegated_response_text,
    _inject_delegated_response_text,
    _is_remote_profile,
    _optimize_delegated_messages,
    _remote_avail_cache_get,
    _remote_avail_cache_set,
    _remote_profile_uses_agent_pool,
    _select_agent_pool_candidate,
    _select_next_available_delegation_target,
)
import model_fleet_manager as _mfm
import agentic_memory_journal as _journal
from real_time_learning_engine import (
    _GAP_DETECTOR,
    _build_gap_failure_text,
    _plan_capability_gap_remediation,
    _record_capability_gap_outcomes,
    _apply_real_time_learning,
    _apply_meta_learning,
)
from runtime_manager import (
    _runtime_registry_lock,
    _coerce_orchestration_context,
    _load_runtime_registry,
    _provider_health_summary,
    _get_domain_disclosure_summary,
    _parity_scorecard_path,
)
from agent_registry import (
    _agent_lessons_lock,
    _agent_evaluations_lock,
    _active_lesson_refs,
    _load_agent_lessons_registry,
    _save_agent_lessons_registry,
    _load_agent_evaluations_registry,
)
from workflow_planning import _load_aq_report_status_summary
from skill_usage_tracker import (
    get_skill_usage_stats as _get_skill_usage_stats,
    get_skill_recommendation as _get_skill_recommendation,
)

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level state (promoted / moved from http_server.py)
# ---------------------------------------------------------------------------

# Model catalog cache (moved from http_server.py module-level)
_MODEL_CATALOG: Dict[str, Any] = {}
_MODEL_CATALOG_TS: float = 0.0
_MODEL_CATALOG_TTL_S = 300.0
_MODEL_CATALOG_PATH = Path(__file__).resolve().parents[3] / "config" / "model-catalog.yaml"

# Async delegate task registry (Phase 8.6)
_DELEGATE_TASK_REGISTRY: Dict[str, Dict[str, Any]] = {}
_DELEGATE_TASK_TTL_S: float = 600.0

# ---------------------------------------------------------------------------
# Injected dependencies
# ---------------------------------------------------------------------------
_AGENT_POOL_MANAGER: Optional[Any] = None
_store_memory: Optional[Callable] = None
_error_payload: Optional[Callable] = None


def init(
    *,
    agent_pool_manager: Any,
    store_memory_fn: Callable,
    error_payload_fn: Callable,
) -> None:
    """Inject runtime dependencies. Call once from http_server.py init()."""
    global _AGENT_POOL_MANAGER, _store_memory, _error_payload
    _AGENT_POOL_MANAGER = agent_pool_manager
    _store_memory = store_memory_fn
    _error_payload = error_payload_fn


# ---------------------------------------------------------------------------
# Supporting helpers (moved from http_server.py module-level)
# ---------------------------------------------------------------------------

def _load_model_catalog() -> Dict[str, Any]:
    """Return flat catalog dict keyed by model key, re-reading YAML if stale."""
    global _MODEL_CATALOG, _MODEL_CATALOG_TS
    now = time.time()
    if _MODEL_CATALOG and now - _MODEL_CATALOG_TS < _MODEL_CATALOG_TTL_S:
        return _MODEL_CATALOG
    if not _MODEL_CATALOG_PATH.exists():
        return _MODEL_CATALOG  # keep stale cache if file missing
    try:
        import yaml  # pyyaml — in ai-stack.nix dependencies
        raw = yaml.safe_load(_MODEL_CATALOG_PATH.read_text())
        catalog: Dict[str, Any] = {}
        for section in ("chat_models", "embedding_models"):
            for key, entry in (raw.get(section) or {}).items():
                catalog[key] = entry
        _MODEL_CATALOG = catalog
        _MODEL_CATALOG_TS = now
    except Exception as exc:
        logger.warning("model-catalog.yaml load failed: %s", exc)
    return _MODEL_CATALOG


def _active_model_capabilities() -> Dict[str, Any]:
    """Best-effort: detect the active llama.cpp model and return its catalog entry.

    Returns an empty dict if llama.cpp is not reachable or model is not in catalog.
    Uses a quick synchronous urllib call (coordinator startup/agent-spawn context).
    """
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8080/v1/models", timeout=2) as resp:
            data = json.loads(resp.read())
        models = data.get("models") or data.get("data") or []
        if not models:
            return {}
        active_file = (models[0].get("model") or models[0].get("id") or "").strip()
        catalog = _load_model_catalog()
        for entry in catalog.values():
            fname = entry.get("file", "")
            if fname and (fname in active_file or active_file.endswith(fname)):
                return entry
    except Exception:
        pass
    return {}


# Phase 14.3: Cache switchboard state for 30s to avoid repeated slow health probes
# during multi-step delegation (ReadTimeout at 2.5s under load — 3 calls per delegate).
_SWB_STATE_CACHE: Dict[str, Any] = {}
_SWB_STATE_CACHE_TS: float = 0.0
_SWB_STATE_CACHE_TTL = 30.0


async def _switchboard_ai_coordinator_state() -> Dict[str, Any]:
    global _SWB_STATE_CACHE, _SWB_STATE_CACHE_TS
    if _SWB_STATE_CACHE and (time.time() - _SWB_STATE_CACHE_TS) < _SWB_STATE_CACHE_TTL:
        return dict(_SWB_STATE_CACHE)
    state: Dict[str, Any] = {
        "remote_configured": bool(Config.SWITCHBOARD_REMOTE_URL),
        "remote_aliases": {
            "gemini": Config.SWITCHBOARD_REMOTE_ALIAS_GEMINI or Config.SWITCHBOARD_REMOTE_ALIAS_FREE or None,
            "free": Config.SWITCHBOARD_REMOTE_ALIAS_FREE or None,
            "coding": Config.SWITCHBOARD_REMOTE_ALIAS_CODING or None,
            "reasoning": Config.SWITCHBOARD_REMOTE_ALIAS_REASONING or None,
            "tool_calling": Config.SWITCHBOARD_REMOTE_ALIAS_TOOL_CALLING or None,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{Config.SWITCHBOARD_URL.rstrip('/')}/health")
        if response.status_code != 200:
            return state
        payload = response.json()
        profiles = payload.get("profiles", {}) if isinstance(payload, dict) else {}
        state["remote_configured"] = bool(payload.get("remote_configured", state["remote_configured"]))
        state["remote_aliases"] = {
            "gemini": ((profiles.get("remote-gemini") or {}).get("model_alias")) or state["remote_aliases"]["gemini"],
            "free": ((profiles.get("remote-free") or {}).get("model_alias")) or state["remote_aliases"]["free"],
            "coding": ((profiles.get("remote-coding") or {}).get("model_alias")) or state["remote_aliases"]["coding"],
            "reasoning": ((profiles.get("remote-reasoning") or {}).get("model_alias")) or state["remote_aliases"]["reasoning"],
            "tool_calling": ((profiles.get("remote-tool-calling") or {}).get("model_alias")) or state["remote_aliases"]["tool_calling"],
        }
    except Exception:
        pass
    _SWB_STATE_CACHE.update(state)
    _SWB_STATE_CACHE_TS = time.time()
    return state


async def _aidb_shared_skills_catalog(limit: int = 25) -> Dict[str, Any]:
    aidb_url = Config.AIDB_URL.rstrip("/")
    if not aidb_url:
        return {"available": False, "source": "", "skills": []}
    cache_bust = str(time.time_ns())
    url = f"{aidb_url}/skills?include_pending=true&_={cache_bust}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {"available": False, "source": url, "skills": [], "error": str(exc)[:180]}

    skills = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "")).strip().lower() != "approved":
            continue
        skills.append(
            {
                "slug": str(item.get("slug", "")).strip(),
                "name": str(item.get("name", "")).strip(),
                "description": str(item.get("description", "")).strip(),
                "managed_by": str(item.get("managed_by", "")).strip(),
                "source_path": str(item.get("source_path", "")).strip(),
            }
        )
    skills = [item for item in skills if item["slug"]]
    skills.sort(key=lambda item: item["slug"])
    return {
        "available": True,
        "source": url,
        "skills": skills[:limit],
        "total": len(skills),
        "truncated": len(skills) > limit,
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_parity_scorecard(_request: web.Request) -> web.Response:
    """Return declarative parity scorecard (from env path, fallback to repo config)."""
    try:
        path = _parity_scorecard_path()
        if not path.exists():
            return web.json_response({"scorecard": {}, "source": str(path), "exists": False})
        data = json.loads(path.read_text(encoding="utf-8"))
        return web.json_response({"scorecard": data, "source": str(path), "exists": True})
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_ai_coordinator_status(_request: web.Request) -> web.Response:
    """Expose declarative coordinator runtime lanes and switchboard-backed readiness."""
    try:
        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        runtimes = list((registry.get("runtimes", {}) or {}).values())
        swb_state = await _switchboard_ai_coordinator_state()
        remote_aliases = swb_state.get("remote_aliases", {})
        remote_configured = bool(swb_state.get("remote_configured", False))
        shared_skills = await _aidb_shared_skills_catalog(limit=10)
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        report_summary = _load_aq_report_status_summary()
        for runtime in runtimes:
            runtime_id = str(runtime.get("runtime_id", "")).strip()
            runtime = _apply_remote_runtime_status(runtime, runtime_id, remote_aliases, remote_configured)
        runtimes.sort(key=lambda item: str(item.get("runtime_id", "")))
        return web.json_response(
            {
                "status": "ok",
                "service": "ai-coordinator",
                "switchboard_url": Config.SWITCHBOARD_URL,
                "remote_configured": remote_configured,
                "remote_aliases": remote_aliases,
                "shared_skill_registry": {
                    "available": shared_skills.get("available", False),
                    "total": int(shared_skills.get("total", 0) or 0),
                    "skills": shared_skills.get("skills", []),
                    "truncated": bool(shared_skills.get("truncated", False)),
                },
                "agent_lessons": {
                    "available": lesson_registry.get("available", False),
                    "counts": lesson_registry.get("counts", {}),
                    "active_lessons": lesson_registry.get("active_lessons", []),
                },
                "report_summary": report_summary,
                "provider_health": _provider_health_summary(),
                "domain_disclosure": _get_domain_disclosure_summary(),
                "active_lesson_refs": lesson_refs,
                "runtimes": runtimes,
                "count": len(runtimes),
            }
        )
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_ai_coordinator_lessons(_request: web.Request) -> web.Response:
    """Expose the persistent agent-lesson registry."""
    try:
        async with _agent_lessons_lock:
            registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(registry, limit=2)
        return web.json_response(
            {
                "status": "ok",
                "service": "ai-coordinator",
                "agent_lessons": registry,
                "active_lesson_refs": lesson_refs,
            }
        )
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_ai_coordinator_lessons_review(request: web.Request) -> web.Response:
    """Update review state for a persisted agent lesson."""
    try:
        data = await request.json()
        requested_key = str(data.get("lesson_key") or "").strip()
        requested_state = str(data.get("state") or "").strip().lower()
        reviewer = str(data.get("reviewer") or "codex").strip()
        comment = str(data.get("comment") or "").strip()
        allowed_states = {"pending_review", "promoted", "avoided", "rejected"}
        if requested_state not in allowed_states:
            return web.json_response({"error": "state must be one of pending_review, promoted, avoided, rejected"}, status=400)
        async with _agent_lessons_lock:
            registry = await _load_agent_lessons_registry()
            entries = [item for item in (registry.get("entries") or []) if isinstance(item, dict)]
            target = None
            for item in entries:
                lesson_key = str(item.get("lesson_key", "") or "").strip()
                if requested_key and lesson_key == requested_key:
                    target = item
                    break
            if target is None:
                return web.json_response({"error": "lesson not found"}, status=404)
            stamp = datetime.utcnow().isoformat() + "Z"
            target["state"] = requested_state
            target["review"] = {
                "reviewer": reviewer[:64],
                "comment": comment[:240],
                "reviewed_at": stamp,
            }
            target["updated_at"] = stamp
            registry["entries"] = entries
            await _save_agent_lessons_registry(registry)
            registry = await _load_agent_lessons_registry()
            lesson_refs = _active_lesson_refs(registry, limit=2)
        return web.json_response(
            {
                "status": "ok",
                "service": "ai-coordinator",
                "agent_lessons": registry,
                "reviewed_lesson": target,
                "active_lesson_refs": lesson_refs,
            }
        )
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_ai_coordinator_evaluations(_request: web.Request) -> web.Response:
    """Expose longitudinal agent evaluation and selection feedback."""
    try:
        async with _agent_evaluations_lock:
            registry = await _load_agent_evaluations_registry()
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        return web.json_response(
            {
                "status": "ok",
                "service": "ai-coordinator",
                "agent_evaluations": registry,
                "active_lesson_refs": lesson_refs,
            }
        )
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_ai_coordinator_evaluation_trends(_request: web.Request) -> web.Response:
    """Expose agent evaluation trends over time for operator analysis."""
    try:
        async with _agent_evaluations_lock:
            registry = await _load_agent_evaluations_registry()

        agents = registry.get("agents", {})
        trends = []

        for agent_name, agent_data in agents.items():
            profiles = agent_data.get("profiles", {})
            roles = agent_data.get("roles", {})
            totals = agent_data.get("totals", {})

            trends.append({
                "agent": agent_name,
                "total_review_events": totals.get("review_events", 0),
                "total_consensus_selected": totals.get("consensus_selected", 0),
                "total_runtime_events": totals.get("runtime_events", 0),
                "average_review_score": totals.get("average_review_score", 0.0),
                "average_runtime_score": totals.get("average_runtime_score", 0.0),
                "profile_count": len(profiles),
                "role_count": len(roles),
                "last_event_at": agent_data.get("last_event_at"),
                "profiles": {
                    profile_name: {
                        "review_events": profile_data.get("review_events", 0),
                        "consensus_selected": profile_data.get("consensus_selected", 0),
                        "runtime_events": profile_data.get("runtime_events", 0),
                        "average_review_score": profile_data.get("average_review_score", 0.0),
                        "average_runtime_score": profile_data.get("average_runtime_score", 0.0),
                    }
                    for profile_name, profile_data in profiles.items()
                },
                "roles": {
                    role_name: {
                        "review_events": role_data.get("review_events", 0),
                        "consensus_selected": role_data.get("consensus_selected", 0),
                        "runtime_events": role_data.get("runtime_events", 0),
                        "average_review_score": role_data.get("average_review_score", 0.0),
                        "average_runtime_score": role_data.get("average_runtime_score", 0.0),
                    }
                    for role_name, role_data in roles.items()
                },
            })

        # Sort by total activity
        trends.sort(key=lambda x: x["total_review_events"] + x["total_consensus_selected"], reverse=True)

        return web.json_response({
            "status": "ok",
            "agent_count": len(trends),
            "trends": trends,
            "summary": registry.get("summary", {}),
            "recent_events": registry.get("recent_events", [])[-10:]
        })
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_ai_coordinator_skills(request: web.Request) -> web.Response:
    """Expose the approved shared skill catalog for local and delegated runtimes."""
    try:
        limit_raw = request.query.get("limit", "25")
        try:
            limit = max(1, min(100, int(limit_raw)))
        except ValueError:
            limit = 25
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        payload = await _aidb_shared_skills_catalog(limit=limit)
        return web.json_response(
            {
                "status": "ok",
                "service": "ai-coordinator",
                "shared_skill_registry": payload,
                "active_lesson_refs": lesson_refs,
            }
        )
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_skill_usage_stats(_request: web.Request) -> web.Response:
    """GET /control/skills/usage — Get skill usage statistics."""
    try:
        stats = _get_skill_usage_stats()
        return web.json_response({
            "status": "ok",
            "service": "skill_usage_tracker",
            "usage_stats": stats,
        })
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_skill_recommendations(request: web.Request) -> web.Response:
    """GET /control/skills/recommendations — Get skill recommendations for an agent."""
    try:
        agent = str(request.query.get("agent", "")).strip()
        task_type = str(request.query.get("task_type", "")).strip() or None

        if not agent:
            return web.json_response({"error": "agent parameter required"}, status=400)

        recommendations = _get_skill_recommendation(agent, task_type)

        return web.json_response({
            "status": "ok",
            "service": "skill_usage_tracker",
            "agent": agent,
            "task_type": task_type,
            "recommended_skills": recommendations,
        })
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_autoresearch_status(_request: web.Request) -> web.Response:
    """Get autoresearch experiment status and summary."""
    try:
        autoresearch_path = Path(__file__).parent.parent.parent / "autoresearch"
        if str(autoresearch_path) not in sys.path:
            sys.path.insert(0, str(autoresearch_path))
        from autoresearch import ExperimentLedger  # type: ignore[import]
        ledger = ExperimentLedger()
        summary = ledger.get_experiment_summary()
        accepted = ledger.get_accepted_experiments(limit=5)
        return web.json_response({
            "status": "ok",
            "service": "autoresearch",
            "summary": summary,
            "recent_accepted": accepted,
        })
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_autoresearch_run(request: web.Request) -> web.Response:
    """Run autoresearch optimization experiments."""
    try:
        data = await request.json() if request.can_read_body else {}
        chat_variants = int(data.get("chat_variants", 3))
        embed_variants = int(data.get("embed_variants", 3))

        autoresearch_path = Path(__file__).parent.parent.parent / "autoresearch"
        if str(autoresearch_path) not in sys.path:
            sys.path.insert(0, str(autoresearch_path))
        from local_model_optimizer import run_full_optimization  # type: ignore[import]

        result = await run_full_optimization(chat_variants, embed_variants)
        return web.json_response({
            "status": "ok",
            "service": "autoresearch",
            "result": result,
        })
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_web_research_fetch(request: web.Request) -> web.Response:
    """POST /research/web/fetch — fetch and extract text from one or more URLs."""
    try:
        from web_research import fetch_web_research  # type: ignore[import]
        data = await request.json() if request.can_read_body else {}
        result = await fetch_web_research(
            urls=data.get("urls", []),
            selectors=data.get("selectors"),
            max_text_chars=data.get("max_text_chars"),
        )
        return web.json_response(result)
    except (ValueError, RuntimeError) as exc:
        return web.json_response(_error_payload("client_error", exc), status=400)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_browser_research_fetch(request: web.Request) -> web.Response:
    """POST /research/web/browser-fetch — fetch URLs via headless browser."""
    try:
        from browser_research import fetch_browser_research  # type: ignore[import]
        data = await request.json() if request.can_read_body else {}
        result = await fetch_browser_research(
            urls=data.get("urls", []),
            selectors=data.get("selectors"),
            max_text_chars=data.get("max_text_chars"),
        )
        return web.json_response(result)
    except (ValueError, RuntimeError) as exc:
        return web.json_response(_error_payload("client_error", exc), status=400)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_curated_research_fetch(request: web.Request) -> web.Response:
    """POST /research/workflows/curated-fetch — run a named curated research workflow."""
    try:
        from research_workflows import run_curated_research_workflow  # type: ignore[import]
        data = await request.json() if request.can_read_body else {}
        workflow_slug = data.get("workflow_slug", "")
        if not workflow_slug:
            return web.json_response(
                _error_payload("client_error", ValueError("workflow_slug is required")),
                status=400,
            )
        result = await run_curated_research_workflow(
            workflow_slug=workflow_slug,
            inputs=data.get("inputs"),
            max_text_chars=data.get("max_text_chars"),
        )
        return web.json_response(result)
    except (ValueError, KeyError, RuntimeError) as exc:
        return web.json_response(_error_payload("client_error", exc), status=400)
    except Exception as exc:
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_ai_coordinator_delegate(request: web.Request) -> web.Response:
    """Run a bounded delegated task through the selected ai-coordinator lane."""
    try:
        data = await request.json()
        task = str(data.get("task") or data.get("query") or "").strip()
        if not task:
            return web.json_response({"error": "task required"}, status=400)
        orchestration = _coerce_orchestration_context(data)
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)

        requested_profile = str(data.get("profile") or "").strip().lower()
        # Phase 14.2: default prefer_local=False — remote free-tier agents are ~10x faster
        # than local llama.cpp (90-120s). Local is only used when explicitly requested.
        prefer_local = bool(data.get("prefer_local", False))
        tools_present = isinstance(data.get("tools"), list) and len(data.get("tools") or []) > 0

        # Phase 14.2: Support legacy agent_type field by mapping to profile
        if not requested_profile:
            agent_type = str(data.get("agent_type") or "").strip().lower()
            if agent_type:
                requested_profile = (
                    "remote-free" if agent_type in {"qwen", "gemini", "dolphin"}
                    else "remote-coding" if agent_type == "codex"
                    else "remote-gemini"
                )

        # Phase 14.2: Force remote-free fast-path when no profile and free agents available
        if not requested_profile and not prefer_local:
            if _AGENT_POOL_MANAGER and (
                sum(
                    1 for a in _AGENT_POOL_MANAGER.agents.values()
                    if getattr(a.tier, "value", "") == "free" and a.is_available()
                ) > 0
            ):
                routing_decision = {
                    "recommended_profile": "remote-free",
                    "complexity": "auto-free",
                    "rationale": "agent pool free-tier fast-path (Phase 14.2)",
                    "auto_routed": True,
                }
            else:
                routing_decision = _ai_coordinator_route_by_complexity(task, requested_profile, prefer_local)
        else:
            # Phase 9.3 — Use complexity routing for auto-selection
            routing_decision = _ai_coordinator_route_by_complexity(task, requested_profile, prefer_local)
        selected_profile = routing_decision["recommended_profile"]

        # Phase 9 — Remote availability pre-check: if the selected profile is
        # remote and was recently marked unavailable, fall back to local immediately
        # rather than failing. Remote agents are optional; local is always required.
        if _is_remote_profile(selected_profile):
            cached_avail = _remote_avail_cache_get(selected_profile)
            if cached_avail is False:
                local_fallback_profile = _ai_coordinator_local_fallback_profile(
                    task,
                    tools_present=tools_present,
                    requested_profile=requested_profile,
                )
                logger.info(
                    "delegate: remote profile %s cached as unavailable, falling back to %s",
                    selected_profile,
                    local_fallback_profile,
                )
                selected_profile = local_fallback_profile
                routing_decision = dict(routing_decision)
                routing_decision["recommended_profile"] = selected_profile
                routing_decision["rationale"] = routing_decision.get("rationale", "") + " [local-fallback:remote-cached-unavailable]"

        selected_runtime_id = _ai_coordinator_default_runtime_id_for_profile(selected_profile)
        # Phase 8.11 — Propagate thinking mode recommendation unless caller overrides
        if "thinking_mode" not in data:
            data = dict(data)
            data["thinking_mode"] = routing_decision.get("thinking_mode", "off")

        async with _runtime_registry_lock:
            registry = await _load_runtime_registry()
            runtime = (registry.get("runtimes", {}) or {}).get(selected_runtime_id)
        if not isinstance(runtime, dict):
            return web.json_response({"error": "runtime not found"}, status=404)

        swb_state = await _switchboard_ai_coordinator_state()
        remote_aliases = swb_state.get("remote_aliases", {})
        remote_configured = bool(swb_state.get("remote_configured", False))
        if _is_remote_profile(selected_profile) and not remote_configured:
            selected_profile = _ai_coordinator_local_fallback_profile(
                task,
                tools_present=tools_present,
                requested_profile=requested_profile,
            )
            selected_runtime_id = _ai_coordinator_default_runtime_id_for_profile(selected_profile)
            routing_decision = dict(routing_decision)
            routing_decision["recommended_profile"] = selected_profile
            routing_decision["rationale"] = (
                f"{routing_decision.get('rationale', '')} [local-fallback:remote-not-configured]"
            ).strip()
            async with _runtime_registry_lock:
                registry = await _load_runtime_registry()
                runtime = (registry.get("runtimes", {}) or {}).get(selected_runtime_id)
            if not isinstance(runtime, dict):
                return web.json_response({"error": "runtime not found"}, status=404)
        runtime = _apply_remote_runtime_status(runtime, selected_runtime_id, remote_aliases, remote_configured)

        status = str(runtime.get("status", "unknown")).strip().lower()
        if status not in {"ready", "degraded"}:
            # Phase 20.2: Instead of immediately failing, try failover chain
            logger.warning(
                "delegation_failover: runtime %s unavailable (status=%s), attempting failover",
                selected_runtime_id,
                status,
            )

            # Build fallback chain based on task type
            fallback_chain = _build_delegation_fallback_chain(
                task,
                requested_profile,
                prefer_local,
            )

            # Find next available target
            next_target = _select_next_available_delegation_target(
                fallback_chain,
                exclude_profiles={selected_profile},
            )

            if next_target:
                logger.info(
                    "delegation_failover: selected fallback profile=%s runtime=%s reason='%s'",
                    next_target["profile"],
                    next_target["runtime_id"],
                    next_target["reason"],
                )
                # Update selected profile and runtime
                selected_profile = next_target["profile"]
                selected_runtime_id = next_target["runtime_id"]

                # Reload runtime with new profile
                async with _runtime_registry_lock:
                    registry = await _load_runtime_registry()
                    runtime = (registry.get("runtimes", {}) or {}).get(selected_runtime_id)
                if not isinstance(runtime, dict):
                    return web.json_response(
                        {"error": "runtime not found after failover", "runtime_id": selected_runtime_id},
                        status=404,
                    )

                # Re-check runtime status
                swb_state = await _switchboard_ai_coordinator_state()
                remote_aliases = swb_state.get("remote_aliases", {})
                remote_configured = bool(swb_state.get("remote_configured", False))
                runtime = _apply_remote_runtime_status(runtime, selected_runtime_id, remote_aliases, remote_configured)
                status = str(runtime.get("status", "unknown")).strip().lower()

                if status not in {"ready", "degraded"}:
                    # Even failover target is unavailable
                    return web.json_response(
                        {
                            "error": "runtime_unavailable_after_failover",
                            "requested_runtime": selected_runtime_id,
                            "failed_over_to": next_target,
                            "status": status,
                            "hint": "All delegation targets are currently unavailable. Retry later or use local execution.",
                        },
                        status=503,
                    )
            else:
                # No failover targets available
                return web.json_response(
                    {
                        "error": "runtime_unavailable_no_failover",
                        "runtime_id": selected_runtime_id,
                        "status": status,
                        "hint": "No alternative delegation targets available. Retry later or use local execution.",
                    },
                    status=503,
                )

        messages = data.get("messages")
        if not isinstance(messages, list) or not messages:
            system_prompt = str(data.get("system_prompt") or "").strip()
            context = data.get("context") if isinstance(data.get("context"), dict) else None
            messages = _ai_coordinator_build_messages(
                task,
                system_prompt=system_prompt,
                context=context,
                profile=selected_profile,
            )
        progressive_context, progressive_context_meta = await _apply_progressive_context(
            task,
            messages,
            context=data.get("context") if isinstance(data.get("context"), dict) else None,
            profile_name=selected_profile,
            context_budget=int(data.get("max_tokens") or 0),
        )
        messages = progressive_context
        messages, prompt_optimization = _optimize_delegated_messages(messages, selected_profile)

        payload: Dict[str, Any] = {
            "messages": messages,
            "stream": False,
        }
        if "model" in data:
            payload["model"] = str(data.get("model") or "").strip()
        if "tools" in data and isinstance(data.get("tools"), list):
            payload["tools"] = data.get("tools")
        if "tool_choice" in data:
            payload["tool_choice"] = data.get("tool_choice")
        if "max_tokens" in data:
            payload["max_tokens"] = int(data.get("max_tokens") or 0)
        if "temperature" in data:
            payload["temperature"] = float(data.get("temperature"))

        timeout_s = float(data.get("timeout_s") or float(os.getenv("AI_DELEGATE_TIMEOUT_S", "240")))  # Phase 12.1: increased from 180 for llama.cpp 90-120s inference
        finalization_applied = False
        finalization_status_code = None
        openrouter_empty_content_retries = 0
        pool_agent: Optional[RemoteAgent] = None
        pool_agent_acquired = False
        pool_quality_score = 0.0
        request_started_at = time.perf_counter()

        # ── Local subprocess agent spawning ──────────────────────────────
        # For local runtimes, spawn actual subprocess agents instead of
        # just proxying HTTP to the switchboard. This enables independent
        # agent processes with their own tool sets, system prompts, and
        # state tracking.
        def _is_local_runtime(runtime_id: str) -> bool:
            return str(runtime_id or "").startswith("local-")

        async def _spawn_local_agent(
            role: str, task_text: str, system_prompt: str,
            max_tokens: int, temperature: float, timeout_sec: float,
            sse_request: Optional[web.Request] = None,
        ) -> web.Response:
            """Spawn a local agent subprocess and wait for result.
            When sse_request is provided, streams token chunks as SSE (Phase 8.9)."""
            import uuid as _uuid
            agent_id = str(_uuid.uuid4())[:8]
            state_dir = Path(os.environ.get("AGENT_STATE_DIR", "/tmp/agent-spawner"))
            state_dir.mkdir(parents=True, exist_ok=True)
            agent_state_file = state_dir / f"agent-{agent_id}.json"

            # Phase 12.4 / senior review: agent logic lives in a real Python file.
            _runtime_path = (
                Path(__file__).parent.parent.parent
                / "agents" / "runtimes" / "local_agent_runtime.py"
            )
            if not _runtime_path.exists():
                logger.error("local_agent_runtime.py not found at %s", _runtime_path)
                return web.json_response(
                    {"error": "agent_runtime_missing", "path": str(_runtime_path)},
                    status=500,
                )
            # Resolve model capabilities from catalog for model-agnostic agent spawning.
            _model_caps = _active_model_capabilities()
            _stop_seqs_default = json.dumps(_model_caps.get("stop_sequences") or ["<|im_end|>", "<|endoftext|>"])
            _no_think_prefix = _model_caps.get("no_think_prefix") or ""
            _think_supported = bool(_model_caps.get("think_mode", True))
            env = os.environ.copy()
            env.update({
                "AGENT_ID": agent_id,
                "AGENT_ROLE": role,
                "AGENT_TASK": task_text,
                "AGENT_SYSTEM_PROMPT": system_prompt,
                "AGENT_STATE_FILE": str(agent_state_file),
                "AGENT_MAX_TOKENS": str(max_tokens),
                "AGENT_TEMPERATURE": str(temperature),
                "AGENT_TIMEOUT": str(timeout_sec),
                # Enable thinking mode only when caller requests and model supports it.
                "AGENT_THINKING_MODE": str(data.get("thinking_mode", "off")) if _think_supported else "off",
                # Model-agnostic stop sequences and no-think prefix from model-catalog.yaml.
                "AGENT_STOP_SEQUENCES": _stop_seqs_default,
                "AGENT_NO_THINK_PREFIX": _no_think_prefix,
                # Phase 8.7 — tool calling: pass through caller preference
                "AGENT_TOOLS_ENABLED": "true" if bool(data.get("tools_enabled", False)) else "false",
                "AGENT_MAX_TOOL_ROUNDS": str(int(data.get("max_tool_rounds", 3))),
                "HYBRID_URL": "http://127.0.0.1:8003",
                "SWITCHBOARD_URL": Config.SWITCHBOARD_URL,
                "LLAMA_CPP_URL": Config.LLAMA_CPP_URL,  # Phase 12.1: direct fallback URL
                "PYTHONUNBUFFERED": "1",
            })
            # Phase 8.9 — streaming mode overrides: force stream, disable tools
            if sse_request is not None:
                env["AGENT_STREAMING"] = "true"
                env["AGENT_TOOLS_ENABLED"] = "false"

            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(_runtime_path),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

            # Phase 8.9 — SSE streaming path: read stdout chunks, write SSE events
            if sse_request is not None:
                sse_resp = web.StreamResponse(headers={
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "X-Agent-Id": agent_id,
                })
                await sse_resp.prepare(sse_request)
                deadline = time.perf_counter() + timeout_sec
                try:
                    while time.perf_counter() < deadline:
                        try:
                            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=8.0)
                        except asyncio.TimeoutError:
                            await sse_resp.write(b": keepalive\n\n")
                            continue
                        if not raw:
                            break
                        line_str = raw.decode(errors="replace").strip()
                        if not line_str:
                            continue
                        try:
                            chunk = json.loads(line_str)
                        except Exception:
                            continue
                        if chunk.get("done"):
                            final = json.dumps({"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]})
                            await sse_resp.write(b"data: " + final.encode() + b"\n\n")
                            await sse_resp.write(b"data: [DONE]\n\n")
                            break
                        if "t" in chunk:
                            piece = chunk["t"]
                            event = json.dumps({"choices": [{"delta": {"content": piece}, "finish_reason": None}]})
                            await sse_resp.write(b"data: " + event.encode() + b"\n\n")
                except Exception as _sse_exc:
                    logger.warning("sse_delegate_error agent_id=%s error=%s", agent_id, _sse_exc)
                finally:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                await sse_resp.write_eof()
                return sse_resp

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_sec,
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                return web.json_response({
                    "error": "local_agent_timeout",
                    "agent_id": agent_id,
                    "timeout_s": timeout_sec,
                }, status=504)

            if proc.returncode != 0:
                error_msg = stderr.decode(errors="replace")[:500] if stderr else "unknown"
                return web.json_response({
                    "error": "local_agent_failed",
                    "agent_id": agent_id,
                    "stderr": error_msg,
                }, status=500)

            try:
                result = json.loads(stdout.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                result = {"ok": False, "error": f"parse error: {stdout.decode(errors='replace')[:200]}"}

            if not result.get("ok"):
                return web.json_response({
                    "error": result.get("error", "unknown"),
                    "agent_id": agent_id,
                }, status=500)

            # Return in the same format as switchboard responses
            return web.json_response({
                "id": f"agent-{agent_id}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": f"local-{role}",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": result.get("content", "")},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "agent_metadata": {
                    "agent_id": agent_id,
                    "role": role,
                    "execution_mode": "local_subprocess",
                    "state_file": str(agent_state_file),
                },
            })

        # If local runtime, spawn subprocess agent instead of HTTP proxy
        if _is_local_runtime(selected_runtime_id):
            # Determine agent role from profile
            role_map = {
                "default": "coordinator",
                "local-tool-calling": "coder",
            }
            agent_role = role_map.get(selected_profile, "coordinator")

            # Extract system prompt from messages
            system_prompt = ""
            user_task = task
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "system":
                    system_prompt = msg.get("content", "")
                elif isinstance(msg, dict) and msg.get("role") == "user":
                    user_task = msg.get("content", task)

            _spawn_kwargs = dict(
                role=agent_role,
                task_text=user_task,
                system_prompt=system_prompt or f"You are a {agent_role} agent. Execute the task using available tools.",
                max_tokens=int(data.get("max_tokens", 768)),
                temperature=float(data.get("temperature", 0.3)),
                timeout_sec=timeout_s,
            )

            # Phase 8.9 — Streaming dispatch: SSE token stream to caller.
            # Enabled via streaming_mode=true. Incompatible with async_mode and tools.
            if bool(data.get("streaming_mode", False)) and not bool(data.get("async_mode", False)):
                return await _spawn_local_agent(**_spawn_kwargs, sse_request=request)

            # Phase 8.6 — Async dispatch: return task_id immediately, caller polls.
            # Enabled via async_mode=true in request body. Default: synchronous.
            if bool(data.get("async_mode", False)):
                import uuid as _uuid
                _task_id = str(_uuid.uuid4())
                _DELEGATE_TASK_REGISTRY[_task_id] = {
                    "status": "pending",
                    "task_id": _task_id,
                    "role": agent_role,
                    "created_at": time.time(),
                }

                async def _run_async_delegate(tid: str, kwargs: dict, _role: str, _utask: str, _rout: dict) -> None:
                    _DELEGATE_TASK_REGISTRY[tid]["status"] = "running"
                    try:
                        _resp = await _spawn_local_agent(**kwargs)
                        _body: Dict[str, Any] = {}
                        try:
                            _body = json.loads(_resp.body)
                        except Exception:
                            pass
                        _DELEGATE_TASK_REGISTRY[tid].update({
                            "status": "done" if _resp.status == 200 else "failed",
                            "http_status": _resp.status,
                            "result": _body,
                            "completed_at": time.time(),
                        })
                        # Phase 8.8 memory consolidation for async path
                        if _resp.status == 200 and _store_memory is not None:
                            try:
                                _rc = (_body.get("choices") or [{}])[0].get("message", {}).get("content", "")
                                if _rc and len(_rc.strip()) > 20:
                                    await _store_memory(
                                        content=f"Delegate task [{_role}]: {_utask[:200]}\nOutcome: {_rc[:400]}",
                                        memory_type="procedural",
                                        tags=["delegate", _role, _rout.get("task_archetype", "general")],
                                        source="delegate_auto_consolidation",
                                    )
                            except Exception as _me:
                                logger.debug("delegate_memory_consolidation_skipped error=%s", _me)
                    except Exception as _ex:
                        _DELEGATE_TASK_REGISTRY[tid].update({
                            "status": "failed",
                            "error": str(_ex),
                            "completed_at": time.time(),
                        })

                asyncio.create_task(
                    _run_async_delegate(_task_id, _spawn_kwargs, agent_role, user_task, routing_decision)
                )
                return web.json_response({
                    "task_id": _task_id,
                    "status": "pending",
                    "poll_url": f"/control/ai-coordinator/delegate/status/{_task_id}",
                }, status=202)

            local_response = await _spawn_local_agent(**_spawn_kwargs)
            # Phase 8.8 — Auto-consolidate successful delegate outcomes into memory.
            if (
                local_response.status == 200
                and _store_memory is not None
                and bool(data.get("auto_memorize", True))
            ):
                try:
                    resp_body = json.loads(local_response.body)
                    result_content = (
                        (resp_body.get("choices") or [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    if result_content and len(result_content.strip()) > 20:
                        await _store_memory(
                            content=f"Delegate task [{agent_role}]: {user_task[:200]}\nOutcome: {result_content[:400]}",
                            memory_type="procedural",
                            tags=["delegate", agent_role, routing_decision.get("task_archetype", "general")],
                            source="delegate_auto_consolidation",
                        )
                except Exception as _mem_exc:
                    logger.debug("delegate_memory_consolidation_skipped error=%s", _mem_exc)
            return local_response

        if "model" not in payload and _remote_profile_uses_agent_pool(selected_profile):
            pool_agent = _select_agent_pool_candidate(
                selected_profile,
                min_context_window=int(payload.get("max_tokens") or 0),
            )
            if pool_agent and _AGENT_POOL_MANAGER.acquire_agent(pool_agent.agent_id):
                pool_agent_acquired = True
                payload["model"] = pool_agent.model_id

        async def _post_delegate(profile_name: str, delegate_payload: Optional[Dict[str, Any]] = None) -> httpx.Response:
            local_profiles = {"default", "local-tool-calling"}
            headers = {
                "Content-Type": "application/json",
                "X-AI-Profile": "continue-local" if profile_name == "default" else profile_name,
            }
            if profile_name in local_profiles:
                headers["X-AI-Route"] = "local"
            else:
                headers["X-AI-Route"] = "remote"
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                return await client.post(
                    f"{Config.SWITCHBOARD_URL.rstrip('/')}/v1/chat/completions",
                    headers=headers,
                    json=delegate_payload or payload,
                )

        effective_profile = selected_profile
        effective_runtime_id = selected_runtime_id
        fallback_applied = False
        local_fallback_applied = False
        fallback_reason = ""
        failover_chain_used = False
        excluded_profiles = set()

        response = await _post_delegate(effective_profile)
        initial_response = response
        # Guard against non-JSON upstream responses (e.g. Cloudflare HTML 400 errors)
        # that would otherwise raise JSONDecodeError before the failover logic runs.
        try:
            initial_body = response.json()
        except Exception:
            initial_body = {"error": {"message": response.text[:200], "code": response.status_code}}

        # Phase 20.2: Enhanced failover chain for 402/429 errors + 401/403 auth/policy
        # Also handle 400 from upstream WAF/auth rejections (e.g. Cloudflare 400 = invalid key).
        if response.status_code in {400, 401, 402, 403, 429}:
            # Mark agent as rate-limited if applicable
            if pool_agent:
                _AGENT_POOL_MANAGER.mark_rate_limited(pool_agent.agent_id)
                if pool_agent_acquired:
                    _AGENT_POOL_MANAGER.release_agent(pool_agent.agent_id, success=False, latency_ms=0.0, quality_score=0.0)
                    pool_agent_acquired = False

            # Add failed profile to exclusion list
            excluded_profiles.add(effective_profile)

            # Phase 15.1: Record per-model error for the failing model in fleet state
            _failing_model = (pool_agent.model_id if pool_agent else "") or payload.get("model", "")
            if _failing_model:
                _err_msg_init = str((initial_body.get("error") or {}).get("message", ""))[:200]
                asyncio.create_task(_mfm.record_error(
                    _failing_model,
                    error_code=response.status_code,
                    error_msg=_err_msg_init,
                ))

            # Build and use failover chain
            failover_chain = _build_delegation_fallback_chain(
                task,
                requested_profile,
                prefer_local,
            )

            next_target = _select_next_available_delegation_target(
                failover_chain,
                exclude_profiles=excluded_profiles,
            )

            if next_target:
                failover_chain_used = True
                effective_profile = next_target["profile"]
                effective_runtime_id = next_target["runtime_id"]
                fallback_applied = True
                fallback_reason = f"failover chain: {response.status_code} on {selected_profile}, fell back to {effective_profile} ({next_target['reason']})"

                logger.info(
                    "delegation_failover_chain: HTTP %d on profile=%s, failing over to profile=%s runtime=%s",
                    response.status_code,
                    selected_profile,
                    effective_profile,
                    effective_runtime_id,
                )

                # Select new pool agent if needed
                if "model" not in data:
                    fallback_pool_agent = _select_agent_pool_candidate(
                        effective_profile,
                        min_context_window=int(payload.get("max_tokens") or 0),
                        exclude_agent_id=pool_agent.agent_id if pool_agent else "",
                    )
                    if fallback_pool_agent and _AGENT_POOL_MANAGER.acquire_agent(fallback_pool_agent.agent_id):
                        pool_agent = fallback_pool_agent
                        pool_agent_acquired = True
                        payload["model"] = fallback_pool_agent.model_id

                # Retry with new profile
                response = await _post_delegate(effective_profile)
                runtime = _apply_remote_runtime_status(
                    dict((registry.get("runtimes", {}) or {}).get(effective_runtime_id) or {}),
                    effective_runtime_id,
                    remote_aliases,
                    remote_configured,
                )
            else:
                # No failover available, fall back to old behavior
                if selected_runtime_id in {"openrouter-gemini", "openrouter-coding", "openrouter-reasoning", "openrouter-tool-calling"} and remote_configured and remote_aliases.get("free"):
                    effective_profile = "remote-free"
                    effective_runtime_id = "openrouter-free"
                    fallback_applied = True
                    fallback_reason = f"remote profile returned {response.status_code} (auth/rate-limit); no failover chain available, retried on remote-free"
        # Guard against non-JSON upstream bodies (Cloudflare WAF HTML, etc.)
        try:
            body = response.json()
        except Exception:
            body = {"error": {"message": response.text[:200], "code": response.status_code}}

        initial_classification = classify_delegated_response(
            task=task,
            messages=messages,
            status_code=int(initial_response.status_code),
            body=initial_body,
            profile=selected_profile,
            runtime_id=selected_runtime_id,
            stage="initial",
            fallback_applied=fallback_applied,
        )
        final_classification = classify_delegated_response(
            task=task,
            messages=messages,
            status_code=int(response.status_code),
            body=body,
            profile=effective_profile,
            runtime_id=effective_runtime_id,
            stage="final",
            fallback_applied=fallback_applied,
        )

        if (
            "tool_call_without_final_text" in (final_classification.get("failure_classes") or [])
            and effective_profile == "remote-tool-calling"
            and response.status_code < 400
        ):
            salvage = final_classification.get("salvage") if isinstance(final_classification.get("salvage"), dict) else {}
            tool_calls = salvage.get("tool_calls") if isinstance(salvage.get("tool_calls"), list) else []
            if tool_calls:
                finalization_messages = _ai_coordinator_build_tool_call_finalization_messages(
                    task,
                    tool_calls,
                    profile=effective_profile,
                )
                finalization_payload: Dict[str, Any] = {
                    "messages": finalization_messages,
                    "stream": False,
                    "max_tokens": min(int(data.get("max_tokens") or 300) or 300, 300),
                    "temperature": 0,
                }
                if "model" in payload:
                    finalization_payload["model"] = payload["model"]
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    finalization_response = await client.post(
                        f"{Config.SWITCHBOARD_URL.rstrip('/')}/v1/chat/completions",
                        headers={
                            "Content-Type": "application/json",
                            "X-AI-Profile": effective_profile,
                            "X-AI-Route": "remote",
                        },
                        json=finalization_payload,
                    )
                finalization_body = finalization_response.json()
                finalization_classification = classify_delegated_response(
                    task=task,
                    messages=finalization_messages,
                    status_code=int(finalization_response.status_code),
                    body=finalization_body,
                    profile=effective_profile,
                    runtime_id=effective_runtime_id,
                    stage="post_tool_finalization",
                    fallback_applied=fallback_applied,
                )
                if finalization_response.status_code < 400 and not finalization_classification.get("is_failure"):
                    response = finalization_response
                    body = finalization_body
                    final_classification = finalization_classification
                    finalization_applied = True
                    finalization_status_code = int(finalization_response.status_code)
        elif (
            "empty_content" in (final_classification.get("failure_classes") or [])
            and effective_profile == "remote-reasoning"
            and response.status_code < 400
        ):
            salvage = final_classification.get("salvage") if isinstance(final_classification.get("salvage"), dict) else {}
            reasoning_excerpt = str(salvage.get("reasoning_excerpt") or "").strip()
            if reasoning_excerpt:
                finalization_messages = _ai_coordinator_build_reasoning_finalization_messages(
                    task,
                    reasoning_excerpt,
                    profile=effective_profile,
                )
                finalization_payload = {
                    "messages": finalization_messages,
                    "stream": False,
                    "max_tokens": min(int(data.get("max_tokens") or 260) or 260, 260),
                    "temperature": 0,
                }
                if "model" in payload:
                    finalization_payload["model"] = payload["model"]
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    finalization_response = await client.post(
                        f"{Config.SWITCHBOARD_URL.rstrip('/')}/v1/chat/completions",
                        headers={
                            "Content-Type": "application/json",
                            "X-AI-Profile": effective_profile,
                            "X-AI-Route": "remote",
                        },
                        json=finalization_payload,
                    )
                finalization_body = finalization_response.json()
                finalization_classification = classify_delegated_response(
                    task=task,
                    messages=finalization_messages,
                    status_code=int(finalization_response.status_code),
                    body=finalization_body,
                    profile=effective_profile,
                    runtime_id=effective_runtime_id,
                    stage="post_reasoning_finalization",
                    fallback_applied=fallback_applied,
                )
                if finalization_response.status_code < 400 and not finalization_classification.get("is_failure"):
                    response = finalization_response
                    body = finalization_body
                    final_classification = finalization_classification
                    finalization_applied = True
                    finalization_status_code = int(finalization_response.status_code)
        elif (
            "empty_content" in (final_classification.get("failure_classes") or [])
            and effective_profile.startswith("remote-")
            and effective_profile != "remote-reasoning"
            and response.status_code < 400
        ):
            # Simplified retry: strip tool schemas, request plain text only.
            retry_messages = _ai_coordinator_build_empty_content_retry_messages(
                task,
                profile=effective_profile,
            )
            retry_payload: Dict[str, Any] = {
                "messages": retry_messages,
                "stream": False,
                "max_tokens": min(int(data.get("max_tokens") or 400) or 400, 400),
                "temperature": 0,
            }
            if "model" in payload:
                retry_payload["model"] = payload["model"]
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                retry_response = await client.post(
                    f"{Config.SWITCHBOARD_URL.rstrip('/')}/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "X-AI-Profile": effective_profile,
                        "X-AI-Route": "remote",
                    },
                    json=retry_payload,
                )
            openrouter_empty_content_retries += 1
            retry_body = retry_response.json()
            retry_classification = classify_delegated_response(
                task=task,
                messages=retry_messages,
                status_code=int(retry_response.status_code),
                body=retry_body,
                profile=effective_profile,
                runtime_id=effective_runtime_id,
                stage="post_empty_content_retry",
                fallback_applied=fallback_applied,
            )
            if retry_response.status_code < 400 and not retry_classification.get("is_failure"):
                response = retry_response
                body = retry_body
                final_classification = retry_classification
                finalization_applied = True
                finalization_status_code = int(retry_response.status_code)
        delegated_quality: Dict[str, Any] = {"available": False}
        if response.status_code < 400:
            delegated_quality = await _assess_delegated_response_quality(
                task,
                body,
                agent_id=pool_agent.agent_id if pool_agent else effective_profile,
            )
            if delegated_quality.get("available"):
                pool_quality_score = float(delegated_quality.get("quality_score", 0.0) or 0.0)
                updated_text = str(delegated_quality.get("response_text") or "").strip()
                if updated_text:
                    body = _inject_delegated_response_text(body, updated_text)
        local_fallback_needed = (
            prefer_local
            and not local_fallback_applied
            and effective_profile not in {"default", "local-tool-calling"}
            and (
                response.status_code >= 400
                or final_classification.get("is_failure")
                or (
                    delegated_quality.get("available")
                    and not delegated_quality.get("passed")
                    and delegated_quality.get("fallback_recommended")
                )
            )
        )
        if local_fallback_needed:
            local_profile = _ai_coordinator_local_fallback_profile(
                task,
                tools_present=isinstance(payload.get("tools"), list) and len(payload.get("tools") or []) > 0,
                requested_profile=requested_profile,
            )
            local_runtime_id = _ai_coordinator_default_runtime_id_for_profile(local_profile)
            local_payload = dict(payload)
            local_payload.pop("model", None)
            local_response = await _post_delegate(local_profile, delegate_payload=local_payload)
            local_body = local_response.json()
            local_classification = classify_delegated_response(
                task=task,
                messages=messages,
                status_code=int(local_response.status_code),
                body=local_body,
                profile=local_profile,
                runtime_id=local_runtime_id,
                stage="local_fallback",
                fallback_applied=True,
            )
            if local_response.status_code < 400 and not local_classification.get("is_failure"):
                response = local_response
                body = local_body
                final_classification = local_classification
                effective_profile = local_profile
                effective_runtime_id = local_runtime_id
                runtime = dict((registry.get("runtimes", {}) or {}).get(effective_runtime_id) or {})
                fallback_applied = True
                local_fallback_applied = True
                fallback_reason = "remote failure or failed delegated QA triggered bounded local retry"
                delegated_quality = {"available": False, "fallback_recommended": True}
        capability_gaps: List[Any] = []
        capability_gap_failure_text = _build_gap_failure_text(final_classification, delegated_quality)
        if final_classification.get("is_failure") or (delegated_quality.get("available") and not delegated_quality.get("passed")):
            capability_gaps = _GAP_DETECTOR.detect_from_failure(
                capability_gap_failure_text or f"delegated failure for {effective_profile}",
                task,
                {
                    "profile": effective_profile,
                    "requesting_agent": orchestration["requesting_agent"],
                    "requester_role": orchestration["requester_role"],
                },
            )
        remediation_plans = [_plan_capability_gap_remediation(gap) for gap in capability_gaps]
        real_time_learning = await _apply_real_time_learning(
            task,
            body,
            profile_name=effective_profile,
            delegated_quality=delegated_quality,
            final_classification=final_classification,
            context=data.get("context") if isinstance(data.get("context"), dict) else None,
        ) if response.status_code < 400 else {"available": False}
        meta_learning = await _apply_meta_learning(
            task,
            body,
            profile_name=effective_profile,
            delegated_quality=delegated_quality,
        ) if response.status_code < 400 else {"available": False}
        recovered_artifact = (
            {"available": False}
            if not final_classification.get("is_failure")
            else build_recovered_artifact(task, final_classification)
        )
        try:
            record_delegation_feedback(
                task=task,
                requested_profile=requested_profile,
                selected_profile=selected_profile,
                selected_runtime_id=selected_runtime_id,
                classification=initial_classification,
                final_profile=effective_profile,
                final_runtime_id=effective_runtime_id,
                requesting_agent=orchestration["requesting_agent"],
                requester_role=orchestration["requester_role"],
            )
        except OSError as exc:
            logger.error("delegation_feedback_write_failed error=%s", exc)
        if fallback_applied or final_classification.get("is_failure"):
            try:
                record_delegation_feedback(
                    task=task,
                    requested_profile=requested_profile,
                    selected_profile=selected_profile,
                    selected_runtime_id=selected_runtime_id,
                    classification=final_classification,
                    final_profile=effective_profile,
                    final_runtime_id=effective_runtime_id,
                    requesting_agent=orchestration["requesting_agent"],
                    requester_role=orchestration["requester_role"],
                )
            except OSError as exc:
                logger.error("delegation_feedback_write_failed error=%s", exc)
        request["audit_metadata"] = {
            "selected_runtime_id": effective_runtime_id,
            "selected_profile": effective_profile,
            "requesting_agent": orchestration["requesting_agent"],
            "requester_role": orchestration["requester_role"],
            "delegate_via_coordinator_only": orchestration["delegate_via_coordinator_only"],
            "delegated_http_status": int(response.status_code),
            "fallback_applied": fallback_applied,
            "local_fallback_applied": local_fallback_applied,
            "delegation_failure_class": final_classification.get("primary_failure_class", ""),
            "delegation_failure_classes": final_classification.get("failure_classes", []),
            "delegation_salvage_useful": bool((final_classification.get("salvage") or {}).get("has_useful_data")),
            "delegation_recovery_class": recovered_artifact.get("recovery_class", "") if recovered_artifact.get("available") else "",
            "delegation_finalization_applied": finalization_applied,
            "delegation_handoff_requested": bool(final_classification.get("handoff_requested")),
            "agent_pool_agent_id": pool_agent.agent_id if pool_agent else "",
            "agent_pool_tier": pool_agent.tier.value if pool_agent else "",
            "agent_pool_provider": pool_agent.provider if pool_agent else "",
            "delegated_quality_score": pool_quality_score,
            "delegated_quality_passed": bool(delegated_quality.get("passed")) if delegated_quality.get("available") else False,
            "delegated_quality_refined": bool(delegated_quality.get("refinement_applied")) if delegated_quality.get("available") else False,
            "delegated_quality_cached_fallback": bool(delegated_quality.get("cached_fallback_used")) if delegated_quality.get("available") else False,
            "prompt_optimization_applied": bool(prompt_optimization.get("applied")),
            "prompt_tokens_before": int(prompt_optimization.get("original_tokens", 0) or 0),
            "prompt_tokens_after": int(prompt_optimization.get("compressed_tokens", 0) or 0),
            "progressive_context_applied": bool(progressive_context_meta.get("applied")),
            "progressive_context_tier": str(progressive_context_meta.get("tier", "") or ""),
            "progressive_context_category": str(progressive_context_meta.get("category", "") or ""),
            "capability_gap_count": len(capability_gaps),
            "real_time_learning_applied": bool(real_time_learning.get("available")),
            "meta_learning_applied": bool(meta_learning.get("available")),
            "openrouter_empty_content_retries": openrouter_empty_content_retries,
        }

        if pool_agent and response.status_code in {402, 429}:
            _AGENT_POOL_MANAGER.mark_rate_limited(pool_agent.agent_id)
        if pool_agent and pool_agent_acquired:
            _AGENT_POOL_MANAGER.release_agent(
                pool_agent.agent_id,
                success=response.status_code < 400,
                latency_ms=max(0.0, (time.perf_counter() - request_started_at) * 1000.0),
                quality_score=pool_quality_score,
            )
            pool_agent_acquired = False
        # Phase 9 — Update remote availability cache based on actual response.
        if _is_remote_profile(effective_profile):
            if response.status_code in {401, 403, 429} or response.status_code >= 500:
                _remote_avail_cache_set(effective_profile, False)
                logger.warning(
                    "delegate: remote profile %s returned HTTP %s — marked unavailable for %ss",
                    effective_profile,
                    response.status_code,
                    int(_REMOTE_AVAIL_TTL_S),
                )
            elif response.status_code < 400:
                _remote_avail_cache_set(effective_profile, True)

        # Phase 15.1 + 15.3: Fleet model state update + agentic memory journal write
        _delegate_model_id = (pool_agent.model_id if pool_agent else "") or payload.get("model", "")
        _delegate_latency_ms = max(0.0, (time.perf_counter() - request_started_at) * 1000.0)
        _fleet_entry = _mfm.get_model_entry(_delegate_model_id)
        if _delegate_model_id:
            if response.status_code < 400:
                asyncio.create_task(_mfm.record_success(
                    _delegate_model_id,
                    latency_ms=_delegate_latency_ms,
                    tokens_out=int((body.get("usage") or {}).get("completion_tokens", 0) or 0),
                ))
            else:
                asyncio.create_task(_mfm.record_error(
                    _delegate_model_id,
                    error_code=response.status_code,
                    error_msg=str((body.get("error") or {}).get("message", ""))[:200],
                ))
        asyncio.create_task(_journal.write_entry(
            task_summary=task,
            task_archetype=_mfm.infer_capability_from_task(task, effective_profile),
            model_id=_delegate_model_id or effective_profile,
            provider=_fleet_entry.provider if _fleet_entry else "",
            tier=_fleet_entry.tier if _fleet_entry else (
                "local" if not _is_remote_profile(effective_profile) else "remote"
            ),
            profile=effective_profile,
            runtime_id=effective_runtime_id,
            agent_role=str(routing_decision.get("task_archetype", "implementer") or "implementer"),
            success=response.status_code < 400,
            error_code=response.status_code if response.status_code >= 400 else 0,
            error_msg=str((body.get("error") or {}).get("message", ""))[:200] if response.status_code >= 400 else "",
            latency_ms=_delegate_latency_ms,
            tokens_in=int((body.get("usage") or {}).get("prompt_tokens", 0) or 0),
            tokens_out=int((body.get("usage") or {}).get("completion_tokens", 0) or 0),
            outcome_summary=(_extract_delegated_response_text(body) or "")[:300],
            session_id=str(request.get("request_id", "") or ""),
            task_id=str(data.get("task_id") or request.get("request_id", "") or ""),
            fallback_used=fallback_applied,
            fallback_from=next(iter(excluded_profiles), "") if fallback_applied else "",
        ))

        _record_capability_gap_outcomes(
            capability_gaps,
            duration_seconds=max(0.0, time.perf_counter() - request_started_at),
            response_status=int(response.status_code),
            fallback_applied=fallback_applied,
            finalization_applied=finalization_applied,
            delegated_quality=delegated_quality,
        )
        prompt_tokens_before = int(prompt_optimization.get("original_tokens", 0) or 0)
        prompt_tokens_after = int(prompt_optimization.get("compressed_tokens", 0) or 0)
        DELEGATED_PROMPT_TOKENS_BEFORE.labels(profile=effective_profile).observe(prompt_tokens_before)
        DELEGATED_PROMPT_TOKENS_AFTER.labels(profile=effective_profile).observe(prompt_tokens_after)
        if prompt_tokens_before > prompt_tokens_after:
            DELEGATED_PROMPT_TOKEN_SAVINGS.labels(profile=effective_profile).inc(prompt_tokens_before - prompt_tokens_after)
        if delegated_quality.get("available"):
            quality_value = float(delegated_quality.get("quality_score", 0.0) or 0.0)
            DELEGATED_QUALITY_SCORE.labels(profile=effective_profile).observe(quality_value)
            quality_outcome = (
                "passed" if delegated_quality.get("passed")
                else "cached_fallback" if delegated_quality.get("cached_fallback_used")
                else "refined" if delegated_quality.get("refinement_applied")
                else "failed"
            )
            DELEGATED_QUALITY_EVENTS.labels(profile=effective_profile, outcome=quality_outcome).inc()
        if progressive_context_meta.get("applied"):
            PROGRESSIVE_CONTEXT_LOADS.labels(
                category=str(progressive_context_meta.get("category", "") or "unknown"),
                tier=str(progressive_context_meta.get("tier", "") or "unknown"),
                profile=effective_profile,
            ).inc()
        for gap in capability_gaps:
            CAPABILITY_GAP_DETECTIONS.labels(
                gap_type=gap.gap_type.value,
                severity=gap.severity.name.lower(),
            ).inc()
        if real_time_learning.get("available"):
            REAL_TIME_LEARNING_EVENTS.labels(profile=effective_profile, event_type="learning_example").inc()
            if int(real_time_learning.get("executed_action_count", 0) or 0) > 0:
                REAL_TIME_LEARNING_EVENTS.labels(profile=effective_profile, event_type="feedback_action").inc(
                    int(real_time_learning.get("executed_action_count", 0) or 0)
                )
        if meta_learning.get("available"):
            META_LEARNING_ADAPTATIONS.labels(
                domain=str(meta_learning.get("domain", "") or "unknown"),
                method=str(meta_learning.get("method", "") or "unknown"),
            ).inc()

        return web.json_response(
            {
                "status": "ok" if response.status_code < 400 else "error",
                "task": task,
                "orchestration": orchestration,
                "selected_runtime": {
                    "runtime_id": effective_runtime_id,
                    "name": runtime.get("name", effective_runtime_id),
                    "profile": runtime.get("profile", effective_profile),
                    "model_alias": runtime.get("model_alias", ""),
                    "status": runtime.get("status", status),
                },
                # Phase 9.3 — Query complexity routing decision
                "routing_decision": {
                    "complexity": routing_decision.get("complexity", "unknown"),
                    "auto_routed": routing_decision.get("auto_routed", False),
                    "rationale": routing_decision.get("rationale", ""),
                },
                "fallback": (
                    {
                        "applied": True,
                        "from_profile": selected_profile,
                        "to_profile": effective_profile,
                        "reason": fallback_reason or "delegated fallback applied",
                        "failover_chain_used": failover_chain_used,
                    }
                    if fallback_applied else {"applied": False}
                ),
                "failover_chain": (
                    {
                        "used": failover_chain_used,
                        "original_profile": selected_profile,
                        "final_profile": effective_profile,
                        "reason": fallback_reason,
                    }
                    if failover_chain_used else {"used": False}
                ),
                "finalization": {
                    "applied": finalization_applied,
                    "status_code": finalization_status_code,
                    "reason": (
                        "tool_call_without_final_text remediation"
                        if finalization_applied and effective_profile == "remote-tool-calling"
                        else "reasoning_only remediation"
                        if finalization_applied and effective_profile == "remote-reasoning"
                        else ""
                    ),
                },
                "active_lesson_refs": lesson_refs,
                "delegation_feedback": {
                    "initial": initial_classification,
                    "final": final_classification,
                },
                "progressive_context": progressive_context_meta,
                "prompt_optimization": prompt_optimization,
                "capability_gaps": [
                    {
                        "gap_id": gap.gap_id,
                        "gap_type": gap.gap_type.value,
                        "severity": gap.severity.name.lower(),
                        "priority_score": round(float(gap.priority_score or 0.0), 4),
                        "description": gap.description,
                    }
                    for gap in capability_gaps
                ],
                "remediation_plans": remediation_plans,
                "real_time_learning": real_time_learning,
                "meta_learning": meta_learning,
                "agent_pool": (
                    {
                        "applied": True,
                        "agent_id": pool_agent.agent_id,
                        "provider": pool_agent.provider,
                        "model_id": pool_agent.model_id,
                        "tier": pool_agent.tier.value,
                    }
                    if pool_agent else {"applied": False}
                ),
                "quality_assurance": delegated_quality,
                "artifact_recovery": recovered_artifact,
                "response": body,
            },
            status=response.status_code,
        )
    except httpx.HTTPError as exc:
        pool_agent = locals().get("pool_agent")
        pool_agent_acquired = bool(locals().get("pool_agent_acquired"))
        request_started_at = float(locals().get("request_started_at") or time.perf_counter())
        if pool_agent and pool_agent_acquired:
            _AGENT_POOL_MANAGER.release_agent(
                pool_agent.agent_id,
                success=False,
                latency_ms=max(0.0, (time.perf_counter() - request_started_at) * 1000.0),
                quality_score=0.0,
            )
        return web.json_response(_error_payload("switchboard_unavailable", exc), status=502)
    except Exception as exc:
        pool_agent = locals().get("pool_agent")
        pool_agent_acquired = bool(locals().get("pool_agent_acquired"))
        request_started_at = float(locals().get("request_started_at") or time.perf_counter())
        if pool_agent and pool_agent_acquired:
            _AGENT_POOL_MANAGER.release_agent(
                pool_agent.agent_id,
                success=False,
                latency_ms=max(0.0, (time.perf_counter() - request_started_at) * 1000.0),
                quality_score=0.0,
            )
        return web.json_response(_error_payload("internal_error", exc), status=500)


async def handle_ai_coordinator_delegate_status(request: web.Request) -> web.Response:
    """Poll the status of an async delegate task submitted with async_mode=true."""
    task_id = request.match_info.get("task_id", "").strip()
    if not task_id:
        return web.json_response({"error": "task_id required"}, status=400)
    entry = _DELEGATE_TASK_REGISTRY.get(task_id)
    if not entry:
        return web.json_response({"error": "task_not_found", "task_id": task_id}, status=404)
    # Lazy TTL cleanup
    if time.time() - entry.get("created_at", 0) > _DELEGATE_TASK_TTL_S:
        _DELEGATE_TASK_REGISTRY.pop(task_id, None)
        return web.json_response({"error": "task_expired", "task_id": task_id}, status=410)
    return web.json_response(entry)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(http_app: web.Application) -> None:
    http_app.router.add_post("/research/web/fetch", handle_web_research_fetch)
    http_app.router.add_post("/research/web/browser-fetch", handle_browser_research_fetch)
    http_app.router.add_post("/research/workflows/curated-fetch", handle_curated_research_fetch)
    http_app.router.add_get("/parity/scorecard", handle_parity_scorecard)
    http_app.router.add_get("/control/ai-coordinator/status", handle_ai_coordinator_status)
    http_app.router.add_get("/control/ai-coordinator/lessons", handle_ai_coordinator_lessons)
    http_app.router.add_post("/control/ai-coordinator/lessons/review", handle_ai_coordinator_lessons_review)
    http_app.router.add_get("/control/ai-coordinator/evaluations", handle_ai_coordinator_evaluations)
    http_app.router.add_get("/control/ai-coordinator/evaluations/trends", handle_ai_coordinator_evaluation_trends)
    http_app.router.add_get("/control/ai-coordinator/skills", handle_ai_coordinator_skills)
    http_app.router.add_post("/control/ai-coordinator/delegate", handle_ai_coordinator_delegate)
    http_app.router.add_get(
        "/control/ai-coordinator/delegate/status/{task_id}",
        handle_ai_coordinator_delegate_status,
    )
    http_app.router.add_get("/control/skills/usage", handle_skill_usage_stats)
    http_app.router.add_get("/control/skills/recommendations", handle_skill_recommendations)
    http_app.router.add_get("/control/autoresearch/status", handle_autoresearch_status)
    http_app.router.add_post("/control/autoresearch/run", handle_autoresearch_run)
