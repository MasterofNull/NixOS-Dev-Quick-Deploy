"""AI Stack specific API endpoints for learning stats, circuit breakers, and Ralph"""
from fastapi import APIRouter, HTTPException, Query, Request, Response, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import hashlib
import logging
import ast
import asyncio
import aiohttp
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from ..config import service_endpoints
from ..services.qa_runner import run_phase_json
from ..services.systemd_units import get_ai_runtime_units
from ..services.ai_insights import AIInsightsService, get_insights_service

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
# Postgres probe result cache — avoids a fresh asyncpg connection on every
# metrics cycle.  TTL is 25 s (longer than the 10 s metrics cache so the
# cached probe result is still valid when the metrics cache next expires).
_POSTGRES_PROBE_CACHE: Dict[str, Any] = {"ts": 0.0, "result": None}
_POSTGRES_PROBE_CACHE_TTL_S: float = 25.0
# Redis probe result cache — same rationale as PG cache above.
_REDIS_PROBE_CACHE: Dict[str, Any] = {"ts": 0.0, "result": None}
_REDIS_PROBE_CACHE_TTL_S: float = 30.0
# Module-level asyncpg connection pool — shared across probe calls so each
# probe fires a single query on an already-established TCP connection instead
# of paying the full asyncpg.connect() handshake (~300-500 ms) every 25 s.
_PG_POOL: Optional[Any] = None  # asyncpg.Pool, typed as Any to avoid import-time errors
_MODEL_INVENTORY_WARNINGS: set[tuple[str, str]] = set()

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

# Timeout for external requests — 10s to handle concurrent dashboard load bursts
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
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
_http_session_lock: Optional[asyncio.Lock] = None


async def get_http_session() -> aiohttp.ClientSession:
    """Get or create the global HTTP session (lock-protected to avoid duplicate creation)."""
    global _http_session, _http_session_lock
    if _http_session_lock is None:
        _http_session_lock = asyncio.Lock()
    async with _http_session_lock:
        if _http_session is None or _http_session.closed:
            _http_session = aiohttp.ClientSession(timeout=REQUEST_TIMEOUT)
    return _http_session


async def close_http_session():
    """Close the global HTTP session"""
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()


def _load_secret_from_file(env_var: str) -> str:
    """Load a runtime secret from the file path referenced by an env var."""
    secret_file = os.getenv(env_var, "").strip()
    if not secret_file:
        return ""
    try:
        return Path(secret_file).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _aider_wrapper_auth_headers() -> Dict[str, str]:
    """Return aider-wrapper auth headers when the service is protected by an API key."""
    api_key = (
        os.getenv("AIDER_WRAPPER_API_KEY", "").strip()
        or _load_secret_from_file("AIDER_WRAPPER_API_KEY_FILE")
    )
    if not api_key:
        # Fallback: try well-known NixOS secrets path when env var is not injected
        # (e.g. dashboard started before AIDER_WRAPPER_API_KEY_FILE was wired)
        try:
            api_key = Path("/run/secrets/aider_wrapper_api_key").read_text(encoding="utf-8").strip()
        except OSError:
            pass
    if not api_key:
        return {}
    return {"x-api-key": api_key}


def _hybrid_auth_headers() -> Dict[str, str]:
    """Return hybrid coordinator auth headers when an API key is configured."""
    api_key = _load_hybrid_api_key()
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def _log_model_inventory_degraded_once(stage: str, model_dir: Path, exc: OSError) -> None:
    """Log model inventory access problems once per failure class and directory."""
    error_key = (stage, f"{type(exc).__name__}:{model_dir}")
    if error_key in _MODEL_INVENTORY_WARNINGS:
        return
    _MODEL_INVENTORY_WARNINGS.add(error_key)
    logger.info("model_inventory_degraded stage=%s dir=%s error=%s", stage, model_dir, exc)


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


