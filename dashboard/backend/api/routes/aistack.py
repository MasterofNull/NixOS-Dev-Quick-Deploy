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
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from ..config import service_endpoints
from ..services.systemd_units import get_ai_runtime_units

try:
    import asyncpg
    _ASYNCPG_AVAILABLE = True
except ImportError:
    _ASYNCPG_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)

# Prometheus-compatible in-memory gauges for dashboard infra probes.
_REDIS_PING_OK_GAUGE: float = 0.0
_POSTGRES_QUERY_OK_GAUGE: float = 0.0
_AQ_REPORT_CACHE: Dict[str, Any] = {"ts": 0.0, "payload": {}}
_AI_METRICS_CACHE: Dict[str, Any] = {"ts": 0.0, "payload": None}
_QDRANT_POINTS_CACHE: Dict[str, Any] = {"ts": 0.0, "collections": tuple(), "payload": {}}

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
    "nixos_docs": service_endpoints.NIXOS_DOCS_URL,
}

# Timeout for external requests
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=5)
HARNESS_EVAL_TIMEOUT = aiohttp.ClientTimeout(
    total=float(os.getenv("HARNESS_EVAL_TIMEOUT_SECONDS", "15"))
)
# Lightweight timeout used exclusively for health-probe HTTP GETs (Task 17.2)
_HEALTH_PROBE_TIMEOUT = aiohttp.ClientTimeout(total=2)
AI_METRICS_CACHE_TTL_SECONDS = float(os.getenv("DASHBOARD_AI_METRICS_TTL_SECONDS", "10"))
QDRANT_POINTS_CACHE_TTL_SECONDS = float(os.getenv("DASHBOARD_QDRANT_POINTS_TTL_SECONDS", "30"))

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
    "ai-nixos-docs": f"{service_endpoints.NIXOS_DOCS_URL}/health",
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
        pattern="^(phase_plan|research_sync|catalog_sync|acceptance_checks|improvement_pass)$",
    )


class PRSIApprovalPayload(BaseModel):
    action_id: str = Field(..., min_length=4)
    decision: str = Field(..., pattern="^(approve|reject)$")
    by: str = Field(default="dashboard")
    note: Optional[str] = None


class PRSIExecutePayload(BaseModel):
    limit: int = Field(default=5, ge=1, le=50)
    dry_run: bool = False
    auto_sync: bool = True


def _repo_root() -> Path:
    # dashboard/backend/api/routes -> repo root
    return Path(__file__).resolve().parents[4]


def _script_path(name: str) -> Path:
    candidates = [
        _repo_root() / "scripts" / name,
        _repo_root() / "scripts" / "automation" / name,
        _repo_root() / "scripts" / "ai" / name,
        _repo_root() / "scripts" / "testing" / name,
        _repo_root() / "scripts" / "governance" / name,
        _repo_root() / "scripts" / "deploy" / name,
        _repo_root() / "scripts" / "security" / name,
        _repo_root() / "scripts" / "health" / name,
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


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


async def _run_harness_script(
    script_name: str,
    args: Optional[List[str]] = None,
    timeout_seconds: int = 180,
) -> Dict[str, Any]:
    path = _script_path(script_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Script not found: {path}")
    if not os.access(path, os.X_OK):
        raise HTTPException(status_code=400, detail=f"Script not executable: {path}")
    argv = [str(path)] + (args or [])
    t0 = time.monotonic()
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            cwd=str(_repo_root()),
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail=f"Script timeout: {script_name}") from exc
    duration_ms = int((time.monotonic() - t0) * 1000)
    return {
        "script": script_name,
        "args": args or [],
        "exit_code": result.returncode,
        "success": result.returncode == 0,
        "duration_ms": duration_ms,
        "stdout": (result.stdout or "")[-2000:],
        "stderr": (result.stderr or "")[-2000:],
    }


async def _run_prsi_orchestrator(args: List[str], timeout_seconds: int = 90) -> Dict[str, Any]:
    path = _script_path("prsi-orchestrator.py")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"PRSI orchestrator script not found: {path}")
    argv = [sys.executable, str(path)] + args
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            cwd=str(_repo_root()),
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="PRSI orchestrator timeout") from exc

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    payload: Dict[str, Any] = {}
    if stdout:
        last_line = stdout.splitlines()[-1]
        try:
            parsed = json.loads(last_line)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = {"raw": last_line}
    return {
        "exit_code": result.returncode,
        "stdout": stdout[-2000:],
        "stderr": stderr[-2000:],
        "payload": payload,
        "ok": result.returncode == 0,
    }


def _extract_improvement_summary(stdout: str) -> Dict[str, Any]:
    """Extract structured summary JSON from improvement-pass script stdout."""
    marker = "IMPROVEMENT_SUMMARY_JSON="
    for line in reversed((stdout or "").splitlines()):
        if line.startswith(marker):
            payload = line[len(marker):].strip()
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {}
    return {}


def _build_aidb_dsn() -> str:
    pg_user = os.getenv("AIDB_DB_USER", "aidb")
    pg_name = os.getenv("AIDB_DB_NAME", "aidb")
    dsn = os.getenv(
        "AIDB_DB_URL",
        f"postgresql://{pg_user}@{service_endpoints.SERVICE_HOST}:{service_endpoints.POSTGRES_PORT}/{pg_name}",
    )
    return _inject_password_into_dsn(dsn, pg_user)


def _inject_password_into_dsn(dsn: str, pg_user: str) -> str:
    """Add password from secret file if DSN user has no password."""
    pg_pw_file = os.getenv("POSTGRES_PASSWORD_FILE")
    if not pg_pw_file:
        fallback_pw = Path("/run/secrets/postgres_password")
        if fallback_pw.exists():
            pg_pw_file = str(fallback_pw)
    if not pg_pw_file:
        return dsn
    try:
        parsed = urlsplit(dsn)
    except ValueError:
        return dsn
    if not parsed.hostname or parsed.username is None or parsed.password is not None:
        return dsn
    if parsed.username != pg_user:
        return dsn
    try:
        pw = Path(pg_pw_file).read_text(encoding="utf-8").strip()
    except OSError:
        return dsn
    if not pw:
        return dsn
    netloc = f"{parsed.username}:{quote(pw, safe='')}@{parsed.hostname}"
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


