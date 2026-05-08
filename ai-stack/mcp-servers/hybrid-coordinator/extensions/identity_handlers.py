"""
Identity Handlers — Phase 16.4

HTTP routes for the identity kernel.  Follows the extracted-handler pattern
used throughout the hybrid coordinator (init() + register_routes()).

Routes:
  GET  /identity/self   — current identity summary (values + history + sessions)
  POST /identity/event  — append event to journal (internal, API-key protected)

Depends on:
  ai-stack/identity-kernel/narrative_engine.py
  ai-stack/identity-kernel/value_constitution.py
  ai-stack/identity-kernel/checkpoint_service.py
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level state injected via init()
# ---------------------------------------------------------------------------
_journal_path: str = ""
_value_constitution_file: str = ""
_api_key: str = ""          # guards POST /identity/event
_engine: Optional[Any] = None
_constitution: Optional[Any] = None
_checkpoint_svc: Optional[Any] = None


def _identity_kernel_path() -> Path:
    """Resolve path to ai-stack/identity-kernel/ relative to this file."""
    return Path(__file__).resolve().parents[2] / "identity-kernel"


def _ensure_imports() -> None:
    """Add identity-kernel to sys.path once."""
    p = str(_identity_kernel_path())
    if p not in sys.path:
        sys.path.insert(0, p)


def init(
    *,
    journal_path: str = "",
    value_constitution_file: str = "",
    api_key: str = "",
) -> None:
    """
    Configure and start the identity kernel services.
    Called once from http_server.py run_http_mode() before register_routes().
    """
    global _journal_path, _value_constitution_file, _api_key
    global _engine, _constitution, _checkpoint_svc

    _journal_path = journal_path or os.environ.get(
        "IDENTITY_JOURNAL_PATH",
        "/var/lib/ai-stack/identity/journal.jsonl",
    )
    _value_constitution_file = value_constitution_file or os.environ.get(
        "IDENTITY_VALUE_CONSTITUTION",
        "config/identity-values.yaml",
    )
    _api_key = api_key or os.environ.get("HYBRID_COORDINATOR_API_KEY", "")

    _ensure_imports()

    try:
        from narrative_engine import NarrativeEngine  # type: ignore
        _engine = NarrativeEngine(journal_path=_journal_path)
        _engine.append_event("boot", {"session": "startup"})
        logger.info("identity_handlers: narrative engine ready path=%s", _journal_path)
    except Exception as exc:
        logger.warning("identity_handlers: narrative engine init failed: %s", exc)

    try:
        from value_constitution import ValueConstitution  # type: ignore
        _constitution = ValueConstitution(_value_constitution_file)
        logger.info("identity_handlers: value constitution loaded values=%d",
                    len(_constitution.get_values()))
    except Exception as exc:
        logger.warning("identity_handlers: value constitution init failed: %s", exc)

    try:
        from checkpoint_service import CheckpointService  # type: ignore
        _checkpoint_svc = CheckpointService(journal_path=_journal_path)
        _checkpoint_svc.start_thread()
    except Exception as exc:
        logger.warning("identity_handlers: checkpoint service init failed: %s", exc)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def handle_identity_self(request: web.Request) -> web.Response:
    """GET /identity/self — structured identity summary."""
    summary: dict = {}
    values: list = []
    last_checkpoint: Optional[str] = None

    if _engine is not None:
        try:
            summary = _engine.generate_summary()
        except Exception as exc:
            logger.warning("identity_handlers: generate_summary failed: %s", exc)

    if _constitution is not None:
        try:
            values = _constitution.get_values()
        except Exception as exc:
            logger.warning("identity_handlers: get_values failed: %s", exc)

    # Read last_checkpoint timestamp from checkpoint file if available
    cp_dir = os.environ.get("IDENTITY_CHECKPOINT_PATH", "/var/lib/ai-stack/identity")
    cp_file = Path(cp_dir) / "checkpoint.json"
    if cp_file.exists():
        try:
            import time as _time
            last_checkpoint = _time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", _time.gmtime(cp_file.stat().st_mtime)
            )
        except OSError:
            pass

    payload = {
        "summary": summary,
        "values": values,
        "uptime_sessions": summary.get("uptime_sessions", 0),
        "last_checkpoint": last_checkpoint,
    }
    return web.Response(
        content_type="application/json",
        body=json.dumps(payload, default=str),
    )


async def handle_identity_event(request: web.Request) -> web.Response:
    """POST /identity/event — append a typed event (internal, API-key protected)."""
    # Validate API key
    req_key = request.headers.get("X-API-Key", "").strip()
    if _api_key and req_key != _api_key:
        return web.Response(status=401, text="Unauthorized")

    if _engine is None:
        return web.Response(status=503, text="identity kernel not initialized")

    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400, text="invalid JSON body")

    event_type = body.get("event_type", "").strip()
    payload_data = body.get("payload", {})
    if not event_type:
        return web.Response(status=400, text="event_type required")

    try:
        event_id = _engine.append_event(event_type, payload_data)
    except Exception as exc:
        logger.warning("identity_handlers: append_event failed: %s", exc)
        return web.Response(status=500, text=str(exc))

    return web.Response(
        content_type="application/json",
        body=json.dumps({"event_id": event_id, "event_type": event_type}),
    )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/identity/self", handle_identity_self)
    http_app.router.add_post("/identity/event", handle_identity_event)
    logger.info("identity_handlers: routes registered /identity/self /identity/event")
