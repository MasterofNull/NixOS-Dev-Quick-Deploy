#!/usr/bin/env python3
"""
NixOS System Dashboard - FastAPI Backend
Main application entry point with WebSocket support
"""

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
import logging
import os
from typing import Dict, List
from pathlib import Path

from api.routes import metrics, services, containers, config, websockets, actions, aistack, adk, audit, deployments, health, insights, workflows, collaboration, firewall
from api.services.metrics_collector import MetricsCollector
from api.services.ai_insights import get_insights_service
from api.services.runtime_controls import get_dashboard_rate_limiter, get_operator_audit_log

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
METRICS_BROADCAST_INTERVAL_SECONDS = float(os.getenv("DASHBOARD_METRICS_INTERVAL_SECONDS", "1.0"))
rate_limiter = get_dashboard_rate_limiter()
operator_audit = get_operator_audit_log()


def _default_content_security_policy() -> str:
    """Default CSP for the single-origin dashboard surface."""
    return "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "img-src 'self' data:",
            "font-src 'self' data:",
            "connect-src 'self' ws: wss:",
            "script-src 'self' 'unsafe-inline'",
            "style-src 'self' 'unsafe-inline'",
        ]
    )


def _build_security_headers() -> Dict[str, str]:
    """Security headers for HTTP routes served by the dashboard API."""
    headers = {
        "Content-Security-Policy": os.getenv("DASHBOARD_CSP", _default_content_security_policy()),
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": os.getenv("DASHBOARD_REFERRER_POLICY", "no-referrer"),
        "Permissions-Policy": os.getenv(
            "DASHBOARD_PERMISSIONS_POLICY",
            "camera=(), microphone=(), geolocation=()",
        ),
        "Cross-Origin-Opener-Policy": os.getenv("DASHBOARD_COOP", "same-origin"),
        "Cross-Origin-Resource-Policy": os.getenv("DASHBOARD_CORP", "same-origin"),
    }
    if os.getenv("DASHBOARD_ENABLE_HSTS", "false").strip().lower() in {"1", "true", "yes", "on"}:
        headers["Strict-Transport-Security"] = os.getenv(
            "DASHBOARD_HSTS_POLICY",
            "max-age=31536000; includeSubDomains",
        )
    return headers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global metrics_collector
    
    # Startup
    logger.info("Starting NixOS Dashboard API...")
    metrics_collector = MetricsCollector()
    insights_service = get_insights_service()
    
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
    await insights_service.shutdown()
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
service_host = os.getenv("SERVICE_HOST", "localhost")
cors_env = os.getenv("DASHBOARD_CORS_ORIGINS", "")
if cors_env:
    cors_origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
