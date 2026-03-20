"""
Deployment tracking and history API routes
Provides real-time deployment progress and historical deployment data
Integrated with context-aware storage (SQLite + FTS5)
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import logging
import asyncio
import os
import shlex
import subprocess
from pathlib import Path

from api.services.context_store import get_context_store

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket connections for real-time updates
deployment_connections: List[WebSocket] = []
deployment_lock = asyncio.Lock()

# Get context store singleton
context_store = get_context_store()
REPO_ROOT = Path(__file__).resolve().parents[4]
BASH_BIN = os.getenv("BASH_BIN", "bash")

# Deployment event types (for WebSocket broadcasting)
class DeploymentEventType:
    STARTED = "started"
    PROGRESS = "progress"
    LOG = "log"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"


class DeploymentRollbackRequest(BaseModel):
    """Rollback request for an existing deployment."""
    confirm: bool = Field(default=False)
    execute: bool = Field(default=False)
    reason: str = Field(default="Operator-requested rollback from dashboard")
    command: str = Field(default="deploy system --rollback")


class DeploymentProgressRequest(BaseModel):
    """Progress/log update payload from the deploy CLI."""
    progress: int = Field(ge=0, le=100)
    message: str
    log: Optional[str] = None


class DeploymentCompleteRequest(BaseModel):
    """Deployment completion payload from the deploy CLI."""
    success: bool = True
    message: Optional[str] = None


async def _run_rollback_command(command: str) -> subprocess.CompletedProcess:
    """Run rollback command in the repo root and capture output."""
    proc = await asyncio.create_subprocess_exec(
        BASH_BIN,
        "-lc",
        command,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )
    stdout, stderr = await proc.communicate()
    return subprocess.CompletedProcess(
        args=command,
        returncode=proc.returncode,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )


# ============================================================================
# WebSocket Endpoint for Real-Time Deployment Updates
# ============================================================================

@router.websocket("/ws/deployments")
async def websocket_deployments(websocket: WebSocket):
    """WebSocket endpoint for real-time deployment progress"""
    await websocket.accept()
    async with deployment_lock:
        deployment_connections.append(websocket)

    logger.info(f"Deployment WebSocket client connected. Active: {len(deployment_connections)}")

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong"})
            elif data == "get_active":
                # Send current active deployments from context store
                active = context_store.get_recent_deployments(limit=50, status="running")
                await websocket.send_json({
                    "type": "active_deployments",
                    "deployments": active
                })
    except WebSocketDisconnect:
        async with deployment_lock:
            if websocket in deployment_connections:
                deployment_connections.remove(websocket)
        logger.info(f"Deployment WebSocket client disconnected. Active: {len(deployment_connections)}")
    except Exception as e:
        logger.error(f"Deployment WebSocket error: {e}")
        async with deployment_lock:
            if websocket in deployment_connections:
                deployment_connections.remove(websocket)


async def broadcast_deployment_event(event_dict: dict):
    """Broadcast deployment event to all connected WebSocket clients"""
    if not deployment_connections:
        return

    message = {
        "type": "deployment_event",
        "event": event_dict
    }

    disconnected = []
    async with deployment_lock:
        for connection in deployment_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to WebSocket client: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            if conn in deployment_connections:
                deployment_connections.remove(conn)


# ============================================================================
# HTTP API Endpoints
# ============================================================================

@router.post("/deployments/start")
async def start_deployment(deployment_id: str, command: str, user: str = "system"):
    """Start tracking a new deployment"""
    # Store in context store
    context_store.start_deployment(deployment_id, command, user)

    # Broadcast to WebSocket clients
    event_dict = {
        "deployment_id": deployment_id,
        "event_type": DeploymentEventType.STARTED,
        "message": f"Deployment started: {command}",
        "progress": 0,
        "metadata": {"command": command, "user": user},
        "timestamp": datetime.utcnow().isoformat()
    }
    await broadcast_deployment_event(event_dict)

    logger.info(f"Started tracking deployment: {deployment_id}")
    return {"status": "started", "deployment_id": deployment_id}


@router.post("/deployments/{deployment_id}/progress")
async def update_deployment_progress(
    deployment_id: str,
    request: DeploymentProgressRequest,
):
    """Update deployment progress"""
    # Store event in context store
    event_type = DeploymentEventType.PROGRESS if not request.log else DeploymentEventType.LOG
    metadata = {"log": request.log} if request.log else None

    context_store.add_event(
        deployment_id=deployment_id,
        event_type=event_type,
        message=request.message,
        progress=request.progress,
        metadata=metadata
    )

    # Broadcast to WebSocket clients
    event_dict = {
        "deployment_id": deployment_id,
        "event_type": event_type,
        "message": request.message,
        "progress": request.progress,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow().isoformat()
    }
    await broadcast_deployment_event(event_dict)

    return {"status": "updated", "progress": request.progress}


@router.post("/deployments/{deployment_id}/complete")
async def complete_deployment(
    deployment_id: str,
    request: DeploymentCompleteRequest,
):
    """Mark deployment as complete"""
    # Complete in context store
    context_store.complete_deployment(
        deployment_id=deployment_id,
        success=request.success,
        message=request.message
    )

    # Broadcast to WebSocket clients
    event_type = DeploymentEventType.SUCCESS if request.success else DeploymentEventType.FAILED
    event_dict = {
        "deployment_id": deployment_id,
        "event_type": event_type,
        "message": request.message or f"Deployment {'completed successfully' if request.success else 'failed'}",
        "progress": 100 if request.success else 0,
        "metadata": {"success": request.success},
        "timestamp": datetime.utcnow().isoformat()
    }
    await broadcast_deployment_event(event_dict)

    status = "success" if request.success else "failed"
    logger.info(f"Deployment {deployment_id} completed: {status}")
    return {"status": status}


@router.get("/deployments/active")
async def get_active_deployments():
    """Get all currently active deployments"""
    deployments = context_store.get_recent_deployments(limit=100, status="running")
    return {
        "deployments": deployments,
        "count": len(deployments)
    }


@router.get("/deployments/history")
async def get_deployment_history(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    include_timeline_preview: bool = False,
):
    """Get deployment history"""
    deployments = context_store.get_recent_deployments(limit=limit, status=status)
    total = context_store.count_deployments(status=status)

    # Apply offset
    if offset > 0 and offset < len(deployments):
        deployments = deployments[offset:]
    elif offset >= len(deployments):
        deployments = []

    if include_timeline_preview:
        deployments = [
            {
                **deployment,
                "timeline_preview": context_store.get_deployment_timeline(deployment["deployment_id"])[:5],
            }
            for deployment in deployments
        ]

    return {
        "deployments": deployments,
        "total": total,
        "limit": limit,
        "offset": offset,
        "status": status,
        "has_more": offset + len(deployments) < total,
    }


@router.get("/deployments/search")
async def search_deployments(query: str, limit: int = 20, offset: int = 0, mode: str = "hybrid"):
    """Search deployment history using keyword, semantic, or hybrid retrieval."""
    normalized_mode = (mode or "hybrid").strip().lower()
    if normalized_mode not in {"keyword", "semantic", "hybrid", "auto", "natural"}:
        raise HTTPException(status_code=400, detail="mode must be keyword, semantic, hybrid, auto, or natural")

    query_analysis = context_store.analyze_deployment_query(query)
    effective_mode = query_analysis["recommended_mode"] if normalized_mode in {"auto", "natural"} else normalized_mode

    semantic_sync = None
    if effective_mode in {"semantic", "hybrid"}:
        try:
            semantic_sync = await asyncio.wait_for(
                asyncio.to_thread(context_store.sync_recent_deployments, 1),
                timeout=1.5,
            )
        except asyncio.TimeoutError:
            semantic_sync = {"status": "timed_out", "synced": 0, "failed": []}

    if effective_mode == "keyword":
        results = context_store.search_deployments(query, limit=limit, offset=offset)
    elif effective_mode == "semantic":
        results = context_store.search_deployments_semantic(query, limit=limit, offset=offset)
    else:
        results = context_store.search_deployments_hybrid(query, limit=limit, offset=offset)

    explained_results = []
    for result in results:
        item = dict(result)
        item["explanation"] = context_store.explain_deployment_search_result(query, item)
        explained_results.append(item)

    return {
        "results": explained_results,
        "query": query,
        "mode": normalized_mode,
        "effective_mode": effective_mode,
        "query_analysis": query_analysis,
        "count": len(explained_results),
        "limit": limit,
        "offset": offset,
        "semantic_sync": semantic_sync,
    }


@router.get("/deployments/search/status")
async def get_deployment_search_status(recent_limit: int = 8):
    """Get operator-facing status for deployment semantic search coverage."""
    return await asyncio.to_thread(context_store.get_deployment_search_status, recent_limit)


@router.get("/deployments/graph")
async def get_deployment_graph(
    recent_limit: int = 8,
    deployment_id: Optional[str] = None,
    view: str = "overview",
    focus: Optional[str] = None,
):
    """Get a lightweight relationship graph for recent deployments or a single deployment."""
    return await asyncio.to_thread(
        context_store.get_deployment_graph,
        recent_limit,
        deployment_id,
        view,
        focus,
    )


@router.get("/deployments/{deployment_id}")
async def get_deployment(deployment_id: str):
    """Get deployment details"""
    # Get summary from context store
    summary = context_store.get_deployment_summary(deployment_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Get timeline for events
    timeline = context_store.get_deployment_timeline(deployment_id)

    return {
        **summary,
        "timeline": timeline,
        "rollback": {
            "available": summary["status"] in {"running", "failed", "success"},
            "command": "deploy system --rollback",
        },
    }


@router.get("/deployments/{deployment_id}/logs")
async def get_deployment_logs(deployment_id: str, errors_only: bool = False, limit: int = 100):
    """Get deployment logs (context-efficient)"""
    # Check if deployment exists
    summary = context_store.get_deployment_summary(deployment_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Get errors only if requested (progressive disclosure)
    if errors_only:
        errors = context_store.get_deployment_errors_only(deployment_id, limit=limit)
        return {"logs": errors, "errors_only": True}

    # Get timeline (condensed, not full logs)
    timeline = context_store.get_deployment_timeline(deployment_id)
    return {"logs": timeline, "condensed": True}


@router.post("/deployments/{deployment_id}/rollback")
async def rollback_deployment(deployment_id: str, request: DeploymentRollbackRequest):
    """Record or execute a rollback request for a deployment."""
    summary = context_store.get_deployment_summary(deployment_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Rollback confirmation is required")

    safe_command = request.command.strip() or "deploy system --rollback"
    if safe_command != "deploy system --rollback":
        raise HTTPException(status_code=400, detail="Unsupported rollback command")

    quoted_command = shlex.join(safe_command.split())
    context_store.add_event(
        deployment_id=deployment_id,
        event_type=DeploymentEventType.ROLLBACK,
        message=request.reason,
        progress=summary.get("progress") or 0,
        metadata={
            "execute": request.execute,
            "command": quoted_command,
            "status_before": summary.get("status"),
        },
    )

    if not request.execute:
        event_dict = {
            "deployment_id": deployment_id,
            "event_type": DeploymentEventType.ROLLBACK,
            "message": request.reason,
            "progress": summary.get("progress") or 0,
            "metadata": {
                "execute": False,
                "command": quoted_command,
                "planned": True,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        await broadcast_deployment_event(event_dict)
        return {
            "status": "planned",
            "deployment_id": deployment_id,
            "rollback_command": quoted_command,
            "executed": False,
        }

    result = await _run_rollback_command(quoted_command)
    success = result.returncode == 0
    output = (result.stdout + result.stderr).strip()
    if len(output) > 4000:
        output = "...[truncated]...\n" + output[-4000:]

    event_dict = {
        "deployment_id": deployment_id,
        "event_type": DeploymentEventType.ROLLBACK,
        "message": request.reason,
        "progress": summary.get("progress") or 0,
        "metadata": {
            "execute": True,
            "command": quoted_command,
            "success": success,
            "returncode": result.returncode,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
    await broadcast_deployment_event(event_dict)

    return {
        "status": "success" if success else "failed",
        "deployment_id": deployment_id,
        "rollback_command": quoted_command,
        "executed": True,
        "returncode": result.returncode,
        "output": output,
    }