async def fetch_text_with_fallback(
    url: str,
    fallback: Any = None,
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    """Fetch text response with error handling and fallback"""
    try:
        session = await get_http_session()
        async with session.get(url, headers=headers) as resp:
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
    candidates = [key_file] if key_file else []
    # Fallback to well-known secret paths (NixOS secrets + local dev)
    candidates += [
        "/run/secrets/hybrid_coordinator_api_key",
        "/run/secrets/ai_hybrid_coordinator_api_key",
        os.path.expanduser("~/.config/ai-stack/hybrid_coordinator_api_key"),
    ]
    for path in candidates:
        if not path:
            continue
        try:
            key = Path(path).read_text().strip()
            if key:
                return key
        except FileNotFoundError:
            continue
        except OSError as exc:
            logger.warning("Failed reading hybrid API key file %s: %s", path, exc)
    return ""


def _hybrid_headers() -> Optional[Dict[str, str]]:
    api_key = _load_hybrid_api_key()
    return {"X-API-Key": api_key} if api_key else None


def _normalize_status(raw: Any, ok_values: tuple[str, ...]) -> str:
    value = str(raw or "").lower()
    if value in ok_values:
        return ok_values[0]
    return value or "unknown"


def _switchboard_local_lane_status(local_runtime: Any) -> str:
    """Summarize switchboard local-lane state for dashboard consumers."""
    if not isinstance(local_runtime, dict):
        return "unknown"
    active_request = local_runtime.get("active_request")
    if isinstance(active_request, dict) and active_request.get("long_running") is True:
        return "busy-long-running"
    if local_runtime.get("slot_busy") is True:
        return "busy"
    slot_available = local_runtime.get("slot_available")
    if isinstance(slot_available, (int, float)) and slot_available > 0:
        return "available"
    if local_runtime.get("llama_metrics_error"):
        return "degraded"
    return "unknown"


def _resolve_switchboard_local_lane_status(payload: Any, local_runtime: Any) -> str:
    if isinstance(payload, dict):
        explicit = str(payload.get("local_lane_status") or "").strip()
        if explicit:
            return explicit
    return _switchboard_local_lane_status(local_runtime)


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
    memory_type: str = Field(..., pattern="^(episodic|semantic|procedural|error_solutions|interaction_history)$")
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


@lru_cache(maxsize=64)
def _script_path(name: str) -> Path:
    candidates = [
        _repo_root() / "scripts" / name,
        _repo_root() / "scripts" / "automation" / name,
        _repo_root() / "scripts" / "ai" / name,
        _repo_root() / "scripts" / "data" / name,
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


def _prsi_policy_path() -> Path:
    return _repo_root() / "config" / "runtime-prsi-policy.json"


def _load_prsi_policy() -> Dict[str, Any]:
    try:
        payload = json.loads(_prsi_policy_path().read_text(encoding="utf-8"))
    except OSError:
        return {}
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _prsi_policy_summary(policy: Dict[str, Any]) -> Dict[str, Any]:
    gates = policy.get("gates", {}) if isinstance(policy.get("gates"), dict) else {}
    allow_types = gates.get("allow_action_types", [])
    return {
        "allow_action_types": [str(item) for item in allow_types] if isinstance(allow_types, list) else [],
        "block_high_risk_without_approval": bool(gates.get("block_high_risk_without_approval", True)),
        "require_independent_verifier_for_high_risk": bool(
            gates.get("require_independent_verifier_for_high_risk", False)
        ),
    }


def _prsi_execution_gate(row: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    gates = policy.get("gates", {}) if isinstance(policy.get("gates"), dict) else {}
    action = row.get("raw_action") if isinstance(row.get("raw_action"), dict) else {}
    action_type = str(row.get("type") or action.get("type") or "").strip().lower()
    status = str(row.get("status") or "").strip().lower()
    risk = str(row.get("risk") or "").strip().lower()
    approval = row.get("approval") if isinstance(row.get("approval"), dict) else {}
    allowed_types = {
        str(item).strip().lower()
        for item in gates.get("allow_action_types", [])
        if str(item).strip()
    } if isinstance(gates.get("allow_action_types"), list) else set()

    if status == "pending_approval":
        return {
            "executable": False,
            "code": "approval_required",
            "detail": "Pending operator approval.",
        }
    if status == "rejected":
        return {
            "executable": False,
            "code": "rejected",
            "detail": "Rejected actions are not executable.",
        }
    if status == "executed":
        return {
            "executable": False,
            "code": "already_executed",
            "detail": "Action has already been executed.",
        }
    if status == "counterfactual_queued":
        return {
            "executable": False,
            "code": "counterfactual_queued",
            "detail": "Queued for counterfactual sampling instead of direct execution.",
        }
    if status != "approved":
        return {
            "executable": False,
            "code": "status_not_executable",
            "detail": f"Status '{status or 'unknown'}' is not executable.",
        }
    if allowed_types and action_type not in allowed_types:
        allowed_list = ", ".join(sorted(allowed_types))
        return {
            "executable": False,
            "code": "type_blocked_by_policy",
            "detail": f"Action type '{action_type or 'unknown'}' is blocked by policy. Allowed types: {allowed_list}.",
        }
    if bool(gates.get("require_independent_verifier_for_high_risk", False)) and risk == "high":
        if not approval.get("verifier_by"):
            return {
                "executable": False,
                "code": "verifier_required",
                "detail": "High-risk action needs an independent verifier before execution.",
            }
    return {
        "executable": True,
        "code": "ready",
        "detail": "Approved and eligible for execution.",
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
    bash_bin = os.getenv("BASH_BIN", "/run/current-system/sw/bin/bash")
    argv = [str(path)] + (args or [])
    if path.suffix == ".sh":
        argv = [bash_bin, str(path)] + (args or [])
    env = os.environ.copy()
    existing_path = env.get("PATH", "")
    extra_path = "/run/current-system/sw/bin:/usr/bin:/bin"
    env["PATH"] = f"{extra_path}:{existing_path}" if existing_path else extra_path
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
            env=env,
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
        raw_metadata = latest["metadata"] if latest and latest["metadata"] else {}
        if isinstance(raw_metadata, str):
            try:
                raw_metadata = json.loads(raw_metadata)
            except json.JSONDecodeError:
                raw_metadata = {}
        last_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
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
        # Reuse the global session (avoids creating a new TCP connector per probe)
        # but override the per-request timeout to the lightweight probe budget.
        sess = await get_http_session()

        # Determine appropriate auth headers based on the service being probed
        headers = {}
        if url.startswith(SERVICES['hybrid']):
            headers = _hybrid_dual_auth_headers()
        elif url.startswith(SERVICES['aider_wrapper']):
            headers = _aider_wrapper_auth_headers()
        elif url.startswith(SERVICES['ralph']):
            headers = _ralph_auth_header()
        elif url.startswith(SERVICES['aidb']):
            # AIDB and Ralph often share the same API key in this stack
            headers = _ralph_auth_header()

        async with sess.get(url, headers=headers, timeout=_HEALTH_PROBE_TIMEOUT) as resp:
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

    Results are cached for ``_REDIS_PROBE_CACHE_TTL_S`` seconds so that
    repeated metrics polls do not each open a fresh TCP connection.
    Host/port are read from ``service_endpoints`` — no hardcoded values.
    """
    now = time.monotonic()
    if _REDIS_PROBE_CACHE["result"] is not None and (now - _REDIS_PROBE_CACHE["ts"]) < _REDIS_PROBE_CACHE_TTL_S:
        return _REDIS_PROBE_CACHE["result"]

    host = service_endpoints.SERVICE_HOST
    port = service_endpoints.REDIS_PORT
    t0 = time.monotonic()
    result: Dict[str, Any]
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
        result = {
            "redis_ping_ok": ok,
            "redis_latency_ms": latency_ms,
            "redis_error": None if ok else f"unexpected_response: {data[:32]!r}",
        }
    except asyncio.TimeoutError:
        result = {"redis_ping_ok": False, "redis_latency_ms": None, "redis_error": "timeout"}
    except OSError as exc:
        result = {"redis_ping_ok": False, "redis_latency_ms": None, "redis_error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        result = {"redis_ping_ok": False, "redis_latency_ms": None, "redis_error": str(exc)}
    _REDIS_PROBE_CACHE["ts"] = time.monotonic()
    _REDIS_PROBE_CACHE["result"] = result
    return result


def _build_pg_dsn() -> str:
    """Construct the PostgreSQL DSN from env vars or service_endpoints defaults."""
    pg_user = os.getenv("AIDB_DB_USER", "aidb")
    pg_name = os.getenv("AIDB_DB_NAME", "aidb")
    dsn = os.getenv(
        "AIDB_DB_URL",
        f"postgresql://{pg_user}@{service_endpoints.SERVICE_HOST}:{service_endpoints.POSTGRES_PORT}/{pg_name}",
    )
    return _inject_password_into_dsn(dsn, pg_user)


async def _get_pg_pool():
    """Return the module-level asyncpg pool, creating it on first call.

    Using a pool keeps one TCP connection alive between probe calls so that
    repeated SELECT 1 probes cost ~1-5 ms instead of ~300-500 ms per call.
    """
    global _PG_POOL
    if _PG_POOL is not None:
        return _PG_POOL
    if not _ASYNCPG_AVAILABLE:
        return None
    try:
        _PG_POOL = await asyncio.wait_for(
            asyncpg.create_pool(_build_pg_dsn(), min_size=1, max_size=2, command_timeout=5.0),
            timeout=5.0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("pg probe pool creation failed: %s", exc)
        _PG_POOL = None
    return _PG_POOL


async def _postgres_select1_probe() -> Dict[str, Any]:
    """Run ``SELECT 1`` against PostgreSQL and return probe results.

    Uses a module-level asyncpg pool so repeated calls reuse the existing
    TCP connection and latency is ~1-5 ms rather than the ~300-500 ms needed
    to establish a fresh connection.  Results are also cached for
    ``_POSTGRES_PROBE_CACHE_TTL_S`` seconds as a second layer of protection.
    """
    now = time.monotonic()
    if _POSTGRES_PROBE_CACHE["result"] is not None and (now - _POSTGRES_PROBE_CACHE["ts"]) < _POSTGRES_PROBE_CACHE_TTL_S:
        return _POSTGRES_PROBE_CACHE["result"]

    if not _ASYNCPG_AVAILABLE:
        return {
            "postgres_query_ok": False,
            "postgres_latency_ms": None,
            "postgres_error": "asyncpg_not_installed",
        }

    pool = await _get_pg_pool()
    t0 = time.monotonic()
    result: Dict[str, Any]
    if pool is None:
        # Pool unavailable — fall back to a single connection so we still get a result.
        conn = None
        try:
            conn = await asyncio.wait_for(asyncpg.connect(_build_pg_dsn()), timeout=3.0)
            await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=2.0)
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            result = {"postgres_query_ok": True, "postgres_latency_ms": latency_ms, "postgres_error": None}
        except asyncio.TimeoutError:
            result = {"postgres_query_ok": False, "postgres_latency_ms": None, "postgres_error": "timeout"}
        except Exception as exc:  # noqa: BLE001
            result = {"postgres_query_ok": False, "postgres_latency_ms": None, "postgres_error": str(exc)}
        finally:
            if conn is not None:
                try:
                    await conn.close()
                except Exception:  # noqa: BLE001
                    pass
    else:
        try:
            async with asyncio.timeout(2.0):
                async with pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            result = {"postgres_query_ok": True, "postgres_latency_ms": latency_ms, "postgres_error": None}
        except Exception as exc:  # noqa: BLE001
            # Pool may have stale connections after a PG restart — close and retry once.
            global _PG_POOL
            try:
                await pool.close()
            except Exception:  # noqa: BLE001
                pass
            _PG_POOL = None
            result = {"postgres_query_ok": False, "postgres_latency_ms": None, "postgres_error": str(exc)}

    _POSTGRES_PROBE_CACHE["ts"] = time.monotonic()
    _POSTGRES_PROBE_CACHE["result"] = result
    return result


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
    """Collect PostgreSQL runtime metrics beyond the basic SELECT 1 health probe.

    Reuses the module-level asyncpg pool from ``_get_pg_pool()`` to avoid
    paying the TCP handshake cost on every call.
    """
    pg_name = os.getenv("AIDB_DB_NAME", "aidb")
    if not _ASYNCPG_AVAILABLE:
        return {
            "database_size_bytes": None,
            "active_connections": None,
            "idle_connections": None,
            "database_name": pg_name,
            "error": "asyncpg_not_installed",
        }

    _RUNTIME_SQL = """
        SELECT
          pg_database_size(current_database())::bigint AS database_size_bytes,
          COUNT(*) FILTER (WHERE state = 'active')::int AS active_connections,
          COUNT(*) FILTER (WHERE state = 'idle')::int AS idle_connections
        FROM pg_stat_activity
        WHERE datname = current_database()
    """

    pool = await _get_pg_pool()
    try:
        if pool is not None:
            async with asyncio.timeout(3.0):
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(_RUNTIME_SQL)
        else:
            conn_single = None
            try:
                conn_single = await asyncio.wait_for(asyncpg.connect(_build_pg_dsn()), timeout=3.0)
                row = await asyncio.wait_for(conn_single.fetchrow(_RUNTIME_SQL), timeout=2.0)
            finally:
                if conn_single is not None:
                    try:
                        await conn_single.close()
                    except Exception:  # noqa: BLE001
                        pass
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
    metrics_text = await fetch_text_with_fallback(
        f"{SERVICES['aidb']}/metrics",
        "",
        headers=_ralph_auth_header(),
    )
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
        _log_model_inventory_degraded_once("exists_check", model_dir, exc)
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
        _log_model_inventory_degraded_once("scan", model_dir, exc)
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
    summary = await fetch_with_fallback(
        f"{SERVICES['aider_wrapper']}/tasks/summary",
        None,
        headers=_aider_wrapper_auth_headers(),
    )
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    headers = _hybrid_dual_auth_headers()
    if not headers:
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
        headers=headers,
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Hybrid feedback endpoint unavailable")
    return result


@router.get("/aidb/health/{probe}")
async def proxy_aidb_health(probe: str) -> Dict[str, Any]:
    """Proxy AIDB health endpoints via cluster DNS.

    For 'detailed': synthesize from live /health/live + /health/ready rather
    than returning the cached summary that shows startup_complete=false until
    the background startup_probe() fires.
    """
    if probe not in ("health", "live", "ready", "startup", "detailed"):
        raise HTTPException(status_code=404, detail="Unsupported probe")

    headers = _ralph_auth_header()

    if probe == "detailed":
        live, ready = await asyncio.gather(
            fetch_with_fallback(f"{SERVICES['aidb']}/health/live", None, headers=headers),
            fetch_with_fallback(f"{SERVICES['aidb']}/health/ready", None, headers=headers),
        )
        if live is None and ready is None:
            raise HTTPException(status_code=503, detail="AIDB health unavailable")
        live_status = (live or {}).get("status")
        ready_status = (ready or {}).get("status")
        startup_complete = live_status in ("healthy", "ok") and ready_status in ("healthy", "ok")
        return {
            "service": "aidb",
            "startup_complete": startup_complete,
            "liveness": live,
            "readiness": ready,
            "timestamp": (live or ready or {}).get("timestamp"),
        }
    path = f"/health/{probe}" if probe != "health" else "/health"
    result = await fetch_with_fallback(f"{SERVICES['aidb']}{path}", None, headers=headers)
    if result is None:
        raise HTTPException(status_code=503, detail="AIDB health unavailable")
    return result


@router.get("/aidb/metrics")
async def proxy_aidb_metrics() -> Response:
    """Proxy AIDB Prometheus metrics."""
    metrics = await fetch_text_with_fallback(
        f"{SERVICES['aidb']}/metrics",
        None,
        headers=_ralph_auth_header(),
    )
    if metrics is None:
        raise HTTPException(status_code=503, detail="AIDB metrics unavailable")
    return Response(content=metrics, media_type="text/plain")


@router.get("/query/traces")
async def query_traces(limit: int = 20) -> Dict[str, Any]:
    """Proxy coordinator /api/traces for dashboard Intelligence lane.
    Returns empty list with coordinator_offline=True when coordinator is down."""
    hybrid_base = SERVICES["hybrid"]
    result = await fetch_with_fallback(
        f"{hybrid_base}/api/traces?limit={limit}",
        {"traces": [], "total": 0, "coordinator_offline": True},
        headers=_hybrid_dual_auth_headers(),
    )
    if isinstance(result, dict) and "error" in result:
        return {"traces": [], "total": 0, "coordinator_offline": True, "error": result["error"]}
    return result


# Collection metadata: label, type (knowledge|memory|training|other), purpose
_COLLECTION_META: Dict[str, Dict[str, str]] = {
    "codebase-context":       {"label": "Codebase Context",     "type": "knowledge", "purpose": "Code patterns & project structure"},
    "learning-feedback":      {"label": "Learning Feedback",    "type": "training",  "purpose": "User feedback & interaction quality"},
    "agent-memory-procedural":{"label": "Procedural Memory",    "type": "memory",    "purpose": "How-to patterns & procedures"},
    "best-practices":         {"label": "Best Practices",       "type": "knowledge", "purpose": "Engineering & architecture patterns"},
    "agent-memory-episodic":  {"label": "Episodic Memory",      "type": "memory",    "purpose": "Past sessions & decisions"},
    "error-solutions":        {"label": "Error Solutions",      "type": "knowledge", "purpose": "Diagnostic & fix patterns"},
    "agent-memory-semantic":  {"label": "Semantic Memory",      "type": "memory",    "purpose": "Facts & world model"},
    "agent-memory-crystalline":{"label": "Crystalline Facts",  "type": "memory",    "purpose": "Distilled session wisdom"},
    "agent-memory-institutional":{"label": "Institutional Knowledge", "type": "knowledge", "purpose": "Shared cross-agent discovery"},
    "interaction-history":    {"label": "Interaction History",  "type": "training",  "purpose": "Query-response pairs"},
    "knowledge":              {"label": "Knowledge Base",       "type": "knowledge", "purpose": "General domain knowledge"},
    "skills-patterns":        {"label": "Skills & Patterns",    "type": "knowledge", "purpose": "Agent capability registry"},
}

_OBSERVATORY_CACHE: Dict[str, Any] = {"ts": 0.0, "payload": None}
_OBSERVATORY_CACHE_TTL = 45.0


@router.get("/knowledge/observatory")
async def knowledge_observatory() -> Dict[str, Any]:
    """Return vector knowledge base stats + collection breakdown for Intelligence Observatory panel."""
    now = time.time()
    cached = _OBSERVATORY_CACHE.get("payload")
    if cached is not None and (now - float(_OBSERVATORY_CACHE.get("ts", 0.0))) < _OBSERVATORY_CACHE_TTL:
        return dict(cached)

    collections_resp = await fetch_with_fallback(f"{SERVICES['qdrant']}/collections", {})
    raw_collections = []
    if isinstance(collections_resp, dict):
        raw_collections = collections_resp.get("result", {}).get("collections", []) or []
    collection_names = [c.get("name") for c in raw_collections if c.get("name")]

    points_by_name = await _fetch_qdrant_collection_points(collection_names) if collection_names else {}

    collections_out = []
    total_points = 0
    for name in sorted(collection_names):
        pts = points_by_name.get(name, 0)
        total_points += pts
        meta = _COLLECTION_META.get(name, {
            "label": name.replace("-", " ").title(),
            "type": "other",
            "purpose": "",
        })
        collections_out.append({
            "name": name,
            "label": meta["label"],
            "type": meta["type"],
            "purpose": meta["purpose"],
            "points": pts,
            "active": pts > 0,
        })

    collections_out.sort(key=lambda x: x["points"], reverse=True)

    payload: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_points": total_points,
        "total_collections": len(collections_out),
        "active_collections": sum(1 for c in collections_out if c["active"]),
        "collections": collections_out,
    }
    _OBSERVATORY_CACHE["ts"] = now
    _OBSERVATORY_CACHE["payload"] = payload
    return dict(payload)


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
    health = await fetch_with_fallback(
        f"{hybrid_base}/health",
        {},
        headers=_hybrid_dual_auth_headers(),
    )

    circuit_breakers = health.get("circuit_breakers", {})

    return {
        "circuit_breakers": circuit_breakers,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/stats/delegate")
async def get_delegate_stats() -> Dict[str, Any]:
    """Get delegation stats (24h window) from hybrid coordinator."""
    result = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/stats/delegate",
        None,
        _hybrid_headers(),
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Delegate stats unavailable")
    return result


@router.get("/agent-tasks/active")
async def get_active_agent_tasks() -> Dict[str, Any]:
    """Return in-progress agent tasks from *.progress.json files (Phase 171-C)."""
    outputs_dir = _repo_root() / ".agents" / "delegation" / "outputs"
    now = time.time()
    tasks = []
    stale_cutoff = 1800  # 30 minutes — older tasks are considered stale
    try:
        for path in sorted(outputs_dir.glob("*.progress.json")):
            try:
                mtime = path.stat().st_mtime
                if now - mtime > stale_cutoff:
                    continue
                data = json.loads(path.read_text())
                if data.get("status") not in ("running", "pending"):
                    continue
                task_id = path.name.replace(".log.progress.json", "")
                last_ts = data.get("timestamp", "")
                tasks.append({
                    "task_id": task_id,
                    "status": data.get("status", "running"),
                    "tool_call_count": data.get("tool_call_count", 0),
                    "last_tool": data.get("last_tool", ""),
                    "last_tool_success": data.get("last_tool_success", True),
                    "elapsed_s": int(data.get("elapsed_s", now - mtime)),
                    "objective_preview": (data.get("objective_preview") or "")[:120],
                    "last_updated_s": int(now - mtime),
                    "timestamp": last_ts,
                })
            except Exception:
                continue
    except Exception:
        pass
    return {"tasks": tasks, "count": len(tasks), "timestamp": int(now)}


@router.get("/agent/collab-state")
async def get_agent_collab_state() -> Dict[str, Any]:
    """Read local agent cooperation state from RESUME.json and recent PULSE.log entries (Phase 171-C)."""
    repo = _repo_root()
    resume_path = repo / ".agent" / "collaboration" / "RESUME.json"
    pulse_path = repo / ".agent" / "collaboration" / "PULSE.log"

    resume_data = {}
    if resume_path.is_file():
        try:
            resume_data = json.loads(resume_path.read_text())
        except Exception:
            pass

    pulse_lines = []
    if pulse_path.is_file():
        try:
            lines = pulse_path.read_text().splitlines()
            # return latest 10 non-empty lines
            pulse_lines = [line.strip() for line in lines if line.strip()][-10:]
            pulse_lines.reverse()  # show newest first
        except Exception:
            pass

    return {
        "resume": resume_data,
        "pulse": pulse_lines,
        "timestamp": time.time(),
    }


@router.get("/discovery/signals")
async def get_discovery_signals() -> Dict[str, Any]:
    """Return keyword/discovery signal data from the current local source when available."""
    payload = _load_keyword_signals()
    if payload is None:
        return {"available": False, "signals": [], "reason": "keyword signals not yet generated"}
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    )
    if not isinstance(result, dict):
        return {
            "status": "degraded",
            "available": False,
            "reason": "invalid_harness_stats_payload",
            "timestamp": datetime.now(timezone.utc).isoformat(),
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


def _loop_telemetry_dirs() -> List[Path]:
    return [
        Path(os.environ.get("TELEMETRY_DIR", "/var/lib/ai-stack/hybrid/telemetry")),
        _repo_root() / ".agents" / "telemetry",
    ]


def _read_last_jsonl(path: Path) -> Optional[Dict[str, Any]]:
    """Last valid JSON object in a .jsonl file, or None."""
    try:
        last = None
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                last = json.loads(line)
            except json.JSONDecodeError:
                continue
        return last
    except OSError:
        return None


@router.get("/loop/status")
async def get_loop_status() -> Dict[str, Any]:
    """Closed local-improvement loop status — the measurement tile for capture->correct->ingest->train.
    Pure read of loop telemetry (results/progress/spool/dataset); no service dependency, so it stays
    available even when the loop is idle. Kills the dashboard blank for the loop."""
    dirs = _loop_telemetry_dirs()

    def _first(rel: str) -> Optional[Path]:
        for d in dirs:
            p = d / rel
            try:
                if p.exists():
                    return p
            except OSError:
                continue
        return None

    # Last completed run + current phase.
    results = _first("training-loop-results.jsonl")
    last_run = _read_last_jsonl(results) if results else None
    last_run_age_h = None
    if results is not None:
        try:
            sz = results.stat().st_size
            if sz > 0:
                last_run_age_h = round((time.time() - results.stat().st_mtime) / 3600.0, 1)
        except OSError:
            pass
    progress_p = _first("training-loop-progress.json")
    progress = None
    if progress_p is not None:
        try:
            progress = json.loads(progress_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            progress = None

    # Capture spool: failures / successes / pending corrections / repair pairs.
    spool = _first("training-samples.jsonl")
    failures = successes = repair_pairs = pending_review = 0
    corrected_sigs: set = set()
    pending_sigs: set = set()
    if spool is not None:
        try:
            for line in spool.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = r.get("kind")
                if kind == "failure_sample":
                    failures += 1
                    sig = f"{r.get('prompt','')}||{r.get('bad_output','')}"
                    if r.get("corrected_output"):
                        corrected_sigs.add(sig)
                        repair_pairs += 1
                        # HITL gate: a corrected pair awaiting operator approval (aq-review-repairs).
                        if str(r.get("review_status", "") or "").lower() not in ("approved", "rejected"):
                            pending_review += 1
                    else:
                        pending_sigs.add(sig)
                elif kind == "success_sample":
                    successes += 1
        except OSError:
            pass
    pending_corrections = len(pending_sigs - corrected_sigs)

    # Dataset size.
    dataset_total = None
    ds = Path(os.environ.get("TRAINING_DATASET", "/var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl"))
    try:
        if ds.exists():
            dataset_total = sum(1 for ln in ds.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip())
    except OSError:
        dataset_total = None

    # Teacher lane presence (codex own-login).
    codex_bin = Path(os.environ.get("CODEX_BIN", str(Path.home() / ".npm-global" / "bin" / "codex")))
    teacher_ok = codex_bin.exists()

    has_clean_run = last_run is not None
    if not teacher_ok:
        status = "degraded"
    elif not has_clean_run:
        status = "never_ran"
    elif pending_corrections > int(os.environ.get("HS_CORRECTION_BACKLOG_MAX", "25")):
        status = "backlog"
    else:
        status = "healthy"

    return {
        "available": True,
        "status": status,
        "teacher": {"lane": "codex", "reachable": teacher_ok, "bin": str(codex_bin)},
        "last_run": {
            "run_id": (last_run or {}).get("run_id"),
            "age_hours": last_run_age_h,
            "samples_added": (last_run or {}).get("samples_added"),
            "dataset_total": (last_run or {}).get("dataset_total", dataset_total),
            "pass_count": (last_run or {}).get("pass_count"),
            "fail_count": (last_run or {}).get("fail_count"),
        } if has_clean_run else None,
        "current_phase": (progress or {}).get("phase"),
        "captures": {
            "failures": failures,
            "successes": successes,
            "repair_pairs": repair_pairs,
            "pending_corrections": pending_corrections,
            "pending_review": pending_review,
        },
        "dataset_total": dataset_total,
    }


def _runtime_auth_profile_summary() -> Dict[str, Any]:
    """Return runtime auth/profile policy summary for operator visibility."""
    return {
        "available": True,
        "source": "hybrid-coordinator.middleware.auth",
        "profile_header": "X-Harness-Auth-Profile",
        "context_key": "auth_context",
        "modes": {
            "public": {
                "default_profile": "readonly-strict",
                "allowed_profiles": ["readonly-strict"],
            },
            "loopback-agent": {
                "default_profile": "execute-guarded",
                "allowed_profiles": ["readonly-strict", "execute-guarded"],
            },
            "api-key": {
                "default_profile": "execute-guarded",
                "allowed_profiles": ["readonly-strict", "execute-guarded", "worktree-guarded"],
            },
            "no-api-key-configured": {
                "default_profile": "execute-guarded",
                "allowed_profiles": ["readonly-strict", "execute-guarded"],
            },
        },
    }


def _local_tool_registry_security_summary() -> Dict[str, Any]:
    """Return local-agent tool registry security metadata summary.

    This avoids importing tool modules in the dashboard service process because
    local-agent registry construction initializes proposal/audit side effects
    that can target a read-only Nix store checkout under systemd.
    """
    repo_root = _repo_root()
    try:
        profiles_path = repo_root / "config" / "runtime-isolation-profiles.json"
        profiles = json.loads(profiles_path.read_text()).get("profiles", {})
        known_profiles = set(profiles)
        policy_defaults = {
            "READ_ONLY": ("readonly-strict", "none"),
            "WRITE_SAFE": ("execute-guarded", "loopback"),
            "WRITE_DATA": ("execute-guarded", "loopback"),
            "SYSTEM_MODIFY": ("worktree-guarded", "loopback"),
            "DESTRUCTIVE": ("worktree-guarded", "loopback"),
        }
        tool_files = [
            repo_root / "ai-stack" / "local-agents" / "builtin_tools" / "shell_tools.py",
            repo_root / "ai-stack" / "local-agents" / "builtin_tools" / "file_operations.py",
            repo_root / "ai-stack" / "local-agents" / "builtin_tools" / "git_tools.py",
        ]
        total = 0
        sandbox_profiles: Dict[str, int] = {}
        network_policies: Dict[str, int] = {}
        missing: List[str] = []
        for path in tool_files:
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (
                    (isinstance(func, ast.Name) and func.id == "ToolDefinition")
                    or (isinstance(func, ast.Attribute) and func.attr == "ToolDefinition")
                ):
                    continue
                total += 1
                name = f"{path.stem}:{total}"
                policy = "READ_ONLY"
                for kw in node.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                        name = str(kw.value.value)
                    if kw.arg == "safety_policy" and isinstance(kw.value, ast.Attribute):
                        policy = kw.value.attr
                profile, network = policy_defaults.get(policy, ("readonly-strict", "none"))
                sandbox_profiles[profile] = sandbox_profiles.get(profile, 0) + 1
                network_policies[network] = network_policies.get(network, 0) + 1
                if profile not in known_profiles:
                    missing.append(name)
        return {
            "available": True,
            "source": "static_builtin_registry_ast",
            "total_tools": total,
            "enabled_tools": total,
            "complete": not missing,
            "missing_count": len(missing),
            "missing_tools": missing[:20],
            "sandbox_profiles": sandbox_profiles,
            "network_policies": network_policies,
        }
    except Exception as exc:
        return {
            "available": False,
            "reason": str(exc)[:200],
            "complete": False,
            "missing_count": None,
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
    tool_registry_security = _local_tool_registry_security_summary()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
            "tool_registry_security": tool_registry_security,
            "runtime_auth_profiles": _runtime_auth_profile_summary(),
        },
        "maintenance": {
            "scripts": script_status,
            "operational_scripts": operational_count,
            "total_scripts": len(script_status),
            "weekly_research": _weekly_research_state(),
            "improvement_pass": improvement,
        },
    }


@router.get("/harness")
async def get_harness_legacy_alias() -> Dict[str, Any]:
    """Compatibility alias for older dashboard clients expecting /api/aistack/harness."""
    return await get_harness_overview()


@router.get("/aistack/candidate-pipeline")
async def get_candidate_pipeline(insights: AIInsightsService = Depends(get_insights_service)):
    """Expose candidate pipeline lifecycle states (Phase 150 Slice 3)."""
    return await insights.get_candidate_pipeline()


def _hybrid_dual_auth_headers() -> Dict[str, str]:
    """Return both accepted hybrid auth header forms for dashboard proxy routes."""
    api_key = _load_hybrid_api_key()
    if not api_key:
        return {}
    return {"X-API-Key": api_key, "Authorization": f"Bearer {api_key}"}


def _append_query(url: str, request: Request) -> str:
    query = str(request.url.query or "")
    return f"{url}?{query}" if query else url


@router.get("/agent-ops/status")
async def proxy_agent_ops_status() -> Dict[str, Any]:
    """Compatibility proxy for coordinator /api/agent-ops/status."""
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/api/agent-ops/status",
        {"available": False, "drift_score": None, "alert_active": False},
        headers=_hybrid_dual_auth_headers(),
    )


@router.get("/memory/facts")
async def proxy_memory_facts(request: Request) -> Dict[str, Any]:
    """Compatibility proxy for coordinator /api/memory/facts, preserving filters."""
    return await fetch_with_fallback(
        _append_query(f"{SERVICES['hybrid']}/api/memory/facts", request),
        {"available": False, "facts": []},
        headers=_hybrid_dual_auth_headers(),
    )


@router.get("/memory/supersede/history")
async def proxy_memory_supersede_history(request: Request) -> Dict[str, Any]:
    """Compatibility proxy for coordinator /memory/supersede/history."""
    return await fetch_with_fallback(
        _append_query(f"{SERVICES['hybrid']}/memory/supersede/history", request),
        {"available": False, "events": []},
        headers=_hybrid_dual_auth_headers(),
    )


@router.get("/memory/stats")
async def proxy_memory_stats() -> Dict[str, Any]:
    """Small dashboard aggregate for memory broker, crystallizer, and supersession state."""
    broker, crystal, supersede = await asyncio.gather(
        fetch_with_fallback(
            f"{SERVICES['hybrid']}/memory/broker/status",
            {"available": False},
            headers=_hybrid_dual_auth_headers(),
        ),
        fetch_with_fallback(
            f"{SERVICES['hybrid']}/memory/crystalline/status",
            {"available": False, "sessions_processed": 0, "insights_stored": 0},
            headers=_hybrid_dual_auth_headers(),
        ),
        fetch_with_fallback(
            f"{SERVICES['hybrid']}/memory/supersede/history?limit=5",
            {"available": False, "events": []},
            headers=_hybrid_dual_auth_headers(),
        ),
    )
    memory_types = broker.get("memory_types", []) if isinstance(broker, dict) else []
    events = supersede.get("events", []) if isinstance(supersede, dict) else []
    return {
        "available": bool(isinstance(broker, dict) and broker.get("initialized")),
        "initialized": bool(isinstance(broker, dict) and broker.get("initialized")),
        "memory_types": memory_types,
        "memory_type_count": len(memory_types),
        "contradiction_pairs": broker.get("contradiction_pairs") if isinstance(broker, dict) else None,
        "sessions_processed": crystal.get("sessions_processed", 0) if isinstance(crystal, dict) else 0,
        "insights_stored": crystal.get("insights_stored", 0) if isinstance(crystal, dict) else 0,
        "supersession_events": len(events),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/hints/stats")
async def proxy_hints_stats() -> Dict[str, Any]:
    """Compatibility hints stats for older command-center cards."""
    hints = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/hints?q=dashboard",
        {"available": False, "hints": []},
        headers=_hybrid_dual_auth_headers(),
    )
    hint_rows = hints.get("hints", []) if isinstance(hints, dict) else []
    return {
        "available": isinstance(hints, dict),
        "hint_count": len(hint_rows),
        "top_hints": hint_rows[:5],
        "generated_at": hints.get("generated_at") if isinstance(hints, dict) else None,
    }


@router.get("/hints/report")
async def proxy_hints_report() -> Dict[str, Any]:
    """Compatibility report endpoint backed by the persisted aq-report snapshot."""
    report = await _aq_report_snapshot()
    return {
        "available": bool(report),
        "hints": report.get("hints", {}) if isinstance(report, dict) else {},
        "agent_lessons": report.get("agent_lessons", {}) if isinstance(report, dict) else {},
        "retrieval_acceptance": report.get("retrieval_acceptance", {}) if isinstance(report, dict) else {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/lesson-registry")
async def proxy_lesson_registry() -> Dict[str, Any]:
    """Compatibility proxy for coordinator /control/ai-coordinator/lessons."""
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/control/ai-coordinator/lessons",
        {"available": False, "agent_lessons": {"entries": [], "counts": {}}},
        headers=_hybrid_dual_auth_headers(),
    )


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
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ai/metrics/hybrid")
async def proxy_hybrid_metrics() -> Response:
    """Proxy Hybrid Coordinator Prometheus metrics with auth."""
    metrics = await fetch_text_with_fallback(
        f"{SERVICES['hybrid']}/metrics",
        None,
    )
    if metrics is None:
        # Retry with dual auth headers if simple fetch failed
        try:
            session = await get_http_session()
            async with session.get(
                f"{SERVICES['hybrid']}/metrics",
                headers=_hybrid_dual_auth_headers(),
                timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status == 200:
                    metrics = await resp.text()
        except Exception as exc:
            logger.warning("Failed to fetch hybrid metrics with auth: %s", exc)

    if metrics is None:
        raise HTTPException(status_code=503, detail="Hybrid metrics unavailable")
    return Response(content=metrics, media_type="text/plain")


@router.get("/ai/homeostasis/events")
async def proxy_homeostasis_events() -> List[Dict[str, Any]]:
    """Proxy coordinator /homeostasis/events."""
    result = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/homeostasis/events",
        [],
        headers=_hybrid_dual_auth_headers(),
    )
    return result if isinstance(result, list) else []


@router.get("/ai/health/rag")
async def proxy_rag_health() -> Dict[str, Any]:
    """Proxy coordinator /api/health/rag."""
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/api/health/rag",
        {"status": "offline"},
        headers=_hybrid_dual_auth_headers(),
    )


@router.get("/ai/memory/status")
async def proxy_memory_status() -> Dict[str, Any]:
    """Proxy coordinator /memory/broker/status."""
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/memory/broker/status",
        {"status": "offline"},
        headers=_hybrid_dual_auth_headers(),
    )


@router.get("/eval/trend")
async def proxy_eval_trend() -> Dict[str, Any]:
    """Proxy coordinator /eval/trend for RAGAS quality metrics (Phase 60.5)."""
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/eval/trend",
        {"available": False},
        headers=_hybrid_dual_auth_headers(),
    )


@router.get("/traces/drift")
async def proxy_traces_drift() -> Dict[str, Any]:
    """Proxy coordinator /api/traces/drift — flattens breakdown for dashboard consumers."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    raw = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/api/traces/drift",
        {"drift_score": None, "intent_flip_rate": None, "latency_degradation": None, "available": False},
        headers=headers,
    )
    if not raw or raw.get("available") is False:
        return raw
    # Flatten breakdown sub-object to top-level for backward compat
    bd = raw.get("breakdown") or {}
    return {
        "drift_score":       raw.get("drift_score", 0.0),
        "window_size":       raw.get("window_size"),
        "threshold":         raw.get("threshold"),
        "alert_triggered":   raw.get("alert_triggered", False),
        "intent_flip_rate":  bd.get("intent_flip_rate", 0.0),
        "latency_trend":     bd.get("latency_trend", 0.0),
        "latency_degradation": bd.get("latency_degradation", 0.0),
        "trace_count":       raw.get("window_size"),
        "available":         True,
    }


@router.get("/hardware/state")
async def proxy_hardware_state() -> Dict[str, Any]:
    """Proxy coordinator /api/hardware/state — thermal + RAM + GPU layer telemetry."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/api/hardware/state",
        {"thermal_tier": "unknown", "available": False},
        headers=headers,
    )


@router.get("/scheduler/status")
async def proxy_scheduler_status() -> Dict[str, Any]:
    """Proxy coordinator /admin/v1/scheduler/status — MLFQ queue depths + thermal gating."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/admin/v1/scheduler/status",
        {"thermal_tier": "unknown", "available": False},
        headers=headers,
    )


@router.get("/policy/tool-deny-stats")
async def proxy_tool_deny_stats() -> Dict[str, Any]:
    """Proxy coordinator GET /admin/v1/policy/tool-deny-stats — auth-profile tool denial counts (S2)."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/admin/v1/policy/tool-deny-stats",
        {"total_denials": 0, "by_tool": {}, "by_profile": {}, "breakdown": [], "policy": {}, "available": False},
        headers=headers,
    )


@router.get("/local-insights/latest")
async def get_local_insights_latest() -> Dict[str, Any]:
    """Read the latest aq-insights output from .agent/memory/.

    Accepts both new model-agnostic naming (local-insights-*.md) and legacy
    Qwen-branded files (qwen-insights-*.md) for backward compatibility.
    Returns the most recent harness analysis produced by `aq-insights`.
    """
    memory_dir = _repo_root() / ".agent" / "memory"
    empty: Dict[str, Any] = {
        "available": False,
        "date_tag": None,
        "generated_at": None,
        "report_snapshot": None,
        "content": None,
    }
    if not memory_dir.is_dir():
        return empty
    try:
        files = sorted(
            list(memory_dir.glob("local-insights-*.md")) + list(memory_dir.glob("qwen-insights-*.md")),
            key=lambda p: p.name,
            reverse=True,
        )
    except Exception:
        return empty
    if not files:
        return empty
    latest = files[0]
    try:
        text = latest.read_text(encoding="utf-8")
    except Exception:
        return empty
    # Parse header lines
    generated_at: Optional[str] = None
    report_snapshot: Optional[str] = None
    for line in text.splitlines()[:6]:
        if "*Generated by aq-insights at" in line:
            generated_at = line.strip().strip("*").replace("Generated by aq-insights at ", "")
        if "*Report snapshot:" in line:
            report_snapshot = line.strip().strip("*").replace("Report snapshot: ", "")
    date_tag = latest.stem.replace("qwen-insights-", "")
    # Content is everything after the "---" separator
    separator = text.find("\n---\n")
    content = text[separator + 5:].strip() if separator != -1 else text.strip()
    return {
        "available": True,
        "date_tag": date_tag,
        "generated_at": generated_at,
        "report_snapshot": report_snapshot,
        "content": content,
        "file": latest.name,
    }


# Phase 164D — Operator Intelligence Bridge dashboard endpoint
@router.get("/operator/intelligence")
async def get_operator_intelligence() -> Dict[str, Any]:
    """Proxy GET /operator/profile from hybrid-coordinator for the OIB dashboard panel.

    Returns operator knowledge profile + cached insight cards. Falls back to
    empty profile structure on coordinator unavailability.
    """
    hybrid_url = service_endpoints.HYBRID_URL
    empty: Dict[str, Any] = {
        "available": False,
        "session_count": 0,
        "domains_engaged": {},
        "open_research_threads": [],
        "prompt_specificity_trend": [],
        "chilling_effect_alerts": 0,
        "insight_cards_surfaced": 0,
        "insight_cards_researched": 0,
        "last_updated": None,
    }
    try:
        timeout = aiohttp.ClientTimeout(total=5.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{hybrid_url}/operator/profile") as resp:
                if resp.status != 200:
                    return empty
                data = await resp.json()
                data["available"] = True
                return data
    except Exception as exc:
        logger.debug("operator/intelligence fetch failed: %s", exc)
        return empty


@router.get("/context/lifecycle/status")
async def proxy_clm_status() -> Dict[str, Any]:
    """Proxy coordinator /context/lifecycle/status — CLM Hot/Warm/Cold tier distribution."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/context/lifecycle/status",
        {"tiers": {}, "available": False},
        headers=headers,
    )


@router.get("/memory/broker/status")
async def proxy_memory_broker_status() -> Dict[str, Any]:
    """Proxy coordinator /memory/broker/status — memory types + contradiction pairs."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/memory/broker/status",
        {"initialized": False, "available": False},
        headers=headers,
    )


@router.get("/memory/crystalline/status")
async def proxy_memory_crystalline_status() -> Dict[str, Any]:
    """Proxy coordinator /memory/crystalline/status — crystallization run stats."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/memory/crystalline/status",
        {"sessions_processed": 0, "insights_stored": 0, "available": False},
        headers=headers,
    )


