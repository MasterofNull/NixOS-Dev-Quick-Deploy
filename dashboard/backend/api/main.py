#!/usr/bin/env python3
"""
NixOS System Dashboard - FastAPI Backend
Main application entry point with WebSocket support
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import logging
from typing import List
from pathlib import Path

from api.routes import metrics, services, containers, config, websockets, actions, aistack
from api.services.metrics_collector import MetricsCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
active_connections: List[WebSocket] = []
connections_lock = asyncio.Lock()  # Protect against race conditions
metrics_collector: MetricsCollector = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global metrics_collector
    
    # Startup
    logger.info("Starting NixOS Dashboard API...")
    metrics_collector = MetricsCollector()
    
    # Start background metrics collection
    asyncio.create_task(broadcast_metrics())
    
    logger.info("Dashboard API started successfully")
    yield
    
    # Shutdown
    logger.info("Shutting down Dashboard API...")
    async with connections_lock:
        for connection in active_connections:
            await connection.close()
        active_connections.clear()
    # Close aistack HTTP session
    from api.routes import aistack
    await aistack.close_http_session()


# Create FastAPI app
app = FastAPI(
    title="NixOS System Dashboard API",
    description="Real-time system monitoring and control API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8888",  # HTML dashboard
        "http://localhost:8890",  # React dashboard
        "http://localhost:5173",  # Vite dev
        "http://127.0.0.1:8888",
        "http://127.0.0.1:8890",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(services.router, prefix="/api/services", tags=["services"])
app.include_router(containers.router, prefix="/api/containers", tags=["containers"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(actions.router, prefix="/api/actions", tags=["actions"])
app.include_router(aistack.router, prefix="/api", tags=["aistack"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "NixOS Dashboard API",
        "version": "2.0.0"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "websocket_connections": len(active_connections),
        "metrics_collector": "running"
    }


# WebSocket endpoint for real-time metrics
@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for streaming real-time metrics"""
    await websocket.accept()
    async with connections_lock:
        active_connections.append(websocket)

    try:
        while True:
            # Keep connection alive and wait for client messages
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        async with connections_lock:
            if websocket in active_connections:
                active_connections.remove(websocket)
        logger.info(f"Client disconnected. Active connections: {len(active_connections)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        async with connections_lock:
            if websocket in active_connections:
                active_connections.remove(websocket)


async def broadcast_metrics():
    """Background task to broadcast metrics to all connected clients"""
    while True:
        # Create snapshot under lock
        async with connections_lock:
            if not active_connections:
                await asyncio.sleep(2)
                continue
            connections_snapshot = list(active_connections)

        # Broadcast without holding lock
        try:
            metrics = await metrics_collector.get_current_metrics()

            # Broadcast to all connected clients
            disconnected = []
            for connection in connections_snapshot:
                try:
                    await connection.send_json({
                        "type": "metrics_update",
                        "data": metrics
                    })
                except Exception as e:
                    logger.error(f"Error sending to client: {e}")
                    disconnected.append(connection)

            # Remove disconnected clients under lock
            if disconnected:
                async with connections_lock:
                    for conn in disconnected:
                        if conn in active_connections:
                            active_connections.remove(conn)

        except Exception as e:
            logger.error(f"Error broadcasting metrics: {e}")

        # Update every 2 seconds
        await asyncio.sleep(2)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8889,
        reload=True,
        log_level="info"
    )