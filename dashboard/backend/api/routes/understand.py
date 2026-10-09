"""Understand-Anything graph summary for the dashboard tile/module page.

GET /api/understand/summary -- read-only: graph age, node/edge counts by normalised
type, stale flag (limits from config/understand-anything.json) and wiki age. Parses the
graph in-process (stdlib helper, mtime-cached); no LLM, no writes, no subprocess except
a bounded `git rev-list --count` for commits-since-generation.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from fastapi import APIRouter

_REPO_ROOT = Path(__file__).resolve().parents[4]
_LIB_DIR = _REPO_ROOT / "scripts" / "ai" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import understand_graph  # noqa: E402

router = APIRouter(tags=["understand"])


@router.get("/understand/summary")
async def get_understand_summary() -> dict:
    # file parse + git subprocess are blocking; keep the event loop free
    return await asyncio.to_thread(understand_graph.summary, _REPO_ROOT)