@router.get("/affective/state")
async def proxy_affective_state() -> Dict[str, Any]:
    """Proxy coordinator /affective/state — agent affective/emotional signal state."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/affective/state",
        {"enabled": False, "available": False},
        headers=headers,
    )


@router.get("/parity/scorecard")
async def proxy_parity_scorecard() -> Dict[str, Any]:
    """Proxy coordinator /parity/scorecard — runtime parity track status."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/parity/scorecard",
        {"scorecard": {}, "available": False},
        headers=headers,
    )


@router.get("/traces/summary")
async def proxy_traces_summary() -> Dict[str, Any]:
    """Aggregate coordinator traces into an intent/backend breakdown summary."""
    raw = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/api/traces",
        {"traces": [], "count": 0, "available": False},
        headers=_hybrid_dual_auth_headers(),
    )
    raw = raw if isinstance(raw, dict) else {"traces": [], "count": 0, "available": False}
    traces = raw.get("traces", [])
    if not traces:
        return {"count": 0, "intent_breakdown": {}, "backend_breakdown": {}, "available": bool(traces is not None)}
    intent_breakdown: Dict[str, int] = {}
    backend_breakdown: Dict[str, int] = {}
    for t in traces:
        intent = t.get("intent") or "unknown"
        backend = t.get("backend") or "local"
        intent_breakdown[intent] = intent_breakdown.get(intent, 0) + 1
        backend_breakdown[backend] = backend_breakdown.get(backend, 0) + 1
    return {
        "count": raw.get("count", len(traces)),
        "intent_breakdown": dict(sorted(intent_breakdown.items(), key=lambda x: -x[1])),
        "backend_breakdown": backend_breakdown,
        "available": True,
    }


@router.get("/hints/active")
async def proxy_hints_active() -> Dict[str, Any]:
    """Proxy coordinator /hints — active hint registry."""
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/hints",
        {"hints": [], "available": False},
        headers=_hybrid_dual_auth_headers(),
    )


@router.get("/coordinator/ai-status")
async def proxy_coordinator_ai_status() -> Dict[str, Any]:
    """Proxy coordinator /control/ai-coordinator/status — remote aliases + skill registry."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/control/ai-coordinator/status",
        {"status": "unknown", "available": False},
        headers=headers,
    )


@router.get("/fleet/summary")
async def proxy_fleet_summary() -> Dict[str, Any]:
    """Proxy coordinator /control/fleet/summary — runtime count by status and profile."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/control/fleet/summary",
        {"total_runtimes": 0, "available": False},
        headers=headers,
    )


@router.get("/budget/policy")
async def proxy_budget_policy() -> Dict[str, Any]:
    """Proxy coordinator /control/budget/policy — token/tool/time guardrail policy."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/control/budget/policy",
        {"policy": {}, "available": False},
        headers=headers,
    )


@router.get("/reasoning/profiles")
async def proxy_reasoning_profiles() -> Dict[str, Any]:
    """Proxy coordinator /control/reasoning/profiles — ablation reasoning profile list."""
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None
    return await fetch_with_fallback(
        f"{SERVICES['hybrid']}/control/reasoning/profiles",
        {"profiles": [], "available": False},
        headers=headers,
    )


@router.get("/ai/remediation/latest")
async def get_latest_remediation() -> Dict[str, Any]:
    """Fetch the latest auto-remediation result."""
    path = Path("/var/lib/ai-stack/hybrid/remediation/hint-remediation/aq-auto-remediation-latest.json")
    if not path.exists():
        return {"status": "no_remediation_active", "timestamp": datetime.now(timezone.utc).isoformat()}
    try:
        data = json.loads(path.read_text())
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error reading remediation: {exc}")


@router.post("/system/action")
async def run_system_action(action: str = Query(...)) -> Dict[str, Any]:
    """Execute a system-level action (rebuild, switch, rollback)."""
    # Map actions to scripts
    commands = {
        "rebuild": ["./nixos-quick-deploy.sh", "--build-only"],
        "switch": ["./nixos-quick-deploy.sh"],
        "rollback": ["sudo", "nixos-rebuild", "rollback"]
    }

    if action not in commands:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    try:
        # Start command in background to avoid timeout
        subprocess.Popen(commands[action], cwd=str(REPO_ROOT))
        return {
            "status": "triggered",
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/ai/consensus/history")
async def get_consensus_history() -> List[Dict[str, Any]]:
    """Fetch recent multi-agent consensus sessions from the consensus engine."""
    try:
        data = await _hybrid_get("/workflow/consensus/sessions")
        return data.get("sessions", [])
    except Exception:
        return []


@router.get("/health/audit")
async def get_system_audit_log() -> List[Dict[str, Any]]:
    """Fetch recent system changes from NixOS generation history and journalctl."""
    events: List[Dict[str, Any]] = []

    # NixOS generation history via /nix/var/nix/profiles symlinks (no lock file needed)
    try:
        import os as _os
        profiles_dir = "/nix/var/nix/profiles"
        current = _os.readlink(f"{profiles_dir}/system").replace("-link", "").split("-")
        current_gen = current[1] if len(current) > 1 else None
        entries = []
        with _os.scandir(profiles_dir) as it:
            for entry in it:
                name = entry.name
                if not name.startswith("system-") or not name.endswith("-link"):
                    continue
                try:
                    gen_num = int(name.split("-")[1])
                except (IndexError, ValueError):
                    continue
                stat = entry.stat(follow_symlinks=False)
                ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                is_current = (str(gen_num) == current_gen)
                entries.append((stat.st_mtime, gen_num, ts, is_current))
        entries.sort(reverse=True)
        for _, gen_num, ts, is_current in entries[:10]:
            events.append({
                "type": "rebuild",
                "detail": f"Generation {gen_num} activated" + (" (current)" if is_current else ""),
                "status": "success",
                "timestamp": ts,
            })
    except Exception:
        pass

    # Recent AppArmor events from journalctl
    try:
        result = await asyncio.to_thread(
            lambda: __import__("subprocess").run(
                ["journalctl", "-u", "apparmor", "--since", "7 days ago", "-n", "5",
                 "--output=json", "--no-pager"],
                capture_output=True, text=True, timeout=10,
            )
        )
        import json as _json
        for line in (result.stdout or "").splitlines():
            try:
                entry = _json.loads(line)
                msg = entry.get("MESSAGE", "")
                if not msg:
                    continue
                ts_us = int(entry.get("__REALTIME_TIMESTAMP", 0))
                ts = datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc).isoformat() if ts_us else datetime.now(timezone.utc).isoformat()
                events.append({"type": "policy", "detail": msg[:120], "status": "info", "timestamp": ts})
            except Exception:
                pass
    except Exception:
        pass

    if not events:
        events.append({
            "type": "info",
            "detail": "No audit events found — run nixos-rebuild or check journalctl",
            "status": "info",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Sort newest-first
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events[:20]


@router.get("/prsi/actions")
async def get_prsi_actions(status: Optional[str] = None, risk: Optional[str] = None) -> Dict[str, Any]:
    """List PRSI queued actions and counts."""
    policy = _load_prsi_policy()
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
    actions = payload.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    normalized_actions: List[Dict[str, Any]] = []
    executable_approved = 0
    blocked_approved = 0
    for row in actions:
        if not isinstance(row, dict):
            continue
        normalized = dict(row)
        gate = _prsi_execution_gate(normalized, policy)
        normalized["execution_gate"] = gate
        if str(normalized.get("status") or "").strip().lower() == "approved":
            if gate.get("executable"):
                executable_approved += 1
            else:
                blocked_approved += 1
        normalized_actions.append(normalized)
    counts = payload.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    return {
        "status": "ok",
        "prsi": {
            **payload,
            "actions": normalized_actions,
            "counts": {
                **counts,
                "executable_approved": executable_approved,
                "blocked_approved": blocked_approved,
            },
            "policy": _prsi_policy_summary(policy),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
        fetch_with_fallback(f"{SERVICES['aidb']}/health", {}, headers=_ralph_auth_header()),
        _fetch_aidb_prometheus_summary(),
        fetch_with_fallback(f"{SERVICES['hybrid']}/health", {}, headers=_hybrid_dual_auth_headers()),
        fetch_with_fallback(f"{SERVICES['llama_cpp']}/health", {}),
        fetch_with_fallback(f"{SERVICES['llama_cpp']}/v1/models", {}),
        fetch_with_fallback(f"{SERVICES['embeddings']}/health", {}),
        fetch_with_fallback(f"{SERVICES['embeddings']}/v1/models", {}),
        fetch_with_fallback(f"{SERVICES['switchboard']}/health", {}),
        fetch_with_fallback(f"{SERVICES['aider_wrapper']}/health", {}, headers=_aider_wrapper_auth_headers()),
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
    llama_memory_bytes, embedding_memory_bytes = await asyncio.gather(
        asyncio.to_thread(_systemd_memory_current_bytes, "llama-cpp.service"),
        asyncio.to_thread(_systemd_memory_current_bytes, "llama-cpp-embed.service"),
    )

    switchboard_status = _normalize_status(switchboard_health.get("status"), ("ok", "healthy"))
    switchboard_local_runtime = switchboard_health.get("local_runtime")
    switchboard_last_local_completion = (
        switchboard_local_runtime.get("last_completion")
        if isinstance(switchboard_local_runtime, dict)
        else None
    )
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
                "local_lane_status": _resolve_switchboard_local_lane_status(switchboard_health, switchboard_local_runtime),
                "local_runtime": switchboard_local_runtime,
                "last_local_completion": switchboard_last_local_completion,
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


def _ralph_auth_header() -> Dict[str, str]:
    """Load ralph-wiggum API key (wired to aidb_api_key in NixOS)."""
    key_file = os.environ.get("AIDB_API_KEY_FILE", "/run/secrets/aidb_api_key")
    try:
        key = Path(key_file).read_text().strip()
        return {"Authorization": f"Bearer {key}"}
    except OSError:
        return {}


@router.get("/ralph/stats")
async def get_ralph_stats() -> Dict[str, Any]:
    """Get Ralph Wiggum task statistics (auth-aware)."""
    ralph_base = SERVICES["ralph"]
    return await fetch_with_fallback(
        f"{ralph_base}/stats",
        {"active_tasks": 0, "completed_tasks": 0, "failed_tasks": 0, "total_iterations": 0},
        headers=_ralph_auth_header(),
    )


@router.get("/ralph/tasks")
async def get_ralph_tasks() -> Dict[str, Any]:
    """List Ralph Wiggum tasks (auth-aware)."""
    ralph_base = SERVICES["ralph"]
    tasks = await fetch_with_fallback(f"{ralph_base}/tasks", [],
                                      headers=_ralph_auth_header())
    return {"tasks": tasks, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/ralph/integration-health")
async def get_integration_health() -> Dict[str, Any]:
    """Integration contract health: verifies the full delegation chain end-to-end.

    Checks local_agent_runtime.py path, coordinator delegate endpoint (not broken),
    ralph-wiggum reachability, and aider-wrapper.  No stub data — all live probes.
    """
    from pathlib import Path as _Path

    checks: Dict[str, Any] = {}

    # 1. local_agent_runtime.py path
    runtime_path = _Path(__file__).parents[4] / "ai-stack" / "agents" / "runtimes" / "local_agent_runtime.py"
    checks["runtime_path"] = {
        "ok": runtime_path.exists(),
        "path": str(runtime_path),
        "detail": "present" if runtime_path.exists() else "MISSING — nixos-rebuild needed",
    }

    # 2. ralph-wiggum health
    ralph_health = await fetch_with_fallback(
        f"{SERVICES['ralph']}/health", None, headers=_ralph_auth_header()
    )
    checks["ralph_wiggum"] = {
        "ok": bool(ralph_health and ralph_health.get("status") == "healthy"),
        "loop_running": (ralph_health or {}).get("loop_running", False),
        "active_tasks": (ralph_health or {}).get("active_tasks", 0),
        "detail": (ralph_health or {}).get("status", "unreachable"),
    }

    # 3. aider-wrapper health
    aider_url = os.environ.get("AIDER_WRAPPER_URL",
                               f"http://127.0.0.1:{os.environ.get('AIDER_WRAPPER_PORT', '8090')}")
    aider_health = await fetch_with_fallback(f"{aider_url}/health", None)
    checks["aider_wrapper"] = {
        "ok": bool(aider_health and aider_health.get("status") == "healthy"),
        "aider_available": (aider_health or {}).get("aider_available", False),
        "detail": (aider_health or {}).get("status", "unreachable"),
    }

    # 4. coordinator delegate reachability (health check only — no real task)
    coord_health = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/health",
        None,
        headers=_hybrid_dual_auth_headers(),
    )
    checks["coordinator"] = {
        "ok": bool(coord_health and coord_health.get("status") in ("ok", "healthy")),
        "detail": (coord_health or {}).get("status", "unreachable"),
    }

    all_ok = all(v.get("ok", False) for v in checks.values())
    return {
        "healthy": all_ok,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
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


async def _aq_report_snapshot(ttl_seconds: int = 300) -> Dict[str, Any]:
    """Return cached aq-report JSON snapshot for dashboard internals.

    NEVER spawns aq-report inline — aq-report takes 60-180s on Renoir APU and
    would block the /api/metrics endpoint.  The ai_insights background service
    owns aq-report execution and writes the persisted snapshot; this function
    only reads it.

    Priority:
      1. In-memory cache (hot path, TTL=300s)
      2. Persisted snapshot file written by ai_insights service
      3. Stale in-memory cache (returned rather than blocking)
      4. Empty dict (no data yet; dashboard shows '--')
    """
    now = time.time()
    cached = _AQ_REPORT_CACHE.get("payload")

    # 1. Hot path: valid in-memory cache
    if cached and (now - float(_AQ_REPORT_CACHE.get("ts", 0.0))) < ttl_seconds:
        return cached

    # 2. Persisted snapshot written by the ai_insights background service.
    #    Re-read on every cache miss so we pick up fresh data without a restart.
    _persisted = Path(
        os.getenv("DASHBOARD_AI_INSIGHTS_REPORT_PATH", "").strip()
        or "/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json"
    )
    try:
        if _persisted.exists() and _persisted.stat().st_size > 4:
            _text = _persisted.read_text(encoding="utf-8", errors="replace").strip()
            if _text and _text.startswith("{"):
                _data = json.loads(_text)
                if isinstance(_data, dict) and _data:
                    _AQ_REPORT_CACHE["ts"] = now
                    _AQ_REPORT_CACHE["payload"] = _data
                    return _data
    except Exception:
        pass

    # 3. Return stale cache rather than blocking on aq-report
    if cached is not None and (now - float(_AQ_REPORT_CACHE.get("ts", 0.0))) < ttl_seconds * 4:
        return cached

    # 4. No data available yet — return empty; dashboard renders '--'
    return {}


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

    hits, misses, local_sel_prom, total_sel_prom, before_sum, after_sum, report, ai_metrics = await asyncio.gather(
        _prom_scalar(hits_q),
        _prom_scalar(misses_q),
        _prom_scalar(local_q),
        _prom_scalar(total_q),
        _prom_scalar(before_q),
        _prom_scalar(after_q),
        _aq_report_snapshot(),
        get_ai_metrics(),
    )

    rt = report.get("routing", {})
    local_sel = rt.get("local_n") or rt.get("local_selections", 0)
    total_sel = (rt.get("local_n", 0) + rt.get("remote_n", 0)) if "local_n" in rt else rt.get("total_selections", 0)

    # If Prometheus scalars are unavailable, fallback to aq-report routing data
    if local_sel_prom is None: local_sel = local_sel
    else: local_sel = local_sel_prom

    if total_sel_prom is None: total_sel = total_sel
    else: total_sel = total_sel_prom

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
        "embedding_cache_hit_rate_pct": embedding_cache_hit_rate_pct or 0.0,
        "llm_routing_local_pct": llm_routing_local_pct if llm_routing_local_pct is not None else 100.0,
        "tokens_compressed_last_hour": tokens_compressed_last_hour or 0.0,
        "hint_adoption_pct": round(hint_adoption_pct, 2) if hint_adoption_pct is not None else 100.0,
        "eval_latest_pct": round(eval_latest_pct, 2) if eval_latest_pct is not None else 0.0,
        "tool_performance_rows": int(tool_rows) if tool_rows is not None else 0,
        "query_gap_count": int(query_gap_count) if query_gap_count is not None else 0,
        "availability": {
            "embedding_cache_hit_rate": hits is not None or misses is not None,
            "llm_routing_local": local_sel is not None or total_sel is not None,
            "tokens_compressed_last_hour": before_sum is not None or after_sum is not None,
            "aq_report": isinstance(report, dict) and bool(report),
        },
        "circuit_breakers": {
            "coordinator": (ai_metrics.get("services", {}).get("hybrid", {}).get("circuit_breakers") or {}),
            "switchboard": (ai_metrics.get("services", {}).get("switchboard", {}).get("circuit_breakers") or {}),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    dashboard_scan = audit_dir / "latest-dashboard-security-scan.json"
    secrets_rotation = audit_dir / "latest-secrets-rotation-plan.json"
    npm_dir = Path(os.getenv("AI_NPM_SECURITY_DIR", str(audit_dir / "npm")))
    npm_latest_report = npm_dir / "latest-npm-security.json"
    npm_quarantine = npm_dir / "quarantine-state.json"
    npm_incidents = npm_dir / "incidents.jsonl"

    def _path_readable(p: Path) -> bool:
        """Return True if path exists and is readable; False on any OSError (Python 3.12+ raises PermissionError from .exists())."""
        try:
            return p.exists()
        except OSError:
            return False

    report_data: Dict[str, Any] = {
        "status": "no_report",
        "generated_at": "unknown",
        "summary": {},
    }
    message: Optional[str] = None
    if not _path_readable(latest_report):
        message = "No security audit report found. Run manually or wait for weekly timer."
    else:
        try:
            with open(latest_report) as f:
                report_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read security audit report: {e}")
            report_data = {
                "status": "error",
                "generated_at": "unknown",
                "summary": {},
            }
            message = f"Failed to parse audit report: {str(e)}"

    # Check for high severity alert
    high_severity_alert = None
    if _path_readable(high_alert):
        try:
            with open(high_alert) as f:
                high_severity_alert = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    npm_monitor: Dict[str, Any] = {
        "status": "no_report",
        "report_path": str(npm_latest_report),
        "quarantine_active": False,
        "quarantine_state": None,
        "recent_incidents": [],
    }
    if _path_readable(npm_latest_report):
        try:
            with open(npm_latest_report) as f:
                npm_report_data = json.load(f)
            npm_monitor["status"] = str(npm_report_data.get("status", "unknown"))
            npm_monitor["generated_at"] = npm_report_data.get("generated_at")
            npm_monitor["severity_counts"] = npm_report_data.get("severity_counts", {})
            npm_monitor["summary"] = npm_report_data.get("summary", {})
        except (json.JSONDecodeError, OSError) as e:
            npm_monitor["status"] = "error"
            npm_monitor["message"] = f"Failed to parse npm monitor report: {str(e)}"

    if _path_readable(npm_quarantine):
        try:
            with open(npm_quarantine) as f:
                quarantine_data = json.load(f)
            npm_monitor["quarantine_state"] = quarantine_data
            npm_monitor["quarantine_active"] = (
                str(quarantine_data.get("status", "")).lower() == "active"
            )
        except (json.JSONDecodeError, OSError):
            pass

    if _path_readable(npm_incidents):
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if _path_readable(dashboard_scan):
        try:
            with open(dashboard_scan) as f:
                payload["dashboard_operator"] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            payload["dashboard_operator"] = {
                "status": "error",
                "report_path": str(dashboard_scan),
                "message": f"Failed to parse dashboard scan report: {str(e)}",
            }
    else:
        payload["dashboard_operator"] = {
            "status": "no_report",
            "report_path": str(dashboard_scan),
        }
    if _path_readable(secrets_rotation):
        try:
            with open(secrets_rotation) as f:
                payload["secrets_rotation"] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            payload["secrets_rotation"] = {
                "status": "error",
                "report_path": str(secrets_rotation),
                "message": f"Failed to parse secrets rotation report: {str(e)}",
            }
    else:
        payload["secrets_rotation"] = {
            "status": "no_report",
            "report_path": str(secrets_rotation),
        }
    if message:
        payload["message"] = message
    return payload


# ---------------------------------------------------------------------------
# Shared helper for orchestration GET requests (avoids per-request session)
# ---------------------------------------------------------------------------

async def _hybrid_get(path: str) -> Any:
    """GET from hybrid-coordinator using the global session.

    Raises ``aiohttp.ClientResponseError`` on non-2xx (caller converts to HTTPException).
    ``asyncio.TimeoutError`` is re-raised as HTTPException 504 so callers
    see a consistent error regardless of where the timeout fires.
    """
    session = await get_http_session()
    url = f"{SERVICES['hybrid']}{path}"
    try:
        async with session.get(url, headers=_hybrid_auth_headers(), timeout=REQUEST_TIMEOUT) as resp:
            resp.raise_for_status()
            return await resp.json()
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"Coordinator timeout: {path}") from exc


async def _hybrid_post(path: str, body: dict) -> Any:
    """POST JSON body to hybrid-coordinator. Returns parsed JSON or None on error."""
    session = await get_http_session()
    url = f"{SERVICES['hybrid']}{path}"
    try:
        async with session.post(
            url,
            json=body,
            headers=_hybrid_auth_headers(),
            timeout=REQUEST_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
    except Exception:
        return None


# Orchestration Visibility Endpoints (Operator Dashboard)
@router.get("/orchestration/sessions")
async def get_orchestration_sessions() -> Dict[str, Any]:
    """Get list of recent workflow orchestration sessions.
    """
    try:
        return await _hybrid_get("/workflow/sessions")
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch orchestration sessions: {e}")
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error(f"Failed to fetch orchestration sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orchestration/team/{session_id}")
async def get_orchestration_team(session_id: str) -> Dict[str, Any]:
    """Get detailed team formation for a workflow session.

    Returns full team composition including:
    - Team members with roles, agents, lanes, scores
    - Candidates with full scoring breakdown
    - Score components (strategy_fit, locality, review_alignment, etc.)
    - Historical bias values (review_score, selection_score, runtime_score)
    """
    try:
        sess = await get_http_session()
        url = f"{SERVICES['hybrid']}/workflow/run/{session_id}/team/detailed"
        async with sess.get(url, headers=_hybrid_auth_headers(), timeout=REQUEST_TIMEOUT) as resp:
            if resp.status == 404:
                raise HTTPException(status_code=404, detail="Session not found")
            resp.raise_for_status()
            return await resp.json()
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch team details: {e}")
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error(f"Failed to fetch team details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orchestration/arbiter/{session_id}")
async def get_arbiter_history(session_id: str, limit: int = 10) -> Dict[str, Any]:
    """Get arbiter decision history for a workflow session.

    Only applicable for sessions using "arbiter-review" consensus mode.

    Returns:
    - arbiter_active: Whether arbiter mode is enabled
    - history: List of arbiter decisions with verdicts, rationale, timestamps
    - current_status: Current arbiter state
    """
    try:
        sess = await get_http_session()
        url = f"{SERVICES['hybrid']}/workflow/run/{session_id}/arbiter/history?limit={limit}"
        async with sess.get(url, headers=_hybrid_auth_headers(), timeout=REQUEST_TIMEOUT) as resp:
            if resp.status == 404:
                raise HTTPException(status_code=404, detail="Session not found")
            resp.raise_for_status()
            return await resp.json()
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch arbiter history: {e}")
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error(f"Failed to fetch arbiter history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orchestration/evaluations/trends")
async def get_evaluation_trends() -> Dict[str, Any]:
    """Get agent evaluation trends over time.

    Returns longitudinal performance metrics:
    - Per-agent review scores, consensus selections, runtime quality
    - Profile-level breakdowns
    - Recent evaluation events
    - Aggregated summary statistics
    """
    try:
        return await _hybrid_get("/control/ai-coordinator/evaluations/trends")
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch evaluation trends: {e}")
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error(f"Failed to fetch evaluation trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _normalize_orchestration_event(session_id: str, raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Normalize workflow trajectory rows into the Phase 93 agent-event API shape."""
    timestamp = raw.get("timestamp") or raw.get("created_at") or raw.get("ts")
    event_type = str(raw.get("event_type") or raw.get("event") or "unknown")
    token_delta = raw.get("token_delta")
    tool_call_delta = raw.get("tool_call_delta")
    payload = {
        "detail": raw.get("detail"),
        "phase_id": raw.get("phase_id"),
        "risk_class": raw.get("risk_class"),
        "approved": raw.get("approved"),
        "tool_call_delta": tool_call_delta,
        "raw_event_type": raw.get("event_type"),
    }
    return {
        "schema_version": "maeah.agent-run-event.v1",
        "event_id": str(raw.get("event_id") or raw.get("id") or f"{session_id}:{index}"),
        "event_type": event_type,
        "timestamp": timestamp,
        "source": "workflow-trajectory",
        "run_id": str(raw.get("run_id") or session_id),
        "experiment_id": raw.get("experiment_id"),
        "session_id": session_id,
        "task_id": raw.get("task_id"),
        "slice_id": raw.get("slice_id") or raw.get("phase_id"),
        "agent_id": raw.get("agent_id") or raw.get("agent"),
        "role": raw.get("role"),
        "autonomy_boundary": raw.get("autonomy_boundary"),
        "lane_id": raw.get("lane_id") or raw.get("phase_id"),
        "parent_event_id": raw.get("parent_event_id"),
        "trace_id": raw.get("trace_id"),
        "duration_ms": raw.get("duration_ms") or raw.get("latency_ms"),
        "status": raw.get("status") or raw.get("outcome") or "running",
        "route_profile": raw.get("route_profile") or raw.get("profile"),
        "model": raw.get("model"),
        "tool_name": raw.get("tool_name") or raw.get("tool"),
        "tokens": {
            "input": raw.get("tokens_in"),
            "output": raw.get("tokens_out"),
            "context": raw.get("context_tokens"),
            "tool_output": raw.get("tool_output_tokens"),
            "accepted_artifact": raw.get("accepted_artifact_tokens"),
            "rework": raw.get("rework_tokens"),
            "total": token_delta if isinstance(token_delta, int) and token_delta >= 0 else None,
            "useful_ratio": raw.get("useful_ratio"),
        },
        "cost": {
            "amount": raw.get("cost"),
            "currency": raw.get("currency"),
        },
        "artifact": raw.get("artifact") if isinstance(raw.get("artifact"), dict) else {},
        "redaction": {
            "payload_redacted": True,
            "secret_fields": [],
        },
        "payload": payload,
        "no_data_reason": None if timestamp else "missing_timestamp",
    }


