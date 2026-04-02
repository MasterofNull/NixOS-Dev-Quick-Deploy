"""
Deployment tracking and history API routes
Provides real-time deployment progress and historical deployment data
Integrated with context-aware storage (SQLite + FTS5)
"""

import importlib.util
from dataclasses import asdict
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import asyncio
import os
import shlex
import subprocess
from pathlib import Path

from api.services.context_store import get_context_store
from api.services.ai_insights import get_insights_service

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket connections for real-time updates
deployment_connections: List[WebSocket] = []
deployment_lock = asyncio.Lock()
runtime_deployment_lock = asyncio.Lock()
runtime_deployment_tasks: Dict[str, asyncio.Task[Any]] = {}
pending_deployment_approvals: Dict[str, Dict[str, Any]] = {}
_AUTO_DEPLOYER_MODULE: Any | None = None

# Get context store singleton
context_store = get_context_store()
insights_service = get_insights_service()
REPO_ROOT = Path(__file__).resolve().parents[4]
BASH_BIN = os.getenv("BASH_BIN", "bash")


async def _attach_operator_insight(guidance: dict) -> dict:
    if not isinstance(guidance, dict):
        return guidance
    target = str(guidance.get("insight_target") or "full_report")
    try:
        digest = await insights_service.get_operator_insight_digest(target)
    except Exception as exc:
        logger.warning("Failed to load operator insight digest for %s: %s", target, exc)
        digest = {
            "target": target,
            "title": "Insight unavailable",
            "status": "unavailable",
            "summary": str(exc),
        }
    guidance = {**guidance, "insight_digest": digest}
    return guidance

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


class DeploymentExecuteRequest(BaseModel):
    """Safe runtime execution request for the repo-native auto-deployer."""
    deployment_id: Optional[str] = None
    strategy: str = Field(default="blue_green", pattern="^(blue_green|canary|rolling|immediate)$")
    dry_run: bool = True
    require_approval: bool = False
    confirm: bool = False
    user: str = "system"
    auto_rollback: bool = True
    canary_percentage: int = Field(default=10, ge=1, le=100)
    rollback_on_error_rate: float = Field(default=0.05, gt=0.0, le=1.0)
    validation_timeout_seconds: int = Field(default=60, ge=10, le=1800)
    verification_timeout_seconds: int = Field(default=120, ge=10, le=3600)
    approval_timeout_seconds: int = Field(default=300, ge=10, le=3600)


class DeploymentApprovalRequest(BaseModel):
    """Approve or reject a pending runtime deployment."""
    decision: str = Field(..., pattern="^(approve|reject)$")
    reviewer: str = "operator"
    reason: str = "Operator decision recorded from dashboard"


