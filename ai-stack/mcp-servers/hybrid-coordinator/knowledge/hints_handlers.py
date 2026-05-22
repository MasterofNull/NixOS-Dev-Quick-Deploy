"""
Hints, feedback, and agent status HTTP handlers.

Covers:
  - GET/POST /hints               — ranked workflow hints (Phase 19.2.x)
  - POST     /hints/feedback      — explicit agent feedback loop
  - GET/POST /agent-status        — remote agent pool availability (Phase 20.1)

Extracted from http_server.py (Phase 12.4 decomposition).
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from aiohttp import web

from agent_registry import (
    _active_lesson_refs,
    _agent_lessons_lock,
    _hint_feedback_log_path,
    _load_agent_lessons_registry,
)

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Injected dependencies
# ---------------------------------------------------------------------------
_PERFORMANCE_PROFILER: Optional[Any] = None
_AGENT_POOL_MANAGER: Optional[Any] = None


def init(*, performance_profiler: Any, agent_pool_manager: Any) -> None:
    """Inject runtime dependencies. Call once from http_server.py init()."""
    global _PERFORMANCE_PROFILER, _AGENT_POOL_MANAGER
    _PERFORMANCE_PROFILER = performance_profiler
    _AGENT_POOL_MANAGER = agent_pool_manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_remote_agent_status() -> Dict[str, Any]:
    """Return remote agent pool availability and rate-limit status."""
    try:
        stats = _AGENT_POOL_MANAGER.get_pool_stats()
        agents_detail = []
        for agent_id, agent in _AGENT_POOL_MANAGER.agents.items():
            is_rl = agent.is_rate_limited()
            eta_minutes = 0
            if is_rl and agent.last_rate_limit:
                elapsed = (datetime.now() - agent.last_rate_limit).total_seconds()
                remaining = max(0, 60 - elapsed)
                eta_minutes = int(remaining / 60) + (1 if remaining % 60 > 0 else 0)

            agents_detail.append({
                "agent_id": agent_id,
                "name": agent.name,
                "status": agent.status.value,
                "tier": agent.tier.value,
                "is_available": agent.is_available(),
                "is_rate_limited": is_rl,
                "current_load": agent.current_load,
                "max_concurrent": agent.max_concurrent,
                "success_rate": round(agent.success_rate(), 2),
                "eta_available_minutes": eta_minutes if is_rl else None,
                "last_rate_limit": agent.last_rate_limit.isoformat() if agent.last_rate_limit else None,
            })

        return {
            "pool_status": "ok",
            "total_agents": stats.total_agents,
            "available_agents": stats.available_agents,
            "free_agents_available": stats.free_agents_available,
            "agents": agents_detail,
        }
    except Exception as exc:
        logger.warning("agent_pool_status_unavailable error=%s", exc)
        return {
            "pool_status": "unavailable",
            "error": str(exc),
            "total_agents": 0,
            "available_agents": 0,
            "free_agents_available": 0,
            "agents": [],
        }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_hints(request: web.Request) -> web.Response:
    """POST /hints or GET /hints?q= — return ranked workflow hints for any agent.

    Phase 19.3.2: When format=continue (GET param) or body contains 'fullInput'
    (Continue.dev HTTP context provider), returns [{"name","description","content"}].

    Phase 20.1: Returns agent availability and rate-limit status in metadata.
    """
    try:
        async with _agent_lessons_lock:
            lesson_registry = await _load_agent_lessons_registry()
        lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
        if request.method == "POST":
            try:
                body = await request.json()
            except Exception:
                body = {}
            # Continue.dev HTTP context provider sends {"query":..., "fullInput":...}
            is_continue = "fullInput" in body or body.get("format") == "continue"
            query = body.get("query", "") or body.get("fullInput", "")
            ctx = body.get("context", {})
            file_ext = ctx.get("file_ext", "") if isinstance(ctx, dict) else str(ctx)
            max_hints = int(body.get("max_hints", 4))
            agent_type = ctx.get("agent_type", "remote") if isinstance(ctx, dict) else "remote"
            include_debug_metadata = bool(body.get("include_debug_metadata") or body.get("debug"))
            # Phase 10.3 — Token-efficient hint delivery
            max_hint_tokens = int(body.get("max_hint_tokens", 0))
            compact_mode = bool(body.get("compact", False))
            # Context-aware token budgeting
            task_phase = body.get("task_phase", "")  # new_phase, continued_work, sub_task, refinement
            post_compaction = bool(body.get("post_compaction", False))
            # Phase 10.4 — Escalation: model requests expanded context
            force_escalation = bool(body.get("escalate", False))
        else:
            is_continue = request.rel_url.query.get("format") == "continue"
            query = request.rel_url.query.get("q", "")
            file_ext = request.rel_url.query.get("context", "")
            max_hints = int(request.rel_url.query.get("max", "4"))
            agent_type = request.rel_url.query.get("agent", "remote")
            include_debug_metadata = request.rel_url.query.get("debug", "0").strip().lower() in {"1", "true", "yes"}
            # Phase 10.3 — Token-efficient hint delivery
            max_hint_tokens = int(request.rel_url.query.get("max_tokens", "0"))
            compact_mode = request.rel_url.query.get("compact", "0").strip().lower() in {"1", "true", "yes"}
            # Context-aware token budgeting
            task_phase = request.rel_url.query.get("task_phase", "")
            post_compaction = request.rel_url.query.get("post_compaction", "0").strip().lower() in {"1", "true", "yes"}
            # Phase 10.4 — Escalation: model requests expanded context
            force_escalation = request.rel_url.query.get("escalate", "0").strip().lower() in {"1", "true", "yes"}

        try:
            import sys as _sys
            from pathlib import Path as _Path
            # .parent = knowledge/, .parent.parent = hybrid-coordinator/
            # Must insert coordinator root so top-level hints_engine.py shim is
            # found; importing knowledge/hints_engine.py directly as a top-level
            # module breaks its relative imports (.hints_engine_impl, etc.).
            _hints_dir = _Path(__file__).parent.parent
            if str(_hints_dir) not in _sys.path:
                _sys.path.insert(0, str(_hints_dir))
            from hints_engine import HintsEngine  # type: ignore[import]
            engine = HintsEngine()
            # Phase 1.3 — Profile hints engine operation
            _hints_start = time.time()
            result = engine.rank_as_dict(
                query,
                context=file_ext,
                max_hints=max_hints,
                agent_type=agent_type,
                include_debug_metadata=include_debug_metadata,
                max_hint_tokens=max_hint_tokens,
                compact_mode=compact_mode,
                force_escalation=force_escalation,
            )
            _hints_duration_ms = (time.time() - _hints_start) * 1000
            _PERFORMANCE_PROFILER.record_metric(
                "hints_engine_rank", _hints_duration_ms,
                {"query_len": len(query), "max_hints": max_hints},
            )
        except Exception as exc:
            logger.warning("hints_engine_unavailable error=%s", exc)
            result = {
                "hints": [],
                "generated_at": "",
                "query": query,
                "error": f"hints_engine unavailable: {exc}",
            }

        # Phase 20.1 — Attach remote agent status to hint responses
        result["agent_status"] = _get_remote_agent_status()

        # Phase 19.3.2 — Continue.dev HTTP context provider format
        if is_continue:
            hints = result.get("hints", [])
            content_lines = ["# AI Stack Hints\n\n"]
            for i, h in enumerate(hints, 1):
                score_pct = f"{h.get('score', 0):.0%}"
                block = (
                    f"{i}. [{h.get('type', 'hint')}] {h.get('title', '')} ({score_pct})\n"
                    f"   {h.get('snippet', '')[:120]}\n"
                )
                if include_debug_metadata and h.get("reason"):
                    block += f"   Reason: {h.get('reason', '')}\n"
                content_lines.append(block + "\n")
            return web.json_response([{
                "name": "aq-hints",
                "description": "AI Stack workflow hints" + (f" for: {query[:60]}" if query else ""),
                "content": "".join(content_lines) or "No hints available — run aq-prompt-eval to score registry prompts.",
                "active_lesson_refs": lesson_refs,
            }])

        # Agent-type-specific augmentation
        if result.get("hints") and agent_type in ("claude", "codex", "qwen", "aider", "gemini"):
            top = result["hints"][0]
            result["inject_prefix"] = top.get("snippet", "")[:150]
        result["active_lesson_refs"] = lesson_refs
        result["feedback_contract"] = {
            "endpoint": "/hints/feedback",
            "required_any_of": ["helpful", "score"],
            "required": ["hint_id"],
        }

        return web.json_response(result)
    except Exception as exc:
        logger.error("handle_hints error=%s", exc)
        return web.json_response({"error": str(exc)}, status=500)


async def handle_hints_feedback(request: web.Request) -> web.Response:
    """POST /hints/feedback — explicit agent feedback loop for hint quality."""
    try:
        data = await request.json()
    except Exception:
        data = {}

    hint_id = str(data.get("hint_id", "") or "").strip()
    if not hint_id:
        return web.json_response({"error": "hint_id required"}, status=400)

    helpful_raw = data.get("helpful")
    helpful = bool(helpful_raw) if isinstance(helpful_raw, bool) else None
    score_raw = data.get("score")
    score_val: Optional[float] = None
    if score_raw is not None:
        try:
            score_val = float(score_raw)
        except (TypeError, ValueError):
            return web.json_response({"error": "score must be numeric"}, status=400)

    if helpful is None and score_val is None:
        return web.json_response({"error": "helpful or score required"}, status=400)

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hint_id": hint_id,
        "helpful": helpful,
        "score": score_val,
        "comment": str(data.get("comment", "") or "").strip()[:240],
        "agent": str(data.get("agent", "") or "").strip()[:48] or "unknown",
        "task_id": str(data.get("task_id", "") or "").strip()[:80],
        "source": "agent_feedback",
    }
    prefs = data.get("agent_preferences", {})
    if isinstance(prefs, dict):
        def _norm_list(value: object, limit: int = 8) -> List[str]:
            if not isinstance(value, list):
                return []
            out: List[str] = []
            seen: set = set()
            for item in value:
                text = str(item or "").strip().lower()
                if not text or text in seen:
                    continue
                seen.add(text)
                out.append(text[:48])
                if len(out) >= limit:
                    break
            return out

        entry["agent_preferences"] = {
            "preferred_tools": _norm_list(prefs.get("preferred_tools")),
            "preferred_data_sources": _norm_list(prefs.get("preferred_data_sources")),
            "preferred_hint_types": _norm_list(prefs.get("preferred_hint_types")),
            "preferred_tags": _norm_list(prefs.get("preferred_tags")),
        }
    try:
        log_path = _hint_feedback_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logger.error("hint_feedback_write_failed error=%s", exc)
        return web.json_response({"error": "feedback_write_failed"}, status=500)

    payload: Dict[str, Any] = {"status": "recorded", "hint_id": hint_id}
    async with _agent_lessons_lock:
        lesson_registry = await _load_agent_lessons_registry()
    lesson_refs = _active_lesson_refs(lesson_registry, limit=2)
    if lesson_refs:
        payload["active_lesson_refs"] = lesson_refs
    return web.json_response(payload)


async def handle_agent_status(request: web.Request) -> web.Response:
    """GET/POST /agent-status — remote agent pool availability and rate-limit status.

    Phase 20.1: Provides explicit endpoint for agents to check remote pool status.
    Returns ETA for rate-limited agents and availability counts.
    """
    try:
        detail = request.rel_url.query.get("detail", "0").strip().lower() in {"1", "true", "yes"}
        if request.method == "POST":
            try:
                body = await request.json()
            except Exception:
                body = {}
            detail = detail or bool(body.get("detail", False))
            agent_filter = body.get("agent_id", "") or body.get("agent", "")
        else:
            agent_filter = (
                request.rel_url.query.get("agent_id", "")
                or request.rel_url.query.get("agent", "")
            )

        status_data = _get_remote_agent_status()

        if agent_filter:
            matching = [
                a for a in status_data["agents"]
                if a["agent_id"] == agent_filter or a["name"].lower() == agent_filter.lower()
            ]
            if not matching:
                return web.json_response({
                    "error": f"agent not found: {agent_filter}",
                    "available_agents": status_data["available_agents"],
                    "hint": "Use GET /agent-status without filter to see all agents",
                }, status=404)
            status_data["agents"] = matching
            status_data["filtered"] = True

        if not detail:
            for agent in status_data.get("agents", []):
                agent.pop("last_rate_limit", None)

        return web.json_response(status_data)
    except Exception as exc:
        logger.error("handle_agent_status error=%s", exc)
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(http_app: web.Application) -> None:
    http_app.router.add_post("/hints", handle_hints)           # Phase 19.2.1
    http_app.router.add_get("/hints", handle_hints)            # Phase 19.2.2
    http_app.router.add_post("/hints/feedback", handle_hints_feedback)
    http_app.router.add_get("/agent-status", handle_agent_status)      # Phase 20.1
    http_app.router.add_post("/agent-status", handle_agent_status)     # Phase 20.1