else:
    cors_hosts = [service_host, "127.0.0.1"]
    cors_ports = [8888, 8890, 5173]
    cors_origins = [f"http://{host}:{port}" for host in cors_hosts for port in cors_ports]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Apply baseline security headers to dashboard HTTP responses."""
    response = await call_next(request)
    for name, value in _build_security_headers().items():
        response.headers.setdefault(name, value)
    return response


@app.middleware("http")
async def runtime_controls_middleware(request: Request, call_next):
    """Apply rate limiting and audit logging to dashboard API traffic."""
    client_ip = getattr(request.client, "host", None) or "unknown"
    if rate_limiter.enabled():
        decision = rate_limiter.check(client_ip, request.url.path, request.method)
        if not decision["allowed"]:
            response = JSONResponse(
                {
                    "detail": "rate limit exceeded",
                    "category": decision["category"],
                    "retry_after_seconds": decision["retry_after"],
                },
                status_code=429,
            )
            response.headers["Retry-After"] = str(decision["retry_after"])
            response.headers["X-RateLimit-Limit"] = str(decision["limit"])
            response.headers["X-RateLimit-Remaining"] = str(decision["remaining"])
            response.headers["X-RateLimit-Category"] = decision["category"]
            operator_audit.append(
                path=request.url.path,
                method=request.method,
                status_code=429,
                client_ip=client_ip,
                user_agent=request.headers.get("user-agent", ""),
                query_keys=list(request.query_params.keys()),
                category=decision["category"],
            )
            return response
    else:
        decision = {"category": "disabled", "limit": 0, "remaining": 0}

    response = await call_next(request)
    response.headers.setdefault("X-RateLimit-Category", str(decision["category"]))
    if decision["limit"]:
        response.headers.setdefault("X-RateLimit-Limit", str(decision["limit"]))
        response.headers.setdefault("X-RateLimit-Remaining", str(decision["remaining"]))
    operator_audit.append(
        path=request.url.path,
        method=request.method,
        status_code=response.status_code,
        client_ip=client_ip,
        user_agent=request.headers.get("user-agent", ""),
        query_keys=list(request.query_params.keys()),
        category=str(decision["category"]),
    )
    return response

# Include routers
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(services.router, prefix="/api/services", tags=["services"])
app.include_router(containers.router, prefix="/api/containers", tags=["containers"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(actions.router, prefix="/api/actions", tags=["actions"])
app.include_router(aistack.router, prefix="/api", tags=["aistack"])
# Preserve the legacy /api/aistack/* route family used by the static dashboard
# and older tests while the normalized /api/* endpoints remain primary.
app.include_router(aistack.router, prefix="/api/aistack", tags=["aistack-legacy"])
app.include_router(audit.router, prefix="/api", tags=["audit"])
app.include_router(deployments.router, prefix="/api", tags=["deployments"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(insights.router, prefix="/api/insights", tags=["insights"])
app.include_router(workflows.router, prefix="/api", tags=["workflows"])
app.include_router(collaboration.router, prefix="/api", tags=["collaboration"])
app.include_router(firewall.router, prefix="/api/firewall", tags=["firewall"])
app.include_router(adk.router, prefix="/api/adk", tags=["adk"])


# ── Direct routes — must be registered BEFORE the StaticFiles mount ──────────
# app.mount("/", StaticFiles(...)) is a catch-all that shadows any route
# registered after it.  Register /api/health and /metrics here so they are
# evaluated first when Starlette iterates the route list.

@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "websocket_connections": len(active_connections),
        "metrics_collector": "running"
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus exposition endpoint for dashboard-level probe gauges."""
    return aistack.render_prometheus_metrics()


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


# ── Frontend static file serving ────────────────────────────────────────────
# Serve Command Center dashboard (at repo root)
_COMMAND_CENTER_PATH = Path(__file__).parent.parent.parent.parent / "dashboard.html"
_ASSETS_PATH = Path(__file__).parent.parent.parent.parent / "assets"

# Mount assets directory for Chart.js and other static files
if _ASSETS_PATH.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_ASSETS_PATH)), name="assets")
    logger.info("Assets directory mounted from %s", _ASSETS_PATH)
else:
    logger.warning("Assets directory not found at %s", _ASSETS_PATH)

@app.get("/")
async def root():
    """Serve the Command Center dashboard"""
    if _COMMAND_CENTER_PATH.exists():
        return FileResponse(_COMMAND_CENTER_PATH)
    else:
        return JSONResponse(
            {"status": "online", "service": "NixOS Dashboard API", "version": "2.0.0",
             "note": "Command Center dashboard not found"},
            status_code=200,
        )


@app.get("/index.html")
async def root_index():
    """Serve the dashboard entrypoint for health checks and static clients."""
    if _COMMAND_CENTER_PATH.exists():
        return FileResponse(_COMMAND_CENTER_PATH)
    else:
        return JSONResponse(
            {"status": "online", "service": "NixOS Dashboard API", "version": "2.0.0",
             "note": "Command Center dashboard not found"},
            status_code=200,
        )


async def broadcast_metrics():
    """Background task to broadcast metrics to all connected clients"""
    while True:
        # Create snapshot under lock
        async with connections_lock:
            if not active_connections:
                await asyncio.sleep(METRICS_BROADCAST_INTERVAL_SECONDS)
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

        await asyncio.sleep(METRICS_BROADCAST_INTERVAL_SECONDS)


if __name__ == "__main__":
    import uvicorn
    bind_address = os.getenv("DASHBOARD_API_BIND_ADDRESS", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_API_PORT", "8889"))
    uvicorn.run(
        "main:app",
        host=bind_address,
        port=port,
        reload=True,
        log_level="info"
    )
