"""
operator_intelligence_handlers.py — Operator Intelligence Bridge HTTP handlers.

Phase 164: Exposes OIB insight generation via HTTP endpoints.

Routes:
  POST /operator/insights  — Generate session insight cards and return OIB output
  GET  /operator/profile   — Return the persisted operator knowledge profile

Design doc: .agents/designs/OPERATOR-INTELLIGENCE-BRIDGE.md
"""
from __future__ import annotations

import json
import logging

from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

# lazy import to avoid circular deps at module load time
def _oib():
    from extensions.operator_intelligence import (
        generate_session_insights,
        load_operator_profile,
        asdict,
    )
    return generate_session_insights, load_operator_profile, asdict


async def handle_operator_insights(request: web.Request) -> web.Response:
    """
    POST /operator/insights

    Body (all optional):
    {
      "session_context": "string describing what was worked on",
      "recent_work": "brief description of the most recent completed task",
      "provider_preach_level": 0.0,
      "prompt_history": ["prompt1", "prompt2", ...]
    }

    Returns:
    {
      "session_topics": [...],
      "insight_cards": [...],
      "open_research_threads": [...],
      "prompt_specificity": {...},
      "profile_summary": {...},
      "provider_preach_level": 0.0,
      "generated_at": "ISO"
    }
    """
    try:
        body: dict = {}
        try:
            body = await request.json()
        except Exception:
            pass

        generate_session_insights, _, _ = _oib()
        result = await __import__("asyncio").to_thread(
            generate_session_insights,
            body.get("session_context", ""),
            body.get("recent_work", ""),
            float(body.get("provider_preach_level", 0.0)),
            body.get("prompt_history") or None,
        )
        return web.json_response(result)
    except Exception as exc:
        logger.exception("handle_operator_insights error: %s", exc)
        return web.json_response({"error": str(exc)}, status=500)


async def handle_operator_profile(request: web.Request) -> web.Response:
    """
    GET /operator/profile

    Returns the persisted operator knowledge profile.
    """
    try:
        _, load_operator_profile, asdict = _oib()
        from dataclasses import asdict as _asdict
        profile = await __import__("asyncio").to_thread(load_operator_profile)
        return web.json_response(_asdict(profile))
    except Exception as exc:
        logger.exception("handle_operator_profile error: %s", exc)
        return web.json_response({"error": str(exc)}, status=500)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_post("/operator/insights", handle_operator_insights)
    http_app.router.add_get("/operator/profile", handle_operator_profile)