async def _record_telemetry_event(
    *,
    event_type: str,
    event_category: str,
    severity: str,
    source: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Record an event in telemetry_events table (best-effort, non-fatal)."""
    if not _ASYNCPG_AVAILABLE:
        return
    conn = None
    try:
        conn = await asyncpg.connect(_build_aidb_dsn(), timeout=5.0)
        event_meta = dict(metadata or {})
        event_meta.setdefault("event_category", event_category)
        event_meta.setdefault("severity", severity)
        event_meta.setdefault("message", message[:4000])
        try:
            await conn.execute(
                """
                INSERT INTO telemetry_events
                (event_type, event_category, severity, source, message, metadata, duration_ms)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                """,
                event_type,
                event_category,
                severity,
                source,
                message[:4000],
                json.dumps(event_meta, separators=(",", ":")),
                duration_ms,
            )
        except Exception as schema_exc:  # noqa: BLE001
            # Backward compatibility for legacy telemetry_events schema
            # (source,event_type,metadata,latency_ms,created_at...).
            await conn.execute(
                """
                INSERT INTO telemetry_events
                (source, event_type, metadata, latency_ms)
                VALUES ($1, $2, $3::json, $4)
                """,
                source,
                event_type,
                json.dumps(event_meta, separators=(",", ":")),
                duration_ms,
            )
            logger.info(
                "telemetry_event_insert_legacy_schema type=%s detail=%s",
                event_type,
                schema_exc,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "telemetry_event_insert_failed type=%s err_type=%s error=%r",
            event_type,
            type(exc).__name__,
            exc,
        )
    finally:
        if conn is not None:
            try:
                await conn.close()
            except Exception:  # noqa: BLE001
                pass


async def _fetch_improvement_pass_stats(hours: int = 24) -> Dict[str, Any]:
    """Return recent improvement-pass execution stats from telemetry_events."""
    if not _ASYNCPG_AVAILABLE:
        return {"available": False, "reason": "asyncpg_not_installed"}
    conn = None
    try:
        conn = await asyncio.wait_for(asyncpg.connect(_build_aidb_dsn()), timeout=3.0)
        row = await asyncio.wait_for(
            conn.fetchrow(
                """
                SELECT
                  COUNT(*)::int AS total_runs,
                  COUNT(*) FILTER (
                    WHERE COALESCE((metadata->>'success')::boolean, false)
                  )::int AS successful_runs,
                  MAX(created_at) AS last_run_at
                FROM telemetry_events
                WHERE event_type = 'harness_improvement_pass'
                  AND created_at >= NOW() - ($1::text || ' hours')::interval
                """,
                str(hours),
            ),
            timeout=3.0,
        )
        latest = await asyncio.wait_for(
            conn.fetchrow(
                """
                SELECT metadata, created_at
                FROM telemetry_events
                WHERE event_type = 'harness_improvement_pass'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            timeout=3.0,
        )
        total = int(row["total_runs"] or 0)
        successful = int(row["successful_runs"] or 0)
        last_metadata = dict(latest["metadata"]) if latest and latest["metadata"] else {}
        return {
            "available": True,
            "window_hours": hours,
            "total_runs": total,
            "successful_runs": successful,
            "success_rate_pct": round((successful / total) * 100, 1) if total else None,
            "last_run_at": row["last_run_at"].isoformat() if row and row["last_run_at"] else None,
            "last_report": last_metadata.get("report", {}),
            "last_probe_status": last_metadata.get("probes", {}),
        }
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": str(exc)}
    finally:
        if conn is not None:
            try:
                await conn.close()
            except Exception:  # noqa: BLE001
                pass


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
    pg_user = os.getenv("AIDB_DB_USER", "aidb")
    pg_name = os.getenv("AIDB_DB_NAME", "aidb")
    dsn = os.getenv(
        "AIDB_DB_URL",
        f"postgresql://{pg_user}@{service_endpoints.SERVICE_HOST}:{service_endpoints.POSTGRES_PORT}/{pg_name}",
    )
    dsn = _inject_password_into_dsn(dsn, pg_user)
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


async def _redis_runtime_probe() -> Dict[str, Any]:
    """Collect Redis runtime metrics with a raw RESP session."""
    host = service_endpoints.SERVICE_HOST
    port = service_endpoints.REDIS_PORT
    reader = None
    writer = None

    async def _read_resp() -> Any:
        prefix = await reader.readexactly(1)
        if prefix == b"+":
            return (await reader.readline()).decode("utf-8", errors="replace").strip()
        if prefix == b":":
            return int((await reader.readline()).decode("utf-8", errors="replace").strip())
        if prefix == b"$":
            length = int((await reader.readline()).decode("utf-8", errors="replace").strip())
            if length < 0:
                return None
            payload = await reader.readexactly(length)
            await reader.readexactly(2)
            return payload.decode("utf-8", errors="replace")
        if prefix == b"-":
            err = (await reader.readline()).decode("utf-8", errors="replace").strip()
            raise RuntimeError(err)
        raise RuntimeError(f"unsupported_redis_resp_prefix:{prefix!r}")

    def _encode_command(*parts: str) -> bytes:
        chunks = [f"*{len(parts)}\r\n".encode("utf-8")]
        for part in parts:
            encoded = str(part).encode("utf-8")
            chunks.append(f"${len(encoded)}\r\n".encode("utf-8"))
            chunks.append(encoded + b"\r\n")
        return b"".join(chunks)

    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2.0)
        writer.write(_encode_command("DBSIZE"))
        writer.write(_encode_command("INFO", "memory"))
        writer.write(_encode_command("INFO", "clients"))
        await writer.drain()

        dbsize = await asyncio.wait_for(_read_resp(), timeout=2.0)
        memory_info = await asyncio.wait_for(_read_resp(), timeout=2.0)
        clients_info = await asyncio.wait_for(_read_resp(), timeout=2.0)

        parsed: Dict[str, str] = {}
        for payload in (memory_info, clients_info):
            if not isinstance(payload, str):
                continue
            for line in payload.splitlines():
                if ":" not in line or line.startswith("#"):
                    continue
                key, value = line.split(":", 1)
                parsed[key.strip()] = value.strip()

        memory_bytes = int(parsed.get("used_memory", "0") or 0)
        connected_clients = int(parsed.get("connected_clients", "0") or 0)
        return {
            "keys": int(dbsize or 0),
            "memory_bytes": memory_bytes,
            "memory_human": parsed.get("used_memory_human"),
            "connected_clients": connected_clients,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "keys": 0,
            "memory_bytes": None,
            "memory_human": None,
            "connected_clients": None,
            "error": str(exc),
        }
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass


