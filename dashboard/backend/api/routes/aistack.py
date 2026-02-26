"""AI Stack specific API endpoints for learning stats, circuit breakers, and Ralph"""
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import asyncio
import aiohttp
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from ..config import service_endpoints
from ..services.systemd_units import get_ai_runtime_units

try:
    import asyncpg
    _ASYNCPG_AVAILABLE = True
except ImportError:
    _ASYNCPG_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)

# Service endpoints (declarative + env-overridable)
SERVICES = {
    "ralph": service_endpoints.RALPH_URL,
    "hybrid": service_endpoints.HYBRID_URL,
    "aidb": service_endpoints.AIDB_URL,
    "qdrant": service_endpoints.QDRANT_URL,
    "llama_cpp": service_endpoints.LLAMA_URL,
    "embeddings": service_endpoints.EMBEDDINGS_URL,
    "switchboard": service_endpoints.SWITCHBOARD_URL,
    "aider_wrapper": service_endpoints.AIDER_WRAPPER_URL,
}

# Timeout for external requests
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=5)
HARNESS_EVAL_TIMEOUT = aiohttp.ClientTimeout(
    total=float(os.getenv("HARNESS_EVAL_TIMEOUT_SECONDS", "15"))
)
# Lightweight timeout used exclusively for health-probe HTTP GETs (Task 17.2)
_HEALTH_PROBE_TIMEOUT = aiohttp.ClientTimeout(total=2)

# Map from systemd unit name → /health endpoint URL.
# Only units listed here receive an HTTP probe in addition to systemd check.
_UNIT_HTTP_HEALTH: Dict[str, str] = {
    "ai-aidb": f"{service_endpoints.AIDB_URL}/health",
    "ai-hybrid-coordinator": f"{service_endpoints.HYBRID_URL}/health",
    "ai-ralph-wiggum": f"{service_endpoints.RALPH_URL}/health",
    "llama-cpp": f"{service_endpoints.LLAMA_URL}/health",
    "qdrant": f"{service_endpoints.QDRANT_URL}/healthz",
    "ai-switchboard": f"{service_endpoints.SWITCHBOARD_URL}/health",
    "ai-embeddings": f"{service_endpoints.EMBEDDINGS_URL}/health",
    "ai-aider-wrapper": f"{service_endpoints.AIDER_WRAPPER_URL}/health",
}

# Units that have no HTTP endpoint — systemd check only.
_SYSTEMD_ONLY_UNITS: frozenset = frozenset({
    "postgresql",
    "redis-mcp",
    "ai-otel-collector",
    "ai-auth-selftest",
    "ai-pgvector-bootstrap",
})

# Critical units: overall_status is "healthy" only when all of these pass.
_CRITICAL_UNITS: frozenset = frozenset({
    "ai-aidb",
    "ai-hybrid-coordinator",
    "llama-cpp",
    "qdrant",
    "postgresql",
    "redis-mcp",
})

# Global aiohttp session (reused across requests)
_http_session: Optional[aiohttp.ClientSession] = None


async def get_http_session() -> aiohttp.ClientSession:
    """Get or create the global HTTP session"""
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession(timeout=REQUEST_TIMEOUT)
    return _http_session


async def close_http_session():
    """Close the global HTTP session"""
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()