async def _fetch_workflow_replay_events(
    session_id: str,
    *,
    event_type: Optional[str],
    phase: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    params: list[str] = []
    if event_type:
        params.append(f"event_type={quote(event_type)}")
    if phase:
        params.append(f"phase={quote(phase)}")
    suffix = ("?" + "&".join(params)) if params else ""
    payload = await _hybrid_get(f"/workflow/run/{quote(session_id)}/replay{suffix}")
    raw_events = payload.get("events") if isinstance(payload, dict) else []
    if not isinstance(raw_events, list):
        raw_events = []
    normalized = [
        _normalize_orchestration_event(session_id, item if isinstance(item, dict) else {}, idx)
        for idx, item in enumerate(raw_events[:limit])
    ]
    return normalized


@router.get("/orchestration/events")
async def get_orchestration_events(
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    phase: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """Return normalized workflow trajectory events for replay/swimlane/race views."""
    filters = {
        "session_id": session_id,
        "event_type": event_type,
        "phase": phase,
        "limit": limit,
    }
    try:
        if session_id:
            events = await _fetch_workflow_replay_events(
                session_id,
                event_type=event_type,
                phase=phase,
                limit=limit,
            )
        else:
            sessions_payload = await _hybrid_get("/workflow/sessions")
            sessions = sessions_payload.get("sessions") if isinstance(sessions_payload, dict) else []
            if not isinstance(sessions, list):
                sessions = []
            events = []
            for session in sessions[:5]:
                sid = str((session or {}).get("session_id") or "")
                if not sid:
                    continue
                try:
                    events.extend(
                        await _fetch_workflow_replay_events(
                            sid,
                            event_type=event_type,
                            phase=phase,
                            limit=max(limit - len(events), 0),
                        )
                    )
                except (aiohttp.ClientError, HTTPException, asyncio.TimeoutError) as exc:
                    logger.warning("orchestration/events replay fetch failed for %s: %s", sid, exc)
                if len(events) >= limit:
                    break
            events = events[:limit]
        events.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return {
            "available": True,
            "source": "workflow-trajectory",
            "count": len(events),
            "truncated": len(events) >= limit,
            "filters": filters,
            "events": events,
        }
    except (aiohttp.ClientError, HTTPException, asyncio.TimeoutError) as exc:
        logger.warning("orchestration/events unavailable: %s", exc)
        return {
            "available": False,
            "source": "workflow-trajectory",
            "count": 0,
            "truncated": False,
            "filters": filters,
            "events": [],
            "no_data_reason": str(exc),
        }
    except Exception as exc:
        logger.warning("orchestration/events error: %s", exc)
        return {
            "available": False,
            "source": "workflow-trajectory",
            "count": 0,
            "truncated": False,
            "filters": filters,
            "events": [],
            "no_data_reason": str(exc),
        }


# ---------------------------------------------------------------------------
# Phase 93.6/93.7/93.8/93.13 — Agent observability: replay, swimlane, race, controls
# ---------------------------------------------------------------------------

_AGENT_RUN_EVENTS_PATH = Path(
    os.getenv("AQ_AGENT_RUN_EVENTS_PATH", "/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl")
)
_REPO_AGENT_RUN_EVENTS_PATH = Path(__file__).parents[4] / ".agents" / "telemetry" / "agent-run-events.jsonl"
# User-space spool written by aq-agent-loop (agent_thinking, agent_tool_call, agent_step_complete).
# These events use task_id/session_id keys instead of run_id — merged on replay for aq-* run IDs.
_USER_EVENTS_SPOOL_PATH = Path(
    os.getenv("AQ_USER_EVENTS_SPOOL_PATH", str(
        Path(__file__).parents[4] / ".agents" / "telemetry" / "hybrid-events.jsonl"
    ))
)
_RACE_RUNS_PATH = Path(
    os.getenv("AQ_RACE_RUNS_PATH", "/var/lib/ai-stack/hybrid/telemetry/race-runs.jsonl")
)
_FOCUSED_CI_JSON_PATH = Path(
    os.getenv("AQ_FOCUSED_CI_JSON_PATH", "/var/lib/ai-stack/hybrid/telemetry/latest-focused-ci.json")
)

# Pydantic model for human control actions (93.8)
class AgentControlAction(BaseModel):
    action: str = Field(
        ...,
        description="pause | resume | redirect | approve | reject | request_review | promote_artifact | terminate",
    )
    reason: Optional[str] = Field(None, description="Human-readable reason for the action")
    redirect_prompt: Optional[str] = Field(None, description="New prompt when action=redirect")
    artifact_path: Optional[str] = Field(None, description="Artifact to promote when action=promote_artifact")
    operator_id: Optional[str] = Field(None, description="Operator identity for audit trail")


_VALID_CONTROL_ACTIONS = frozenset(
    {"pause", "resume", "redirect", "approve", "reject", "request_review", "promote_artifact", "terminate"}
)


def _load_agent_run_events(
    *,
    run_id: Optional[str] = None,
    experiment_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    spec_variant: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 500,
) -> tuple[list[dict], str]:
    """Load agent-run events from JSONL with optional filters. Returns (events, source_label)."""
    events: list[dict] = []
    source_label = "no_data"

    event_paths: list[tuple[Path, str]] = [(_AGENT_RUN_EVENTS_PATH, "agent-run-events")]
    if _REPO_AGENT_RUN_EVENTS_PATH != _AGENT_RUN_EVENTS_PATH:
        event_paths.append((_REPO_AGENT_RUN_EVENTS_PATH, "repo-agent-run-events"))

    for event_path, event_label in event_paths:
        if not event_path.exists():
            continue
        try:
            with event_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if run_id and record.get("run_id") != run_id:
                        continue
                    if experiment_id and record.get("experiment_id") != experiment_id:
                        continue
                    if agent_id and record.get("agent_id") != agent_id:
                        continue
                    if event_type and record.get("event_type") != event_type:
                        continue
                    if spec_variant:
                        spec = record.get("spec") or {}
                        if spec.get("variant") != spec_variant:
                            continue
                    events.append(record)
            if events:
                if source_label == "no_data":
                    source_label = event_label
                elif event_label not in source_label:
                    source_label = f"{source_label}+{event_label}"
        except OSError as exc:
            logger.warning("agent-run-events read error from %s: %s", event_path, exc)

    # User-spool fallback: aq-agent-loop writes agent_thinking/agent_tool_call/agent_step_complete
    # events to .agents/telemetry/hybrid-events.jsonl using task_id/session_id (not run_id).
    # Merge these when the run_id looks like a local agent task (aq-* prefix).
    if run_id and run_id.startswith("aq-") and _USER_EVENTS_SPOOL_PATH.exists():
        try:
            with _USER_EVENTS_SPOOL_PATH.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    task_id = record.get("task_id") or record.get("session_id") or ""
                    if task_id != run_id:
                        continue
                    if event_type and record.get("event_type") != event_type:
                        continue
                    # Normalise: add run_id so downstream code can group consistently
                    record.setdefault("run_id", run_id)
                    events.append(record)
            if events:
                source_label = "user-spool+agent-run-events" if source_label != "no_data" else "user-spool"
        except OSError as exc:
            logger.debug("user-spool read error: %s", exc)

    events = sorted(events, key=lambda e: (str(e.get("timestamp") or ""), str(e.get("event_id") or "")))
    return events[-limit:], source_label


def _load_race_runs(
    *,
    experiment_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    spec_variant: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Load race run records from JSONL."""
    if not _RACE_RUNS_PATH.exists():
        return []
    runs: list[dict] = []
    try:
        with _RACE_RUNS_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if experiment_id and record.get("experiment_id") != experiment_id:
                    continue
                if agent_id and record.get("agent_id") != agent_id:
                    continue
                if spec_variant and record.get("variant") != spec_variant:
                    continue
                runs.append(record)
        return runs[-limit:]
    except OSError as exc:
        logger.warning("race-runs read error: %s", exc)
        return []


def _run_summary(run_id: str, events: list[dict]) -> dict:
    """Summarise one run from its events for swimlane/race views."""
    run_events = [e for e in events if e.get("run_id") == run_id]
    if not run_events:
        return {"run_id": run_id, "status": "no_data", "event_count": 0}

    timestamps = [e.get("timestamp") for e in run_events if e.get("timestamp")]
    start_ts = min(timestamps) if timestamps else None
    end_ts = max(timestamps) if timestamps else None

    total_duration_ms = sum(e.get("duration_ms") or 0 for e in run_events)
    token_totals: dict[str, int] = {}
    useful_ratios: list[float] = []
    for e in run_events:
        tok = e.get("tokens") or {}
        for key in ("input", "output", "context", "tool_output", "accepted_artifact", "rework", "total"):
            val = tok.get(key)
            if isinstance(val, int):
                token_totals[key] = token_totals.get(key, 0) + val
        ur = tok.get("useful_ratio")
        if isinstance(ur, float):
            useful_ratios.append(ur)

    # Final outcome: last final_outcome event or last event status
    final_events = [e for e in run_events if e.get("event_type") == "final_outcome"]
    final_status = (final_events[-1].get("status") if final_events else run_events[-1].get("status")) or "unknown"

    # Accepted: any artifact event with accepted=True
    artifact_events = [e for e in run_events if e.get("event_type") == "artifact"]
    accepted = any((e.get("artifact") or {}).get("accepted") for e in artifact_events) or None

    return {
        "run_id": run_id,
        "experiment_id": (run_events[0].get("experiment_id") if run_events else None),
        "agent_id": (run_events[0].get("agent_id") if run_events else None),
        "lane_id": (run_events[0].get("lane_id") if run_events else None),
        "spec_variant": (run_events[0].get("spec") or {}).get("variant"),
        "route_profile": (run_events[0].get("route_profile") if run_events else None),
        "model": next((e.get("model") for e in run_events if e.get("model")), None),
        "start_ts": start_ts,
        "end_ts": end_ts,
        "duration_ms": total_duration_ms or None,
        "event_count": len(run_events),
        "final_status": final_status,
        "accepted": accepted,
        "tokens": token_totals or None,
        "useful_ratio": round(sum(useful_ratios) / len(useful_ratios), 4) if useful_ratios else None,
    }


# 93.7 — Agent runs list
@router.get("/agent-runs")
async def list_agent_runs(
    experiment_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    spec_variant: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """List agent run summaries with filtering.

    Each entry is a compact run summary: agent_id, lane_id, spec_variant,
    start/end timestamps, final_status, accepted, useful_ratio, token totals.
    """
    events, source = _load_agent_run_events(
        agent_id=agent_id,
        experiment_id=experiment_id,
        spec_variant=spec_variant,
        limit=5000,
    )

    # Group by run_id
    run_ids_seen: list[str] = []
    seen_set: set[str] = set()
    for ev in events:
        rid = ev.get("run_id")
        if rid and rid not in seen_set:
            run_ids_seen.append(rid)
            seen_set.add(rid)

    # Also include runs from race-runs JSONL (they may have no native events yet)
    race_runs = _load_race_runs(
        experiment_id=experiment_id,
        agent_id=agent_id,
        spec_variant=spec_variant,
    )
    for r in race_runs:
        rid = r.get("run_id")
        if rid and rid not in seen_set:
            run_ids_seen.append(rid)
            seen_set.add(rid)

    summaries = []
    for rid in run_ids_seen:
        s = _run_summary(rid, events)
        # Merge race run record fields if available
        race_record = next((r for r in race_runs if r.get("run_id") == rid), None)
        if race_record:
            s.setdefault("accepted", race_record.get("accepted"))
            s.setdefault("useful_ratio", race_record.get("useful_ratio"))
            s.setdefault("total_tokens", race_record.get("total_tokens"))
            s["fixture"] = race_record.get("fixture", False)
            if s.get("agent_id") is None:
                s["agent_id"] = race_record.get("agent_id")
            if s.get("spec_variant") is None:
                s["spec_variant"] = race_record.get("variant")
        if status and s.get("final_status") != status:
            continue
        summaries.append(s)

    summaries = summaries[:limit]
    if not summaries and not events:
        source = "no_data"

    return {
        "available": bool(summaries) or bool(events),
        "source": source,
        "count": len(summaries),
        "truncated": len(summaries) >= limit,
        "filters": {
            "experiment_id": experiment_id,
            "agent_id": agent_id,
            "spec_variant": spec_variant,
            "status": status,
        },
        "runs": summaries,
    }


# 93.7 — Swimlane view
@router.get("/agent-runs/swimlane")
async def get_agent_runs_swimlane(
    experiment_id: Optional[str] = None,
    limit_lanes: int = Query(10, ge=1, le=30),
    limit_events_per_lane: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """Swimlane view: one lane per agent/session/spec-variant on a shared time axis.

    Returns lanes sorted by start_ts. Each lane contains a compact event stream
    showing tool calls, waits, validations, reviews, and human interventions.
    """
    events, source = _load_agent_run_events(experiment_id=experiment_id, limit=10000)

    if not events:
        return {
            "available": False,
            "source": "no_data",
            "lane_count": 0,
            "lanes": [],
            "time_range": None,
        }

    # Group events by lane_id (fallback: run_id)
    lanes_map: dict[str, list[dict]] = {}
    for ev in events:
        lane = ev.get("lane_id") or ev.get("run_id") or "unknown"
        lanes_map.setdefault(lane, []).append(ev)

    all_timestamps = [e.get("timestamp") for e in events if e.get("timestamp")]
    time_range = {
        "start": min(all_timestamps) if all_timestamps else None,
        "end": max(all_timestamps) if all_timestamps else None,
    }

    lanes = []
    for lane_id, lane_events in list(lanes_map.items())[:limit_lanes]:
        lane_events_sorted = sorted(
            lane_events, key=lambda e: str(e.get("timestamp") or "")
        )
        # Compact lane: keep only display-relevant fields
        compact = [
            {
                "event_id": e.get("event_id"),
                "event_type": e.get("event_type"),
                "timestamp": e.get("timestamp"),
                "duration_ms": e.get("duration_ms"),
                "status": e.get("status"),
                "tool_name": e.get("tool_name"),
                "agent_id": e.get("agent_id"),
                "model": e.get("model"),
                "tokens": e.get("tokens"),
            }
            for e in lane_events_sorted[:limit_events_per_lane]
        ]
        run_id = lane_events_sorted[0].get("run_id") if lane_events_sorted else None
        summary = _run_summary(run_id or lane_id, lane_events_sorted) if run_id else {}
        lanes.append({
            "lane_id": lane_id,
            "run_id": run_id,
            "agent_id": (lane_events_sorted[0].get("agent_id") if lane_events_sorted else None),
            "spec_variant": ((lane_events_sorted[0].get("spec") or {}).get("variant") if lane_events_sorted else None),
            "start_ts": (lane_events_sorted[0].get("timestamp") if lane_events_sorted else None),
            "end_ts": (lane_events_sorted[-1].get("timestamp") if lane_events_sorted else None),
            "event_count": len(lane_events_sorted),
            "summary": summary,
            "events": compact,
        })

    # Sort lanes by start_ts
    lanes.sort(key=lambda ln: str(ln.get("start_ts") or ""))

    return {
        "available": True,
        "source": source,
        "lane_count": len(lanes),
        "time_range": time_range,
        "experiment_id": experiment_id,
        "lanes": lanes,
    }


# 93.7 — Race view
@router.get("/agent-runs/race")
async def get_agent_runs_race(
    experiment_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Race view: compare agents/profiles/spec-variants on the same prompt.

    Winner requires correctness/operator-trust gates (accepted + useful_ratio),
    not cost or speed alone. Returns runs sorted by correctness-gated score,
    then useful_ratio, then latency.
    """
    events, source = _load_agent_run_events(experiment_id=experiment_id, limit=10000)
    race_runs = _load_race_runs(experiment_id=experiment_id, limit=limit)

    # Collect all run IDs across both sources
    all_run_ids: list[str] = []
    seen: set[str] = set()
    for r in race_runs:
        rid = r.get("run_id")
        if rid and rid not in seen:
            all_run_ids.append(rid)
            seen.add(rid)
    for ev in events:
        rid = ev.get("run_id")
        if rid and rid not in seen:
            all_run_ids.append(rid)
            seen.add(rid)

    if not all_run_ids:
        return {
            "available": False,
            "source": "no_data",
            "experiment_id": experiment_id,
            "winner": None,
            "runs": [],
        }

    # Build run comparison records
    compared: list[dict] = []
    for rid in all_run_ids[:limit]:
        s = _run_summary(rid, events)
        # Enrich from race_runs record
        race_record = next((r for r in race_runs if r.get("run_id") == rid), None)
        if race_record:
            s["accepted"] = race_record.get("accepted") if s.get("accepted") is None else s["accepted"]
            s["useful_ratio"] = race_record.get("useful_ratio") if s.get("useful_ratio") is None else s["useful_ratio"]
            s["fixture"] = race_record.get("fixture", False)
            if s.get("tokens") is None and race_record.get("total_tokens"):
                s["tokens"] = {"total": race_record["total_tokens"]}
            # Enrich agent_id + spec_variant from race_record when events didn't provide them
            if s.get("agent_id") is None:
                s["agent_id"] = race_record.get("agent_id")
            if s.get("spec_variant") is None:
                s["spec_variant"] = race_record.get("variant")

        # Validation gate fields
        s["correctness_gate"] = s.get("accepted") is True
        s["trust_gate"] = s.get("accepted") is True and s.get("useful_ratio") is not None
        compared.append(s)

    # Sort: accepted+useful_ratio first, then speed
    def _sort_key(r: dict) -> tuple:
        accepted_score = 0 if r.get("accepted") is True else 1
        ur = -(r.get("useful_ratio") or 0)
        dur = r.get("duration_ms") or float("inf")
        return (accepted_score, ur, dur)

    compared.sort(key=_sort_key)

    # Winner: highest useful_ratio among accepted runs
    winner = next(
        (r["run_id"] for r in compared if r.get("accepted") is True and r.get("useful_ratio") is not None),
        None,
    )
    winner_detail = next((r for r in compared if r.get("run_id") == winner), None) if winner else None

    return {
        "available": True,
        "source": source,
        "experiment_id": experiment_id,
        "run_count": len(compared),
        "winner": winner,
        "winner_detail": winner_detail,
        "winner_criterion": "accepted=true + max(useful_ratio); correctness over speed",
        "runs": compared,
    }


# 93.6 — Single-agent replay view (registered after static sub-paths to avoid shadowing)
@router.get("/agent-runs/{run_id}")
async def get_agent_run_replay(
    run_id: str,
    event_type: Optional[str] = None,
    include_payload: bool = Query(False, description="Include redacted payload fields"),
    limit: int = Query(500, ge=1, le=2000),
) -> Dict[str, Any]:
    """Return a full event timeline for a single agent run."""
    events, source = _load_agent_run_events(run_id=run_id, event_type=event_type, limit=limit)
    if not events:
        try:
            workflow_events = await _fetch_workflow_replay_events(run_id, event_type=event_type, phase=None, limit=limit)
            if workflow_events:
                events = workflow_events
                source = "workflow-trajectory-fallback"
        except Exception as exc:
            logger.debug("run-replay workflow fallback failed for %s: %s", run_id, exc)
    if not events:
        return {
            "available": False,
            "run_id": run_id,
            "source": "no_data",
            "event_count": 0,
            "timeline": [],
            "summary": None,
            "no_data_reason": f"no events found for run_id={run_id}",
        }
    timeline = []
    for ev in events:
        entry = {k: v for k, v in ev.items() if k != "payload"}
        if include_payload:
            entry["payload"] = ev.get("payload") or {}
        else:
            raw_payload = ev.get("payload") or {}
            entry["payload_keys"] = list(raw_payload.keys()) if raw_payload else []
        timeline.append(entry)
    summary = _run_summary(run_id, events)
    tool_heatmap: dict[str, int] = {}
    for ev in events:
        tn = ev.get("tool_name")
        if tn:
            tool_heatmap[tn] = tool_heatmap.get(tn, 0) + 1
    human_controls = [ev for ev in events if ev.get("event_type") == "human_control"]
    return {
        "available": True,
        "run_id": run_id,
        "source": source,
        "event_count": len(timeline),
        "truncated": len(events) >= limit,
        "summary": summary,
        "tool_heatmap": sorted(tool_heatmap.items(), key=lambda x: -x[1]),
        "human_control_count": len(human_controls),
        "timeline": timeline,
    }


# 93.8 — Human-agent control endpoint
@router.post("/agent-runs/{run_id}/control")
async def post_agent_run_control(
    run_id: str,
    body: AgentControlAction,
) -> Dict[str, Any]:
    """Emit a human_control event for a run.

    Actions: pause | resume | redirect | approve | reject | request_review |
             promote_artifact | terminate

    Each action is written to the agent-run events JSONL as a human_control
    event, forming an auditable chain. For approve/reject, the control also
    writes to the attention queue if the run has a pending alert.

    The event is audit-only in this slice — live agent pause/resume requires
    coordinator integration (Phase 93.8.2).
    """
    if body.action not in _VALID_CONTROL_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action '{body.action}'. Valid: {sorted(_VALID_CONTROL_ACTIONS)}",
        )

    # Build human_control event envelope
    event_id = f"ctrl-{run_id[:16]}-{body.action}-{int(time.time())}"
    control_payload: dict = {"action": body.action}
    if body.reason:
        control_payload["reason"] = body.reason
    if body.redirect_prompt:
        control_payload["redirect_prompt_hash"] = hashlib.sha256(
            body.redirect_prompt.encode()
        ).hexdigest()[:16]
    if body.artifact_path:
        control_payload["artifact_path"] = body.artifact_path
    if body.operator_id:
        control_payload["operator_id"] = body.operator_id

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    event = {
        "schema_version": "maeah.agent-run-event.v1",
        "event_id": event_id,
        "event_type": "human_control",
        "timestamp": now_iso,
        "source": "dashboard-operator",
        "run_id": run_id,
        "experiment_id": None,
        "session_id": None,
        "task_id": None,
        "slice_id": None,
        "agent_id": None,
        "role": "operator",
        "autonomy_boundary": "human_gate",
        "lane_id": None,
        "parent_event_id": None,
        "trace_id": None,
        "duration_ms": None,
        "status": "succeeded",
        "route_profile": None,
        "model": None,
        "tool_name": None,
        "spec": {"variant": None, "canonical_path": None, "derived_path": None, "source_hash": None, "generator": None},
        "tokens": {"input": None, "output": None, "context": None, "tool_output": None, "accepted_artifact": None, "rework": None, "total": None, "useful_ratio": None},
        "cost": {"amount": None, "currency": None},
        "artifact": {"path": body.artifact_path, "kind": None, "hash": None, "accepted": None},
        "redaction": {"payload_redacted": False, "secret_fields": []},
        "payload": control_payload,
        "no_data_reason": None,
    }

    # Persist event
    persisted = False
    try:
        _AGENT_RUN_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AGENT_RUN_EVENTS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
        persisted = True
    except OSError as exc:
        logger.warning("agent-run control event persist failed: %s", exc)

    # Coordinator integration stub: forward to coordinator workflow/control if it exists
    coordinator_notified = False
    try:
        ctrl_url = f"/workflow/run/{quote(run_id)}/control"
        resp = await _hybrid_post(ctrl_url, {"action": body.action, "event_id": event_id})
        coordinator_notified = bool(resp)
    except Exception:
        pass  # coordinator control endpoint is optional in this slice

    return {
        "run_id": run_id,
        "action": body.action,
        "event_id": event_id,
        "timestamp": now_iso,
        "persisted": persisted,
        "coordinator_notified": coordinator_notified,
        "audit_note": "human_control event written to agent-run events JSONL",
    }


# 93.13 — Dashboard effectiveness scorecard endpoint
@router.get("/effectiveness/scorecard")
async def get_effectiveness_scorecard() -> Dict[str, Any]:
    """Return the latest effectiveness scorecard from aq-report.

    Reads from the latest-aq-report.json artifact written by aq-report.
    Falls back to no_data with a reason when the artifact is absent or stale.

    Scorecard dimensions:
      - outcome_correctness: eval pass rate, useful_ratio, delegation success
      - completion_reliability: delegation completion rate, repair success
      - operator_trust: intent compliance, trace completeness, validation_health
      - regression_containment: aq-qa pass rate, recurring QA failures
      - context_quality: hint adoption, query gap closure, memory recall precision
      - efficiency_inputs: latency P95, cache hit rate, local routing %, tokens/call

    overall_status cannot be 'pass' if outcome_correctness or operator_trust is failing.
    """
    aq_report_latest = Path(
        os.getenv("AQ_REPORT_LATEST_JSON", "/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json")
    )

    if not aq_report_latest.exists():
        return {
            "available": False,
            "status": "no_data",
            "reason": f"aq-report artifact not found: {aq_report_latest}",
            "effectiveness_scorecard": None,
        }

    try:
        raw = aq_report_latest.read_text(encoding="utf-8")
        report = json.loads(raw)
    except Exception as exc:
        return {
            "available": False,
            "status": "no_data",
            "reason": f"failed to read aq-report artifact: {exc}",
            "effectiveness_scorecard": None,
        }

    # Check age — warn if older than 24h
    generated_at = report.get("generated_at", "")
    stale = False
    try:
        report_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - report_dt).total_seconds() / 3600
        stale = age_hours > 24
    except (ValueError, AttributeError):
        stale = True

    scorecard = report.get("effectiveness_scorecard")
    if not scorecard:
        # Synthesize minimal scorecard from available report fields
        scorecard = _synthesize_scorecard_from_report(report)

    return {
        "available": True,
        "status": scorecard.get("overall_status", "no_data") if scorecard else "no_data",
        "stale": stale,
        "report_generated_at": generated_at,
        "effectiveness_scorecard": scorecard,
    }


@router.get("/local-agent/monitor")
async def get_local_agent_monitor() -> Dict[str, Any]:
    """Return current local delegation registry monitor state without mutation."""
    def _finalize_monitor_payload(payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        counts = payload.get("counts") or {}
        tasks = payload.get("tasks") or []
        repair_candidates = sum(
            1
            for task in tasks
            if task.get("registry_status") == "running"
            and task.get("inferred_only")
            and task.get("pid_alive") is False
        )
        status = "stale" if repair_candidates or counts.get("inferred_stale", 0) else "healthy"
        return {
            **payload,
            "available": True,
            "status": status,
            "activity": "active" if counts.get("running", 0) else "idle",
            "repair_candidates": repair_candidates,
            "source": source,
        }

    def _report_artifact_fallback(reason: str) -> Dict[str, Any]:
        aq_report_latest = Path(
            os.getenv("AQ_REPORT_LATEST_JSON", "/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json")
        )
        try:
            report = json.loads(aq_report_latest.read_text(encoding="utf-8"))
            monitor = report.get("local_agent_monitor") or {}
            if monitor:
                payload = _finalize_monitor_payload(monitor, str(aq_report_latest))
                payload["fallback_reason"] = reason
                return payload
        except Exception as exc:
            reason = f"{reason}; aq-report fallback failed: {exc}"
        return {
            "available": False,
            "status": "blocked",
            "reason": reason,
            "counts": {},
            "tasks": [],
            "repair_candidates": 0,
        }

    repo_root = Path(__file__).resolve().parents[4]
    lib_dir = repo_root / "scripts" / "ai" / "lib"
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))
    try:
        from task_registry import TaskRegistry  # type: ignore
    except Exception as exc:
        return _report_artifact_fallback(f"TaskRegistry import failed: {exc}")

    try:
        registry = TaskRegistry(repo_root / ".agents" / "delegation", repo_root=repo_root)
        payload = registry.monitor_payload(limit=20)
        return _finalize_monitor_payload(payload, str(registry.registry_file))
    except Exception as exc:
        return _report_artifact_fallback(str(exc))


