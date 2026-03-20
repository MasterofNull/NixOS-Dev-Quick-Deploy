"""
AI Service Health Monitoring API Routes
Provides real-time health status and metrics for all AI stack services.
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List, Optional
import logging
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api.services.ai_service_health import get_health_monitor
from api.config.service_endpoints import HYBRID_URL

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket connections for real-time health updates
health_connections: List[WebSocket] = []
health_lock = asyncio.Lock()

# Background task for broadcasting health updates
_broadcast_task: Optional[asyncio.Task] = None


def _load_hybrid_api_key() -> str:
    direct = os.getenv("HYBRID_API_KEY", "").strip()
    if direct:
        return direct
    key_file = os.getenv("HYBRID_API_KEY_FILE", "").strip()
    if not key_file:
        return ""
    try:
        return Path(key_file).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning("Hybrid API key file not found: %s", key_file)
        return ""
    except OSError as exc:
        logger.warning("Failed reading hybrid API key file %s: %s", key_file, exc)
        return ""


def _hybrid_request(path: str, *, method: str = "GET", payload: Optional[dict] = None, query: Optional[dict] = None) -> dict:
    base = HYBRID_URL.rstrip("/")
    url = f"{base}{path}"
    if query:
        encoded = urlencode({key: value for key, value in query.items() if value not in {None, ""}})
        if encoded:
            url = f"{url}?{encoded}"
    headers = {"Accept": "application/json"}
    api_key = _load_hybrid_api_key()
    if api_key:
        headers["X-API-Key"] = api_key
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method=method.upper(), headers=headers)
    with urlopen(request, timeout=10.0) as response:
        return json.loads(response.read().decode("utf-8"))


# ============================================================================
# HTTP API Endpoints
# ============================================================================

@router.get("/services/all")
async def get_all_services_health():
    """Get health status for all AI services."""
    try:
        monitor = await get_health_monitor()
        health = await monitor.check_all_services()
        return health
    except Exception as e:
        logger.error(f"Failed to get all services health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services/{service_id}")
async def get_service_health(service_id: str):
    """Get health status for a specific service."""
    try:
        monitor = await get_health_monitor()
        health = await monitor.get_service_metrics(service_id)

        if health is None:
            raise HTTPException(status_code=404, detail=f"Service {service_id} not found")

        return health
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get service health for {service_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories/{category}")
async def get_category_health(category: str):
    """Get aggregated health for services in a category."""
    try:
        monitor = await get_health_monitor()
        health = await monitor.get_category_health(category)

        if "error" in health:
            raise HTTPException(status_code=404, detail=health["error"])

        return health
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get category health for {category}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def list_categories():
    """List all service categories."""
    from api.services.ai_service_health import AI_SERVICES

    categories = set(config["category"] for config in AI_SERVICES.values())
    return {
        "categories": sorted(categories),
        "count": len(categories),
    }


@router.get("/aggregate")
async def get_aggregate_health():
    """Get high-level aggregate health status."""
    try:
        monitor = await get_health_monitor()
        health = await monitor.check_all_services()
        return health["aggregate"]
    except Exception as e:
        logger.error(f"Failed to get aggregate health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WebSocket Endpoint for Real-Time Health Updates
# ============================================================================

@router.websocket("/ws")
async def health_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time health monitoring."""
    await websocket.accept()

    async with health_lock:
        health_connections.append(websocket)

    logger.info(f"Health monitoring WebSocket client connected. Active: {len(health_connections)}")

    # Start broadcast task if not running
    global _broadcast_task
    if _broadcast_task is None or _broadcast_task.done():
        _broadcast_task = asyncio.create_task(_health_broadcast_loop())

    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong"})
            elif data == "get_health":
                # Send current health status
                monitor = await get_health_monitor()
                health = await monitor.check_all_services()
                await websocket.send_json({
                    "type": "health_update",
                    "data": health,
                })

    except WebSocketDisconnect:
        async with health_lock:
            if websocket in health_connections:
                health_connections.remove(websocket)
        logger.info(f"Health monitoring WebSocket client disconnected. Active: {len(health_connections)}")

    except Exception as e:
        logger.error(f"Health monitoring WebSocket error: {e}")
        async with health_lock:
            if websocket in health_connections:
                health_connections.remove(websocket)


async def _health_broadcast_loop():
    """Background task to broadcast health updates every 10 seconds."""
    while True:
        try:
            # Wait for 10 seconds
            await asyncio.sleep(10)

            # Only broadcast if there are active connections
            if not health_connections:
                continue

            # Get current health
            monitor = await get_health_monitor()
            health = await monitor.check_all_services()

            # Broadcast to all connected clients
            message = {
                "type": "health_update",
                "data": health,
            }

            disconnected = []
            async with health_lock:
                for connection in health_connections:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.error(f"Failed to send health update to client: {e}")
                        disconnected.append(connection)

                # Remove disconnected clients
                for conn in disconnected:
                    if conn in health_connections:
                        health_connections.remove(conn)

        except asyncio.CancelledError:
            logger.info("Health broadcast loop cancelled")
            break
        except Exception as e:
            logger.error(f"Error in health broadcast loop: {e}")
            await asyncio.sleep(5)  # Wait before retrying on error


# ============================================================================
# Alert Endpoints (Placeholder for Phase 2.2.4)
# ============================================================================

@router.get("/alerts")
async def get_alerts():
    """Get current system alerts."""
    try:
        return await asyncio.to_thread(_hybrid_request, "/alerts")
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch alerts: {e}")


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    try:
        return await asyncio.to_thread(_hybrid_request, f"/alerts/{alert_id}/acknowledge", method="POST", payload={})
    except Exception as e:
        logger.error(f"Failed to acknowledge alert %s: %s", alert_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to acknowledge alert: {e}")


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Resolve an alert."""
    try:
        return await asyncio.to_thread(_hybrid_request, f"/alerts/{alert_id}/resolve", method="POST", payload={})
    except Exception as e:
        logger.error(f"Failed to resolve alert %s: %s", alert_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to resolve alert: {e}")