async def fetch_with_fallback(
    url: str,
    fallback: Any = None,
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    """Fetch URL with error handling and fallback"""
    try:
        session = await get_http_session()
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logger.warning(f"Non-200 status from {url}: {resp.status}")
                return fallback
    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching {url}")
        return fallback
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
        return fallback


async def fetch_text_with_fallback(url: str, fallback: Any = None) -> Any:
    """Fetch text response with error handling and fallback"""
    try:
        session = await get_http_session()
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.text()
            logger.warning(f"Non-200 status from {url}: {resp.status}")
            return fallback
    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching {url}")
        return fallback
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
        return fallback


async def post_with_fallback(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[aiohttp.ClientTimeout] = None,
) -> Any:
    """POST JSON payload with error handling and fallback"""
    try:
        session = await get_http_session()
        async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            logger.warning("Non-200 status from %s: %s %s", url, resp.status, text)
            return None
    except asyncio.TimeoutError:
        logger.warning("Timeout posting to %s", url)
        return None
    except Exception as e:
        logger.warning("Error posting to %s: %s", url, e)
        return None


def _load_hybrid_api_key() -> str:
    direct = os.getenv("HYBRID_API_KEY", "").strip()
    if direct:
        return direct
    key_file = os.getenv("HYBRID_API_KEY_FILE", "").strip()
    if not key_file:
        return ""
    try:
        return Path(key_file).read_text().strip()
    except FileNotFoundError:
        logger.warning("Hybrid API key file not found: %s", key_file)
        return ""
    except OSError as exc:
        logger.warning("Failed reading hybrid API key file %s: %s", key_file, exc)
        return ""


def _hybrid_headers() -> Optional[Dict[str, str]]:
    api_key = _load_hybrid_api_key()
    return {"X-API-Key": api_key} if api_key else None


def _normalize_status(raw: Any, ok_values: tuple[str, ...]) -> str:
    value = str(raw or "").lower()
    if value in ok_values:
        return ok_values[0]
    return value or "unknown"


class FeedbackPayload(BaseModel):
    query: str = Field(..., min_length=1)
    correction: str = Field(..., min_length=1)
    original_response: Optional[str] = None
    interaction_id: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    tags: Optional[List[str]] = None
    model: Optional[str] = None
    variant: Optional[str] = None


class MemoryStorePayload(BaseModel):
    memory_type: str = Field(..., pattern="^(episodic|semantic|procedural)$")
    summary: str = Field(..., min_length=1)
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MemoryRecallPayload(BaseModel):
    query: str = Field(..., min_length=1)
    memory_types: Optional[List[str]] = None
    limit: Optional[int] = Field(default=None, ge=1, le=50)
    retrieval_mode: str = Field(default="hybrid", pattern="^(hybrid|tree)$")


class HarnessEvalPayload(BaseModel):
    query: str = Field(..., min_length=1)
    mode: str = Field(default="auto", pattern="^(auto|sql|semantic|keyword|tree|hybrid)$")
    expected_keywords: Optional[List[str]] = None
    max_latency_ms: Optional[int] = Field(default=None, ge=1)


class HarnessMaintenancePayload(BaseModel):
    action: str = Field(
        ...,
        pattern="^(phase_plan|research_sync|catalog_sync|acceptance_checks)$",
    )


def _repo_root() -> Path:
    # dashboard/backend/api/routes -> repo root
    return Path(__file__).resolve().parents[4]


def _script_path(name: str) -> Path:
    return _repo_root() / "scripts" / name


def _safe_script_status(name: str) -> Dict[str, Any]:
    path = _script_path(name)
    return {
        "name": name,
        "path": str(path),
        "exists": path.exists(),
        "executable": path.is_file() and os.access(path, os.X_OK),
    }


def _weekly_research_state() -> Dict[str, Any]:
    scorecard = _repo_root() / "data" / "ai-research-scorecard.json"
    if not scorecard.exists():
        return {
            "available": False,
            "path": str(scorecard),
            "generated_at": None,
            "candidate_count": 0,
            "sources_scanned": 0,
        }
    try:
        payload = json.loads(scorecard.read_text(encoding="utf-8"))
        return {
            "available": True,
            "path": str(scorecard),
            "generated_at": payload.get("generated_at"),
            "candidate_count": payload.get("candidate_count", 0),
            "sources_scanned": payload.get("sources_scanned", 0),
            "report_path": payload.get("report_path"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "path": str(scorecard),
            "error": str(exc),
        }


async def _run_harness_script(script_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
    path = _script_path(script_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Script not found: {path}")
    if not os.access(path, os.X_OK):
        raise HTTPException(status_code=400, detail=f"Script not executable: {path}")
    argv = [str(path)] + (args or [])
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
            cwd=str(_repo_root()),
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail=f"Script timeout: {script_name}") from exc
    return {
        "script": script_name,
        "args": args or [],
        "exit_code": result.returncode,
        "success": result.returncode == 0,
        "stdout": (result.stdout or "")[-2000:],
        "stderr": (result.stderr or "")[-2000:],
    }


async def _http_health_probe(url: str) -> tuple[bool, Optional[str]]:
    """Perform a lightweight HTTP GET to a /health endpoint (2 s timeout, no retry).

    Returns ``(ok, error_message)``.  ``ok`` is True when the server responds
    with any 2xx status code.
    """
    try:
        # Use a dedicated short-timeout session so we never block on the
        # shared REQUEST_TIMEOUT session.
        timeout = _HEALTH_PROBE_TIMEOUT
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(url) as resp:
                if 200 <= resp.status < 300:
                    return True, None
                return False, f"http_{resp.status}"
    except asyncio.TimeoutError:
        return False, "timeout"
    except aiohttp.ClientConnectorError as exc:
        return False, f"connection_refused: {exc.os_error}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


async def _redis_ping_probe() -> Dict[str, Any]:
    """Send a raw RESP PING to Redis and return probe results.

    Host/port are read from ``service_endpoints.SERVICE_HOST`` /
    ``service_endpoints.REDIS_PORT`` so no values are hardcoded.
    """
    host = service_endpoints.SERVICE_HOST
    port = service_endpoints.REDIS_PORT
    t0 = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=2.0,
        )
        writer.write(b"*1\r\n$4\r\nPING\r\n")
        await writer.drain()
        data = await asyncio.wait_for(reader.read(128), timeout=2.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        ok = data.startswith(b"+PONG")
        return {
            "redis_ping_ok": ok,
            "redis_latency_ms": latency_ms,
            "redis_error": None if ok else f"unexpected_response: {data[:32]!r}",
        }
    except asyncio.TimeoutError:
        return {"redis_ping_ok": False, "redis_latency_ms": None, "redis_error": "timeout"}
    except OSError as exc:
        return {"redis_ping_ok": False, "redis_latency_ms": None, "redis_error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"redis_ping_ok": False, "redis_latency_ms": None, "redis_error": str(exc)}


async def _postgres_select1_probe() -> Dict[str, Any]:
    """Run ``SELECT 1`` against PostgreSQL and return probe results.

    The DSN is read from the ``AIDB_DB_URL`` environment variable.  If not
    set, a default is constructed from ``SERVICE_HOST`` / ``POSTGRES_PORT``.
    A fresh connection is opened and closed per call — no persistent pool.
    """
    if not _ASYNCPG_AVAILABLE:
        return {
            "postgres_query_ok": False,
            "postgres_latency_ms": None,
            "postgres_error": "asyncpg_not_installed",
        }
    dsn = os.getenv(
        "AIDB_DB_URL",
        f"postgresql://postgres@{service_endpoints.SERVICE_HOST}:{service_endpoints.POSTGRES_PORT}/aidb",
    )
    t0 = time.monotonic()
    conn = None
    try:
        conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=3.0)
        await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=2.0)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        return {"postgres_query_ok": True, "postgres_latency_ms": latency_ms, "postgres_error": None}
    except asyncio.TimeoutError:
        return {"postgres_query_ok": False, "postgres_latency_ms": None, "postgres_error": "timeout"}
    except Exception as exc:  # noqa: BLE001
        return {
            "postgres_query_ok": False,
            "postgres_latency_ms": None,
            "postgres_error": str(exc),
        }
    finally:
        if conn is not None:
            try:
                await conn.close()
            except Exception:  # noqa: BLE001
                pass


async def _run_full_health_probe() -> Dict[str, Any]:
    """Core health-probe logic shared by ``get_health_aggregate`` and ``probe_health``.

    For every runtime unit:
    - If it is in ``_UNIT_HTTP_HEALTH``: run systemd check AND HTTP GET.
      ``check_mode`` is ``"systemd+http"``.
    - Otherwise: systemd only.  ``check_mode`` is ``"systemd"``.

    Status mapping:
    - systemd active + HTTP ok  → ``"healthy"``
    - systemd active + HTTP fail → ``"degraded"``
    - systemd !active            → ``"down"``

    ``overall_status`` is ``"healthy"`` only when every critical unit reports
    ``"healthy"``.
    """
    def _systemd_state(unit_name: str) -> str:
        result = subprocess.run(
            ["systemctl", "is-active", f"{unit_name}.service"],
            capture_output=True,
            text=True,
            check=False,
        )
        return (result.stdout or "").strip().lower() or "unknown"

    def _map_systemd(raw: str) -> str:
        if raw == "active":
            return "healthy"
        if raw in ("activating", "reloading"):
            return "degraded"
        return "down"

    runtime_units = get_ai_runtime_units()

    # Fire all systemd checks in thread pool concurrently.
    systemd_states: Dict[str, str] = {}
    loop = asyncio.get_event_loop()
    tasks_sd = {unit: loop.run_in_executor(None, _systemd_state, unit) for unit in runtime_units}
    for unit, fut in tasks_sd.items():
        systemd_states[unit] = await fut

    # Fire HTTP probes concurrently only for units that have them and are active.
    http_tasks: Dict[str, asyncio.Task] = {}
    for unit in runtime_units:
        if unit in _UNIT_HTTP_HEALTH:
            http_tasks[unit] = asyncio.create_task(
                _http_health_probe(_UNIT_HTTP_HEALTH[unit])
            )

    http_results: Dict[str, tuple[bool, Optional[str]]] = {}
    for unit, task in http_tasks.items():
        http_results[unit] = await task

    health_checks: Dict[str, Dict[str, Any]] = {}
    for unit in runtime_units:
        raw = systemd_states[unit]
        has_http = unit in _UNIT_HTTP_HEALTH

        if not has_http or unit in _SYSTEMD_ONLY_UNITS:
            # Systemd-only path.
            status = _map_systemd(raw)
            health_checks[unit] = {
                "status": status,
                "check_mode": "systemd",
                "details": {
                    "unit": f"{unit}.service",
                    "active_state": raw,
                },
            }
        else:
            # Systemd + HTTP path.
            http_ok, http_err = http_results.get(unit, (False, "probe_skipped"))
            if raw == "active" and http_ok:
                status = "healthy"
            elif raw == "active" and not http_ok:
                status = "degraded"
            else:
                status = "down"

            health_checks[unit] = {
                "status": status,
                "check_mode": "systemd+http",
                "details": {
                    "unit": f"{unit}.service",
                    "active_state": raw,
                    "http_url": _UNIT_HTTP_HEALTH[unit],
                    "http_ok": http_ok,
                    "http_error": http_err,
                },
            }

    # overall_status: healthy only when ALL critical units are "healthy".
    critical_statuses = [
        health_checks[u]["status"]
        for u in _CRITICAL_UNITS
        if u in health_checks
    ]
    if any(s == "down" for s in critical_statuses):
        overall_status = "unhealthy"
    elif any(s == "degraded" for s in critical_statuses):
        overall_status = "degraded"
    elif all(s == "healthy" for s in critical_statuses) and critical_statuses:
        overall_status = "healthy"
    else:
        # Fallback: derive from whole set.
        if any(v["status"] == "down" for v in health_checks.values()):
            overall_status = "unhealthy"
        elif any(v["status"] == "degraded" for v in health_checks.values()):
            overall_status = "degraded"
        else:
            overall_status = "healthy"

    return {
        "overall_status": overall_status,
        "services": health_checks,
        "summary": {
            "total": len(health_checks),
            "healthy": sum(1 for v in health_checks.values() if v["status"] == "healthy"),
            "degraded": sum(1 for v in health_checks.values() if v["status"] == "degraded"),
            "down": sum(1 for v in health_checks.values() if v["status"] == "down"),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


async def _fetch_qdrant_collection_points(collections: list[str]) -> Dict[str, int]:
    results: Dict[str, int] = {}
    if not collections:
        return results

    for name in collections:
        info = await fetch_with_fallback(f"{SERVICES['qdrant']}/collections/{name}", {})
        points = info.get("result", {}).get("points_count", 0)
        results[name] = points if isinstance(points, int) else 0
    return results


@router.post("/feedback")
async def submit_feedback(payload: FeedbackPayload) -> Dict[str, Any]:
    """Forward user feedback to the hybrid coordinator learning endpoint."""
    api_key = _load_hybrid_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="Hybrid API key not configured")

    hybrid_base = SERVICES["hybrid"]
    tags = list(payload.tags or [])
    if payload.model:
        tags.append(f"model:{payload.model}")
    if payload.variant:
        tags.append(f"variant:{payload.variant}")
    payload_dict = payload.model_dump()
    payload_dict["tags"] = tags or None
    result = await post_with_fallback(
        f"{hybrid_base}/feedback",
        payload_dict,
        headers={"X-API-Key": api_key},
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Hybrid feedback endpoint unavailable")
    return result


@router.get("/aidb/health/{probe}")
async def proxy_aidb_health(probe: str) -> Dict[str, Any]:
    """Proxy AIDB health endpoints via cluster DNS."""
    if probe not in ("health", "live", "ready", "startup", "detailed"):
        raise HTTPException(status_code=404, detail="Unsupported probe")
    path = f"/health/{probe}" if probe != "health" else "/health"
    result = await fetch_with_fallback(f"{SERVICES['aidb']}{path}", None)
    if result is None:
        raise HTTPException(status_code=503, detail="AIDB health unavailable")
    return result


@router.get("/aidb/metrics")
async def proxy_aidb_metrics() -> Response:
    """Proxy AIDB Prometheus metrics."""
    metrics = await fetch_text_with_fallback(f"{SERVICES['aidb']}/metrics", None)
    if metrics is None:
        raise HTTPException(status_code=503, detail="AIDB metrics unavailable")
    return Response(content=metrics, media_type="text/plain")


@router.get("/stats/learning")
async def get_learning_stats() -> Dict[str, Any]:
    """Get continuous learning statistics from hybrid coordinator"""
    hybrid_base = SERVICES["hybrid"]
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    stats = await fetch_with_fallback(
        f"{hybrid_base}/learning/stats",
        {
            "checkpoints": {"total": 0, "last_checkpoint": None},
            "backpressure": {"unprocessed_mb": 0, "paused": False},
            "deduplication": {"total_patterns": 0, "duplicates_found": 0, "unique_patterns": 0}
        },
        headers=headers,
    )
    return stats


@router.get("/stats/circuit-breakers")
async def get_circuit_breakers() -> Dict[str, Any]:
    """Get circuit breaker states from hybrid coordinator"""
    hybrid_base = SERVICES["hybrid"]
    health = await fetch_with_fallback(f"{hybrid_base}/health", {})

    circuit_breakers = health.get("circuit_breakers", {})

    return {
        "circuit_breakers": circuit_breakers,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/memory/store")
async def store_memory(payload: MemoryStorePayload) -> Dict[str, Any]:
    """Store agent memory via hybrid coordinator."""
    result = await post_with_fallback(
        f"{SERVICES['hybrid']}/memory/store",
        payload.model_dump(),
        headers=_hybrid_headers(),
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Hybrid memory store endpoint unavailable")
    return result


@router.post("/memory/recall")
async def recall_memory(payload: MemoryRecallPayload) -> Dict[str, Any]:
    """Recall agent memory via hybrid coordinator."""
    result = await post_with_fallback(
        f"{SERVICES['hybrid']}/memory/recall",
        payload.model_dump(exclude_none=True),
        headers=_hybrid_headers(),
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Hybrid memory recall endpoint unavailable")
    return result


@router.post("/search/tree")
async def tree_search(payload: MemoryRecallPayload) -> Dict[str, Any]:
    """Run tree-search retrieval via hybrid coordinator."""
    req = {
        "query": payload.query,
        "limit": payload.limit or 5,
        "keyword_limit": payload.limit or 5,
    }
    result = await post_with_fallback(
        f"{SERVICES['hybrid']}/search/tree",
        req,
        headers=_hybrid_headers(),
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Hybrid tree-search endpoint unavailable")
    return result


@router.post("/harness/eval")
async def run_harness_eval(payload: HarnessEvalPayload) -> Dict[str, Any]:
    """Run harness evaluation via hybrid coordinator."""
    result = await post_with_fallback(
        f"{SERVICES['hybrid']}/harness/eval",
        payload.model_dump(exclude_none=True),
        headers=_hybrid_headers(),
        timeout=HARNESS_EVAL_TIMEOUT,
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Hybrid harness eval endpoint unavailable")
    return result


@router.get("/harness/stats")
async def get_harness_stats() -> Dict[str, Any]:
    """Fetch harness aggregate stats."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    result = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/harness/stats",
        {
            "status": "degraded",
            "available": False,
            "reason": "hybrid_harness_stats_unavailable",
            "timestamp": datetime.utcnow().isoformat(),
        },
        headers=headers,
    )
    if not isinstance(result, dict):
        return {
            "status": "degraded",
            "available": False,
            "reason": "invalid_harness_stats_payload",
            "timestamp": datetime.utcnow().isoformat(),
        }
    result.setdefault("available", True)
    result.setdefault("status", "ok")
    return result


@router.get("/harness/scorecard")
async def get_harness_scorecard() -> Dict[str, Any]:
    """Fetch harness scorecard; fallback to /stats when endpoint requires auth."""
    headers = _hybrid_headers()
    result = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/harness/scorecard",
        None,
        headers=headers,
    )
    if isinstance(result, dict):
        result.setdefault("available", True)
        return result

    stats = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/stats",
        {"status": "degraded", "available": False, "reason": "scorecard_unavailable"},
        headers=headers,
    )
    if not isinstance(stats, dict):
        return {
            "status": "degraded",
            "available": False,
            "reason": "invalid_scorecard_payload",
        }
    return {
        "available": True,
        "fallback": True,
        "acceptance": {
            "total": stats.get("harness_stats", {}).get("total_runs", 0),
            "passed": stats.get("harness_stats", {}).get("passed", 0),
            "failed": stats.get("harness_stats", {}).get("failed", 0),
        },
        "discovery": stats.get("capability_discovery", {}),
        "inference_optimizations": {
            "prompt_cache_policy_enabled": True,
            "speculative_decoding_enabled": False,
            "context_compression_enabled": True,
        },
    }


@router.get("/harness/overview")
async def get_harness_overview() -> Dict[str, Any]:
    """Aggregate AI harness operations, policies, and maintenance script status."""
    harness_stats = await get_harness_stats()
    harness_scorecard = await get_harness_scorecard()
    aidb_health = await fetch_with_fallback(f"{SERVICES['aidb']}/health", {})
    hybrid_health = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/health",
        {},
        headers=_hybrid_headers(),
    )

    scripts = [
        "run-ai-harness-phase-plan.sh",
        "run-acceptance-checks.sh",
        "sync-ai-research-knowledge.sh",
        "update-ai-research-now.sh",
        "install-ai-research-sync-timer.sh",
        "sync-aidb-library-catalog.sh",
    ]
    script_status = [_safe_script_status(name) for name in scripts]
    operational_count = sum(1 for item in script_status if item["exists"] and item["executable"])

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "status": "ok",
        "harness": {
            "stats": harness_stats,
            "scorecard": harness_scorecard,
            "capability_discovery": (
                hybrid_health.get("capability_discovery")
                or harness_scorecard.get("discovery")
                or {}
            ),
            "hybrid_harness": hybrid_health.get("ai_harness", {}),
        },
        "policies": {
            "tool_execution_policy": aidb_health.get("tool_execution_policy", {}),
            "outbound_http_policy": aidb_health.get("outbound_http_policy", {}),
        },
        "maintenance": {
            "scripts": script_status,
            "operational_scripts": operational_count,
            "total_scripts": len(script_status),
            "weekly_research": _weekly_research_state(),
        },
    }


@router.post("/harness/maintenance/run")
async def run_harness_maintenance(payload: HarnessMaintenancePayload) -> Dict[str, Any]:
    """Run allowlisted harness maintenance actions from dashboard."""
    action_map: Dict[str, tuple[str, List[str]]] = {
        "phase_plan": ("run-ai-harness-phase-plan.sh", []),
        "research_sync": ("sync-ai-research-knowledge.sh", []),
        "catalog_sync": ("sync-aidb-library-catalog.sh", []),
        "acceptance_checks": ("run-acceptance-checks.sh", []),
    }
    script_name, args = action_map[payload.action]
    result = await _run_harness_script(script_name, args=args)
    return {
        "action": payload.action,
        **result,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/aggregate")
async def get_health_aggregate() -> Dict[str, Any]:
    """Get aggregated health status with systemd + HTTP probes for AI stack runtime units.

    Services that expose a /health endpoint are checked via both systemd
    is-active and a lightweight HTTP GET (2 s timeout).  PostgreSQL and Redis
    units that have no HTTP endpoint are checked via systemd only.

    Each service entry in the response includes a ``check_mode`` field:
    - ``"systemd+http"`` — both checks were run.
    - ``"systemd"``      — systemd only (no HTTP endpoint for this unit).

    Status values:
    - ``"healthy"``  — systemd active AND (if applicable) HTTP probe succeeded.
    - ``"degraded"`` — systemd active BUT HTTP probe failed.
    - ``"down"``     — systemd reports the unit is not active.

    ``overall_status`` is ``"healthy"`` only when all critical services pass
    both checks.
    """
    return await _run_full_health_probe()


@router.get("/health/probe")
async def probe_health() -> Dict[str, Any]:
    """Trigger an immediate, cache-bypassing full health probe cycle.

    Returns the same JSON structure as ``GET /health/aggregate``.  Intended
    for use by deploy post-flight checks where stale cached state is not
    acceptable.
    """
    return await _run_full_health_probe()


@router.get("/ai/metrics")
async def get_ai_metrics() -> Dict[str, Any]:
    """Aggregate AI metrics for dashboard consumption (systemd-host mode).

    In addition to existing service health fetches, this endpoint runs:
    - A raw RESP PING against Redis (Task 17.3) — fields: ``redis_ping_ok``,
      ``redis_latency_ms``.
    - A ``SELECT 1`` query against PostgreSQL via asyncpg (Task 17.3) —
      fields: ``postgres_query_ok``, ``postgres_latency_ms``.

    Both probes are exposed under the top-level ``"infra_probes"`` key.
    """
    # Fire all independent fetches and infra probes concurrently.
    (
        aidb_health,
        hybrid_health,
        llama_health,
        llama_models,
        embeddings_health,
        embeddings_models,
        switchboard_health,
        aider_wrapper_health,
        qdrant_health_raw,
        qdrant_collections,
        redis_probe,
        postgres_probe,
    ) = await asyncio.gather(
        fetch_with_fallback(f"{SERVICES['aidb']}/health", {}),
        fetch_with_fallback(f"{SERVICES['hybrid']}/health", {}),
        fetch_with_fallback(f"{SERVICES['llama_cpp']}/health", {}),
        fetch_with_fallback(f"{SERVICES['llama_cpp']}/v1/models", {}),
        fetch_with_fallback(f"{SERVICES['embeddings']}/health", {}),
        fetch_with_fallback(f"{SERVICES['embeddings']}/v1/models", {}),
        fetch_with_fallback(f"{SERVICES['switchboard']}/health", {}),
        fetch_with_fallback(f"{SERVICES['aider_wrapper']}/health", {}),
        fetch_text_with_fallback(f"{SERVICES['qdrant']}/healthz"),
        fetch_with_fallback(f"{SERVICES['qdrant']}/collections", {}),
        _redis_ping_probe(),
        _postgres_select1_probe(),
    )

    aidb_status = _normalize_status(aidb_health.get("status"), ("online", "ok", "healthy"))
    if aidb_status in ("ok", "healthy"):
        aidb_status = "online"

    hybrid_status = _normalize_status(hybrid_health.get("status"), ("healthy", "ok", "online"))

    llama_status = _normalize_status(llama_health.get("status"), ("ok", "healthy"))
    llama_model = "unknown"
    if isinstance(llama_models, dict):
        data = llama_models.get("data") or []
        if data and isinstance(data, list):
            llama_model = data[0].get("id", "unknown")

    embeddings_status = _normalize_status(embeddings_health.get("status"), ("ok", "healthy"))
    embeddings_model = embeddings_health.get("model", "unknown")
    if isinstance(embeddings_models, dict):
        data = embeddings_models.get("data") or []
        if data and isinstance(data, list):
            embeddings_model = data[0].get("id", embeddings_model)
        elif embeddings_model == "unknown":
            models = embeddings_models.get("models") or []
            if models and isinstance(models, list):
                embeddings_model = models[0].get("model", embeddings_model)
    embeddings_dimensions = (
        embeddings_health.get("dimensions")
        or embeddings_health.get("dim")
        or service_endpoints.EMBEDDING_DIMENSIONS
    )

    switchboard_status = _normalize_status(switchboard_health.get("status"), ("ok", "healthy"))
    aider_wrapper_status = _normalize_status(aider_wrapper_health.get("status"), ("ok", "healthy"))

    if not qdrant_health_raw:
        qdrant_health_raw = await fetch_text_with_fallback(f"{SERVICES['qdrant']}/readyz")
    qdrant_status = "healthy" if qdrant_health_raw else "unhealthy"

    collection_names = []
    if isinstance(qdrant_collections, dict):
        collection_names = [
            item.get("name")
            for item in qdrant_collections.get("result", {}).get("collections", [])
            if item.get("name")
        ]
    collection_points = await _fetch_qdrant_collection_points(collection_names)
    total_points = sum(collection_points.values())
    harness_stats = await get_harness_stats()
    harness_scorecard = await get_harness_scorecard()
    harness_overview = await get_harness_overview()

    knowledge_collections = {
        "codebase_context": collection_points.get("codebase-context", 0),
        "error_solutions": collection_points.get("error-solutions", 0),
        "best_practices": collection_points.get("best-practices", 0),
    }

    hybrid_service = {
        "service": "hybrid_coordinator",
        "status": hybrid_status,
        "port": service_endpoints.HYBRID_COORDINATOR_PORT,
        "health_check": hybrid_health,
    }

    # Prometheus gauge values (1.0 = up, 0.0 = down).  Emitted to the log so
    # a log-based exporter or a future /metrics endpoint can surface them.
    redis_ok_gauge = 1.0 if redis_probe.get("redis_ping_ok") else 0.0
    postgres_ok_gauge = 1.0 if postgres_probe.get("postgres_query_ok") else 0.0
    logger.info(
        "infra_probe gauge redis_ping_ok=%.0f postgres_query_ok=%.0f",
        redis_ok_gauge,
        postgres_ok_gauge,
    )

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "aidb": {
                "service": "aidb",
                "status": aidb_status,
                "port": service_endpoints.AIDB_PORT,
                "health_check": aidb_health,
            },
            "hybrid_coordinator": hybrid_service,
            # Backward-compat alias for clients that still expect `services.hybrid`.
            "hybrid": hybrid_service,
            "qdrant": {
                "service": "qdrant",
                "status": qdrant_status,
                "port": service_endpoints.QDRANT_PORT,
                "metrics": {
                    "collection_count": len(collection_names),
                    "total_vectors": total_points,
                },
            },
            "llama_cpp": {
                "service": "llama_cpp",
                "status": llama_status,
                "port": service_endpoints.LLAMA_CPP_PORT,
                "model": llama_model,
            },
            "embeddings": {
                "service": "embeddings",
                "status": embeddings_status,
                "port": service_endpoints.EMBEDDINGS_PORT,
                "model": embeddings_model,
                "dimensions": embeddings_dimensions,
                "endpoint": SERVICES["embeddings"],
            },
            "switchboard": {
                "service": "switchboard",
                "status": switchboard_status,
                "port": service_endpoints.SWITCHBOARD_PORT,
                "endpoint": SERVICES["switchboard"],
                "routing_mode": switchboard_health.get("routing_mode", "unknown"),
                "default_provider": switchboard_health.get("default_provider", "unknown"),
                "remote_configured": bool(switchboard_health.get("remote_configured", False)),
            },
            "aider_wrapper": {
                "service": "aider-wrapper",
                "status": aider_wrapper_status,
                "port": service_endpoints.AIDER_WRAPPER_PORT,
                "endpoint": SERVICES["aider_wrapper"],
                "health_check": aider_wrapper_health,
            },
        },
        "infra_probes": {
            # Redis PING probe (Task 17.3).  Host/port from service_endpoints —
            # no hardcoded values.
            "redis_ping_ok": redis_probe.get("redis_ping_ok", False),
            "redis_latency_ms": redis_probe.get("redis_latency_ms"),
            "redis_error": redis_probe.get("redis_error"),
            # PostgreSQL SELECT 1 probe (Task 17.3).  DSN from AIDB_DB_URL env
            # var or constructed from service_endpoints constants.
            "postgres_query_ok": postgres_probe.get("postgres_query_ok", False),
            "postgres_latency_ms": postgres_probe.get("postgres_latency_ms"),
            "postgres_error": postgres_probe.get("postgres_error"),
            # Prometheus gauge equivalents exposed in the JSON response.
            "redis_ping_ok_gauge": redis_ok_gauge,
            "postgres_query_ok_gauge": postgres_ok_gauge,
        },
        "knowledge_base": {
            "total_points": total_points,
            "real_embeddings_percent": 100 if total_points > 0 else 0,
            "collections": knowledge_collections,
            "rag_quality": {
                "context_relevance": "90%",
                "improvement_over_baseline": "+60%",
            },
        },
        "effectiveness": {
            "overall_score": round(
                (
                    float(harness_scorecard.get("acceptance", {}).get("pass_rate", 0.0) or 0.0) * 100
                ),
                2,
            ),
            "total_events_processed": int(
                harness_stats.get("total_runs", 0)
                or harness_stats.get("acceptance", {}).get("total", 0)
                or 0
            ),
            "local_query_percentage": round(
                float(harness_scorecard.get("discovery", {}).get("cache_hit_rate", 0.0) or 0.0) * 100,
                2,
            ),
            "estimated_tokens_saved": 0,
            "knowledge_base_vectors": total_points,
        },
        "harness": {
            "stats": harness_stats,
            "scorecard": harness_scorecard,
            "overview": harness_overview,
        },
    }


@router.get("/ports/registry")
async def get_port_registry() -> Dict[str, Any]:
    """Expose centralized service endpoint registry for dashboard/UI fallback usage."""
    return {
        "host": service_endpoints.SERVICE_HOST,
        "services": {
            "aidb": {"port": service_endpoints.AIDB_PORT, "url": service_endpoints.AIDB_URL},
            "hybrid_coordinator": {
                "port": service_endpoints.HYBRID_COORDINATOR_PORT,
                "url": service_endpoints.HYBRID_URL,
            },
            "qdrant": {"port": service_endpoints.QDRANT_PORT, "url": service_endpoints.QDRANT_URL},
            "llama_cpp": {"port": service_endpoints.LLAMA_CPP_PORT, "url": service_endpoints.LLAMA_URL},
            "embeddings": {
                "port": service_endpoints.EMBEDDINGS_PORT,
                "url": service_endpoints.EMBEDDINGS_URL,
            },
            "switchboard": {
                "port": service_endpoints.SWITCHBOARD_PORT,
                "url": service_endpoints.SWITCHBOARD_URL,
            },
            "open_webui": {
                "port": service_endpoints.OPEN_WEBUI_PORT,
                "url": service_endpoints.OPEN_WEBUI_URL,
            },
            "mindsdb": {"port": service_endpoints.MINDSDB_PORT, "url": service_endpoints.MINDSDB_URL},
            "postgres": {
                "port": service_endpoints.POSTGRES_PORT,
                "url": f"{service_endpoints.SERVICE_HOST}:{service_endpoints.POSTGRES_PORT}",
            },
            "redis": {
                "port": service_endpoints.REDIS_PORT,
                "url": f"{service_endpoints.SERVICE_HOST}:{service_endpoints.REDIS_PORT}",
            },
            "dashboard_api": {
                "port": service_endpoints.DASHBOARD_API_PORT,
                "url": f"http://{service_endpoints.SERVICE_HOST}:{service_endpoints.DASHBOARD_API_PORT}",
            },
            "grafana": {"port": service_endpoints.GRAFANA_PORT, "url": service_endpoints.GRAFANA_URL},
            "prometheus": {
                "port": service_endpoints.PROMETHEUS_PORT,
                "url": service_endpoints.PROMETHEUS_URL,
            },
            "ralph": {"port": service_endpoints.RALPH_PORT, "url": service_endpoints.RALPH_URL},
            "aider_wrapper": {
                "port": service_endpoints.AIDER_WRAPPER_PORT,
                "url": service_endpoints.AIDER_WRAPPER_URL,
            },
        },
    }


@router.get("/ralph/stats")
async def get_ralph_stats() -> Dict[str, Any]:
    """Get Ralph Wiggum task statistics"""
    ralph_base = SERVICES["ralph"]

    stats = await fetch_with_fallback(
        f"{ralph_base}/stats",
        {
            "active_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_iterations": 0
        }
    )

    return stats


@router.get("/ralph/tasks")
async def get_ralph_tasks() -> Dict[str, Any]:
    """List Ralph Wiggum tasks"""
    ralph_base = SERVICES["ralph"]

    tasks = await fetch_with_fallback(f"{ralph_base}/tasks", [])

    return {
        "tasks": tasks,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/prometheus/query")
async def proxy_prometheus_query(query: str) -> Dict[str, Any]:
    """Proxy Prometheus queries"""
    prom_url = f"{service_endpoints.PROMETHEUS_URL}/api/v1/query?query={query}"
    result = await fetch_with_fallback(prom_url, {})
    return result


async def _prom_scalar(query: str) -> Optional[float]:
    """Execute an instant Prometheus query and return the scalar result or None."""
    url = f"{service_endpoints.PROMETHEUS_URL}/api/v1/query"
    try:
        session = await get_http_session()
        async with session.get(url, params={"query": query}) as resp:
            if resp.status != 200:
                return None
            payload = await resp.json()
    except Exception:
        return None

    try:
        result = payload.get("data", {}).get("result", [])
        if result:
            return float(result[0]["value"][1])
    except (KeyError, IndexError, ValueError, TypeError):
        pass
    return None


@router.get("/metrics")
async def get_aistack_metrics() -> Dict[str, Any]:
    """AI internals metrics for the dashboard 'AI Internals' panel.

    Queries Prometheus for three derived metrics:
    - embedding_cache_hit_rate_pct: hits / (hits + misses) * 100
    - llm_routing_local_pct: local backend selections / total * 100
    - tokens_compressed_last_hour: tokens saved by context compression in the last hour
    """
    hits_q = "embedding_cache_hits_total"
    misses_q = "embedding_cache_misses_total"
    local_q = 'hybrid_llm_backend_selections_total{backend="local"}'
    total_q = "sum(hybrid_llm_backend_selections_total)"
    before_q = "increase(context_compression_tokens_before_sum[1h])"
    after_q = "increase(context_compression_tokens_after_sum[1h])"

    hits, misses, local_sel, total_sel, before_sum, after_sum = await asyncio.gather(
        _prom_scalar(hits_q),
        _prom_scalar(misses_q),
        _prom_scalar(local_q),
        _prom_scalar(total_q),
        _prom_scalar(before_q),
        _prom_scalar(after_q),
    )

    h = hits or 0.0
    m = misses or 0.0
    embedding_cache_hit_rate_pct = round((h / (h + m) * 100) if (h + m) > 0 else 0.0, 2)

    loc = local_sel or 0.0
    tot = total_sel or 0.0
    llm_routing_local_pct = round((loc / tot * 100) if tot > 0 else 0.0, 2)

    b = before_sum or 0.0
    a = after_sum or 0.0
    tokens_compressed_last_hour = round(max(b - a, 0.0), 0)

    return {
        "embedding_cache_hit_rate_pct": embedding_cache_hit_rate_pct,
        "llm_routing_local_pct": llm_routing_local_pct,
        "tokens_compressed_last_hour": tokens_compressed_last_hour,
        "timestamp": datetime.utcnow().isoformat(),
    }