def _load_auto_deployer_module():
    """Load the repo-native auto-deployer from the checkout path."""
    global _AUTO_DEPLOYER_MODULE
    if _AUTO_DEPLOYER_MODULE is not None:
        return _AUTO_DEPLOYER_MODULE

    module_path = REPO_ROOT / "ai-stack" / "deployment" / "auto_deployer.py"
    spec = importlib.util.spec_from_file_location("dashboard_auto_deployer", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load auto deployer module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _AUTO_DEPLOYER_MODULE = module
    return module


def _deployment_command_from_request(request: DeploymentExecuteRequest) -> str:
    parts = [f"auto-deployer --strategy {request.strategy}"]
    if request.dry_run:
        parts.append("--dry-run")
    if request.require_approval:
        parts.append("--require-approval")
    if request.auto_rollback:
        parts.append("--auto-rollback")
    if request.strategy == "canary":
        parts.append(f"--canary-percentage {request.canary_percentage}")
    parts.append(f"--rollback-on-error-rate {request.rollback_on_error_rate:.3f}")
    return " ".join(parts)


def _serialize_runtime_request(request: DeploymentExecuteRequest) -> Dict[str, Any]:
    return {
        "strategy": request.strategy,
        "dry_run": request.dry_run,
        "require_approval": request.require_approval,
        "auto_rollback": request.auto_rollback,
        "canary_percentage": request.canary_percentage,
        "rollback_on_error_rate": request.rollback_on_error_rate,
        "validation_timeout_seconds": request.validation_timeout_seconds,
        "verification_timeout_seconds": request.verification_timeout_seconds,
        "approval_timeout_seconds": request.approval_timeout_seconds,
        "user": request.user,
    }


def _serialize_deployment_result(result: Any) -> Dict[str, Any]:
    payload = asdict(result)
    payload["status"] = result.status.value
    payload["strategy"] = result.strategy.value
    payload["started_at"] = result.started_at.isoformat()
    payload["completed_at"] = result.completed_at.isoformat() if result.completed_at else None
    return payload


def _build_runtime_summary(summary: Dict[str, Any], timeline: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract operator-facing runtime deployment metadata from timeline events."""
    request_metadata: Dict[str, Any] = {}
    result_metadata: Dict[str, Any] = {}
    approval: Dict[str, Any] = {}

    for event in timeline:
        metadata = event.get("metadata") or {}
        if not isinstance(metadata, dict):
            continue
        event_type = str(event.get("event_type") or "")
        if event_type == "runtime_plan":
            request_metadata = metadata
        elif event_type == "runtime_result":
            result_metadata = metadata
        elif event_type in {"approval_requested", "approval_approved", "approval_rejected"}:
            approval = {
                "status": event_type.removeprefix("approval_"),
                "timestamp": event.get("timestamp"),
                "reviewer": metadata.get("reviewer"),
                "reason": event.get("message"),
            }

    result_payload = result_metadata if result_metadata else {}
    strategy = request_metadata.get("strategy") or result_payload.get("strategy")
    if not strategy and not approval:
        return None

    return {
        "strategy": strategy,
        "dry_run": request_metadata.get("dry_run"),
        "require_approval": request_metadata.get("require_approval"),
        "auto_rollback": request_metadata.get("auto_rollback"),
        "canary_percentage": request_metadata.get("canary_percentage"),
        "rollback_on_error_rate": request_metadata.get("rollback_on_error_rate"),
        "validation_timeout_seconds": request_metadata.get("validation_timeout_seconds"),
        "verification_timeout_seconds": request_metadata.get("verification_timeout_seconds"),
        "approval_timeout_seconds": request_metadata.get("approval_timeout_seconds"),
        "validation_passed": result_payload.get("validation_passed"),
        "deployment_succeeded": result_payload.get("deployment_succeeded"),
        "verification_passed": result_payload.get("verification_passed"),
        "rollback_performed": result_payload.get("rollback_performed"),
        "result_status": result_payload.get("status") or summary.get("status"),
        "metrics": result_payload.get("metrics") or {},
        "logs": result_payload.get("logs") or [],
        "approval": approval or None,
    }


async def _broadcast_runtime_status(
    deployment_id: str,
    event_type: str,
    message: str,
    *,
    progress: int,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    await broadcast_deployment_event(
        {
            "deployment_id": deployment_id,
            "event_type": event_type,
            "message": message,
            "progress": progress,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


async def _run_runtime_deployment(deployment_id: str, request: DeploymentExecuteRequest) -> None:
    """Execute the repo-native auto-deployer and reflect outcome into deployment history."""
    try:
        auto_deployer = _load_auto_deployer_module()
        config = auto_deployer.DeploymentConfig(
            strategy=auto_deployer.DeploymentStrategy(request.strategy),
            require_approval=False,
            approval_timeout_seconds=request.approval_timeout_seconds,
            validation_timeout_seconds=request.validation_timeout_seconds,
            verification_timeout_seconds=request.verification_timeout_seconds,
            auto_rollback=request.auto_rollback,
            rollback_on_error_rate=request.rollback_on_error_rate,
            canary_percentage=request.canary_percentage,
        )
        deployer = auto_deployer.AutoDeployer(config=config, dry_run=request.dry_run)

        context_store.update_deployment_status(deployment_id, "running", progress=5)
        context_store.add_event(
            deployment_id=deployment_id,
            event_type="runtime_execution",
            message=f"Runtime deployment executing via {request.strategy}",
            progress=5,
            metadata=_serialize_runtime_request(request),
        )
        await _broadcast_runtime_status(
            deployment_id,
            DeploymentEventType.PROGRESS,
            f"Executing {request.strategy} deployment",
            progress=5,
            metadata={"runtime_execution": True, **_serialize_runtime_request(request)},
        )

        result = await deployer.deploy(deployment_id=deployment_id, approval_callback=lambda: True)
        serialized = _serialize_deployment_result(result)
        success = serialized["status"] == "completed"
        final_status = "rolled_back" if serialized.get("rollback_performed") else ("success" if success else "failed")
        final_progress = 100 if success else 0

        context_store.add_event(
            deployment_id=deployment_id,
            event_type="runtime_result",
            message=serialized.get("error_message") or f"Runtime deployment finished with status {serialized['status']}",
            progress=final_progress,
            metadata=serialized,
        )
        if final_status == "success":
            context_store.complete_deployment(
                deployment_id=deployment_id,
                success=True,
                exit_code=0,
                message="Runtime deployment completed successfully",
            )
        else:
            context_store.update_deployment_status(
                deployment_id,
                final_status,
                progress=final_progress,
                exit_code=0 if serialized.get("rollback_performed") else 1,
                completed=True,
            )
            context_store.add_event(
                deployment_id=deployment_id,
                event_type=final_status,
                message=serialized.get("error_message") or f"Runtime deployment ended in {final_status}",
                progress=final_progress,
                metadata={"runtime_execution": True, "rollback_performed": serialized.get("rollback_performed", False)},
            )

        await _broadcast_runtime_status(
            deployment_id,
            DeploymentEventType.SUCCESS if final_status == "success" else DeploymentEventType.FAILED,
            serialized.get("error_message") or f"Runtime deployment {final_status}",
            progress=final_progress,
            metadata={"runtime_result": serialized, "final_status": final_status},
        )
    except Exception as exc:
        logger.exception("Runtime deployment %s failed: %s", deployment_id, exc)
        context_store.update_deployment_status(deployment_id, "failed", progress=0, exit_code=1, completed=True)
        context_store.add_event(
            deployment_id=deployment_id,
            event_type="runtime_error",
            message=f"Runtime deployment error: {exc}",
            progress=0,
            metadata={"runtime_execution": True},
        )
        await _broadcast_runtime_status(
            deployment_id,
            DeploymentEventType.FAILED,
            f"Runtime deployment error: {exc}",
            progress=0,
            metadata={"runtime_execution": True},
        )
    finally:
        async with runtime_deployment_lock:
            runtime_deployment_tasks.pop(deployment_id, None)


async def _start_runtime_deployment(deployment_id: str, request: DeploymentExecuteRequest) -> None:
    async with runtime_deployment_lock:
        task = asyncio.create_task(_run_runtime_deployment(deployment_id, request))
        runtime_deployment_tasks[deployment_id] = task


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


@router.post("/deployments/execute")
async def execute_deployment(request: DeploymentExecuteRequest):
    """Execute the repo-native deployment pipeline with safe defaults."""
    deployment_id = request.deployment_id or f"runtime-deploy-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    command = _deployment_command_from_request(request)

    async with runtime_deployment_lock:
        if deployment_id in runtime_deployment_tasks:
            raise HTTPException(status_code=409, detail="Deployment already executing")
        if deployment_id in pending_deployment_approvals:
            raise HTTPException(status_code=409, detail="Deployment is already pending approval")

    existing = context_store.get_deployment_summary(deployment_id)
    if existing:
        raise HTTPException(status_code=409, detail="Deployment ID already exists")

    if not request.dry_run and not request.confirm:
        raise HTTPException(status_code=400, detail="Live deployment requires explicit confirmation")

    context_store.start_deployment(deployment_id, command, request.user)
    context_store.add_event(
        deployment_id=deployment_id,
        event_type="runtime_plan",
        message="Runtime deployment request accepted",
        progress=0,
        metadata={"command": command, **_serialize_runtime_request(request)},
    )

    if request.require_approval:
        pending_deployment_approvals[deployment_id] = {
            "deployment_id": deployment_id,
            "command": command,
            "requested_at": datetime.utcnow().isoformat(),
            "request": _serialize_runtime_request(request),
        }
        context_store.update_deployment_status(deployment_id, "pending_approval", progress=0)
        context_store.add_event(
            deployment_id=deployment_id,
            event_type="approval_requested",
            message="Awaiting operator approval for runtime deployment",
            progress=0,
            metadata={"command": command, "require_approval": True},
        )
        await _broadcast_runtime_status(
            deployment_id,
            "approval_requested",
            "Awaiting operator approval",
            progress=0,
            metadata={"command": command},
        )
        return {
            "status": "pending_approval",
            "deployment_id": deployment_id,
            "command": command,
            "request": _serialize_runtime_request(request),
        }

    await _start_runtime_deployment(deployment_id, request)
    return {
        "status": "started",
        "deployment_id": deployment_id,
        "command": command,
        "request": _serialize_runtime_request(request),
    }


@router.get("/deployments/approvals/pending")
async def get_pending_deployment_approvals():
    """List runtime deployments awaiting operator approval."""
    items = sorted(
        pending_deployment_approvals.values(),
        key=lambda item: str(item.get("requested_at") or ""),
        reverse=True,
    )
    return {"deployments": items, "count": len(items)}


@router.post("/deployments/{deployment_id}/approval")
async def review_deployment_approval(deployment_id: str, request: DeploymentApprovalRequest):
    """Approve or reject a pending runtime deployment execution."""
    pending = pending_deployment_approvals.get(deployment_id)
    if not pending:
        raise HTTPException(status_code=404, detail="Pending deployment approval not found")

    runtime_request = DeploymentExecuteRequest(
        deployment_id=deployment_id,
        **{k: v for k, v in (pending.get("request") or {}).items() if k != "user"},
        user=str((pending.get("request") or {}).get("user") or "system"),
        confirm=True,
    )

    if request.decision == "reject":
        pending_deployment_approvals.pop(deployment_id, None)
        context_store.update_deployment_status(deployment_id, "rejected", progress=0, exit_code=1, completed=True)
        context_store.add_event(
            deployment_id=deployment_id,
            event_type="approval_rejected",
            message=request.reason,
            progress=0,
            metadata={"reviewer": request.reviewer},
        )
        await _broadcast_runtime_status(
            deployment_id,
            "approval_rejected",
            request.reason,
            progress=0,
            metadata={"reviewer": request.reviewer},
        )
        return {"status": "rejected", "deployment_id": deployment_id}

    pending_deployment_approvals.pop(deployment_id, None)
    context_store.update_deployment_status(deployment_id, "approved", progress=0)
    context_store.add_event(
        deployment_id=deployment_id,
        event_type="approval_approved",
        message=request.reason,
        progress=0,
        metadata={"reviewer": request.reviewer},
    )
    await _broadcast_runtime_status(
        deployment_id,
        "approval_approved",
        request.reason,
        progress=0,
        metadata={"reviewer": request.reviewer},
    )
    await _start_runtime_deployment(deployment_id, runtime_request)
    return {"status": "approved", "deployment_id": deployment_id}


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
        except Exception as exc:
            semantic_sync = {"status": "error", "synced": 0, "failed": [str(exc)]}

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

    operator_guidance = await _attach_operator_insight(
        context_store.build_operator_guidance(query, query_analysis, explained_results)
    )
    return {
        "results": explained_results,
        "query": query,
        "mode": normalized_mode,
        "effective_mode": effective_mode,
        "query_analysis": query_analysis,
        "operator_guidance": operator_guidance,
        "count": len(explained_results),
        "limit": limit,
        "offset": offset,
        "semantic_sync": semantic_sync,
    }


@router.get("/deployments/search/status")
async def get_deployment_search_status(recent_limit: int = 8):
    """Get operator-facing status for deployment semantic search coverage."""
    return await asyncio.to_thread(context_store.get_deployment_search_status, recent_limit)


@router.get("/deployments/search/context")
async def search_deployment_context(query: str, limit: int = 12, mode: str = "natural"):
    """Search deployment-related context across deployments, config, and code."""
    normalized_mode = (mode or "natural").strip().lower()
    if normalized_mode not in {"keyword", "semantic", "hybrid", "auto", "natural"}:
        raise HTTPException(status_code=400, detail="mode must be keyword, semantic, hybrid, auto, or natural")

    semantic_sync = None
    query_analysis = context_store.analyze_deployment_query(query)
    effective_mode = query_analysis["recommended_mode"] if normalized_mode in {"auto", "natural"} else normalized_mode
    if effective_mode in {"semantic", "hybrid"}:
        try:
            semantic_sync = await asyncio.wait_for(
                asyncio.to_thread(context_store.sync_recent_deployments, 1),
                timeout=1.5,
            )
        except asyncio.TimeoutError:
            semantic_sync = {"status": "timed_out", "synced": 0, "failed": []}
        except Exception as exc:
            semantic_sync = {"status": "error", "synced": 0, "failed": [str(exc)]}

    result = await asyncio.to_thread(context_store.search_deployment_context, query, limit, normalized_mode)
    operator_guidance = await _attach_operator_insight(result.get("operator_guidance") or {})
    return {
        **result,
        "operator_guidance": operator_guidance,
        "query": query,
        "mode": normalized_mode,
        "semantic_sync": semantic_sync,
        "count": len(result.get("results") or []),
        "limit": limit,
    }


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
        "runtime_summary": _build_runtime_summary(summary, timeline),
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


# ============================================================================
# Phase 3.2: Service-Level Knowledge Graph Endpoints
# ============================================================================

@router.get("/deployments/{deployment_id}/services")
async def get_deployment_services(deployment_id: str):
    """Get service states for a deployment"""
    summary = context_store.get_deployment_summary(deployment_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Deployment not found")

    services = context_store.query_services_by_deployment(deployment_id)
    return {
        "deployment_id": deployment_id,
        "services": services,
        "count": len(services),
    }


@router.get("/deployments/{deployment_id}/configs")
async def get_deployment_configs(deployment_id: str):
    """Get configuration changes for a deployment"""
    summary = context_store.get_deployment_summary(deployment_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Deployment not found")

    configs = context_store.query_configs_by_deployment(deployment_id)
    return {
        "deployment_id": deployment_id,
        "configs": configs,
        "count": len(configs),
    }


@router.get("/deployments/{deployment_id}/causality")
async def get_deployment_causality(deployment_id: str):
    """Get causality relationships for a deployment"""
    summary = context_store.get_deployment_summary(deployment_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Deployment not found")

    root_cause_group = context_store.find_root_cause_group(deployment_id)
    return {
        "deployment_id": deployment_id,
        "root_cause_group": root_cause_group,
    }


# ============================================================================
# Phase 3.2: Service Health Timeline Endpoints
# ============================================================================

@router.get("/services/{service_name}/health-timeline")
async def get_service_health_timeline(service_name: str, limit: int = 100):
    """Get health timeline for a specific service across all deployments"""
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")

    timeline = context_store.query_service_health_timeline(service_name, limit=limit)
    return {
        "service_name": service_name,
        "timeline": timeline,
        "count": len(timeline),
        "limit": limit,
    }


@router.get("/configs/{config_key}/impact-timeline")
async def get_config_impact_timeline(config_key: str, limit: int = 100):
    """Get impact timeline of a config key across all deployments"""
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")

    timeline = context_store.query_config_impact_timeline(config_key, limit=limit)
    return {
        "config_key": config_key,
        "timeline": timeline,
        "count": len(timeline),
        "limit": limit,
    }