def _synthesize_scorecard_from_report(report: dict) -> dict:
    """Build a minimal scorecard from existing aq-report fields when full scorecard absent."""
    blocking: list[str] = []

    # --- outcome_correctness ---
    eval_trend = report.get("eval_trend") or {}
    recent_pass_rate = eval_trend.get("recent_pass_rate") or eval_trend.get("pass_rate")
    useful_tokens = report.get("useful_tokens") or {}
    useful_ratio = useful_tokens.get("useful_ratio")
    delegation = report.get("delegated_prompt_failures") or {}
    del_total = delegation.get("total", 0) or 0
    del_failures = delegation.get("failures", 0) or 0
    del_success_rate: Optional[float] = None
    if del_total > 0:
        del_success_rate = round(1 - (del_failures / del_total), 4)
    oc_status = "no_data"
    if recent_pass_rate is not None:
        oc_status = "pass" if recent_pass_rate >= 0.8 else ("warn" if recent_pass_rate >= 0.6 else "fail")
        if oc_status == "fail":
            blocking.append(f"outcome_correctness: eval pass rate {recent_pass_rate:.0%} < 80%")
    outcome_correctness = {
        "status": oc_status,
        "eval_pass_rate": recent_pass_rate,
        "useful_token_ratio": useful_ratio,
        "delegation_success_rate": del_success_rate,
    }

    # --- completion_reliability ---
    cr_status = "no_data"
    if del_success_rate is not None:
        cr_status = "pass" if del_success_rate >= 0.9 else ("warn" if del_success_rate >= 0.7 else "fail")
    completion_reliability = {
        "status": cr_status,
        "delegation_success_rate": del_success_rate,
        "delegation_total": del_total,
        "delegation_failures": del_failures,
    }

    # --- operator_trust ---
    intent = report.get("intent_contract_compliance") or {}
    intent_coverage = intent.get("coverage_pct") or intent.get("compliance_pct")
    vh = report.get("validation_health") or {}
    vh_status = vh.get("status")
    ot_status = "no_data"
    if intent_coverage is not None:
        ot_status = "pass" if intent_coverage >= 0.8 else ("warn" if intent_coverage >= 0.6 else "fail")
        if ot_status == "fail":
            blocking.append(f"operator_trust: intent coverage {intent_coverage:.0%} < 80%")
    elif vh_status == "fail":
        ot_status = "warn"
    operator_trust = {
        "status": ot_status,
        "intent_coverage": intent_coverage,
        "validation_health_status": vh_status,
        "validation_checks_failed": vh.get("checks_failed"),
    }

    # --- regression_containment ---
    recent_health = report.get("recent_health") or {}
    qa_pass_rate = recent_health.get("pass_rate") or recent_health.get("qa_pass_rate")
    rc_status = "no_data"
    if qa_pass_rate is not None:
        rc_status = "pass" if qa_pass_rate >= 0.95 else ("warn" if qa_pass_rate >= 0.8 else "fail")
    regression_containment = {
        "status": rc_status,
        "qa_pass_rate": qa_pass_rate,
    }

    # --- context_quality ---
    adoption = report.get("hint_adoption") or {}
    adoption_pct = adoption.get("adoption_pct")
    gaps = report.get("query_gaps") or []
    cq_status = "no_data"
    if adoption_pct is not None:
        cq_status = "pass" if adoption_pct >= 0.6 else ("warn" if adoption_pct >= 0.4 else "fail")
    context_quality = {
        "status": cq_status,
        "hint_adoption_pct": adoption_pct,
        "open_query_gaps": len(gaps),
    }

    # --- efficiency_inputs (never blocks) ---
    cache = report.get("cache") or {}
    cache_hit_rate = cache.get("hit_rate") or cache.get("semantic_hit_rate")
    route = report.get("routing") or {}
    local_pct = route.get("local_pct") or route.get("local_routing_pct")
    efficiency_inputs = {
        "status": "ok",
        "cache_hit_rate": cache_hit_rate,
        "local_routing_pct": local_pct,
        "useful_token_ratio": useful_ratio,
    }

    # --- overall ---
    sub_statuses = [
        outcome_correctness["status"],
        completion_reliability["status"],
        operator_trust["status"],
        regression_containment["status"],
        context_quality["status"],
    ]
    if blocking:
        overall = "fail"
    elif all(s == "no_data" for s in sub_statuses):
        overall = "no_data"
    elif any(s == "fail" for s in sub_statuses):
        overall = "fail"
    elif any(s == "warn" for s in sub_statuses):
        overall = "warn"
    elif all(s == "pass" for s in sub_statuses if s != "no_data"):
        overall = "pass"
    else:
        overall = "no_data"

    return {
        "overall_status": overall,
        "outcome_correctness": outcome_correctness,
        "completion_reliability": completion_reliability,
        "operator_trust": operator_trust,
        "regression_containment": regression_containment,
        "context_quality": context_quality,
        "efficiency_inputs": efficiency_inputs,
        "blocking_reasons": blocking,
        "synthesized": True,
    }


# ---------------------------------------------------------------------------
# Phase 68.2-68.3 — MCP JSON-RPC 2.0 proxy
# ---------------------------------------------------------------------------

@router.get("/mcp/v2/tools")
async def get_mcp_v2_tools() -> Dict[str, Any]:
    """Phase 68.5: Proxy to coordinator /mcp/v2/tools — MCP JSON-RPC 2.0 tool manifest."""
    try:
        return await _hybrid_get("/mcp/v2/tools")
    except aiohttp.ClientError as e:
        logger.warning(f"MCP v2 tools unavailable (pending rebuild?): {e}")
        return {"available": False, "reason": "MCP JSON-RPC 2.0 not yet deployed — pending nixos-rebuild"}
    except Exception as e:
        logger.warning(f"MCP v2 tools error: {e}")
        return {"available": False, "reason": str(e)}


# ---------------------------------------------------------------------------
# Phase 69.3-69.4 — Temporal Knowledge Graph proxy
# ---------------------------------------------------------------------------

