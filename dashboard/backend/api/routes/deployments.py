"""
Deployment tracking and history API routes
Provides real-time deployment progress and historical deployment data
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import json
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory deployment tracking (Phase 3 will move to persistent storage)
active_deployments = {}
deployment_history = []
deployment_connections: List[WebSocket] = []
deployment_lock = asyncio.Lock()

# Deployment event types
class DeploymentEventType:
    STARTED = "started"
    PROGRESS = "progress"
    LOG = "log"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"


# ============================================================================
# Deployment Tracking Models
# ============================================================================

class DeploymentEvent:
    def __init__(self, deployment_id: str, event_type: str, message: str,
                 progress: Optional[int] = None, metadata: Optional[dict] = None):
        self.deployment_id = deployment_id
        self.event_type = event_type
        self.message = message
        self.progress = progress or 0
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self):
        return {
            "deployment_id": self.deployment_id,
            "event_type": self.event_type,
            "message": self.message,
            "progress": self.progress,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


class Deployment:
    def __init__(self, deployment_id: str, command: str, user: str):
        self.deployment_id = deployment_id
        self.command = command
        self.user = user
        self.status = "running"
        self.started_at = datetime.utcnow()
        self.completed_at = None
        self.progress = 0
        self.logs = []
        self.events = []

    def to_dict(self):
        return {
            "deployment_id": self.deployment_id,
            "command": self.command,
            "user": self.user,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "duration": (datetime.utcnow() - self.started_at).total_seconds() if self.status == "running" else (self.completed_at - self.started_at).total_seconds() if self.completed_at else 0,
            "events_count": len(self.events)
        }


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
                # Send current active deployments
                active = [d.to_dict() for d in active_deployments.values()]
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


async def broadcast_deployment_event(event: DeploymentEvent):
    """Broadcast deployment event to all connected WebSocket clients"""
    if not deployment_connections:
        return

    message = {
        "type": "deployment_event",
        "event": event.to_dict()
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
    deployment = Deployment(deployment_id, command, user)
    active_deployments[deployment_id] = deployment

    event = DeploymentEvent(
        deployment_id=deployment_id,
        event_type=DeploymentEventType.STARTED,
        message=f"Deployment started: {command}",
        progress=0,
        metadata={"command": command, "user": user}
    )

    deployment.events.append(event)
    await broadcast_deployment_event(event)

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
    if deployment_id not in active_deployments:
        raise HTTPException(status_code=404, detail="Deployment not found")

    deployment = active_deployments[deployment_id]
    deployment.progress = progress

    if log:
        deployment.logs.append({"timestamp": datetime.utcnow().isoformat(), "message": log})

    event = DeploymentEvent(
        deployment_id=deployment_id,
        event_type=DeploymentEventType.PROGRESS if not log else DeploymentEventType.LOG,
        message=message,
        progress=progress,
        metadata={"log": log} if log else {}
    )

    deployment.events.append(event)
    await broadcast_deployment_event(event)

    return {"status": "updated", "progress": progress}


@router.post("/deployments/{deployment_id}/complete")
async def complete_deployment(
    deployment_id: str,
    success: bool = True,
    message: Optional[str] = None
):
    """Mark deployment as complete"""
    if deployment_id not in active_deployments:
        raise HTTPException(status_code=404, detail="Deployment not found")

    deployment = active_deployments[deployment_id]
    deployment.status = "success" if success else "failed"
    deployment.completed_at = datetime.utcnow()
    deployment.progress = 100 if success else deployment.progress

    event = DeploymentEvent(
        deployment_id=deployment_id,
        event_type=DeploymentEventType.SUCCESS if success else DeploymentEventType.FAILED,
        message=message or f"Deployment {'completed successfully' if success else 'failed'}",
        progress=deployment.progress,
        metadata={"success": success}
    )

    deployment.events.append(event)
    await broadcast_deployment_event(event)

    # Move to history
    deployment_history.append(deployment.to_dict())
    del active_deployments[deployment_id]

    # Keep only last 100 deployments in history
    if len(deployment_history) > 100:
        deployment_history.pop(0)

    logger.info(f"Deployment {deployment_id} completed: {deployment.status}")
    return {"status": deployment.status}


@router.get("/deployments/active")
async def get_active_deployments():
    """Get all currently active deployments"""
    return {
        "deployments": [d.to_dict() for d in active_deployments.values()],
        "count": len(active_deployments)
    }


@router.get("/deployments/history")
async def get_deployment_history(limit: int = 20, offset: int = 0):
    """Get deployment history"""
    total = len(deployment_history)
    start = max(0, total - offset - limit)
    end = max(0, total - offset)

    # Return most recent first
    items = list(reversed(deployment_history[start:end]))

    return {
        "deployments": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/deployments/{deployment_id}")
async def get_deployment(deployment_id: str):
    """Get deployment details"""
    # Check active deployments
    if deployment_id in active_deployments:
        deployment = active_deployments[deployment_id]
        return {
            **deployment.to_dict(),
            "logs": deployment.logs,
            "events": [e.to_dict() for e in deployment.events]
        }

    # Check history
    for d in deployment_history:
        if d["deployment_id"] == deployment_id:
            return d

    raise HTTPException(status_code=404, detail="Deployment not found")


@router.get("/deployments/{deployment_id}/logs")
async def get_deployment_logs(deployment_id: str):
    """Get deployment logs"""
    if deployment_id in active_deployments:
        deployment = active_deployments[deployment_id]
        return {"logs": deployment.logs}

    raise HTTPException(status_code=404, detail="Deployment not found or completed")