async def _postgres_runtime_probe() -> Dict[str, Any]:
    """Collect PostgreSQL runtime metrics beyond the basic SELECT 1 health probe."""
    if not _ASYNCPG_AVAILABLE:
        return {
            "database_size_bytes": None,
            "active_connections": None,
            "idle_connections": None,
            "database_name": os.getenv("AIDB_DB_NAME", "aidb"),
            "error": "asyncpg_not_installed",
        }

    pg_user = os.getenv("AIDB_DB_USER", "aidb")
    pg_name = os.getenv("AIDB_DB_NAME", "aidb")
    dsn = _inject_password_into_dsn(
        os.getenv(
            "AIDB_DB_URL",
            f"postgresql://{pg_user}@{service_endpoints.SERVICE_HOST}:{service_endpoints.POSTGRES_PORT}/{pg_name}",
        ),
        pg_user,
    )

    conn = None
    try:
        conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=3.0)
        row = await asyncio.wait_for(
            conn.fetchrow(
                """
                SELECT
                  pg_database_size(current_database())::bigint AS database_size_bytes,
                  COUNT(*) FILTER (WHERE state = 'active')::int AS active_connections,
                  COUNT(*) FILTER (WHERE state = 'idle')::int AS idle_connections
                FROM pg_stat_activity
                WHERE datname = current_database()
                """
            ),
            timeout=2.0,
        )
        return {
            "database_size_bytes": int(row["database_size_bytes"]) if row and row["database_size_bytes"] is not None else None,
            "active_connections": int(row["active_connections"]) if row and row["active_connections"] is not None else None,
            "idle_connections": int(row["idle_connections"]) if row and row["idle_connections"] is not None else None,
            "database_name": pg_name,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "database_size_bytes": None,
            "active_connections": None,
            "idle_connections": None,
            "database_name": pg_name,
            "error": str(exc),
        }
    finally:
        if conn is not None:
            try:
                await conn.close()
            except Exception:  # noqa: BLE001
                pass


def _tail_text_line(path: Path) -> Optional[str]:
    """Return the last non-empty line from a text file without loading it all."""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            end = handle.tell()
            if end == 0:
                return None
            cursor = end - 1
            chunks = bytearray()
            while cursor >= 0:
                handle.seek(cursor)
                byte = handle.read(1)
                if byte == b"\n" and chunks:
                    break
                if byte not in (b"\n", b"\r"):
                    chunks.extend(byte)
                cursor -= 1
            if not chunks:
                return None
            return bytes(reversed(chunks)).decode("utf-8", errors="replace").strip() or None
    except OSError:
        return None


