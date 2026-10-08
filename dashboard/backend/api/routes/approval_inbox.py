"""Read-only projection of the same numbered inbox used by aq-approve."""

import asyncio
import importlib
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

_LIB = str(Path(__file__).resolve().parents[4] / "scripts" / "ai" / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["approval-inbox"])


def _public_text(value: object) -> str:
    # Titles originate in error messages and may contain credential assignments.
    text = str(value)
    text = re.sub(r"(?i)\b(bearer|basic)\s+\S+", r"\1 [redacted]", text)
    text = re.sub(
        r"(?i)([\w-]*(?:secret|token|password|passwd|api[_-]?key|credential)[\w-]*[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
        r"\1[redacted]", text,
    )
    return re.sub(r"(https?://)[^/\s@]+@", r"\1[redacted]@", text)


def _project() -> dict:
    inbox = importlib.import_module("approval_inbox")
    items, degraded = inbox.collect_with_status()
    needs_approval, deferred = [], []
    for n, item in enumerate(items, 1):
        row = {"n": n, **{field: _public_text(item[key]) for field, key in (
            ("severity", "severity"), ("title", "title"),
            ("source", "source"), ("id", "key"),
        )}}
        (needs_approval if item["section"] == "approval" else deferred).append(row)
    result = {
        "tag": inbox.snapshot_tag(items),
        "needs_approval": needs_approval,
        "deferred": deferred,
        "counts": {"needs_approval": len(needs_approval), "deferred": len(deferred), "total": len(items)},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if degraded:
        result["status"] = "degraded"
        result["degraded_sources"] = [{"path": _public_text(d["path"]), "error": d["error"]} for d in degraded]
    return result


@router.get("/approval-inbox")
async def get_approval_inbox() -> dict:
    try:
        return await asyncio.to_thread(_project)
    except Exception:
        # Neither the response nor logs should expose raw errors or file contents.
        logger.warning("Approval inbox projection unavailable")
        return {"status": "unavailable", "reason": "Approval inbox could not be read"}