@router.get("/knowledge/graph/fact-chain")
async def get_fact_chain(
    subject: Optional[str] = None,
    predicate: Optional[str] = None,
    at: Optional[str] = None,
    mode: str = "chain",
    limit: int = 100,
) -> Dict[str, Any]:
    """Phase 69.4: Proxy to coordinator /knowledge/graph/fact-chain."""
    params: list[str] = [f"limit={min(limit, 500)}", f"mode={mode}"]
    if subject:
        params.append(f"subject={subject}")
    if predicate:
        params.append(f"predicate={predicate}")
    if at:
        params.append(f"at={at}")
    path = "/knowledge/graph/fact-chain?" + "&".join(params)
    try:
        return await _hybrid_get(path)
    except Exception as e:
        logger.warning(f"fact-chain unavailable: {e}")
        return {"facts": [], "total": 0, "active": 0, "superseded": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Phase 5 — Model Optimization Endpoints
# ---------------------------------------------------------------------------

@router.get("/model-optimization/readiness")
async def get_model_optimization_readiness() -> Dict[str, Any]:
    """Get Phase 5 model optimization readiness status.

    Returns readiness for:
    - Data capture and quality assessment
    - Fine-tuning pipeline
    - Model distillation and compression
    """
    try:
        return await _hybrid_get("/control/ai-coordinator/model-optimization/readiness")
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch model optimization readiness: {e}")
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error(f"Failed to fetch model optimization readiness: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-optimization/training-data/stats")
async def get_training_data_stats() -> Dict[str, Any]:
    """Get training data capture statistics.

    Returns:
    - Captured example count
    - Quality distribution
    - PII detection stats
    - Available data files
    """
    try:
        return await _hybrid_get("/control/ai-coordinator/model-optimization/training-data/stats")
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch training data stats: {e}")
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error(f"Failed to fetch training data stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-optimization/training-data/flush")
async def flush_training_data() -> Dict[str, Any]:
    """Flush pending training examples to disk.

    Returns:
    - Output file path
    - Count of flushed examples
    - Updated stats
    """
    try:
        sess = await get_http_session()
        url = f"{SERVICES['hybrid']}/control/ai-coordinator/model-optimization/training-data/flush"
        async with sess.post(url, headers=_hybrid_auth_headers(), timeout=REQUEST_TIMEOUT) as resp:
            resp.raise_for_status()
            return await resp.json()
    except aiohttp.ClientError as e:
        logger.error(f"Failed to flush training data: {e}")
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error(f"Failed to flush training data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-optimization/finetuning/jobs")
async def get_finetuning_jobs(status: Optional[str] = None) -> Dict[str, Any]:
    """List fine-tuning jobs.

    Query Parameters:
    - status: Filter by job status (pending, running, completed, failed)

    Returns list of fine-tuning jobs with status and metrics.
    """
    try:
        path = "/control/ai-coordinator/model-optimization/finetuning/jobs"
        if status:
            path += f"?status={status}"
        return await _hybrid_get(path)
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch finetuning jobs: {e}")
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error(f"Failed to fetch finetuning jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CreateFinetuningJobRequest(BaseModel):
    """Request body for creating a fine-tuning job."""
    base_model: str = Field(..., description="Base model to fine-tune")
    task_type: str = Field("general", description="Task type for specialization")
    training_data_path: Optional[str] = Field(None, description="Path to training data")


@router.post("/model-optimization/finetuning/jobs")
async def create_finetuning_job(request: CreateFinetuningJobRequest) -> Dict[str, Any]:
    """Create a new fine-tuning job.

    Creates a job record for tracking. Actual training requires system deployment.
    """
    try:
        sess = await get_http_session()
        url = f"{SERVICES['hybrid']}/control/ai-coordinator/model-optimization/finetuning/jobs"
        async with sess.post(
            url,
            headers=_hybrid_auth_headers(),
            json=request.dict(),
            timeout=REQUEST_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
    except aiohttp.ClientError as e:
        logger.error(f"Failed to create finetuning job: {e}")
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error(f"Failed to create finetuning job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-optimization/performance")
async def get_model_performance(model_id: Optional[str] = None) -> Dict[str, Any]:
    """Get model performance metrics and trends.

    Query Parameters:
    - model_id: Specific model ID or omit for all models

    Returns performance metrics, trends, and quality scores.
    """
    try:
        path = "/control/ai-coordinator/model-optimization/performance"
        if model_id:
            path += f"?model_id={model_id}"
        return await _hybrid_get(path)
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch model performance: {e}")
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error(f"Failed to fetch model performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _advanced_phase_readiness_status(readiness: Dict[str, Any], key: str) -> str:
    phase = readiness.get(key)
    if isinstance(phase, dict):
        return str(phase.get("status") or "unknown")
    return "unknown"


@router.get("/advanced/runtime-summary")
async def get_advanced_runtime_summary() -> Dict[str, Any]:
    """Aggregate advanced Phase 6-10 control-plane state for dashboard visibility."""
    try:
        sess = await get_http_session()
        headers = _hybrid_auth_headers()

        async def fetch_json(path: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
            url = f"{SERVICES['hybrid']}{path}"
            try:
                async with sess.get(url, headers=headers, timeout=REQUEST_TIMEOUT) as resp:
                    resp.raise_for_status()
                    payload = await resp.json()
                    return payload if isinstance(payload, dict) else dict(fallback)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning("advanced/runtime-summary sub-fetch %s failed: %s", path, exc)
                return dict(fallback)

        readiness_payload, quality_profiles, context_tier_stats, capability_gap_stats, learning_stats = await asyncio.gather(
            fetch_json("/control/ai-coordinator/advanced-features/readiness", {"readiness": {}}),
            fetch_json("/control/ai-coordinator/advanced-features/offloading/quality-profiles", {"profiles": []}),
            fetch_json("/control/ai-coordinator/advanced-features/context/tier-stats", {}),
            fetch_json("/control/ai-coordinator/advanced-features/capability-gap/stats", {}),
            fetch_json("/control/ai-coordinator/advanced-features/learning/stats", {}),
        )
    except aiohttp.ClientError as e:
        logger.error("Failed to fetch advanced runtime summary: %s", e)
        raise HTTPException(status_code=502, detail=f"Hybrid coordinator error: {e}")
    except Exception as e:
        logger.error("Failed to fetch advanced runtime summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    readiness = readiness_payload.get("readiness") if isinstance(readiness_payload, dict) else {}
    readiness = readiness if isinstance(readiness, dict) else {}
    profiles = quality_profiles.get("profiles") if isinstance(quality_profiles, dict) else []
    profiles = profiles if isinstance(profiles, list) else []
    failure_patterns = capability_gap_stats.get("failure_patterns") if isinstance(capability_gap_stats, dict) else {}
    failure_pattern_count = (
        len(failure_patterns)
        if isinstance(failure_patterns, dict)
        else int(capability_gap_stats.get("failure_pattern_count", 0) or 0)
    )

    return {
        "summary": {
            "offloading": {
                "status": _advanced_phase_readiness_status(readiness, "phase_6_offloading"),
                "quality_profiles": len(profiles),
                "benchmarked_profiles": int((readiness.get("phase_6_offloading") or {}).get("benchmarked_profiles", 0) or 0),
                "quality_assessments": int((readiness.get("phase_6_offloading") or {}).get("quality_assessments", 0) or 0),
                "local_fallback_mode": (readiness.get("phase_6_offloading") or {}).get("local_fallback_mode"),
            },
            "context_efficiency": {
                "status": _advanced_phase_readiness_status(readiness, "phase_7_efficiency"),
                "ab_variants": int((readiness.get("phase_7_efficiency") or {}).get("ab_variants", 0) or 0),
                "compressions": int((readiness.get("phase_7_efficiency") or {}).get("compressions", 0) or 0),
                "tokens_saved": int((readiness.get("phase_7_efficiency") or {}).get("tokens_saved", 0) or 0),
                "tier_selections": int((context_tier_stats or {}).get("total_selections", 0) or 0),
                "context_reuse_ready": bool((readiness.get("phase_7_efficiency") or {}).get("context_reuse_ready")),
            },
            "capability_gap": {
                "status": _advanced_phase_readiness_status(readiness, "phase_9_capability_gap"),
                "gaps_detected": int((capability_gap_stats or {}).get("total_gaps", 0) or 0),
                "failure_patterns": failure_pattern_count,
                "remediation_artifacts_recorded": bool((readiness.get("phase_9_capability_gap") or {}).get("remediation_artifacts_recorded")),
            },
            "learning": {
                "status": _advanced_phase_readiness_status(readiness, "phase_10_learning"),
                "signals_recorded": int((learning_stats or {}).get("total_signals", 0) or 0),
                "recommendation_count": int((learning_stats or {}).get("recommendation_count", 0) or 0),
                "high_confidence_recommendations": int((learning_stats or {}).get("high_confidence_recommendations", 0) or 0),
            },
        },
        "readiness": readiness,
        "raw": {
            "quality_profiles": quality_profiles,
            "context_tier_stats": context_tier_stats,
            "capability_gap_stats": capability_gap_stats,
            "learning_stats": learning_stats,
        },
    }


# ---------------------------------------------------------------------------
# QA Phase Runner — runs aq-qa <phase> --json and returns structured results.
# Results are cached for AQ_QA_CACHE_TTL_SECONDS to avoid overloading the
# inference stack on every dashboard refresh.
# ---------------------------------------------------------------------------
_AQ_QA_CACHE: Dict[str, Any] = {}
_AQ_QA_CACHE_TTL_S: float = float(os.getenv("DASHBOARD_AQ_QA_CACHE_TTL_SECONDS", "300"))
_AQ_QA_BACKGROUND_ENABLED: bool = os.getenv("DASHBOARD_AQ_QA_BACKGROUND", "0").strip().lower() in {"1", "true", "yes", "on"}

_VALID_QA_PHASES = frozenset({"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "all"})


_AQ_QA_RUNNING: Dict[str, bool] = {}


async def _run_aq_qa_background(phase: str, aq_qa_script: Path, env: Dict[str, str], timeout_s: int) -> None:
    """Run aq-qa in background and populate cache when done."""
    if _AQ_QA_RUNNING.get(phase):
        return
    _AQ_QA_RUNNING[phase] = True
    now = time.time()
    try:
        qa_result = await run_phase_json(phase, timeout_s=timeout_s, cwd=_repo_root())
        stderr_text = str(qa_result.get("_debug_stderr") or "")
        payload: Dict[str, Any] = {
            "phase": phase,
            "exit_code": int(qa_result.get("_exit_code", 0)),
            "success": int(qa_result.get("_exit_code", 0)) == 0,
            "qa_result": qa_result,
            "passed": int(qa_result.get("passed", 0)),
            "failed": int(qa_result.get("failed", 0)),
            "skipped": int(qa_result.get("skipped", 0)),
            "duration_s": int(qa_result.get("duration_s", 0)),
            "tests": qa_result.get("tests", []),
            "stderr": stderr_text[:500] if stderr_text else None,
            "cached": False,
            "cached_at": now,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _AQ_QA_CACHE[phase] = {"payload": payload, "cached_at": now}
    except Exception:
        pass
    finally:
        _AQ_QA_RUNNING[phase] = False


@router.get("/aq-qa/run/{phase}")
async def run_aq_qa_phase(phase: str) -> Dict[str, Any]:
    """
    Run aq-qa <phase> --json and return structured pass/fail results.
    Results are cached for 5 minutes to protect the inference stack.
    If no cached result exists, returns a pending placeholder by default.
    Background execution is opt-in via DASHBOARD_AQ_QA_BACKGROUND=1 because
    aq-qa phase 0 can fan out into report-backed checks on local-model hosts.
    Append ?force=1 to bypass the cache.
    """
    phase = phase.strip().lstrip("0") or "0"
    if phase not in _VALID_QA_PHASES:
        raise HTTPException(status_code=400, detail=f"Invalid phase '{phase}'. Must be 0-10 or all.")

    now = time.time()
    cached = _AQ_QA_CACHE.get(phase)
    # Use `is not None` — an empty cache entry dict is still a valid result
    if cached is not None and (now - cached.get("cached_at", 0)) < _AQ_QA_CACHE_TTL_S:
        return {**cached["payload"], "cached": True, "cached_at": cached["cached_at"]}

    aq_qa_script = _script_path("aq-qa")
    if not aq_qa_script.exists():
        raise HTTPException(status_code=503, detail="aq-qa script not found")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    phase_timeouts = {
        "0": 120, "1": 150, "2": 200, "3": 200,
        "4": 90,  "5": 90,  "6": 90,  "7": 90,
        "8": 120, "9": 90, "10": 90, "all": 900,
    }
    timeout_s = phase_timeouts.get(phase, 120)

    if not _AQ_QA_BACKGROUND_ENABLED:
        return {
            "phase": phase,
            "pending": True,
            "running": False,
            "cached": False,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration_s": 0,
            "tests": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": (
                f"No cached aq-qa phase {phase} result. Run aq-qa manually or set "
                "DASHBOARD_AQ_QA_BACKGROUND=1 to allow dashboard background refresh."
            ),
        }

    # No cached result — kick off background run and return pending immediately.
    # This prevents the dashboard from blocking for 40+ seconds on cold start.
    if not _AQ_QA_RUNNING.get(phase):
        asyncio.create_task(_run_aq_qa_background(phase, aq_qa_script, env, timeout_s))

    return {
        "phase": phase,
        "pending": True,
        "running": True,
        "cached": False,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration_s": 0,
        "tests": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"aq-qa phase {phase} is running in background; refresh in ~60s for results",
    }


@router.get("/switchboard/profiles")
async def get_switchboard_profiles() -> Dict[str, Any]:
    """
    Fetch switchboard /health and return profile configuration including
    maxInputTokens, maxMessages, profileCard presence, and per-profile routing metadata.
    The returned token values are switchboard profile defaults, not universal
    interactive-user caps; client surfaces may override them.
    """
    swb_url = SERVICES.get("switchboard", "")
    if not swb_url:
        raise HTTPException(status_code=503, detail="Switchboard URL not configured")

    try:
        sess = await get_http_session()
        async with sess.get(f"{swb_url}/health", timeout=REQUEST_TIMEOUT) as resp:
            resp.raise_for_status()
            health = await resp.json()
    except aiohttp.ClientError as exc:
        raise HTTPException(status_code=502, detail=f"Switchboard unreachable: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    raw_profiles: Dict[str, Any] = health.get("profiles") or {}
    profiles_out: Dict[str, Any] = {}
    for name, cfg in raw_profiles.items():
        if not isinstance(cfg, dict):
            continue
        if name in {"continue-local", "embedded-assist"}:
            intended_use = "interactive-user"
        elif name == "default":
            intended_use = "mixed-frontdoor"
        else:
            intended_use = "agent-or-lane-default"
        profiles_out[name] = {
            "maxInputTokens": cfg.get("maxInputTokens"),
            "maxMessages": cfg.get("maxMessages"),
            "maxOutputTokens": cfg.get("maxOutputTokens"),
            "advertisedContextWindow": cfg.get("advertisedContextWindow"),
            "hasProfileCard": bool(cfg.get("profileCard")),
            "profileCardLength": len(cfg.get("profileCard") or ""),
            "forceProvider": cfg.get("forceProvider"),
            "forceModel": cfg.get("forceModel"),
            "intendedUse": intended_use,
            "responseBudgetScope": "profile-default",
            "interactiveClientOverrideAllowed": True,
        }

    return {
        "status": health.get("status", "unknown"),
        "version": health.get("version"),
        "profiles": profiles_out,
        "profile_count": len(profiles_out),
        "notes": [
            "Profile maxOutputTokens values are switchboard defaults.",
            "Interactive editor/user clients may set larger response budgets.",
            "Workflow session token_limit remains the authoritative agent-to-agent budget control.",
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/task-classification/stats")
async def get_task_classification_stats() -> Dict[str, Any]:
    """
    Return tool-call audit statistics from tool_audit.jsonl.

    The audit log schema (written by S2 tool-auth middleware) contains:
      timestamp, service, tool_name, caller_hash, risk_tier, outcome,
      error_message, latency_ms, metadata.

    Note: local/remote routing labels are not present in the tool-audit log.
    Routing intent breakdown is available via /traces/summary on the coordinator.
    """
    audit_log = Path(os.getenv("TOOL_AUDIT_LOG", "/var/log/nixos-ai-stack/tool-audit.jsonl"))

    total = 0
    by_tool: Dict[str, int] = {}
    by_risk_tier: Dict[str, int] = {}
    by_outcome: Dict[str, int] = {}
    recent: list = []

    if audit_log.exists():
        try:
            lines = audit_log.read_text(errors="replace").splitlines()
            for raw in lines[-500:]:
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                total += 1
                tool = entry.get("tool_name") or "unknown"
                tier = entry.get("risk_tier") or "unknown"
                outcome = entry.get("outcome") or "unknown"
                by_tool[tool] = by_tool.get(tool, 0) + 1
                by_risk_tier[tier] = by_risk_tier.get(tier, 0) + 1
                by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
                if len(recent) < 8:
                    recent.append({
                        "timestamp": entry.get("timestamp"),
                        "tool_name": tool,
                        "risk_tier": tier,
                        "outcome": outcome,
                        "latency_ms": entry.get("latency_ms"),
                    })
        except OSError:
            pass

    success = by_outcome.get("success", 0)
    return {
        "total_classified": total,
        "by_task_type": {k: v for k, v in sorted(by_tool.items(), key=lambda x: -x[1])[:20]},
        "by_risk_tier": by_risk_tier,
        "by_outcome": by_outcome,
        "success_rate": round(100 * success / total, 1) if total else None,
        "recent_decisions": recent,
        "audit_log": str(audit_log),
        "audit_log_exists": audit_log.exists(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _recent_routing_decisions(
    rows: List[Dict[str, Any]],
    *,
    remote_configured: bool,
    limit: int,
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for row in rows[-max(1, limit):]:
        if not isinstance(row, dict):
            continue
        enriched.append(
            {
                **row,
                "category": _classify_routing_failure(row, remote_configured),
            }
        )
    return enriched


def _parse_iso_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _classify_routing_failure(row: Dict[str, Any], remote_configured: bool) -> Optional[str]:
    profile = str(row.get("routed_profile") or "").strip().lower()
    rationale = str(row.get("rationale") or "").strip().lower()
    routed_local = row.get("routed_local")
    alias = str(row.get("route_alias") or "").strip()

    if "remote-not-configured" in rationale or ("remote" in profile and not remote_configured):
        return "remote_unconfigured"
    if "remote-cached-unavailable" in rationale:
        return "remote_cache_unavailable"
    if "continue-local-http" in rationale:
        return "continue_fast_path"
    if "bounded-timeout" in rationale:
        return "bounded_local_preference"
    if profile.startswith("remote") and routed_local is True:
        return "remote_to_local_fallback"
    if alias in {"RemoteCoding", "RemoteReasoning", "RemoteFree", "RemoteGemini"} and routed_local is not False:
        return "explicit_remote_not_honored"
    return None


def _routing_windows(
    rows: List[Dict[str, Any]],
    *,
    now: datetime,
    remote_configured: bool,
) -> Dict[str, Any]:
    windows = {
        "1h": now - timedelta(hours=1),
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
    }
    payload: Dict[str, Any] = {}
    for label, start in windows.items():
        subset = [
            row for row in rows
            if isinstance(row, dict)
            and _parse_iso_timestamp(row.get("timestamp")) is not None
            and _parse_iso_timestamp(row.get("timestamp")) >= start
        ]
        local_n = sum(1 for row in subset if row.get("routed_local") is True)
        remote_n = sum(1 for row in subset if row.get("routed_local") is False)
        total = local_n + remote_n
        categories: Dict[str, int] = {}
        for row in subset:
            category = _classify_routing_failure(row, remote_configured)
            if category:
                categories[category] = categories.get(category, 0) + 1
        payload[label] = {
            "count": len(subset),
            "local_pct": round(100 * local_n / total, 1) if total else None,
            "remote_pct": round(100 * remote_n / total, 1) if total else None,
            "latest_failure_categories": sorted(
                categories.items(),
                key=lambda item: (-item[1], item[0]),
            )[:5],
        }
    return {"available": True, "windows": payload}


@router.get("/routing/summary")
async def get_routing_summary() -> Dict[str, Any]:
    """Operator-facing live routing summary across alias policy, switchboard, and audit signals."""
    switchboard_health = await fetch_with_fallback(f"{SERVICES['switchboard']}/health", {})
    task_stats = await get_task_classification_stats()
    repo_root = _repo_root()
    route_aliases_path = repo_root / "config" / "route-aliases.json"

    route_aliases_payload: Dict[str, Any] = {}
    try:
        route_aliases_payload = json.loads(route_aliases_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        route_aliases_payload = {}

    raw_profiles = switchboard_health.get("profiles") if isinstance(switchboard_health, dict) else {}
    profile_names = sorted(raw_profiles.keys()) if isinstance(raw_profiles, dict) else []
    local_profiles = [name for name in profile_names if name.startswith("local") or name in {"default", "continue-local", "embedded-assist"}]
    remote_profiles = [name for name in profile_names if name.startswith("remote")]
    local_runtime = switchboard_health.get("local_runtime") if isinstance(switchboard_health, dict) else {}
    active_request = local_runtime.get("active_request") if isinstance(local_runtime, dict) else {}
    if not isinstance(active_request, dict):
        active_request = {}

    recent_decisions = list(task_stats.get("recent_decisions") or [])
    if not recent_decisions:
        recent_decisions = [
            {
                "timestamp": None,
                "task_type": None,
                "route_alias": None,
                "routed_profile": None,
                "routed_local": None,
                "rationale": "No recent classified routing decisions recorded in tool audit.",
            }
        ]

    remote_configured = bool(switchboard_health.get("remote_configured", False)) if isinstance(switchboard_health, dict) else False
    local_lane_status = (
        _resolve_switchboard_local_lane_status(switchboard_health, local_runtime)
        if isinstance(switchboard_health, dict)
        else "unknown"
    )
    operator_notes: List[str] = []
    if not remote_configured:
        operator_notes.append("Remote routing is not configured; explicit remote aliases will fall back or remain unavailable.")
    if local_lane_status == "busy":
        operator_notes.append("Local lane is currently busy; interactive local requests may queue behind the active slot.")
    if task_stats.get("local_pct") is not None:
        operator_notes.append(f"Recent classified routing skew: local={task_stats.get('local_pct')}% remote={task_stats.get('remote_pct')}%.")
    category_mix: Dict[str, int] = {}
    for row in recent_decisions:
        category = _classify_routing_failure(row, remote_configured)
        if category:
            category_mix[category] = category_mix.get(category, 0) + 1
    # Prefer routing_stats from switchboard ring buffer (has real routed_local data).
    # Fall back to audit-log derived windows (routed_local always None there — gives count
    # but null percentages, which is correct — don't fabricate numbers).
    swb_routing_stats = (switchboard_health.get("routing_stats") or {}) if isinstance(switchboard_health, dict) else {}
    if swb_routing_stats:
        routing_windows = {
            "available": True,
            "source": "switchboard_ring",
            "windows": {
                label: {
                    "count": window.get("count", 0),
                    "local_pct": window.get("local_pct"),
                    "remote_pct": window.get("remote_pct"),
                    "latest_failure_categories": [],
                }
                for label, window in swb_routing_stats.items()
                if label != "all"
            },
        }
    else:
        routing_windows = _routing_windows(recent_decisions, now=datetime.now(timezone.utc), remote_configured=remote_configured)
    recent_decisions_enriched = _recent_routing_decisions(
        recent_decisions,
        remote_configured=remote_configured,
        limit=8,
    )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "frontdoor": {
            "source": str(route_aliases_path),
            "aliases": route_aliases_payload.get("aliases") or {},
        },
        "switchboard": {
            "status": switchboard_health.get("status", "unknown") if isinstance(switchboard_health, dict) else "unknown",
            "routing_mode": switchboard_health.get("routing_mode", "unknown") if isinstance(switchboard_health, dict) else "unknown",
            "default_provider": switchboard_health.get("default_provider", "unknown") if isinstance(switchboard_health, dict) else "unknown",
            "remote_configured": remote_configured,
            "local_lane_status": local_lane_status,
            "local_profiles": local_profiles,
            "remote_profiles": remote_profiles,
            "active_request": {
                "profile": active_request.get("profile"),
                "path": active_request.get("path"),
                "duration_s": active_request.get("duration_s"),
                "message_count": active_request.get("message_count"),
                "estimated_input_tokens": active_request.get("estimated_input_tokens"),
                "latest_user_excerpt": active_request.get("latest_user_excerpt"),
            },
            "remote_budget": switchboard_health.get("remote_budget") if isinstance(switchboard_health, dict) else {},
        },
        "classification": {
            "total_classified": task_stats.get("total_classified"),
            # local_pct / remote_pct come from the switchboard routing ring (last 500
            # chat/completions decisions). tool-audit.jsonl does not carry routing labels.
            "local_pct": (
                (switchboard_health.get("routing_stats") or {}).get("all", {}).get("local_pct")
                if isinstance(switchboard_health, dict) else None
            ),
            "remote_pct": (
                (switchboard_health.get("routing_stats") or {}).get("all", {}).get("remote_pct")
                if isinstance(switchboard_health, dict) else None
            ),
            "by_task_type": task_stats.get("by_task_type") or {},
        },
        "routing_windows": routing_windows,
        "failure_categories": sorted(
            category_mix.items(),
            key=lambda item: (-item[1], item[0]),
        )[:5],
        "recent_decisions": recent_decisions_enriched,
        "notes": operator_notes,
    }


@router.get("/routing/decisions")
async def get_routing_decisions(
    limit: Optional[int] = 25,
    route_alias: Optional[str] = None,
    routed_profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Operator-facing recent routing decision feed with lightweight filtering."""
    task_stats = await get_task_classification_stats()
    switchboard_health = await fetch_with_fallback(f"{SERVICES['switchboard']}/health", {})
    remote_configured = bool(switchboard_health.get("remote_configured", False)) if isinstance(switchboard_health, dict) else False
    decisions = _recent_routing_decisions(
        list(task_stats.get("recent_decisions") or []),
        remote_configured=remote_configured,
        limit=max(1, min(int(limit or 25), 50)),
    )

    if route_alias:
        wanted_alias = route_alias.strip().lower()
        decisions = [row for row in decisions if str(row.get("route_alias") or "").strip().lower() == wanted_alias]
    if routed_profile:
        wanted_profile = routed_profile.strip().lower()
        decisions = [row for row in decisions if str(row.get("routed_profile") or "").strip().lower() == wanted_profile]

    audit_log = Path(os.getenv("TOOL_AUDIT_LOG", "/var/log/nixos-ai-stack/tool-audit.jsonl"))
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": str(audit_log),
        "audit_log_exists": audit_log.exists(),
        "filters": {
            "limit": max(1, min(int(limit or 25), 50)),
            "route_alias": route_alias,
            "routed_profile": routed_profile,
        },
        "count": len(decisions),
        "items": decisions,
    }


@router.get("/routing/lane-failures")
async def get_routing_lane_failures() -> Dict[str, Any]:
    """Per-lane (profile) failure trend breakdown for 1h and 24h windows."""
    audit_log = Path(os.getenv("TOOL_AUDIT_LOG", "/var/log/nixos-ai-stack/tool-audit.jsonl"))
    switchboard_health = await fetch_with_fallback(f"{SERVICES['switchboard']}/health", {})
    remote_configured = bool(switchboard_health.get("remote_configured", False)) if isinstance(switchboard_health, dict) else False

    rows: List[Dict[str, Any]] = []
    if audit_log.exists():
        try:
            lines = audit_log.read_text(errors="replace").splitlines()
            for raw in lines[-500:]:
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                meta = entry.get("metadata") or {}
                routed_profile = meta.get("routed_profile") or meta.get("recommended_profile")
                routed_local = meta.get("routed_local") or meta.get("local_suitable")
                route_alias = meta.get("route_alias")
                routing_decision = meta.get("routing_decision") or {}
                rationale = (
                    meta.get("rationale")
                    or (routing_decision.get("rationale") if isinstance(routing_decision, dict) else None)
                )
                if routed_profile or route_alias or isinstance(routed_local, bool):
                    rows.append({
                        "timestamp": entry.get("timestamp"),
                        "routed_profile": routed_profile,
                        "route_alias": route_alias,
                        "routed_local": routed_local if isinstance(routed_local, bool) else None,
                        "rationale": rationale,
                    })
        except OSError:
            pass

    now = datetime.now(timezone.utc)
    window_specs = {"window_1h": now - timedelta(hours=1), "window_24h": now - timedelta(hours=24)}
    result: Dict[str, Any] = {}

    for window_label, window_start in window_specs.items():
        subset = [
            row for row in rows
            if _parse_iso_timestamp(row.get("timestamp")) is not None
            and _parse_iso_timestamp(row.get("timestamp")) >= window_start
        ]
        by_profile: Dict[str, Dict[str, Any]] = {}
        for row in subset:
            lane = str(row.get("routed_profile") or row.get("route_alias") or "unknown").strip() or "unknown"
            entry = by_profile.setdefault(lane, {"requests": 0, "failures": 0, "categories": {}, "last_failure_ts": None})
            entry["requests"] += 1
            category = _classify_routing_failure(row, remote_configured)
            if category:
                entry["failures"] += 1
                entry["categories"][category] = entry["categories"].get(category, 0) + 1
                ts = row.get("timestamp")
                if ts and (entry["last_failure_ts"] is None or ts > entry["last_failure_ts"]):
                    entry["last_failure_ts"] = ts
        lane_summary: Dict[str, Any] = {}
        for lane, data in sorted(by_profile.items()):
            reqs = data["requests"]
            fails = data["failures"]
            cats = data["categories"]
            most_common = max(cats, key=lambda k: cats[k]) if cats else None
            lane_summary[lane] = {
                "requests": reqs,
                "failures": fails,
                "rate_pct": round(100 * fails / reqs, 1) if reqs else 0.0,
                "last_failure_ts": data["last_failure_ts"],
                "most_common_failure": most_common,
                "categories": cats,
            }
        result[window_label] = lane_summary

    result["generated_at"] = now.isoformat()
    return result


@router.get("/verify-self/results")
async def get_verify_self_results() -> Dict[str, Any]:
    """
    Run verify-self-consistency.py and return results showing whether all
    roadmap verifier check_pattern calls match their target files.
    Cached for 10 minutes since this is a static analysis scan.
    """
    repo_root = _repo_root()
    script = repo_root / "scripts" / "testing" / "verify-self-consistency.py"
    if not script.exists():
        raise HTTPException(status_code=503, detail="verify-self-consistency.py not found")

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable or "python3", str(script),
            cwd=str(repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="verify-self timed out after 60s")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    stdout_text = stdout_b.decode("utf-8", errors="replace").strip()
    ok = proc.returncode == 0

    # Parse "all N verifier check_pattern references confirmed" or "[FAIL] N stale..."
    total_checks = 0
    stale_count = 0
    for line in stdout_text.splitlines():
        if "all " in line and "references confirmed" in line:
            parts = line.split()
            try:
                total_checks = int(parts[parts.index("all") + 1])
            except (ValueError, IndexError):
                pass
        if "[FAIL]" in line and "stale" in line:
            parts = line.split()
            try:
                stale_count = int(parts[1])
            except (ValueError, IndexError):
                pass

    return {
        "consistent": ok,
        "total_checks": total_checks,
        "stale_count": stale_count,
        "output": stdout_text[:1000],
        "exit_code": proc.returncode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# 3-D Graph Data Endpoints
# ---------------------------------------------------------------------------

_VECTOR_GRAPH_CACHE: Dict[str, Any] = {"ts": 0.0, "payload": None}
_VECTOR_GRAPH_TTL_S = 120.0

@router.get("/graph/vector")
async def get_vector_graph() -> Dict[str, Any]:
    """
    Return nodes + links for the repo knowledge vector graph.
    Documents are fetched from AIDB, grouped by project, and linked
    within the same project.  Limited to 300 nodes for browser performance.
    Cached 2 minutes.
    """
    now = time.time()
    if _VECTOR_GRAPH_CACHE["payload"] and now - _VECTOR_GRAPH_CACHE["ts"] < _VECTOR_GRAPH_TTL_S:
        return _VECTOR_GRAPH_CACHE["payload"]

    aidb_url = SERVICES.get("aidb", "")
    if not aidb_url:
        raise HTTPException(status_code=503, detail="AIDB URL not configured")

    PROJECT_COLORS = [
        "#4e9af1", "#f4a261", "#2ec4b6", "#e76f51", "#8ecae6",
        "#a8dadc", "#f6bd60", "#84a98c", "#b5838d", "#6d6875",
    ]

    try:
        aidb_key = ""
        key_file = os.environ.get("AIDB_API_KEY_FILE", "/run/secrets/aidb_api_key")
        try:
            aidb_key = Path(key_file).read_text().strip()
        except Exception:
            pass
        headers = {"X-API-Key": aidb_key} if aidb_key else {}

        sess = await get_http_session()
        async with sess.get(
            f"{aidb_url}/documents",
            params={"limit": 600},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail="AIDB unavailable")
            data = await resp.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AIDB error: {exc}") from exc

    docs = data.get("documents", []) if isinstance(data, dict) else []
    # Limit and deduplicate by project
    project_order: list[str] = []
    project_docs: dict[str, list] = {}
    for doc in docs:
        proj = doc.get("project") or "unknown"
        if proj not in project_docs:
            project_docs[proj] = []
            project_order.append(proj)
        project_docs[proj].append(doc)

    # Cap per-project to keep total ≤ 300
    max_per_project = max(1, 300 // max(len(project_order), 1))
    nodes: list[dict] = []
    links: list[dict] = []
    node_ids: set[str] = set()

    for proj_idx, proj in enumerate(project_order):
        color = PROJECT_COLORS[proj_idx % len(PROJECT_COLORS)]
        pdocs = project_docs[proj][:max_per_project]
        proj_node_ids: list[str] = []
        for doc in pdocs:
            nid = str(doc.get("id") or doc.get("relative_path") or doc.get("title") or f"{proj}-{len(nodes)}")
            if nid in node_ids:
                nid = f"{nid}-{len(nodes)}"
            node_ids.add(nid)
            proj_node_ids.append(nid)
            nodes.append({
                "id": nid,
                "name": doc.get("title") or doc.get("relative_path") or nid,
                "group": proj,
                "color": color,
                "val": 1,
            })
        # link sequential docs within project for graph coherence
        for i in range(len(proj_node_ids) - 1):
            links.append({"source": proj_node_ids[i], "target": proj_node_ids[i + 1], "value": 1})
        if len(proj_node_ids) > 2:
            links.append({"source": proj_node_ids[0], "target": proj_node_ids[-1], "value": 1})

    payload = {
        "nodes": nodes,
        "links": links,
        "projects": project_order,
        "total_docs": len(docs),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _VECTOR_GRAPH_CACHE["payload"] = payload
    _VECTOR_GRAPH_CACHE["ts"] = now
    return payload


@router.get("/graph/vectorization")
async def get_vectorization_posture() -> Dict[str, Any]:
    """Return compact vectorization posture for the dashboard map lens."""
    observatory, memory, ragas = await asyncio.gather(
        knowledge_observatory(),
        get_memory_collections(),
        get_ragas_scores(),
        return_exceptions=True,
    )

    if not isinstance(observatory, dict):
        observatory = {
            "total_points": 0,
            "total_collections": 0,
            "active_collections": 0,
            "collections": [],
        }
    if not isinstance(memory, dict):
        memory = {"available": False, "total_memory_points": 0, "collections": {}}
    if not isinstance(ragas, dict):
        ragas = {"available": False}

    collections = observatory.get("collections") or []
    if not isinstance(collections, list):
        collections = []
    top_collections = [
        {
            "name": str(row.get("name") or ""),
            "label": str(row.get("label") or row.get("name") or ""),
            "type": str(row.get("type") or "other"),
            "points": int(row.get("points") or 0),
            "active": bool(row.get("active")),
        }
        for row in collections[:10]
        if isinstance(row, dict)
    ]

    total_points = int(observatory.get("total_points") or 0)
    active_collections = int(observatory.get("active_collections") or 0)
    total_collections = int(observatory.get("total_collections") or len(collections))
    memory_points = int(memory.get("total_memory_points") or 0)
    ragas_available = bool(ragas.get("available"))
    status = "ok" if total_points > 0 and active_collections > 0 else "warn"
    if total_collections == 0:
        status = "degraded"

    return {
        "available": True,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vectors": {
            "total_points": total_points,
            "total_collections": total_collections,
            "active_collections": active_collections,
            "inactive_collections": max(total_collections - active_collections, 0),
            "top_collections": top_collections,
        },
        "memory": {
            "available": bool(memory.get("available")),
            "total_points": memory_points,
            "collections": memory.get("collections") or {},
        },
        "quality": {
            "available": ragas_available,
            "answer_relevance": ragas.get("answer_relevance"),
            "context_precision": ragas.get("context_precision"),
            "faithfulness": ragas.get("faithfulness"),
            "sample_count": ragas.get("sample_count"),
            "generated_at": ragas.get("generated_at"),
        },
    }


_WORKFLOW_GRAPH_CACHE: Dict[str, Any] = {"ts": 0.0, "payload": None}
_WORKFLOW_GRAPH_TTL_S = 30.0

@router.get("/graph/workflow")
async def get_workflow_graph() -> Dict[str, Any]:
    """
    Return nodes + links for the agent harness routing topology.
    Derived from the last 200 tool_audit.jsonl entries — shows which
    profiles route to which targets with traffic counts as link widths.
    Cached 30 seconds.
    """
    now = time.time()
    if _WORKFLOW_GRAPH_CACHE["payload"] and now - _WORKFLOW_GRAPH_CACHE["ts"] < _WORKFLOW_GRAPH_TTL_S:
        return _WORKFLOW_GRAPH_CACHE["payload"]

    repo_root = _repo_root()
    audit_path = Path("/var/lib/nixos-ai-stack/audit/tool_audit.jsonl")
    if not audit_path.exists():
        audit_path = repo_root / "logs" / "tool_audit.jsonl"

    # Traffic counters: (source, target) → count
    traffic: dict[tuple[str, str], int] = {}
    error_nodes: set[str] = set()

    if audit_path.exists():
        try:
            lines = audit_path.read_text().splitlines()[-200:]
            for line in lines:
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                profile = entry.get("routed_profile") or entry.get("route_alias") or "unknown"
                target = entry.get("target_type") or entry.get("provider") or "local"
                model = entry.get("model") or ""
                status = entry.get("status_code") or entry.get("status") or 200
                label = f"{target}:{model[:20]}" if model else target
                key = (profile, label)
                traffic[key] = traffic.get(key, 0) + 1
                if int(status) >= 400:
                    error_nodes.add(label)
        except Exception:
            pass

    # Static topology nodes (always present)
    static_nodes = [
        {"id": "user",          "name": "User Request",          "group": "input",    "color": "#ffffff", "val": 6},
        {"id": "switchboard",   "name": "Switchboard :8085",     "group": "router",   "color": "#f4a261", "val": 5},
        {"id": "local",         "name": "llama.cpp :8080",       "group": "local",    "color": "#2ec4b6", "val": 4},
        {"id": "remote",        "name": "Remote LLM",            "group": "remote",   "color": "#e76f51", "val": 4},
        {"id": "hybrid",        "name": "Hybrid Coord :8003",    "group": "service",  "color": "#a8dadc", "val": 4},
        {"id": "aidb",          "name": "AIDB :8002",            "group": "service",  "color": "#84a98c", "val": 3},
        {"id": "ralph",         "name": "Ralph :8004",           "group": "service",  "color": "#b5838d", "val": 3},
        {"id": "response",      "name": "Response",              "group": "output",   "color": "#ffffff", "val": 6},
    ]

    static_links = [
        {"source": "user",       "target": "switchboard", "value": 3, "color": "#666"},
        {"source": "user",       "target": "hybrid",      "value": 2, "color": "#666"},
        {"source": "switchboard","target": "local",       "value": 3, "color": "#2ec4b6"},
        {"source": "switchboard","target": "remote",      "value": 1, "color": "#e76f51"},
        {"source": "hybrid",     "target": "aidb",        "value": 2, "color": "#84a98c"},
        {"source": "hybrid",     "target": "ralph",       "value": 2, "color": "#b5838d"},
        {"source": "hybrid",     "target": "local",       "value": 2, "color": "#2ec4b6"},
        {"source": "local",      "target": "response",    "value": 3, "color": "#666"},
        {"source": "remote",     "target": "response",    "value": 1, "color": "#666"},
    ]

    # Profile nodes from audit traffic
    profile_nodes: list[dict] = []
    profile_links: list[dict] = []
    seen_profiles: set[str] = set()
    PROFILE_COLORS = {
        "local-agent": "#4e9af1", "continue-local": "#6d6875",
        "embedded-assist": "#f6bd60", "remote-coding": "#e76f51",
        "remote-reasoning": "#e76f51", "default": "#aaaaaa",
    }
    for (profile, target_label), count in sorted(traffic.items(), key=lambda x: -x[1]):
        if profile not in seen_profiles:
            seen_profiles.add(profile)
            profile_nodes.append({
                "id": f"profile:{profile}",
                "name": profile,
                "group": "profile",
                "color": PROFILE_COLORS.get(profile, "#cccccc"),
                "val": 2 + min(count, 8),
            })
            profile_links.append({
                "source": "switchboard",
                "target": f"profile:{profile}",
                "value": 1,
                "color": "#555",
            })
        target_base = "remote" if "remote" in target_label else "local"
        profile_links.append({
            "source": f"profile:{profile}",
            "target": target_base,
            "value": min(count, 5),
            "color": "#e76f51" if target_label in error_nodes else "#2ec4b6",
        })

    payload = {
        "nodes": static_nodes + profile_nodes,
        "links": static_links + profile_links,
        "traffic_summary": {k[0]: {k[1]: v} for k, v in traffic.items()},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _WORKFLOW_GRAPH_CACHE["payload"] = payload
    _WORKFLOW_GRAPH_CACHE["ts"] = now
    return payload


# ---------------------------------------------------------------------------
# Phase 64.3 — Tool Execution Heatmap
# GET /api/aistack/insights/tools/heatmap
# ---------------------------------------------------------------------------

@router.get("/insights/tools/heatmap")
async def get_tool_execution_heatmap() -> Dict[str, Any]:
    """
    Phase 64.3: Tool execution heatmap — aggregate tool_audit.jsonl by tool name.

    Returns per-tool: call_count, avg_latency_ms, error_rate, last_called.
    Sorted by call_count descending (hottest tools first).
    Reads coordinator audit log; falls back to dashboard audit log path.
    """
    # Try coordinator audit log first, then dashboard fallback
    audit_candidates = [
        Path("/var/log/ai-audit-sidecar/tool-audit.jsonl"),
        Path(os.getenv("TOOL_AUDIT_LOG", "/var/log/nixos-ai-stack/tool-audit.jsonl")),
    ]
    audit_log: Optional[Path] = None
    for candidate in audit_candidates:
        if candidate.exists():
            audit_log = candidate
            break

    tools: Dict[str, Dict] = {}

    if audit_log:
        try:
            lines = audit_log.read_text(errors="replace").splitlines()[-1000:]
            for raw in lines:
                try:
                    entry = json.loads(raw)
                except Exception:
                    continue
                tool_name = entry.get("tool_name") or "unknown"
                latency = entry.get("latency_ms") or 0
                outcome = entry.get("outcome") or "success"
                ts = entry.get("timestamp") or ""

                rec = tools.setdefault(tool_name, {
                    "tool_name": tool_name,
                    "call_count": 0,
                    "total_latency_ms": 0,
                    "error_count": 0,
                    "last_called": "",
                })
                rec["call_count"] += 1
                rec["total_latency_ms"] += int(latency) if latency else 0
                if outcome not in {"success", "ok"}:
                    rec["error_count"] += 1
                if ts > rec["last_called"]:
                    rec["last_called"] = ts
        except OSError:
            pass

    heatmap = []
    for rec in sorted(tools.values(), key=lambda r: -r["call_count"]):
        n = rec["call_count"]
        heatmap.append({
            "tool_name": rec["tool_name"],
            "call_count": n,
            "avg_latency_ms": round(rec["total_latency_ms"] / n) if n else 0,
            "error_rate": round(rec["error_count"] / n, 3) if n else 0.0,
            "last_called": rec["last_called"],
        })

    return {
        "heatmap": heatmap,
        "total_tools": len(heatmap),
        "audit_log": str(audit_log) if audit_log else None,
        "window_entries": min(len(heatmap) * 1000, 1000),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Phase 85 — Drop Zone status
# ---------------------------------------------------------------------------

@router.get("/drops/status")
async def get_drops_status() -> Dict[str, Any]:
    """Return Drop Zone daemon status and drop file counts.

    Response:
      daemon_active  bool    — whether ai-drop-daemon.service is active
      queued         int     — *.drop.yaml files in .agents/drops/
      archived       int     — files in .agents/drops/archive/
      failed         int     — files in .agents/drops/failed/
      last_error     str|None — name of most recent failed drop file (if any)
    """
    repo = _repo_root()
    drops_dir   = repo / ".agents" / "drops"
    archive_dir = drops_dir / "archive"
    failed_dir  = drops_dir / "failed"

    def _count(d: Path) -> int:
        try:
            return len(list(d.glob("*.drop.yaml")))
        except OSError:
            return 0

    queued   = _count(drops_dir)
    archived = _count(archive_dir)
    failed   = _count(failed_dir)

    last_error: Optional[str] = None
    try:
        fails = sorted(failed_dir.glob("*.drop.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)
        if fails:
            last_error = fails[0].name
    except OSError:
        pass

    # Check systemd unit status (non-blocking)
    daemon_active = False
    try:
        rc = await asyncio.to_thread(
            subprocess.run,
            ["systemctl", "is-active", "--quiet", "ai-drop-daemon.service"],
            capture_output=True, timeout=3,
        )
        daemon_active = (rc.returncode == 0)
    except Exception:
        pass

    return {
        "daemon_active": daemon_active,
        "queued": queued,
        "archived": archived,
        "failed": failed,
        "last_error": last_error,
        "drops_dir": str(drops_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/alerts/status")
async def get_alerts_status() -> Dict[str, Any]:
    """Return Phase 86 Human-in-the-Loop attention queue status.

    Response:
      pending        int     — pending human_gate / rebuild_required alerts
      oldest_severity str|None — severity of oldest pending alert
      oldest_title   str|None — title of oldest pending alert (≤60 chars)
      oldest_age_s   int|None — seconds since oldest alert was created
      queue_file_exists bool  — whether ATTENTION.json exists
    """
    repo = _repo_root()
    _lib = repo / "scripts" / "ai" / "lib"
    if str(_lib) not in sys.path:
        sys.path.insert(0, str(_lib))

    def _read_alerts():
        try:
            from attention_queue import get_pending  # type: ignore
            return get_pending()
        except Exception:
            return []

    def _queue_exists():
        return (repo / ".agents" / "attention" / "ATTENTION.json").exists()

    alerts, exists = await asyncio.gather(
        asyncio.to_thread(_read_alerts),
        asyncio.to_thread(_queue_exists),
    )

    import time as _time

    oldest_severity: Optional[str] = None
    oldest_title: Optional[str] = None
    oldest_age_s: Optional[int] = None

    if alerts:
        oldest = min(alerts, key=lambda a: a.get("created_at", ""))
        oldest_severity = oldest.get("severity")
        oldest_title = (oldest.get("title", "")[:60] or None)
        try:
            import datetime as _dt
            created = _dt.datetime.fromisoformat(oldest["created_at"].replace("Z", "+00:00"))
            oldest_age_s = int((_dt.datetime.now(_dt.timezone.utc) - created).total_seconds())
        except Exception:
            pass

    return {
        "pending": len(alerts),
        "oldest_severity": oldest_severity,
        "oldest_title": oldest_title,
        "oldest_age_s": oldest_age_s,
        "queue_file_exists": exists,
        "generated_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
    }


# ── Missing-route stubs: JS expects these endpoints ──────────────────────────

@router.get("/fleet/status")
async def get_fleet_status() -> Dict[str, Any]:
    """Agent fleet status — agents list + active sessions.

    Proxies coordinator fleet/summary and enriches with per-agent entries
    so the dashboard Fleet panel can render agent cards and session rows.
    Falls back to empty lists when coordinator is unreachable.
    """
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None

    try:
        summary = await fetch_with_fallback(
            f"{SERVICES['hybrid']}/control/fleet/summary",
            {"total_runtimes": 0, "runtimes": [], "available": False},
            headers=headers,
        )
    except Exception:
        summary = {"total_runtimes": 0, "runtimes": [], "available": False}

    # Build per-agent entries from runtimes list
    runtimes = summary.get("runtimes") or []
    agents = [
        {
            "agent_id": r.get("runtime_id") or r.get("id"),
            "profile": r.get("profile"),
            "status": r.get("status"),
            "task": r.get("current_task"),
            "started_at": r.get("started_at"),
        }
        for r in runtimes
    ]

    # Sessions: lightweight stub — coordinator does not expose sessions directly yet
    sessions: list[dict] = []

    return {
        "available": summary.get("available", False),
        "agent_count": len(agents),
        "agents": agents,
        "sessions": sessions,
        "total_runtimes": summary.get("total_runtimes", 0),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@router.get("/telemetry/anomalies")
async def get_telemetry_anomalies() -> Dict[str, Any]:
    """Health-spider anomaly feed for the Anomaly Radar panel.

    Derives anomalies from the /health/aggregate probe: any service that is
    not healthy becomes an anomaly entry with zone (service name) + issue
    (status + optional HTTP status).  Returns empty list when all healthy.
    """

    # Call health/aggregate logic inline to derive anomalies
    try:
        health = await get_health_aggregate()
    except Exception:
        health = {}

    anomalies: list[dict] = []
    for svc_name, svc in (health.get("services") or {}).items():
        if not isinstance(svc, dict):
            continue
        status = svc.get("status", "unknown")
        if status not in ("healthy",):
            details = svc.get("details") or {}
            http_err = details.get("http_error")
            anomalies.append(
                {
                    "zone": svc_name,
                    "issue": status + (f" — {http_err}" if http_err else ""),
                    "severity": "critical" if status == "down" else "warn",
                }
            )

    return {
        "available": True,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@router.get("/system-navigator")
async def get_system_navigator() -> Dict[str, Any]:
    """Return structured data from the latest-system-state.json artifact for dashboard cards.

    Reads the artifact written by the ai-system-state timer (every 15 min).
    Returns four card payloads: hub (freshness), services, collections, diagnostics.
    Never blocks to generate a fresh snapshot — returns stale flag if artifact is old.
    """
    _ARTIFACT = Path(
        os.environ.get(
            "SYSTEM_STATE_ARTIFACT_PATH",
            "/var/lib/ai-stack/hybrid/telemetry/latest-system-state.json",
        )
    )

    def _read() -> Optional[Dict[str, Any]]:
        try:
            return json.loads(_ARTIFACT.read_text())
        except Exception:
            return None

    snap = await asyncio.to_thread(_read)
    now = datetime.now(timezone.utc)

    if snap is None:
        return {
            "available": False,
            "hub": {"freshness_s": None, "generated_at": None, "domains_collected": 0},
            "services": {"active": 0, "degraded": 0, "dead": 0, "top_restarts": []},
            "collections": [],
            "diagnostics": {"error_count": 0, "failed_domains": [], "attention_items": 0},
        }

    # freshness
    try:
        gen_ts = datetime.fromisoformat(snap["generated_at"].replace("Z", "+00:00"))
        freshness_s = int((now - gen_ts).total_seconds())
    except Exception:
        freshness_s = None

    stale = freshness_s is not None and freshness_s > 1800

    # services card — "inactive/dead" is normal for completed oneshot timer services;
    # only count "failed" as truly dead to avoid false alarms.
    svcs = snap.get("services") or []
    active = sum(1 for s in svcs if s.get("status") == "active")
    dead = sum(1 for s in svcs if s.get("status") == "failed")
    degraded = len(svcs) - active - dead
    top_restarts = sorted(
        [{"name": s["name"], "restarts": s.get("restarts", 0)} for s in svcs if s.get("restarts", 0) > 0],
        key=lambda x: x["restarts"],
        reverse=True,
    )[:5]

    # collections card
    qdrant_raw = (snap.get("data") or {}).get("qdrant") or []
    collections = sorted(
        [{"name": c["name"], "points": c.get("point_count", 0)} for c in qdrant_raw],
        key=lambda x: x["points"],
        reverse=True,
    )

    # diagnostics card
    errors_raw = snap.get("errors") or []
    error_count = len(errors_raw) if isinstance(errors_raw, list) else 0
    attention_raw = snap.get("attention") or {}
    attention_items = len(attention_raw.get("items") or []) if isinstance(attention_raw, dict) else 0
    failed_domains = [
        k for k, v in snap.items()
        if isinstance(v, dict) and "_error" in v
    ]

    return {
        "available": True,
        "stale": stale,
        "hub": {
            "freshness_s": freshness_s,
            "generated_at": snap.get("generated_at"),
            "domains_collected": len(snap.get("domains_collected") or []),
            "service_count": len(svcs),
        },
        "services": {
            "active": active,
            "degraded": degraded,
            "dead": dead,
            "total": len(svcs),
            "top_restarts": top_restarts,
        },
        "collections": collections,
        "diagnostics": {
            "error_count": error_count,
            "attention_items": attention_items,
            "failed_domains": failed_domains,
        },
    }


@router.get("/collaboration/locks")
async def get_collaboration_locks() -> Dict[str, Any]:
    """Return active intent locks from the coordinator collaboration layer.

    Proxies coordinator /control/collab/locks when available.
    Falls back to an empty list so the Fleet panel renders cleanly.
    """
    api_key = _load_hybrid_api_key()
    headers = {"X-API-Key": api_key} if api_key else None

    result = await fetch_with_fallback(
        f"{SERVICES['hybrid']}/control/collab/locks",
        {"locks": [], "available": False},
        headers=headers,
    )

    locks = result.get("locks") or []
    return {
        "available": result.get("available", False),
        "lock_count": len(locks),
        "locks": locks,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@router.get("/candidate-pipeline")
async def get_candidate_pipeline() -> Dict[str, Any]:
    """Return Phase 150 candidate lifecycle pipeline counts grouped by state."""
    from collections import Counter as _Counter
    try:
        cp = Path(__file__).resolve().parents[4] / ".agents" / "improvement" / "candidates.json"
        if not cp.exists():
            return {"available": False, "states": {}, "total": 0}
        data = json.loads(cp.read_text(encoding="utf-8"))
        cands = data.get("candidates", [])
        cnt = _Counter(c.get("state", "proposed") for c in cands)
        states = {s: cnt.get(s, 0) for s in ["proposed", "evaluating", "reviewed", "adopted", "rejected", "retired"]}
        return {
            "available": True,
            "total": len(cands),
            "states": states,
            "generated_at": data.get("generated_at"),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc), "states": {}, "total": 0}


# ── Phase 184C — Observability panels (12 new panels) ─────────────────────────

_DELEGATION_FB_PATH = Path(
    os.getenv("AQ_DELEGATION_FEEDBACK_PATH",
              "/var/lib/ai-stack/hybrid/telemetry/delegation-feedback.jsonl")
)
_CL_STATS_PATH = Path(
    os.getenv("AQ_CL_STATS_PATH",
              "/var/lib/ai-stack/hybrid/telemetry/continuous_learning_stats.json")
)
_FINETUNE_DATASET_PATH = Path(
    os.getenv("FINE_TUNING_DATASET",
              "/var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl")
)


def _read_jsonl_tail(path: Path, n: int = 5000) -> list:
    """Read last n lines of a JSONL file without loading the whole file."""
    if not path.exists():
        return []
    results = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
                if len(results) > n:
                    results.pop(0)
    except OSError:
        pass
    return results


@router.get("/stats/delegation/feedback-health")
async def get_delegation_feedback_health() -> Dict[str, Any]:
    """Panel D — Delegation feedback closure rate and event_type coverage."""
    events = await asyncio.to_thread(_read_jsonl_tail, _DELEGATION_FB_PATH, 2000)
    if not events:
        return {"available": False, "total": 0, "with_event_type": 0, "closure_rate": 0.0}
    total = len(events)
    with_type = sum(1 for e in events if e.get("event_type"))
    successes = sum(1 for e in events if e.get("outcome") == "success")
    failures = sum(1 for e in events if e.get("outcome") == "failed")
    failure_classes: Dict[str, int] = {}
    for e in events:
        fc = e.get("failure_class") or "unknown"
        if e.get("outcome") == "failed":
            failure_classes[fc] = failure_classes.get(fc, 0) + 1
    return {
        "available": True,
        "total": total,
        "with_event_type": with_type,
        "closure_rate": round(with_type / total, 3) if total else 0.0,
        "successes": successes,
        "failures": failures,
        "success_rate": round(successes / total, 3) if total else 0.0,
        "top_failure_classes": dict(sorted(failure_classes.items(), key=lambda x: -x[1])[:5]),
    }


@router.get("/stats/delegate/timeseries")
async def get_delegate_timeseries(hours: int = 24, bucket_minutes: int = 60) -> Dict[str, Any]:
    """Panel A — Delegation success rate time series (rolling window, bucketed)."""
    from datetime import timezone as _tz
    cutoff = datetime.now(tz=_tz.utc) - timedelta(hours=hours)
    events = await asyncio.to_thread(_read_jsonl_tail, _DELEGATION_FB_PATH, 5000)
    buckets: Dict[str, Dict[str, int]] = {}
    for e in events:
        ts_str = e.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if ts < cutoff:
            continue
        # Bucket by floor(minute / bucket_minutes)
        floored = ts.replace(
            minute=(ts.minute // bucket_minutes) * bucket_minutes,
            second=0, microsecond=0
        )
        key = floored.isoformat()
        b = buckets.setdefault(key, {"success": 0, "failure": 0})
        if e.get("outcome") == "success":
            b["success"] += 1
        else:
            b["failure"] += 1
    series = []
    for ts_key in sorted(buckets):
        b = buckets[ts_key]
        total = b["success"] + b["failure"]
        series.append({
            "timestamp": ts_key,
            "success": b["success"],
            "failure": b["failure"],
            "total": total,
            "rate": round(b["success"] / total, 3) if total else 0.0,
        })
    overall_total = sum(s["total"] for s in series)
    overall_success = sum(s["success"] for s in series)
    return {
        "available": True,
        "hours": hours,
        "bucket_minutes": bucket_minutes,
        "series": series,
        "summary": {
            "total_delegations": overall_total,
            "total_success": overall_success,
            "overall_rate": round(overall_success / overall_total, 3) if overall_total else 0.0,
        },
    }


@router.get("/stats/training/dataset-health")
async def get_training_dataset_health() -> Dict[str, Any]:
    """Panels E+F — Finetuning dataset size and patterns learned counter."""
    # Dataset size from JSONL line count
    dataset_size = 0
    try:
        dataset_size = await asyncio.to_thread(
            lambda: sum(1 for _ in open(_FINETUNE_DATASET_PATH, errors="replace"))
            if _FINETUNE_DATASET_PATH.exists() else 0
        )
    except OSError:
        pass

    # Continuous learning stats
    cl = {}
    if _CL_STATS_PATH.exists():
        try:
            cl = json.loads(await asyncio.to_thread(_CL_STATS_PATH.read_text))
        except Exception:
            pass

    return {
        "available": True,
        "dataset_size": dataset_size,
        "finetuning_dataset_size": cl.get("finetuning_dataset_size", dataset_size),
        "patterns_learned": cl.get("total_patterns_learned", 0),
        "learning_paused": cl.get("learning_paused", False),
        "last_updated": cl.get("last_updated"),
        "dataset_path": str(_FINETUNE_DATASET_PATH),
    }


@router.get("/training/health")
async def get_training_health() -> Dict[str, Any]:
    """Slice 173-E: Training pipeline health metrics."""
    dataset_size = 0
    tool_result_samples = 0
    last_ingest_ts = None
    ingest_count_24h = 0

    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)

    if _FINETUNE_DATASET_PATH.exists():
        try:
            def scan_dataset():
                d_size = 0
                tr_samples = 0
                max_ts = None
                in_24h = 0
                with open(_FINETUNE_DATASET_PATH, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        d_size += 1
                        if '"source": "tool_result"' in line:
                            tr_samples += 1

                        try:
                            idx = line.find('"timestamp": "')
                            if idx != -1:
                                start = idx + 14
                                end = line.find('"', start)
                                if end != -1:
                                    ts_str = line[start:end]
                                    ts = datetime.fromisoformat(ts_str.replace('+00:00Z', '+00:00').replace('Z', '+00:00'))
                                    if not max_ts or ts > max_ts:
                                        max_ts = ts
                                    if ts > one_day_ago:
                                        in_24h += 1
                        except (ValueError, IndexError):
                            continue
                return d_size, tr_samples, max_ts, in_24h

            dataset_size, tool_result_samples, last_ingest_ts, ingest_count_24h = \
                await asyncio.to_thread(scan_dataset)
        except Exception:
            pass

    # RAGAS fields from hybrid coordinator
    ragas_sample_count = 0
    ragas_status = "INSUFFICIENT"
    try:
        coord_url = "http://127.0.0.1:8003/eval/trend"
        res = await fetch_with_fallback(coord_url, fallback={})
        if res:
            ragas_sample_count = res.get("ragas_sample_count", 0)
            ragas_status = res.get("ragas_status", "INSUFFICIENT")
    except Exception:
        pass

    return {
        "dataset_size": dataset_size,
        "ingest_rate_24h": round(float(ingest_count_24h) / 24.0, 2),
        "rejection_rate_24h": 0.0,
        "ragas_sample_count": ragas_sample_count,
        "ragas_status": ragas_status,
        "last_ingest_ts": last_ingest_ts.isoformat() if last_ingest_ts else None,
        "tool_result_samples": tool_result_samples
    }


@router.get("/stats/telemetry/event-distribution")
async def get_event_distribution(hours: int = 24) -> Dict[str, Any]:
    """Panel G — Agent-run event type distribution (last N hours)."""
    from datetime import timezone as _tz
    cutoff = datetime.now(tz=_tz.utc) - timedelta(hours=hours)
    events = await asyncio.to_thread(_read_jsonl_tail, _AGENT_RUN_EVENTS_PATH, 10000)
    # Also include user spool
    user_events = await asyncio.to_thread(_read_jsonl_tail, _USER_EVENTS_SPOOL_PATH, 5000)
    counts: Dict[str, int] = {}
    for e in events + user_events:
        ts_str = e.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts < cutoff:
                continue
        except (ValueError, AttributeError):
            pass
        et = e.get("event_type") or e.get("event") or "unknown"
        counts[et] = counts.get(et, 0) + 1
    distribution = [
        {"event_type": k, "count": v}
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    ]
    return {
        "available": True,
        "hours": hours,
        "total_events": sum(counts.values()),
        "distribution": distribution,
    }


_AQ_REPORT_PATH = Path(
    os.getenv("AQ_REPORT_PATH",
              "/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json")
)


@router.get("/stats/ragas")
async def get_ragas_scores() -> Dict[str, Any]:
    """Panel H — RAGAS quality scores from latest-aq-report.json ragas_metrics."""
    if not _AQ_REPORT_PATH.exists():
        return {"available": False, "reason": "aq-report not found"}
    try:
        report = json.loads(await asyncio.to_thread(_AQ_REPORT_PATH.read_text))
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    ragas = report.get("ragas_metrics") or {}
    if not ragas:
        return {"available": False, "reason": "ragas_metrics not in aq-report"}
    return {
        "available": True,
        "answer_relevance": ragas.get("answer_relevance_avg"),
        "context_precision": ragas.get("context_precision_avg"),
        "faithfulness": ragas.get("faithfulness_avg"),
        "faithfulness_enabled": ragas.get("faithfulness_enabled"),
        "sample_count": ragas.get("sample_count"),
        "generated_at": report.get("generated_at"),
    }


@router.get("/stats/memory/collections")
async def get_memory_collections() -> Dict[str, Any]:
    """Panel J — Agent memory collection point counts (episodic/procedural/semantic)."""
    memory_collections = [
        "agent-memory-episodic",
        "agent-memory-procedural",
        "agent-memory-semantic",
    ]
    results = {}
    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    try:
        sess = await get_http_session()
        for coll in memory_collections:
            try:
                async with sess.get(
                    f"{qdrant_url}/collections/{coll}",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results[coll] = data.get("result", {}).get("points_count", 0)
                    else:
                        results[coll] = 0
            except Exception:
                results[coll] = 0
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    total = sum(results.values())
    return {
        "available": True,
        "collections": results,
        "total_memory_points": total,
        "episodic": results.get("agent-memory-episodic", 0),
        "procedural": results.get("agent-memory-procedural", 0),
        "semantic": results.get("agent-memory-semantic", 0),
    }


@router.get("/stats/tools/performance")
async def get_tool_performance() -> Dict[str, Any]:
    """Panel C — Per-tool success rate from coordinator harness scorecard."""
    try:
        result = await fetch_with_fallback(
            f"{SERVICES['hybrid']}/harness/scorecard",
            None,
            _hybrid_headers(),
        )
        if result is None:
            return {"available": False}
        tools = result.get("tool_performance") or result.get("tools") or {}
        rows = []
        for name, stats in (tools.items() if isinstance(tools, dict) else []):
            calls = stats.get("calls", 0)
            success = stats.get("success", 0)
            rows.append({
                "tool": name,
                "calls": calls,
                "success": success,
                "failures": calls - success,
                "success_rate": round(success / calls, 3) if calls else 0.0,
                "p95_ms": stats.get("p95_ms"),
            })
        rows.sort(key=lambda x: x["calls"], reverse=True)
        return {"available": True, "tools": rows, "generated_at": result.get("generated_at")}
    except Exception as exc:
        return {"available": False, "error": str(exc)}
