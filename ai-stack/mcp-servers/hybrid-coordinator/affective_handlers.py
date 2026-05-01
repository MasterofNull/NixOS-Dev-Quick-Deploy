"""
Affective Engine HTTP Handlers — Phase 19: Values Signals

Exposes:
  GET /affective/state — current affective state snapshot + reciprocity debt

Registered via register_routes(app) following the Phase 12.4 extraction pattern.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Lazy affective engine path injection
# ---------------------------------------------------------------------------

_AFFECTIVE_DIR = Path(__file__).resolve().parent.parent.parent / "affective-engine"

def _ensure_affective_path() -> bool:
    """Add affective-engine to sys.path. Returns True if available."""
    if not _AFFECTIVE_DIR.exists():
        return False
    p = str(_AFFECTIVE_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)
    return True


# ---------------------------------------------------------------------------
# Shared last-state cache (written by http_server affective pipeline)
# ---------------------------------------------------------------------------

_last_state_snapshot: Dict[str, Any] = {}


def update_state_snapshot(state_dict: Dict[str, Any]) -> None:
    """Called by the http_server query pipeline to cache the latest state."""
    _last_state_snapshot.clear()
    _last_state_snapshot.update(state_dict)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

async def handle_affective_state(request: web.Request) -> web.Response:
    """GET /affective/state — return last computed affective state snapshot."""
    enabled = os.environ.get("AFFECTIVE_ENABLED", "false").lower() == "true"

    if not enabled:
        return web.json_response({
            "enabled": False,
            "state": None,
            "message": "Affective engine is disabled (AFFECTIVE_ENABLED=false)",
        })

    snapshot = dict(_last_state_snapshot)

    # If no queries processed yet, return a zeroed state
    if not snapshot:
        snapshot = {
            "empathy_signal": 0.0,
            "reciprocity_debt": 0.0,
            "aesthetic_gap": 0.0,
            "compassion_level": 0.0,
            "dominant_signal": "neutral",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return web.json_response({
        "enabled": True,
        "state": snapshot,
    })


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/affective/state", handle_affective_state)
