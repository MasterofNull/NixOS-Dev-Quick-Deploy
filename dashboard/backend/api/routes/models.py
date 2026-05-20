"""models.py — Model lifecycle REST + SSE endpoints for the command-center dashboard.

Endpoints:
  GET  /api/models                      — list all models with state
  GET  /api/models/{id}                 — single model entry
  POST /api/models/{id}/download        — start background download
  GET  /api/models/{id}/download/stream — SSE progress stream
  POST /api/models/{id}/promote         — hot-swap to active
  GET  /api/models/{id}/promote/stream  — SSE swap progress stream
  POST /api/models/{id}/rollback        — rollback archived model to active
  POST /api/models/{id}/cancel          — cancel in-progress download
  GET  /api/models/active               — currently active model entry

Security (Codex AM-C2): dashboard-internal /api/models endpoints allow loopback
for same-node UI use. Canonical /admin/v1/models mutating operations require
X-Dashboard-Internal: 1 or X-API-Key matching HYBRID_COORDINATOR_API_KEY even
from loopback.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Coordinator module import ─────────────────────────────────────────────────
# The coordinator modules live at ai-stack/mcp-servers/hybrid-coordinator/.
# The dashboard backend runs from a separate venv, so we inject the path.

def _coordinator_path() -> Path:
    return Path(__file__).resolve().parents[4] / "ai-stack" / "mcp-servers" / "hybrid-coordinator"


_coord_path = str(_coordinator_path())
if _coord_path not in sys.path:
    sys.path.insert(0, _coord_path)

try:
    from model_registry import ModelState, get_registry
    from model_lifecycle_manager import get_lifecycle_manager
    _LIFECYCLE_AVAILABLE = True
except ImportError as _ie:
    logger.warning("models route: lifecycle modules not available: %s", _ie)
    _LIFECYCLE_AVAILABLE = False

# ── Auth helper ───────────────────────────────────────────────────────────────

_API_KEY = os.getenv("HYBRID_COORDINATOR_API_KEY", "")

def _check_auth(request: Request) -> None:
    """Authorize model lifecycle access.

    `/api/models/*` remains dashboard-internal and loopback-friendly for the
    existing single-node UI. Canonical `/admin/v1/models/*` mutating calls are
    stricter per MAEAH AM-C2: loopback alone is not sufficient.
    """
    client_host = (request.client.host if request.client else "") or ""
    provided = request.headers.get("X-API-Key", "")
    internal = request.headers.get("X-Dashboard-Internal", "") == "1"
    is_admin = str(request.url.path).startswith("/admin/v1/")
    is_mutating = request.method.upper() not in {"GET", "HEAD", "OPTIONS"}

    if is_admin and is_mutating:
        if internal:
            return
        if _API_KEY and provided == _API_KEY:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin lifecycle operation requires API key")

    if client_host in ("127.0.0.1", "::1", "localhost"):
        return
    if _API_KEY and provided == _API_KEY:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="unauthorized")


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse_event(event: str, data: Any) -> str:
    payload = json.dumps(data) if not isinstance(data, str) else data
    return f"event: {event}\ndata: {payload}\n\n"


async def _sse_keep_alive(stop_event: asyncio.Event) -> AsyncGenerator[str, None]:
    """Yield SSE comment keep-alives every 15s until stop_event is set."""
    while not stop_event.is_set():
        yield ": keep-alive\n\n"
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            pass


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/models")
async def list_models(request: Request):
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        return _stub_catalog()
    registry = get_registry()
    models = await registry.list_models()
    # Enrich with disk presence
    for m in models:
        local = m.get("local_path")
        m["file_exists"] = bool(local and Path(local).exists())
    return {"models": models, "count": len(models)}


@router.get("/models/active")
async def get_active_model(request: Request):
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")
    registry = get_registry()
    active = await registry.get_active_model()
    if active is None:
        return {"active": None}
    return {"active": active}


@router.get("/models/{model_id}")
async def get_model(model_id: str, request: Request):
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")
    registry = get_registry()
    entry = await registry.get_model(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    local = entry.get("local_path")
    entry["file_exists"] = bool(local and Path(local).exists())
    return entry


@router.get("/models/{model_id}/llama-args")
async def get_model_llama_args(model_id: str, request: Request):
    """Return the llama-server CLI args for a model + a ready-to-run restart script."""
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")

    from model_lifecycle_manager import _llama_args_to_cli, ACTIVE_SYMLINK
    registry = get_registry()
    entry = await registry.get_model(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")

    llama_args = entry.get("llama_args", {})
    local_path = entry.get("local_path") or f"/var/lib/llama-cpp/models/{entry.get('file','')}"
    cli = _llama_args_to_cli(model_id, local_path, llama_args)

    return {
        "model_id": model_id,
        "llama_args": llama_args,
        "llama_cli": cli,
        "apply_commands": [
            f"sudo ln -sf {local_path} {ACTIVE_SYMLINK}",
            "sudo systemctl restart llama-cpp",
        ],
        "args_file": str(Path.home() / ".local/share/nixos-ai-stack/llama-active-args.env"),
    }


@router.post("/models/{model_id}/download")
async def start_download(model_id: str, request: Request):
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")
    manager = get_lifecycle_manager()
    try:
        await manager.start_download(model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"status": "download_started", "model_id": model_id}


@router.get("/models/{model_id}/download/stream")
async def download_progress_stream(model_id: str, request: Request):
    """SSE stream of download progress events for model_id."""
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")

    registry = get_registry()
    stop = asyncio.Event()
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    def _on_progress(done: int, total: int, pct: float) -> None:
        try:
            queue.put_nowait({"type": "progress", "bytes_done": done, "total": total, "pct": pct})
        except asyncio.QueueFull:
            pass

    manager = get_lifecycle_manager()
    manager.subscribe_progress(model_id, _on_progress)

    async def event_gen() -> AsyncGenerator[str, None]:
        try:
            # Send current state immediately
            entry = await registry.get_model(model_id)
            if entry:
                yield _sse_event("state", {
                    "state": entry.get("state"),
                    "pct": entry.get("download_progress", 0),
                    "bytes_done": entry.get("download_bytes", 0),
                    "total": entry.get("download_total", 0),
                })

            while not stop.is_set():
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield _sse_event("progress", evt)

                    # Check if download finished
                    entry = await registry.get_model(model_id)
                    if entry:
                        state = entry.get("state", "")
                        if state in ("verified", "failed", "active"):
                            yield _sse_event("done", {"state": state, "model_id": model_id})
                            return
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    # Check for terminal state during idle
                    entry = await registry.get_model(model_id)
                    if entry and entry.get("state") in ("verified", "failed", "active"):
                        yield _sse_event("done", {"state": entry["state"], "model_id": model_id})
                        return
        finally:
            manager.unsubscribe_progress(model_id, _on_progress)
            stop.set()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/models/{model_id}/promote")
async def promote_model(model_id: str, request: Request):
    """Promote a VERIFIED model to ACTIVE via hot-swap."""
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")
    manager = get_lifecycle_manager()
    registry = get_registry()
    entry = await registry.get_model(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    if ModelState(entry["state"]) != ModelState.VERIFIED:
        raise HTTPException(
            status_code=409,
            detail=f"Model must be VERIFIED to promote (current: {entry['state']})"
        )
    try:
        result = await manager.promote_model(model_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    code = 200 if result.get("success") else 502
    from fastapi.responses import JSONResponse
    return JSONResponse(content=result, status_code=code)


@router.get("/models/{model_id}/promote/stream")
async def promote_progress_stream(model_id: str, request: Request):
    """SSE stream that runs the promotion and streams phase events."""
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")

    manager = get_lifecycle_manager()
    registry = get_registry()

    async def event_gen() -> AsyncGenerator[str, None]:
        yield _sse_event("phase", {"phase": "starting", "model_id": model_id})

        entry = await registry.get_model(model_id)
        if entry is None:
            yield _sse_event("error", {"message": f"model {model_id!r} not found"})
            return
        if ModelState(entry["state"]) != ModelState.VERIFIED:
            yield _sse_event("error", {"message": f"must be VERIFIED (current: {entry['state']})"})
            return

        yield _sse_event("phase", {"phase": "symlink_update"})
        try:
            result = await manager.promote_model(model_id)
        except Exception as exc:
            yield _sse_event("error", {"message": str(exc)})
            return

        yield _sse_event("done", result)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/models/{model_id}/rollback")
async def rollback_model(model_id: str, request: Request):
    """Roll back to a previously-archived model."""
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")
    manager = get_lifecycle_manager()
    try:
        result = await manager.rollback_to(model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result


@router.post("/models/{model_id}/cancel")
async def cancel_download(model_id: str, request: Request):
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")
    manager = get_lifecycle_manager()
    cancelled = await manager.cancel_download(model_id)
    return {"cancelled": cancelled, "model_id": model_id}


@router.post("/models/{model_id}/reset")
async def reset_failed_model(model_id: str, request: Request):
    """Reset a FAILED model back to VERIFIED so it can be retried."""
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")
    manager = get_lifecycle_manager()
    try:
        result = await manager.reset_failed(model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result


@router.post("/models")
async def add_model(request: Request):
    """Add a user-defined model to the catalog."""
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    registry = get_registry()
    try:
        entry = await registry.add_model(body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"status": "added", "model": entry}


@router.delete("/models/{model_id}")
async def delete_model(model_id: str, request: Request):
    """Remove a user-defined model from the catalog."""
    _check_auth(request)
    if not _LIFECYCLE_AVAILABLE:
        raise HTTPException(status_code=503, detail="lifecycle modules unavailable")
    registry = get_registry()
    try:
        removed = await registry.delete_model(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not removed:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    return {"status": "deleted", "model_id": model_id}


# ── Stub catalog (fallback when coordinator not importable) ───────────────────

def _stub_catalog():
    """Return minimal catalog when lifecycle modules aren't available."""
    return {
        "models": [],
        "count": 0,
        "error": "lifecycle modules not available — coordinator may still be loading",
    }
