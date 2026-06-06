"""
memory/memory_service.py — MemoryService for the hybrid-coordinator.

Phase R2.3 (Strangler Fig): extracted from http_server.py:run_http_mode() closures.
Handles:
  POST /api/memory/facts      — commit structured facts from aq-commit-facts
  GET  /api/memory/facts      — retrieve stored facts (aq-session-start)
  GET  /memory/journal        — agentic memory journal entries
  GET  /memory/journal/stats  — journal aggregate stats
  *    /memory/supersede*     — temporal memory supersession (delegated to extensions)
  *    /memory/crystalline*   — crystalline session distillation (delegated to extensions)

No runtime DI required — all dependencies importable at module level.
"""

from __future__ import annotations

import logging
import time

from aiohttp import web

import agentic_memory_journal as _journal
import memory_broker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


async def handle_memory_facts_post(request: web.Request) -> web.Response:
    """POST /api/memory/facts — store structured facts from aq-commit-facts.

    Writes each fact to MemoryBroker semantic store with valid_from=now().
    Body: {"facts": [{"fact":str, "scope":str, "confidence":float, "source":str,
                      "event_time":str (ISO 8601, optional — Phase 60.1 bitemporal)}]}
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    facts = data.get("facts") or []
    if not isinstance(facts, list):
        return web.json_response({"error": "facts must be array"}, status=400)

    stored = 0
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    mb = memory_broker.get_broker()
    for f in facts[:8]:  # cap at 8 per call
        if not isinstance(f, dict):
            continue
        fact_text = str(f.get("fact") or "").strip()[:500]
        if not fact_text:
            continue
        # Phase 60.1: parse optional event_time for bitemporal writes
        from datetime import datetime, timezone as _tz
        event_time_dt = None
        event_time_raw = f.get("event_time")
        if event_time_raw:
            try:
                event_time_dt = datetime.fromisoformat(str(event_time_raw))
                if event_time_dt.tzinfo is None:
                    event_time_dt = event_time_dt.replace(tzinfo=_tz.utc)
            except (ValueError, TypeError):
                pass

        try:
            result = await mb.write(
                memory_type="semantic",
                content=fact_text,
                event_time=event_time_dt,
                context={
                    "scope":      str(f.get("scope") or "other")[:64],
                    "confidence": float(f.get("confidence") or 0.8),
                    "source":     str(f.get("source") or "aq-commit-facts")[:128],
                    "valid_from": ts,
                    "origin":     "commit_facts",
                },
            )
            # "skipped" (dedup) = already present; "queued" = fire-and-forget accepted
            if result.get("status") in {"stored", "skipped", "queued"}:
                stored += 1
        except Exception as _exc:
            logger.debug("memory_facts_store_skip err=%s", _exc)

    return web.json_response({"stored": stored, "timestamp": ts})


async def handle_memory_facts_get(request: web.Request) -> web.Response:
    """GET /api/memory/facts — retrieve stored facts (used by aq-session-start).

    Query params:
      scope=<str>       — filter by scope
      limit=<int>       — default 10, max 50
      valid_at=<iso8601> — Phase 60.1: time-travel; return facts valid at this instant
    """
    from datetime import datetime, timezone as _tz
    scope = request.rel_url.query.get("scope", "")
    try:
        limit = max(1, min(int(request.rel_url.query.get("limit", "10")), 50))
    except (ValueError, TypeError):
        limit = 10

    valid_at = None
    valid_at_str = request.rel_url.query.get("valid_at", "")
    if valid_at_str:
        try:
            valid_at = datetime.fromisoformat(valid_at_str)
            if valid_at.tzinfo is None:
                valid_at = valid_at.replace(tzinfo=_tz.utc)
        except (ValueError, TypeError):
            return web.json_response({"error": "invalid valid_at format; use ISO 8601"}, status=400)

    mb = memory_broker.get_broker()
    try:
        results = await mb.read(
            memory_type="semantic",
            query=scope or "procedural constraints",
            top_k=limit,
            valid_at=valid_at,
        )
    except Exception as _exc:
        return web.json_response({"facts": [], "error": str(_exc)})

    facts = []
    for item in (results if isinstance(results, list) else []):
        content = item.get("content") or item.get("text") or ""
        ctx = item.get("context") or item.get("metadata") or {}
        if scope and ctx.get("scope", "") != scope:
            continue
        facts.append({
            "fact":         content[:500],
            "scope":        ctx.get("scope", ""),
            "confidence":   ctx.get("confidence", 0.8),
            "source":       ctx.get("source", ""),
            "event_time":   ctx.get("event_time"),      # Phase 60.1: bitemporal
            "ingestion_time": ctx.get("ingestion_time"),
            "valid_from":   ctx.get("valid_from"),
            "valid_until":  ctx.get("valid_until"),
        })
    return web.json_response({"facts": facts[:limit]})


async def handle_journal_entries(request: web.Request) -> web.Response:
    """GET /memory/journal — agentic memory journal entries."""
    try:
        params = request.rel_url.query
        entries = await _journal.get_entries(
            limit=int(params.get("limit", "50")),
            model_id=params.get("model_id") or None,
            tier=params.get("tier") or None,
            task_archetype=params.get("task_archetype") or None,
            success_only=params.get("success_only", "").lower() == "true",
            errors_only=params.get("errors_only", "").lower() == "true",
            since_epoch=float(params.get("since_epoch", "0")),
        )
        return web.json_response({"entries": entries, "count": len(entries)})
    except Exception as exc:
        logger.exception("handle_journal_entries error: %s", exc)
        return web.json_response({"error": str(exc)}, status=500)


async def handle_journal_stats(request: web.Request) -> web.Response:
    """GET /memory/journal/stats — journal aggregate statistics."""
    try:
        params = request.rel_url.query
        stats = await _journal.get_stats(
            since_epoch=float(params.get("since_epoch", "0")),
        )
        return web.json_response(stats)
    except Exception as exc:
        logger.exception("handle_journal_stats error: %s", exc)
        return web.json_response({"error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Route registration helper (called from router.py)
# ---------------------------------------------------------------------------


def register_routes(app: web.Application) -> None:
    """Register all MemoryService routes on the given aiohttp Application."""
    app.router.add_post("/api/memory/facts", handle_memory_facts_post)
    app.router.add_get("/api/memory/facts", handle_memory_facts_get)
    app.router.add_get("/memory/journal", handle_journal_entries)
    app.router.add_get("/memory/journal/stats", handle_journal_stats)

    # Temporal memory supersession (already extracted to extensions/)
    from extensions import memory_superseder as _superseder_routes
    _superseder_routes.register_routes(app)

    # Crystalline session distillation (already extracted to extensions/)
    from extensions import memory_crystallizer as _crystallizer_routes
    _crystallizer_routes.register_routes(app)