def _extract_event_timestamp(record: Dict[str, Any]) -> Optional[str]:
    for key in ("timestamp", "created_at", "ts"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_existing_path(candidates: List[Path]) -> Path:
    expanded = [path.expanduser() for path in candidates if path]
    for path in expanded:
        if path.exists():
            return path
    return expanded[0]


def _telemetry_file_path(name: str) -> Path:
    state_root = Path(os.getenv("AI_STACK_STATE_ROOT", "/var/lib/ai-stack"))
    legacy_root = Path.home() / ".local/share/nixos-ai-stack/telemetry"
    aidb_dir = Path(os.getenv("AIDB_VSCODE_TELEMETRY_DIR", str(state_root / "aidb" / "telemetry")))
    hybrid_dir = Path(os.getenv("CONTINUOUS_LEARNING_TELEMETRY_DIR", str(state_root / "hybrid" / "telemetry")))
    mapping = {
        "aidb": _first_existing_path([
            Path(os.getenv("AIDB_TELEMETRY_PATH", "")) if os.getenv("AIDB_TELEMETRY_PATH") else None,
            aidb_dir / "aidb-events.jsonl",
            state_root / "aidb" / "telemetry" / "aidb-events.jsonl",
            legacy_root / "aidb-events.jsonl",
        ]),
        "hybrid": _first_existing_path([
            Path(os.getenv("HYBRID_TELEMETRY_PATH", "")) if os.getenv("HYBRID_TELEMETRY_PATH") else None,
            hybrid_dir / "hybrid-events.jsonl",
            state_root / "hybrid" / "telemetry" / "hybrid-events.jsonl",
            legacy_root / "hybrid-events.jsonl",
        ]),
        "ralph": _first_existing_path([
            Path(os.getenv("RALPH_TELEMETRY_PATH", "")) if os.getenv("RALPH_TELEMETRY_PATH") else None,
            state_root / "ralph" / "telemetry" / "ralph-events.jsonl",
            legacy_root / "ralph-events.jsonl",
        ]),
        "hint_feedback": _first_existing_path([
            Path(os.getenv("HINT_FEEDBACK_LOG_PATH", "/var/log/nixos-ai-stack/hint-feedback.jsonl")),
        ]),
        "query_gaps": _first_existing_path([
            Path(os.getenv("QUERY_GAPS_LOG_PATH", "/var/log/nixos-ai-stack/query-gaps.jsonl")),
        ]),
    }
    return mapping[name]


def _count_text_records(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def _tail_json_records(path: Path, limit: int = 20) -> List[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    records: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()[-limit:]
    except OSError:
        return []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _systemd_memory_current_bytes(unit: str) -> Optional[int]:
    try:
        result = subprocess.run(
            ["systemctl", "show", unit, "--property=MemoryCurrent", "--value"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        value = (result.stdout or "").strip()
        if result.returncode != 0 or not value:
            return None
        memory_bytes = int(value)
        return memory_bytes if memory_bytes >= 0 else None
    except (OSError, ValueError):
        return None


def _prometheus_metric_sum(metrics_text: str, metric_name: str) -> Optional[float]:
    total = 0.0
    matched = False
    prefix = f"{metric_name}"
    for line in metrics_text.splitlines():
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            total += float(parts[-1])
            matched = True
        except ValueError:
            continue
    return total if matched else None


def _prometheus_metric_scalar(metrics_text: str, metric_name: str) -> Optional[float]:
    prefix = f"{metric_name}"
    for line in metrics_text.splitlines():
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            return float(parts[-1])
        except ValueError:
            continue
    return None


async def _fetch_aidb_prometheus_summary() -> Dict[str, Any]:
    metrics_text = await fetch_text_with_fallback(f"{SERVICES['aidb']}/metrics", "")
    if not isinstance(metrics_text, str) or not metrics_text.strip():
        return {}
    request_total = _prometheus_metric_sum(metrics_text, "aidb_http_requests_total")
    error_total = _prometheus_metric_sum(metrics_text, "aidb_http_request_errors_total")
    process_memory_bytes = _prometheus_metric_scalar(metrics_text, "process_resident_memory_bytes")
    return {
        "request_total": int(round(request_total)) if request_total is not None else None,
        "error_total": int(round(error_total)) if error_total is not None else None,
        "process_memory_bytes": int(round(process_memory_bytes)) if process_memory_bytes is not None else None,
    }


def _list_model_inventory() -> Dict[str, Any]:
    """Best-effort model inventory lookup for dashboard cards.

    The dashboard service runs with a restricted systemd sandbox and may not be
    allowed to traverse the configured model directory. That must degrade to an
    empty inventory instead of taking down ``/api/ai/metrics`` entirely.
    """
    model_dir = Path(os.getenv("LLAMA_CPP_MODEL_DIR", "/var/lib/llama-cpp/models"))
    inventory: Dict[str, Any] = {
        "llama_cpp": [],
        "embeddings": [],
        "source_dir": str(model_dir),
        "available": False,
        "error": None,
    }

    try:
        if not model_dir.exists():
            inventory["error"] = "missing"
            return inventory
    except OSError as exc:
        logger.warning("model_inventory_exists_check_failed dir=%s error=%s", model_dir, exc)
        inventory["error"] = f"{type(exc).__name__}: {exc}"
        return inventory

    try:
        for path in sorted(model_dir.glob("*.gguf")):
            name = path.name
            if name.endswith(".dl.tmp"):
                continue
            if "embed" in name.lower():
                inventory["embeddings"].append(name)
            else:
                inventory["llama_cpp"].append(name)
        inventory["available"] = True
    except OSError as exc:
        logger.warning("model_inventory_scan_failed dir=%s error=%s", model_dir, exc)
        inventory["error"] = f"{type(exc).__name__}: {exc}"

    return inventory


def _collect_file_stats(path: Path) -> Dict[str, Any]:
    exists = path.exists()
    stats = path.stat() if exists else None
    last_line = _tail_text_line(path) if exists and path.is_file() and (stats.st_size or 0) > 0 else None
    last_event = None
    if last_line:
        try:
            payload = json.loads(last_line)
            if isinstance(payload, dict):
                last_event = {
                    "timestamp": _extract_event_timestamp(payload),
                    "keys": sorted(payload.keys())[:8],
                }
        except json.JSONDecodeError:
            last_event = {"timestamp": None, "keys": [], "raw": last_line[:160]}
    return {
        "path": str(path),
        "exists": exists,
        "bytes": int(stats.st_size) if stats else 0,
        "record_count": _count_text_records(path) if exists and path.is_file() else 0,
        "modified_at": datetime.utcfromtimestamp(stats.st_mtime).isoformat() if stats else None,
        "last_event_at": (last_event or {}).get("timestamp"),
        "last_event": last_event,
    }


def _build_feedback_pipeline_stats() -> Dict[str, Any]:
    files = {
        "aidb": _collect_file_stats(_telemetry_file_path("aidb")),
        "hybrid": _collect_file_stats(_telemetry_file_path("hybrid")),
        "ralph": _collect_file_stats(_telemetry_file_path("ralph")),
        "hint_feedback": _collect_file_stats(_telemetry_file_path("hint_feedback")),
        "query_gaps": _collect_file_stats(_telemetry_file_path("query_gaps")),
    }
    available = [meta for meta in files.values() if meta.get("exists")]
    return {
        "files": files,
        "summary": {
            "existing_files": len(available),
            "total_bytes": sum(int(meta.get("bytes") or 0) for meta in available),
            "total_records": sum(int(meta.get("record_count") or 0) for meta in available),
            "latest_activity_at": max(
                (meta.get("modified_at") for meta in available if meta.get("modified_at")),
                default=None,
            ),
        },
    }


def _load_keyword_signals() -> Optional[Dict[str, Any]]:
    candidates = [
        _repo_root() / "data" / "keyword-signals.json",
        Path.home() / ".local/share/nixos-system-dashboard/keyword-signals.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payload.setdefault("source_path", str(path))
            return payload
    return None


async def _prom_series(query: str) -> list[Dict[str, Any]]:
    """Execute an instant Prometheus query and return the vector results."""
    url = f"{service_endpoints.PROMETHEUS_URL}/api/v1/query"
    try:
        session = await get_http_session()
        async with session.get(url, params={"query": query}) as resp:
            if resp.status != 200:
                return []
            payload = await resp.json()
    except Exception:
        return []

    result = payload.get("data", {}).get("result", [])
    return result if isinstance(result, list) else []


async def _fetch_discovery_trends(hybrid_health: Dict[str, Any]) -> Dict[str, Any]:
    """Return richer capability-discovery counters and recent Prometheus-derived trends."""
    queries = {
        "invoked_1h": 'sum(increase(hybrid_capability_discovery_decisions_total{decision="invoked"}[1h]))',
        "cache_hits_1h": 'sum(increase(hybrid_capability_discovery_decisions_total{decision="cache_hit"}[1h]))',
        "skipped_1h": 'sum(increase(hybrid_capability_discovery_decisions_total{decision="skipped"}[1h]))',
        "errors_1h": 'sum(increase(hybrid_capability_discovery_decisions_total{decision="error"}[1h]))',
        "invoked_24h": 'sum(increase(hybrid_capability_discovery_decisions_total{decision="invoked"}[24h]))',
        "cache_hits_24h": 'sum(increase(hybrid_capability_discovery_decisions_total{decision="cache_hit"}[24h]))',
        "skipped_24h": 'sum(increase(hybrid_capability_discovery_decisions_total{decision="skipped"}[24h]))',
        "errors_24h": 'sum(increase(hybrid_capability_discovery_decisions_total{decision="error"}[24h]))',
        "latency_p95_ms": 'histogram_quantile(0.95, sum(rate(hybrid_capability_discovery_latency_seconds_bucket[1h])) by (le)) * 1000',
    }
    values = await asyncio.gather(*(_prom_scalar(query) for query in queries.values()))
    trend = dict(zip(queries.keys(), values))
    reason_rows = await _prom_series(
        "topk(5, sum by (reason) (hybrid_capability_discovery_decisions_total))"
    )
    top_reasons = []
    for row in reason_rows:
        metric = row.get("metric", {})
        value = row.get("value", [None, None])
        try:
            count = float(value[1])
        except (IndexError, TypeError, ValueError):
            count = 0.0
        top_reasons.append(
            {
                "reason": metric.get("reason", "unknown"),
                "count": int(round(count)),
            }
        )

    discovery = hybrid_health.get("capability_discovery", {}) if isinstance(hybrid_health, dict) else {}
    invoked = int(discovery.get("invoked", 0) or 0)
    skipped = int(discovery.get("skipped", 0) or 0)
    cache_hits = int(discovery.get("cache_hits", 0) or 0)
    errors = int(discovery.get("errors", 0) or 0)
    total = invoked + skipped + cache_hits + errors
    return {
        "lifetime": {
            "invoked": invoked,
            "skipped": skipped,
            "cache_hits": cache_hits,
            "errors": errors,
            "total_decisions": total,
            "cache_hit_rate_pct": round((cache_hits / total) * 100, 2) if total else 0.0,
            "last_decision": discovery.get("last_decision"),
            "last_reason": discovery.get("last_reason"),
        },
        "recent": {
            "one_hour": {
                "invoked": int(round(trend.get("invoked_1h") or 0)),
                "cache_hits": int(round(trend.get("cache_hits_1h") or 0)),
                "skipped": int(round(trend.get("skipped_1h") or 0)),
                "errors": int(round(trend.get("errors_1h") or 0)),
            },
            "twenty_four_hours": {
                "invoked": int(round(trend.get("invoked_24h") or 0)),
                "cache_hits": int(round(trend.get("cache_hits_24h") or 0)),
                "skipped": int(round(trend.get("skipped_24h") or 0)),
                "errors": int(round(trend.get("errors_24h") or 0)),
            },
            "latency_p95_ms": round(float(trend.get("latency_p95_ms") or 0.0), 2),
            "top_reasons": top_reasons,
        },
    }


async def _aider_wrapper_task_summary() -> Dict[str, Any]:
    """Fetch queue depth and last terminal task state from aider-wrapper."""
    summary = await fetch_with_fallback(f"{SERVICES['aider_wrapper']}/tasks/summary", None)
    if not isinstance(summary, dict):
        return {"active_tasks": 0, "last_task_status": "unknown", "last_task_id": None}
    return {
        "active_tasks": int(summary.get("active_tasks", 0) or 0),
        "last_task_status": str(summary.get("last_task_status", "unknown")),
        "last_task_id": summary.get("last_task_id"),
    }


def render_prometheus_metrics() -> str:
    """Return dashboard probe metrics in Prometheus exposition text format."""
    lines = [
        "# HELP redis_ping_ok Redis connectivity probe (1=healthy, 0=unhealthy)",
        "# TYPE redis_ping_ok gauge",
        f"redis_ping_ok {_REDIS_PING_OK_GAUGE:.1f}",
        "# HELP postgres_query_ok PostgreSQL SELECT 1 probe (1=healthy, 0=unhealthy)",
        "# TYPE postgres_query_ok gauge",
        f"postgres_query_ok {_POSTGRES_QUERY_OK_GAUGE:.1f}",
        "",
    ]
    return "\n".join(lines)


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
    normalized = tuple(sorted(set(collections)))
    if not normalized:
        return {}

    now = time.time()
    cached_payload = _QDRANT_POINTS_CACHE.get("payload")
    cached_collections = tuple(_QDRANT_POINTS_CACHE.get("collections", tuple()))
    if (
        isinstance(cached_payload, dict)
        and cached_collections == normalized
        and (now - float(_QDRANT_POINTS_CACHE.get("ts", 0.0))) < QDRANT_POINTS_CACHE_TTL_SECONDS
    ):
        return dict(cached_payload)

    infos = await asyncio.gather(
        *(fetch_with_fallback(f"{SERVICES['qdrant']}/collections/{name}", {}) for name in normalized)
    )
    results: Dict[str, int] = {}
    for name, info in zip(normalized, infos):
        points = info.get("result", {}).get("points_count", 0) if isinstance(info, dict) else 0
        results[name] = points if isinstance(points, int) else 0

    _QDRANT_POINTS_CACHE["ts"] = now
    _QDRANT_POINTS_CACHE["collections"] = normalized
    _QDRANT_POINTS_CACHE["payload"] = dict(results)
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
    feedback_pipeline = _build_feedback_pipeline_stats()
    files = feedback_pipeline.get("files", {})
    hint_feedback_path = _telemetry_file_path("hint_feedback")
    hint_records = _tail_json_records(hint_feedback_path, limit=50)
    hint_scores = [
        float(record.get("score"))
        for record in hint_records
        if isinstance(record.get("score"), (int, float))
    ]
    high_value_events = sum(
        1
        for record in hint_records
        if record.get("helpful") is True or float(record.get("score", 0) or 0) >= 0.5
    )
    finetune_path = Path(
        os.getenv("FINETUNE_DATA_PATH", "/var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl")
    )
    finetune_records = _count_text_records(finetune_path)

    backpressure = stats.setdefault("backpressure", {})
    file_sizes = backpressure.setdefault("file_sizes", {})
    file_sizes["aidb-events.jsonl"] = int(files.get("aidb", {}).get("bytes") or 0)
    file_sizes["hybrid-events.jsonl"] = int(files.get("hybrid", {}).get("bytes") or 0)
    file_sizes["ralph-events.jsonl"] = int(files.get("ralph", {}).get("bytes") or 0)
    file_sizes["hint-feedback.jsonl"] = int(files.get("hint_feedback", {}).get("bytes") or 0)
    file_sizes["query-gaps.jsonl"] = int(files.get("query_gaps", {}).get("bytes") or 0)

    activity = {
        "aidb_events": int(files.get("aidb", {}).get("record_count") or 0),
        "hybrid_events": int(files.get("hybrid", {}).get("record_count") or 0),
        "ralph_events": int(files.get("ralph", {}).get("record_count") or 0),
        "hint_feedback_events": int(files.get("hint_feedback", {}).get("record_count") or 0),
        "query_gap_events": int(files.get("query_gaps", {}).get("record_count") or 0),
        "high_value_events": high_value_events,
        "average_feedback_score": round(sum(hint_scores) / len(hint_scores), 3) if hint_scores else None,
        "finetune_records": finetune_records,
        "latest_feedback_at": files.get("hint_feedback", {}).get("last_event_at") or files.get("hint_feedback", {}).get("modified_at"),
    }
    activity["total_events"] = sum(
        activity[key]
        for key in ("aidb_events", "hybrid_events", "ralph_events", "hint_feedback_events", "query_gap_events")
    )
    stats["activity"] = activity

    if int(stats.get("total_metrics_tracked") or 0) == 0 and activity["total_events"] > 0:
        stats["total_metrics_tracked"] = activity["total_events"]
    if int(stats.get("finetuning_dataset_size") or 0) == 0 and finetune_records > 0:
        stats["finetuning_dataset_size"] = finetune_records
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


@router.get("/discovery/signals")
async def get_discovery_signals() -> Dict[str, Any]:
    """Return keyword/discovery signal data from the current local source when available."""
    payload = _load_keyword_signals()
    if payload is None:
        raise HTTPException(status_code=404, detail="keyword signals unavailable")
    return payload


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
        "prsi-orchestrator.py",
        "run-ai-harness-phase-plan.sh",
        "run-acceptance-checks.sh",
        "sync-ai-research-knowledge.sh",
        "update-ai-research-now.sh",
        "install-ai-research-sync-timer.sh",
        "sync-aidb-library-catalog.sh",
        "run-harness-improvement-pass.sh",
    ]
    script_status = [_safe_script_status(name) for name in scripts]
    operational_count = sum(1 for item in script_status if item["exists"] and item["executable"])
    improvement = await _fetch_improvement_pass_stats(hours=24)

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
            "improvement_pass": improvement,
        },
    }


@router.post("/harness/maintenance/run")
async def run_harness_maintenance(payload: HarnessMaintenancePayload) -> Dict[str, Any]:
    """Run allowlisted harness maintenance actions from dashboard."""
    action_map: Dict[str, tuple[str, List[str], int]] = {
        "phase_plan": ("run-ai-harness-phase-plan.sh", [], 180),
        "research_sync": ("sync-ai-research-knowledge.sh", [], 180),
        "catalog_sync": ("sync-aidb-library-catalog.sh", [], 180),
        "acceptance_checks": ("run-acceptance-checks.sh", [], 240),
        "improvement_pass": ("run-harness-improvement-pass.sh", [], 420),
    }
    script_name, args, timeout_seconds = action_map[payload.action]
    result = await _run_harness_script(script_name, args=args, timeout_seconds=timeout_seconds)
    improvement_summary = _extract_improvement_summary(result.get("stdout", ""))
    metadata = {
        "action": payload.action,
        "script": script_name,
        "success": bool(result.get("success", False)),
        "exit_code": int(result.get("exit_code", -1)),
        "duration_ms": int(result.get("duration_ms", 0) or 0),
    }
    if improvement_summary:
        metadata.update(improvement_summary)
    await _record_telemetry_event(
        event_type="harness_improvement_pass" if payload.action == "improvement_pass" else "harness_maintenance_action",
        event_category="usage",
        severity="info" if result.get("success") else "warning",
        source="command-center-dashboard",
        message=f"Dashboard maintenance action {payload.action} completed (exit={result.get('exit_code')})",
        metadata=metadata,
        duration_ms=int(result.get("duration_ms", 0) or 0),
    )
    return {
        "action": payload.action,
        "improvement_summary": improvement_summary or None,
        **result,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/prsi/actions")
async def get_prsi_actions(status: Optional[str] = None, risk: Optional[str] = None) -> Dict[str, Any]:
    """List PRSI queued actions and counts."""
    args = ["list"]
    if status:
        args.extend(["--status", status])
    if risk:
        args.extend(["--risk", risk])
    result = await _run_prsi_orchestrator(args, timeout_seconds=45)
    if not result["ok"]:
        raise HTTPException(status_code=503, detail=result["stderr"] or "prsi_list_failed")
    payload = result.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    return {
        "status": "ok",
        "prsi": payload,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/prsi/sync")
async def sync_prsi_actions(since: str = "1d") -> Dict[str, Any]:
    """Sync PRSI queue from aq-report structured actions."""
    result = await _run_prsi_orchestrator(["sync", "--since", since], timeout_seconds=60)
    if not result["ok"]:
        raise HTTPException(status_code=503, detail=result["stderr"] or "prsi_sync_failed")
    return {
        "status": "ok",
        "result": result.get("payload", {}),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/prsi/approve")
async def approve_prsi_action(payload: PRSIApprovalPayload) -> Dict[str, Any]:
    """Approve or reject a PRSI queued action."""
    args = [payload.decision, "--id", payload.action_id, "--by", payload.by]
    if payload.note:
        args.extend(["--note", payload.note])
    result = await _run_prsi_orchestrator(args, timeout_seconds=30)
    if not result["ok"]:
        raise HTTPException(status_code=503, detail=result["stderr"] or "prsi_approval_failed")
    return {
        "status": "ok",
        "result": result.get("payload", {}),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/prsi/execute")
async def execute_prsi_actions(payload: PRSIExecutePayload) -> Dict[str, Any]:
    """Execute approved PRSI actions (optionally auto-sync first)."""
    sync_result = None
    if payload.auto_sync:
        sync_result = await _run_prsi_orchestrator(["sync", "--since", "1d"], timeout_seconds=60)
        if not sync_result["ok"]:
            raise HTTPException(status_code=503, detail=sync_result["stderr"] or "prsi_sync_before_execute_failed")
    args = ["execute", "--limit", str(payload.limit)]
    if payload.dry_run:
        args.append("--dry-run")
    exec_result = await _run_prsi_orchestrator(args, timeout_seconds=240)
    if not exec_result["ok"]:
        raise HTTPException(status_code=503, detail=exec_result["stderr"] or "prsi_execute_failed")
    await _record_telemetry_event(
        event_type="prsi_execute",
        event_category="usage",
        severity="info",
        source="command-center-dashboard",
        message=f"PRSI execute invoked (limit={payload.limit}, dry_run={payload.dry_run})",
        metadata={
            "auto_sync": payload.auto_sync,
            "sync_result": sync_result.get("payload", {}) if isinstance(sync_result, dict) else None,
            "execute_result": exec_result.get("payload", {}),
        },
    )
    return {
        "status": "ok",
        "sync_result": sync_result.get("payload", {}) if isinstance(sync_result, dict) else None,
        "execute_result": exec_result.get("payload", {}),
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


async def _fetch_prsi_stats() -> Dict[str, Any]:
    """Fetch PRSI (Pessimistic Recursive Self-Improvement) stats from PostgreSQL and JSONL log.

    Queries:
    - query_gaps table: gap_count, unique_gaps, last_gap_at
    - learning_feedback table: negative_feedback_count, total_feedback_count
    - /var/log/nixos-ai-stack/query-gaps.jsonl: synced_gaps (line count)
    """
    if not _ASYNCPG_AVAILABLE:
        return {
            "available": False,
            "gap_count": 0,
            "unique_gaps": 0,
            "negative_feedback_count": 0,
            "total_feedback_count": 0,
            "synced_gaps": 0,
            "last_gap_at": None,
            "sync_loop_active": False,
        }

    pg_user = os.getenv("AIDB_DB_USER", "aidb")
    pg_name = os.getenv("AIDB_DB_NAME", "aidb")
    dsn = os.getenv(
        "AIDB_DB_URL",
        f"postgresql://{pg_user}@{service_endpoints.SERVICE_HOST}:{service_endpoints.POSTGRES_PORT}/{pg_name}",
    )
    # Augment DSN with password from file if available and DSN has no password.
    pg_pw_file = os.getenv("POSTGRES_PASSWORD_FILE")
    if pg_pw_file and "://" in dsn and "@" in dsn and ":" not in dsn.split("@")[0]:
        try:
            pw = open(pg_pw_file).read().strip()  # noqa: WPS515
            dsn = dsn.replace(f"://{pg_user}@", f"://{pg_user}:{pw}@", 1)
        except OSError:
            pass

    conn = None
    try:
        conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=3.0)

        # Query query_gaps table
        gap_row = await asyncio.wait_for(
            conn.fetchrow(
                "SELECT COUNT(*), COUNT(DISTINCT query_text), MAX(created_at) FROM query_gaps"
            ),
            timeout=2.0,
        )
        gap_count = gap_row[0] or 0
        unique_gaps = gap_row[1] or 0
        last_gap_at = gap_row[2].isoformat() if gap_row[2] else None

        # Query learning_feedback table
        negative_feedback_row = await asyncio.wait_for(
            conn.fetchrow("SELECT COUNT(*) FROM learning_feedback WHERE rating < 0"),
            timeout=2.0,
        )
        negative_feedback_count = negative_feedback_row[0] or 0

        total_feedback_row = await asyncio.wait_for(
            conn.fetchrow("SELECT COUNT(*) FROM learning_feedback"),
            timeout=2.0,
        )
        total_feedback_count = total_feedback_row[0] or 0

        # Count lines in JSONL file
        jsonl_path = Path("/var/log/nixos-ai-stack/query-gaps.jsonl")
        synced_gaps = 0
        try:
            synced_gaps = sum(1 for _ in jsonl_path.open(encoding="utf-8"))
        except FileNotFoundError:
            synced_gaps = 0
        except OSError:
            synced_gaps = 0

        return {
            "available": True,
            "gap_count": int(gap_count),
            "unique_gaps": int(unique_gaps),
            "negative_feedback_count": int(negative_feedback_count),
            "total_feedback_count": int(total_feedback_count),
            "synced_gaps": synced_gaps,
            "last_gap_at": last_gap_at,
            "sync_loop_active": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "gap_count": 0,
            "unique_gaps": 0,
            "negative_feedback_count": 0,
            "total_feedback_count": 0,
            "synced_gaps": 0,
            "last_gap_at": None,
            "sync_loop_active": False,
            "error": str(exc),
        }
    finally:
        if conn is not None:
            try:
                await conn.close()
            except Exception:  # noqa: BLE001
                pass


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
    now = time.time()
    cached_payload = _AI_METRICS_CACHE.get("payload")
    if (
        isinstance(cached_payload, dict)
        and (now - float(_AI_METRICS_CACHE.get("ts", 0.0))) < AI_METRICS_CACHE_TTL_SECONDS
    ):
        return cached_payload

    # Fire all independent fetches and infra probes concurrently.
    (
        aidb_health,
        aidb_metrics_summary,
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
        redis_runtime,
        postgres_runtime,
        aider_task_summary,
        prsi_stats,
    ) = await asyncio.gather(
        fetch_with_fallback(f"{SERVICES['aidb']}/health", {}),
        _fetch_aidb_prometheus_summary(),
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
        _redis_runtime_probe(),
        _postgres_runtime_probe(),
        _aider_wrapper_task_summary(),
        _fetch_prsi_stats(),
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
    model_inventory = _list_model_inventory()
    llama_memory_bytes = _systemd_memory_current_bytes("llama-cpp.service")
    embedding_memory_bytes = _systemd_memory_current_bytes("llama-cpp-embed.service")

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
    feedback_pipeline = _build_feedback_pipeline_stats()
    discovery_metrics = await _fetch_discovery_trends(hybrid_health)

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
    global _REDIS_PING_OK_GAUGE, _POSTGRES_QUERY_OK_GAUGE
    _REDIS_PING_OK_GAUGE = redis_ok_gauge
    _POSTGRES_QUERY_OK_GAUGE = postgres_ok_gauge
    logger.info(
        "infra_probe gauge redis_ping_ok=%.0f postgres_query_ok=%.0f",
        redis_ok_gauge,
        postgres_ok_gauge,
    )

    payload = {
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
                    "collection_names": collection_names,
                    "total_vectors": total_points,
                },
            },
            "llama_cpp": {
                "service": "llama_cpp",
                "status": llama_status,
                "port": service_endpoints.LLAMA_CPP_PORT,
                "model": llama_model,
                "cached_models": model_inventory.get("llama_cpp", []),
                "cached_models_count": len(model_inventory.get("llama_cpp", [])),
                "model_inventory_available": bool(model_inventory.get("available")),
                "model_inventory_error": model_inventory.get("error"),
                "memory_mb": round(llama_memory_bytes / (1024 * 1024), 1) if llama_memory_bytes else None,
            },
            "embeddings": {
                "service": "embeddings",
                "status": embeddings_status,
                "port": service_endpoints.EMBEDDINGS_PORT,
                "model": embeddings_model,
                "dimensions": embeddings_dimensions,
                "endpoint": SERVICES["embeddings"],
                "models": model_inventory.get("embeddings", []),
                "model_inventory_available": bool(model_inventory.get("available")),
                "model_inventory_error": model_inventory.get("error"),
                "request_total": None,
                "error_total": None,
                "memory_mb": round(embedding_memory_bytes / (1024 * 1024), 1) if embedding_memory_bytes else None,
                "metrics_exported": False,
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
                "active_tasks": aider_task_summary.get("active_tasks", 0),
                "last_task_status": aider_task_summary.get("last_task_status", "unknown"),
                "last_task_id": aider_task_summary.get("last_task_id"),
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
        "database_metrics": {
            "postgresql": {
                "status": "online" if postgres_probe.get("postgres_query_ok") else "offline",
                "database_name": postgres_runtime.get("database_name"),
                "database_size_bytes": postgres_runtime.get("database_size_bytes"),
                "active_connections": postgres_runtime.get("active_connections"),
                "idle_connections": postgres_runtime.get("idle_connections"),
                "latency_ms": postgres_probe.get("postgres_latency_ms"),
                "error": postgres_runtime.get("error") or postgres_probe.get("postgres_error"),
            },
            "redis": {
                "status": "online" if redis_probe.get("redis_ping_ok") else "offline",
                "keys": redis_runtime.get("keys"),
                "memory_bytes": redis_runtime.get("memory_bytes"),
                "memory_human": redis_runtime.get("memory_human"),
                "connected_clients": redis_runtime.get("connected_clients"),
                "latency_ms": redis_probe.get("redis_latency_ms"),
                "error": redis_runtime.get("error") or redis_probe.get("redis_error"),
            },
            "qdrant": {
                "status": qdrant_status,
                "collection_count": len(collection_names),
                "total_vectors": total_points,
                "collections": collection_points,
            },
        },
        "feedback_pipeline": feedback_pipeline,
        "hybrid_discovery": discovery_metrics,
        "knowledge_base": {
            "total_points": total_points,
            "real_embeddings_percent": 100 if total_points > 0 else 0,
            "collections": knowledge_collections,
            "collection_names": collection_names,
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
        "telemetry": {
            "aidb": aidb_metrics_summary,
        },
        "harness": {
            "stats": harness_stats,
            "scorecard": harness_scorecard,
            "overview": harness_overview,
        },
        "prsi": {
            "available": prsi_stats.get("available", False),
            "gap_count": prsi_stats.get("gap_count", 0),
            "unique_gaps": prsi_stats.get("unique_gaps", 0),
            "negative_feedback_count": prsi_stats.get("negative_feedback_count", 0),
            "total_feedback_count": prsi_stats.get("total_feedback_count", 0),
            "synced_gaps": prsi_stats.get("synced_gaps", 0),
            "last_gap_at": prsi_stats.get("last_gap_at"),
            "sync_loop_active": prsi_stats.get("sync_loop_active", False),
        },
        "validations": {
            "model_inventory": {
                "available": bool(model_inventory.get("available")),
                "source_dir": model_inventory.get("source_dir"),
                "error": model_inventory.get("error"),
            },
            "qdrant_collections": {
                "available": bool(collection_names),
                "count": len(collection_names),
                "total_vectors": total_points,
            },
        },
    }
    _AI_METRICS_CACHE["ts"] = now
    _AI_METRICS_CACHE["payload"] = payload
    return payload


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
            "nixos_docs": {"port": service_endpoints.NIXOS_DOCS_PORT, "url": service_endpoints.NIXOS_DOCS_URL},
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


async def _aq_report_snapshot(ttl_seconds: int = 30) -> Dict[str, Any]:
    """Return cached aq-report JSON snapshot for dashboard internals."""
    now = time.time()
    cached = _AQ_REPORT_CACHE.get("payload")
    if cached and (now - float(_AQ_REPORT_CACHE.get("ts", 0.0))) < ttl_seconds:
        return cached

    report_script = _script_path("aq-report")
    if not report_script.exists():
        payload = {}
    else:
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                [str(report_script), "--since=7d", "--format=json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=12,
                cwd=str(_repo_root()),
            )
            if proc.returncode == 0:
                payload = json.loads(proc.stdout or "{}")
                if not isinstance(payload, dict):
                    payload = {}
            else:
                payload = {}
        except Exception:  # noqa: BLE001
            payload = {}

    _AQ_REPORT_CACHE["ts"] = now
    _AQ_REPORT_CACHE["payload"] = payload
    return payload


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

    hits, misses, local_sel, total_sel, before_sum, after_sum, report = await asyncio.gather(
        _prom_scalar(hits_q),
        _prom_scalar(misses_q),
        _prom_scalar(local_q),
        _prom_scalar(total_q),
        _prom_scalar(before_q),
        _prom_scalar(after_q),
        _aq_report_snapshot(),
    )

    h = hits or 0.0
    m = misses or 0.0
    embedding_cache_hit_rate_pct = (
        round((h / (h + m) * 100), 2)
        if (hits is not None or misses is not None) and (h + m) > 0
        else None
    )

    loc = local_sel or 0.0
    tot = total_sel or 0.0
    llm_routing_local_pct = (
        round((loc / tot * 100), 2)
        if (local_sel is not None or total_sel is not None) and tot > 0
        else None
    )

    b = before_sum or 0.0
    a = after_sum or 0.0
    tokens_compressed_last_hour = (
        round(max(b - a, 0.0), 0)
        if before_sum is not None or after_sum is not None
        else None
    )

    hint_adoption_pct = (
        float(report.get("hint_adoption", {}).get("adoption_pct"))
        if isinstance(report, dict) and report.get("hint_adoption", {}).get("adoption_pct") is not None
        else None
    )
    eval_latest_pct = (
        float(report.get("eval_trend", {}).get("latest_pct"))
        if isinstance(report, dict) and report.get("eval_trend", {}).get("latest_pct") is not None
        else None
    )
    tool_rows = (
        len(report.get("tool_performance", {}))
        if isinstance(report, dict) and isinstance(report.get("tool_performance"), dict)
        else None
    )
    query_gap_count = (
        len(report.get("query_gaps", []))
        if isinstance(report, dict) and isinstance(report.get("query_gaps"), list)
        else None
    )

    return {
        "embedding_cache_hit_rate_pct": embedding_cache_hit_rate_pct,
        "llm_routing_local_pct": llm_routing_local_pct,
        "tokens_compressed_last_hour": tokens_compressed_last_hour,
        "hint_adoption_pct": round(hint_adoption_pct, 2) if hint_adoption_pct is not None else None,
        "eval_latest_pct": round(eval_latest_pct, 2) if eval_latest_pct is not None else None,
        "tool_performance_rows": int(tool_rows) if tool_rows is not None else None,
        "query_gap_count": int(query_gap_count) if query_gap_count is not None else None,
        "availability": {
            "embedding_cache_hit_rate": hits is not None or misses is not None,
            "llm_routing_local": local_sel is not None or total_sel is not None,
            "tokens_compressed_last_hour": before_sum is not None or after_sum is not None,
            "aq_report": isinstance(report, dict) and bool(report),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/security/audit")
async def get_security_audit() -> Dict[str, Any]:
    """Security audit results from Phase 11.5 weekly pip-audit + npm audit.

    Returns the latest security audit JSON report if available.
    The audit runs weekly via systemd timer (ai-security-audit.timer).

    Response fields:
    - status: "ok" | "findings" | "no_report"
    - generated_at: ISO timestamp of last audit run
    - summary: pip and npm vulnerability counts
    - high_severity_alert: present if CVSS >= threshold found
    - report_path: path to full JSON report file
    """
    # Security audit report directory (Phase 11.5.1)
    audit_dir = Path(os.getenv(
        "AI_SECURITY_AUDIT_DIR",
        Path.home() / ".local" / "share" / "nixos-ai-stack" / "security"
    ))

    latest_report = audit_dir / "latest-security-audit.json"
    high_alert = audit_dir / "latest-high-cve-alert.json"
    npm_dir = Path(os.getenv("AI_NPM_SECURITY_DIR", str(audit_dir / "npm")))
    npm_latest_report = npm_dir / "latest-npm-security.json"
    npm_quarantine = npm_dir / "quarantine-state.json"
    npm_incidents = npm_dir / "incidents.jsonl"

    report_data: Dict[str, Any] = {
        "status": "no_report",
        "generated_at": "unknown",
        "summary": {},
    }
    message: Optional[str] = None
    if not latest_report.exists():
        message = "No security audit report found. Run manually or wait for weekly timer."
    else:
        try:
            with open(latest_report) as f:
                report_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read security audit report: {e}")
            report_data = {
                "status": "error",
                "generated_at": "unknown",
                "summary": {},
            }
            message = f"Failed to parse audit report: {str(e)}"

    # Check for high severity alert
    high_severity_alert = None
    if high_alert.exists():
        try:
            with open(high_alert) as f:
                high_severity_alert = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    npm_monitor: Dict[str, Any] = {
        "status": "no_report",
        "report_path": str(npm_latest_report),
        "quarantine_active": False,
        "quarantine_state": None,
        "recent_incidents": [],
    }
    if npm_latest_report.exists():
        try:
            with open(npm_latest_report) as f:
                npm_report_data = json.load(f)
            npm_monitor["status"] = str(npm_report_data.get("status", "unknown"))
            npm_monitor["generated_at"] = npm_report_data.get("generated_at")
            npm_monitor["severity_counts"] = npm_report_data.get("severity_counts", {})
            npm_monitor["summary"] = npm_report_data.get("summary", {})
        except (json.JSONDecodeError, IOError) as e:
            npm_monitor["status"] = "error"
            npm_monitor["message"] = f"Failed to parse npm monitor report: {str(e)}"

    if npm_quarantine.exists():
        try:
            with open(npm_quarantine) as f:
                quarantine_data = json.load(f)
            npm_monitor["quarantine_state"] = quarantine_data
            npm_monitor["quarantine_active"] = (
                str(quarantine_data.get("status", "")).lower() == "active"
            )
        except (json.JSONDecodeError, IOError):
            pass

    if npm_incidents.exists():
        try:
            # Keep payload small for dashboard polling cadence.
            lines = npm_incidents.read_text().splitlines()[-20:]
            parsed = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    parsed.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            npm_monitor["recent_incidents"] = parsed
        except OSError:
            pass

    payload = {
        "status": report_data.get("status", "unknown"),
        "generated_at": report_data.get("generated_at", "unknown"),
        "summary": report_data.get("summary", {}),
        "high_severity_alert": high_severity_alert,
        "npm_monitor": npm_monitor,
        "report_path": str(latest_report),
        "timestamp": datetime.utcnow().isoformat(),
    }
    if message:
        payload["message"] = message
    return payload
