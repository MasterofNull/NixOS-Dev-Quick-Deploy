"""
Deployment tracking and history API routes
Provides real-time deployment progress and historical deployment data
Integrated with context-aware storage (SQLite + FTS5)
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import json
import asyncio
from pathlib import Path

from api.services.context_store import get_context_store

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket connections for real-time updates
deployment_connections: List[WebSocket] = []
deployment_lock = asyncio.Lock()

# Get context store singleton
context_store = get_context_store()

# Deployment event types (for WebSocket broadcasting)
class DeploymentEventType:
    STARTED = "started"
    PROGRESS = "progress"
    LOG = "log"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"


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
    progress: int,
    message: str,
    log: Optional[str] = None
):
    """Update deployment progress"""
    # Store event in context store
    event_type = DeploymentEventType.PROGRESS if not log else DeploymentEventType.LOG
    metadata = {"log": log} if log else None

    context_store.add_event(
        deployment_id=deployment_id,
        event_type=event_type,
        message=message,
        progress=progress,
        metadata=metadata
    )

    # Broadcast to WebSocket clients
    event_dict = {
        "deployment_id": deployment_id,
        "event_type": event_type,
        "message": message,
        "progress": progress,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow().isoformat()
    }
    await broadcast_deployment_event(event_dict)

    return {"status": "updated", "progress": progress}


@router.post("/deployments/{deployment_id}/complete")
async def complete_deployment(
    deployment_id: str,
    success: bool = True,
    message: Optional[str] = None
):
    """Mark deployment as complete"""
    # Complete in context store
    context_store.complete_deployment(
        deployment_id=deployment_id,
        success=success,
        message=message
    )

    # Broadcast to WebSocket clients
    event_type = DeploymentEventType.SUCCESS if success else DeploymentEventType.FAILED
    event_dict = {
        "deployment_id": deployment_id,
        "event_type": event_type,
        "message": message or f"Deployment {'completed successfully' if success else 'failed'}",
        "progress": 100 if success else 0,
        "metadata": {"success": success},
        "timestamp": datetime.utcnow().isoformat()
    }
    await broadcast_deployment_event(event_dict)

    status = "success" if success else "failed"
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
async def get_deployment_history(limit: int = 20, offset: int = 0):
    """Get deployment history"""
    deployments = context_store.get_recent_deployments(limit=limit)

    # Apply offset
    if offset > 0 and offset < len(deployments):
        deployments = deployments[offset:]

    return {
        "deployments": deployments,
        "total": len(deployments),
        "limit": limit,
        "offset": offset
    }


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
        "timeline": timeline
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


@router.get("/deployments/search")
async def search_deployments(query: str, limit: int = 20, offset: int = 0):
    """Search deployment logs using FTS5 with BM25 ranking"""
    results = context_store.search_deployments(query, limit=limit, offset=offset)

    return {
        "results": results,
        "query": query,
        "count": len(results),
        "limit": limit,
        "offset": offset
    }
