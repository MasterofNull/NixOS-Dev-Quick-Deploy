#!/usr/bin/env python3
"""
Hybrid Agent Coordinator MCP Server

Coordinates between local LLMs and remote agents while implementing
continuous learning through interaction tracking and pattern extraction.

Features:
- Context augmentation from Qdrant
- Query routing (local vs remote)
- Outcome tracking and value scoring
- Pattern extraction and storage
- Fine-tuning data generation
- Telemetry file locking (P2-REL-003)
"""

import asyncio
import fcntl  # P2-REL-003: File locking for telemetry
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import structlog
from structlog.contextvars import bind_contextvars, merge_contextvars, clear_contextvars
from mcp import Tool
from mcp.server import Server
from mcp.types import TextContent
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from qdrant_client import QdrantClient
from qdrant_client.models import (
    CollectionInfo,
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from shared.stack_settings import HybridSettings
from shared.auth_http_client import create_embeddings_client
from shared.circuit_breaker import CircuitBreakerError, CircuitBreakerRegistry, CircuitState
from shared.telemetry_privacy import scrub_telemetry_payload
from context_compression import ContextCompressor
from embedding_cache import EmbeddingCache
SERVICE_NAME = "hybrid-coordinator"
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
HYBRID_SETTINGS = HybridSettings.load()


def configure_logging() -> None:
    bind_contextvars(service=SERVICE_NAME, version=SERVICE_VERSION)
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    pre_chain = [
        merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
    ]
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=pre_chain,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    access_logger = logging.getLogger("aiohttp.access")
    access_logger.handlers.clear()
    access_logger.propagate = True

    structlog.configure(
        processors=pre_chain + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


configure_logging()
logger = logging.getLogger(SERVICE_NAME)
STRICT_ENV = os.getenv("AI_STRICT_ENV", "true").strip().lower() in {"1", "true", "yes", "on"}


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _enforce_startup_env() -> None:
    if not STRICT_ENV:
        return

    required_env = [
        "QDRANT_URL",
        "LLAMA_CPP_BASE_URL",
        "EMBEDDING_SERVICE_URL",
        "AIDB_URL",
        "REDIS_URL",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD_FILE",
        "HYBRID_API_KEY_FILE",
        "EMBEDDING_API_KEY_FILE",
        "MCP_SERVER_MODE",
        "MCP_SERVER_PORT",
    ]
    for env_name in required_env:
        _require_env(env_name)

    for secret_env in ("POSTGRES_PASSWORD_FILE", "HYBRID_API_KEY_FILE", "EMBEDDING_API_KEY_FILE"):
        secret_file = Path(_require_env(secret_env))
        if not secret_file.exists():
            raise RuntimeError(f"AI_STRICT_ENV requires existing secret file for {secret_env}: {secret_file}")
        if not secret_file.is_file():
            raise RuntimeError(f"AI_STRICT_ENV requires file path for {secret_env}: {secret_file}")


async def _preflight_check() -> None:
    """
    Phase 1.5.2 — TCP connectivity probe for hard dependencies before accepting requests.
    Logs 'preflight_check: passed' on success; raises RuntimeError on any failure.
    """
    import socket
    from urllib.parse import urlparse

    deps: list[tuple[str, str, int]] = []

    # Redis
    redis_raw = os.getenv("REDIS_URL", "redis://localhost:6379")
    r = urlparse(redis_raw)
    deps.append(("Redis", r.hostname or "localhost", r.port or 6379))

    # Qdrant
    qdrant_raw = os.getenv("QDRANT_URL", "http://localhost:6333")
    q = urlparse(qdrant_raw)
    deps.append(("Qdrant", q.hostname or "localhost", q.port or 6333))

    # Postgres
    deps.append((
        "PostgreSQL",
        os.getenv("POSTGRES_HOST", "localhost"),
        int(os.getenv("POSTGRES_PORT", "5432")),
    ))

    failed: list[str] = []
    for name, host, port in deps:
        try:
            with socket.create_connection((host, port), timeout=5):
                logger.info("preflight_check dep=%s host=%s port=%d status=reachable", name, host, port)
        except OSError as exc:
            logger.error("preflight_check dep=%s host=%s port=%d status=unreachable error=%s",
                         name, host, port, exc)
            failed.append(f"{name} ({host}:{port})")

    if failed:
        raise RuntimeError(f"preflight_check failed — unreachable dependencies: {', '.join(failed)}")

    logger.info("preflight_check status=passed")


def configure_tracing() -> None:
    if os.getenv("OTEL_TRACING_ENABLED", "true").lower() != "true":
        return
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        if STRICT_ENV:
            raise RuntimeError("AI_STRICT_ENV requires OTEL_EXPORTER_OTLP_ENDPOINT when OTEL_TRACING_ENABLED=true")
        return
    resource = Resource.create({"service.name": SERVICE_NAME})
    sample_rate = float(os.getenv("OTEL_SAMPLE_RATE", "1.0"))
    sampler = ParentBased(TraceIdRatioBased(sample_rate))
    provider = TracerProvider(resource=resource, sampler=sampler)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


configure_tracing()
TRACER = trace.get_tracer(SERVICE_NAME)

# Initialize server
app = Server("hybrid-coordinator")

# Global clients
qdrant_client: Optional[QdrantClient] = None
llama_cpp_client: Optional[httpx.AsyncClient] = None
embedding_client: Optional[httpx.AsyncClient] = None
aidb_client: Optional[httpx.AsyncClient] = None
multi_turn_manager: Optional[Any] = None
feedback_api: Optional[Any] = None
progressive_disclosure: Optional[Any] = None
learning_pipeline: Optional[Any] = None  # Continuous learning pipeline
postgres_client: Optional[Any] = None
context_compressor: Optional[ContextCompressor] = None
embedding_cache: Optional[EmbeddingCache] = None

CIRCUIT_BREAKERS = CircuitBreakerRegistry(
    default_config={
        "failure_threshold": int(os.getenv("HYBRID_CB_FAILURE_THRESHOLD", "5")),
        "timeout": float(os.getenv("HYBRID_CB_TIMEOUT_SECONDS", "30")),
        "success_threshold": int(os.getenv("HYBRID_CB_SUCCESS_THRESHOLD", "2")),
    }
)

TELEMETRY_PATH = os.path.expanduser(
    os.getenv(
        "HYBRID_TELEMETRY_PATH",
        os.getenv(
            "TELEMETRY_PATH",
            "~/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl",
        ),
    )
)
TELEMETRY_ENABLED = os.getenv(
    "HYBRID_TELEMETRY_ENABLED",
    os.getenv("AI_TELEMETRY_ENABLED", "false"),
).lower() == "true"

HYBRID_STATS = {
    "total_queries": 0,
    "context_hits": 0,
    "last_query_at": None,
    "agent_types": {},
    "capability_discovery": {
        "invoked": 0,
        "skipped": 0,
        "cache_hits": 0,
        "errors": 0,
        "last_decision": "unknown",
        "last_reason": "not-evaluated",
    },
}

DISCOVERY_CACHE: Dict[str, Dict[str, Any]] = {}
DISCOVERY_CACHE_LOCK = asyncio.Lock()

REQUEST_COUNT = Counter(
    "hybrid_requests_total",
    "Total hybrid coordinator HTTP requests",
    ["endpoint", "status"],
)
REQUEST_ERRORS = Counter(
    "hybrid_request_errors_total",
    "Total hybrid coordinator HTTP request errors",
    ["endpoint", "method"],
)
REQUEST_LATENCY = Histogram(
    "hybrid_request_latency_seconds",
    "Hybrid coordinator HTTP request latency in seconds",
    ["endpoint", "method"],
)
PROCESS_MEMORY_BYTES = Gauge(
    "hybrid_process_memory_bytes",
    "Hybrid coordinator process resident memory in bytes",
)
ROUTE_DECISIONS = Counter(
    "hybrid_route_decisions_total",
    "Hybrid coordinator route decisions",
    ["route"],
)
ROUTE_ERRORS = Counter(
    "hybrid_route_errors_total",
    "Hybrid coordinator route errors",
    ["route"],
)
DISCOVERY_DECISIONS = Counter(
    "hybrid_capability_discovery_decisions_total",
    "Hybrid capability discovery decisions",
    ["decision", "reason"],
)
DISCOVERY_LATENCY = Histogram(
    "hybrid_capability_discovery_latency_seconds",
    "Hybrid capability discovery latency in seconds",
)
AUTONOMY_BUDGET_EXCEEDED = Counter(
    "hybrid_autonomy_budget_exceeded_total",
    "Hybrid autonomy budget exceed events",
    ["budget"],
)
# Phase 2.3.3 — per-backend routing latency (p50/p95/p99 available via Prometheus)
LLM_BACKEND_LATENCY = Histogram(
    "hybrid_llm_backend_latency_seconds",
    "End-to-end LLM call latency by backend (local=llama.cpp, remote=API)",
    ["backend"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
LLM_BACKEND_SELECTIONS = Counter(
    "hybrid_llm_backend_selections_total",
    "LLM backend selection decisions",
    ["backend", "reason_class"],
)


def _get_process_memory_bytes() -> int:
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as handle:
            rss_pages = int(handle.read().split()[1])
        return rss_pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError) as e:
        logger.debug("Failed to read process memory: %s", e)
        return 0


def record_query_stats(agent_type: str, context_found: bool) -> None:
    HYBRID_STATS["total_queries"] += 1
    if context_found:
        HYBRID_STATS["context_hits"] += 1
    HYBRID_STATS["last_query_at"] = datetime.now(timezone.utc).isoformat()
    agent_stats = HYBRID_STATS["agent_types"]
    agent_stats[agent_type] = agent_stats.get(agent_type, 0) + 1


def snapshot_stats() -> Dict[str, Any]:
    stats = dict(HYBRID_STATS)
    total = stats.get("total_queries", 0) or 0
    stats["context_hit_rate"] = (stats.get("context_hits", 0) / total) if total else 0.0
    return stats


def record_telemetry_event(event_type: str, payload: Dict[str, Any]) -> None:
    if not TELEMETRY_ENABLED:
        return

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **payload,
    }
    payload = scrub_telemetry_payload(payload)
    os.makedirs(os.path.dirname(TELEMETRY_PATH), exist_ok=True)

    # P2-REL-003: Write with file locking to prevent corruption
    with open(TELEMETRY_PATH, "a", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(payload) + "\n")
            handle.flush()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def error_payload(message: str, exc: Exception) -> Dict[str, str]:
    error_id = uuid4().hex[:12]
    logger.exception("%s error_id=%s", message, error_id)
    return {"error": message, "error_id": error_id}


def _call_with_breaker(name: str, func: Callable[[], Any]) -> Any:
    breaker = CIRCUIT_BREAKERS.get(name)
    return breaker.call(func)


async def _call_with_breaker_async(name: str, coro: Callable[[], Any]) -> Any:
    breaker = CIRCUIT_BREAKERS.get(name)
    if breaker.state == CircuitState.OPEN:
        raise CircuitBreakerError(name, breaker.timeout)
    try:
        result = await coro()
        await breaker._on_success()
        return result
    except Exception:
        await breaker._on_failure()
        raise


def _looks_like_sql(query: str) -> bool:
    normalized = query.strip().lower()
    if not normalized:
        return False
    sql_start = ("select", "with", "insert", "update", "delete")
    if normalized.startswith(sql_start):
        return True
    if ";" in normalized and (" from " in normalized or " where " in normalized):
        return True
    return False


def _normalize_tokens(query: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9_\-]{2,}", query.lower())
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "http", "https",
        "you", "your", "are", "was", "were", "can", "could", "should", "would",
    }
    return [t for t in tokens if t not in stopwords]


def _payload_matches_tokens(payload: Dict[str, Any], tokens: List[str]) -> Tuple[bool, int]:
    if not tokens or not payload:
        return False, 0
    haystacks: List[str] = []
    for value in payload.values():
        if isinstance(value, str):
            haystacks.append(value.lower())
        elif isinstance(value, list):
            haystacks.extend([str(item).lower() for item in value if isinstance(item, (str, int))])
    combined = " ".join(haystacks)
    matches = sum(1 for token in tokens if token in combined)
    return matches > 0, matches


def _extract_text_from_result(item: Dict[str, Any]) -> str:
    payload = item.get("payload") or {}
    text_parts: List[str] = []
    for key in (
        "summary",
        "description",
        "usage_pattern",
        "solution",
        "response",
        "query",
        "content",
        "procedure",
        "title",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            text_parts.append(value.strip())
    return " ".join(text_parts).strip()


def _keyword_relevance(text: str, expected_keywords: List[str]) -> float:
    if not expected_keywords:
        return 1.0
    if not text:
        return 0.0
    normalized = text.lower()
    hits = sum(1 for kw in expected_keywords if kw and kw.lower() in normalized)
    return hits / max(len(expected_keywords), 1)


def _classify_eval_failure(metrics: Dict[str, Any]) -> str:
    if not metrics.get("response_non_empty", False):
        return "empty_response"
    if metrics.get("latency_ok") is False:
        return "latency_slo_exceeded"
    if float(metrics.get("relevance_score", 0.0)) < 0.5:
        return "low_relevance"
    return "score_below_threshold"


def _tree_expand_queries(query: str, branch_factor: int) -> List[str]:
    tokens = _normalize_tokens(query)
    if not tokens:
        return [query]
    expansions: List[str] = [query]
    top = tokens[: max(1, branch_factor)]
    expansions.extend([f"{query} {token}" for token in top])
    expansions.extend([" ".join(top[:idx + 1]) for idx in range(min(len(top), branch_factor))])
    # preserve order while deduplicating
    deduped: List[str] = []
    for item in expansions:
        if item not in deduped:
            deduped.append(item)
    return deduped[: max(1, branch_factor)]


DISCOVERY_DOMAIN_KEYWORDS = {
    "tool", "tools", "mcp", "server", "servers", "skill", "skills",
    "dataset", "datasets", "document", "documents", "catalog", "library",
    "rag", "embedding", "embeddings", "vector", "workflow", "prompt",
    "prompts", "agent", "agents", "extension", "extensions", "vscodium",
}

DISCOVERY_ACTION_KEYWORDS = {
    "find", "discover", "list", "lookup", "search", "select", "choose",
    "recommend", "use", "apply", "install", "configure", "integrate",
    "wire", "map", "route", "optimize", "ingest",
}


def _update_capability_discovery_stats(decision: str, reason: str) -> None:
    stats = HYBRID_STATS["capability_discovery"]
    stats["last_decision"] = decision
    stats["last_reason"] = reason
    if decision == "invoked":
        stats["invoked"] += 1
    elif decision == "cache_hit":
        stats["cache_hits"] += 1
    elif decision == "skipped":
        stats["skipped"] += 1
    elif decision == "error":
        stats["errors"] += 1
    DISCOVERY_DECISIONS.labels(decision=decision, reason=reason).inc()


def _build_discovery_cache_key(query: str, intent_tags: List[str]) -> str:
    normalized_query = " ".join(_normalize_tokens(query))[:512]
    normalized_tags = ",".join(sorted(intent_tags))
    digest = hashlib.sha256(f"{normalized_query}|{normalized_tags}".encode("utf-8")).hexdigest()
    return digest


def _should_run_capability_discovery(query: str) -> Tuple[bool, str, List[str]]:
    if not Config.AI_CAPABILITY_DISCOVERY_ENABLED:
        return False, "disabled", []
    if len(query.strip()) < Config.AI_CAPABILITY_DISCOVERY_MIN_QUERY_CHARS:
        return False, "query-too-short", []

    tokens = _normalize_tokens(query)
    if not tokens:
        return False, "no-meaningful-tokens", []

    token_set = set(tokens)
    domain_hits = sorted(t for t in token_set if t in DISCOVERY_DOMAIN_KEYWORDS)
    action_hits = sorted(t for t in token_set if t in DISCOVERY_ACTION_KEYWORDS)

    direct_triggers = {"mcp", "tools", "skills", "dataset", "datasets", "rag", "workflow"}
    if token_set.intersection(direct_triggers):
        return True, "explicit-discovery-intent", domain_hits or ["discovery"]

    if domain_hits and action_hits:
        return True, "domain-plus-action", domain_hits

    return False, "no-discovery-intent", []


def _rank_items_for_query(
    items: List[Dict[str, Any]],
    query: str,
    *,
    fields: List[str],
    limit: int,
) -> List[Dict[str, Any]]:
    tokens = _normalize_tokens(query)
    if not items:
        return []
    if not tokens:
        return items[:limit]

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for item in items:
        text_parts: List[str] = []
        for field in fields:
            value = item.get(field)
            if isinstance(value, str):
                text_parts.append(value.lower())
            elif isinstance(value, list):
                text_parts.extend(str(v).lower() for v in value if isinstance(v, (str, int)))
        corpus = " ".join(text_parts)
        score = sum(2 if token == corpus else 1 for token in tokens if token in corpus)
        if score > 0:
            scored.append((score, item))
    if not scored:
        return items[:limit]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]


async def _discover_applicable_resources(query: str) -> Dict[str, Any]:
    decision, reason, intent_tags = _should_run_capability_discovery(query)
    if not decision:
        _update_capability_discovery_stats("skipped", reason)
        return {
            "decision": "skipped",
            "reason": reason,
            "intent_tags": intent_tags,
            "cache_hit": False,
            "tools": [],
            "skills": [],
            "servers": [],
            "datasets": [],
        }

    if aidb_client is None or not Config.AIDB_URL:
        _update_capability_discovery_stats("skipped", "aidb-unavailable")
        return {
            "decision": "skipped",
            "reason": "aidb-unavailable",
            "intent_tags": intent_tags,
            "cache_hit": False,
            "tools": [],
            "skills": [],
            "servers": [],
            "datasets": [],
        }

    cache_key = _build_discovery_cache_key(query, intent_tags)
    now = time.time()
    ttl = max(60, Config.AI_CAPABILITY_DISCOVERY_TTL_SECONDS)
    async with DISCOVERY_CACHE_LOCK:
        cached = DISCOVERY_CACHE.get(cache_key)
        if cached and float(cached.get("expires_at", 0)) > now:
            _update_capability_discovery_stats("cache_hit", "ttl-hit")
            return {
                **cached["payload"],
                "cache_hit": True,
                "decision": "cache_hit",
                "reason": "ttl-hit",
                "intent_tags": intent_tags,
            }

    start = time.time()

    async def _fetch(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        attempts = max(1, Config.AI_AUTONOMY_MAX_RETRIES + 1)
        last_error: Optional[Exception] = None
        for _ in range(attempts):
            try:
                response = await aidb_client.get(path, params=params, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                await asyncio.sleep(0.1)
        AUTONOMY_BUDGET_EXCEEDED.labels(budget="external_retries").inc()
        raise last_error or RuntimeError("external_fetch_failed")

    try:
        fetch_plan = [
            ("tools", "/tools", {"mode": "minimal"}),
            ("skills", "/skills", {"include_pending": "false"}),
            ("documents", "/documents", {"limit": 120, "include_content": "false", "include_pending": "false"}),
            ("servers", "/api/v1/federation/servers", None),
        ]
        max_calls = max(1, Config.AI_AUTONOMY_MAX_EXTERNAL_CALLS)
        if max_calls < len(fetch_plan):
            AUTONOMY_BUDGET_EXCEEDED.labels(budget="external_calls").inc()
        selected_plan = fetch_plan[:max_calls]
        responses = await asyncio.gather(
            *[_fetch(path, params) for _, path, params in selected_plan]
        )
        payload_map = {name: data for (name, _, _), data in zip(selected_plan, responses)}
        tools_payload = payload_map.get("tools", {"tools": []})
        skills_payload = payload_map.get("skills", [])
        docs_payload = payload_map.get("documents", {"documents": []})
        servers_payload = payload_map.get("servers", {"servers": []})

        max_items = max(1, Config.AI_CAPABILITY_DISCOVERY_MAX_RESULTS)
        tools = _rank_items_for_query(
            tools_payload.get("tools", []),
            query,
            fields=["name", "description"],
            limit=max_items,
        )
        skills = _rank_items_for_query(
            skills_payload if isinstance(skills_payload, list) else [],
            query,
            fields=["name", "description", "tags"],
            limit=max_items,
        )
        servers = _rank_items_for_query(
            servers_payload.get("servers", []),
            query,
            fields=["name", "description", "server_type", "source_url"],
            limit=max_items,
        )
        datasets = _rank_items_for_query(
            docs_payload.get("documents", []),
            query,
            fields=["title", "relative_path", "project", "content_type"],
            limit=max_items,
        )

        payload = {
            "decision": "invoked",
            "reason": "live-discovery",
            "intent_tags": intent_tags,
            "cache_hit": False,
            "tools": tools,
            "skills": skills,
            "servers": servers,
            "datasets": datasets,
            "latency_ms": int((time.time() - start) * 1000),
        }
        async with DISCOVERY_CACHE_LOCK:
            DISCOVERY_CACHE[cache_key] = {
                "expires_at": now + ttl,
                "payload": payload,
            }
        DISCOVERY_LATENCY.observe(time.time() - start)
        _update_capability_discovery_stats("invoked", "live-discovery")
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.warning("capability_discovery_failed error=%s", exc)
        _update_capability_discovery_stats("error", "request-failed")
        return {
            "decision": "error",
            "reason": "request-failed",
            "intent_tags": intent_tags,
            "cache_hit": False,
            "tools": [],
            "skills": [],
            "servers": [],
            "datasets": [],
            "error": str(exc),
        }


def _format_discovery_context(discovery: Dict[str, Any]) -> str:
    decision = discovery.get("decision", "unknown")
    if decision in {"skipped", "error"}:
        return ""

    lines: List[str] = ["\n## Applicable Tools, Skills, MCP Servers, and Datasets\n"]
    tools = discovery.get("tools") or []
    skills = discovery.get("skills") or []
    servers = discovery.get("servers") or []
    datasets = discovery.get("datasets") or []

    if tools:
        lines.append("- Tools:\n")
        for item in tools:
            lines.append(f"  - {item.get('name', 'unknown')}: {item.get('description', 'No description')}\n")
    if skills:
        lines.append("- Skills:\n")
        for item in skills:
            lines.append(f"  - {item.get('name', item.get('slug', 'unknown'))}: {item.get('description', 'No description')}\n")
    if servers:
        lines.append("- MCP Servers:\n")
        for item in servers:
            lines.append(f"  - {item.get('name', 'unknown')}: {item.get('description', item.get('source_url', 'No description'))}\n")
    if datasets:
        lines.append("- Datasets/Documents:\n")
        for item in datasets:
            lines.append(f"  - {item.get('title', item.get('relative_path', 'unknown'))} ({item.get('project', 'default')})\n")

    if len(lines) == 1:
        return ""
    return "".join(lines)


# ============================================================================
# Configuration
# ============================================================================


class Config:
    """Hybrid coordinator configuration"""

    QDRANT_URL = _require_env("QDRANT_URL") if STRICT_ENV else os.getenv("QDRANT_URL", HYBRID_SETTINGS.qdrant_url)
    QDRANT_API_KEY_FILE = os.getenv("QDRANT_API_KEY_FILE", "")
    QDRANT_API_KEY = ""
    QDRANT_HNSW_M = int(os.getenv("QDRANT_HNSW_M", HYBRID_SETTINGS.qdrant_hnsw_m))
    QDRANT_HNSW_EF_CONSTRUCT = int(os.getenv("QDRANT_HNSW_EF_CONSTRUCT", HYBRID_SETTINGS.qdrant_hnsw_ef_construct))
    QDRANT_HNSW_FULL_SCAN_THRESHOLD = int(
        os.getenv("QDRANT_HNSW_FULL_SCAN_THRESHOLD", HYBRID_SETTINGS.qdrant_hnsw_full_scan_threshold)
    )
    LLAMA_CPP_URL = _require_env("LLAMA_CPP_BASE_URL") if STRICT_ENV else os.getenv("LLAMA_CPP_BASE_URL", HYBRID_SETTINGS.llama_cpp_url)
    LLAMA_CPP_CODER_URL = os.getenv(
        "LLAMA_CPP_CODER_URL", HYBRID_SETTINGS.llama_cpp_url
    )
    LLAMA_CPP_DEEPSEEK_URL = os.getenv(
        "LLAMA_CPP_DEEPSEEK_URL", HYBRID_SETTINGS.llama_cpp_url
    )

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", HYBRID_SETTINGS.embedding_model)
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSIONS", HYBRID_SETTINGS.embedding_dimensions))
    EMBEDDING_SERVICE_URL = _require_env("EMBEDDING_SERVICE_URL") if STRICT_ENV else os.getenv("EMBEDDING_SERVICE_URL", "")
    EMBEDDING_API_KEY_FILE = os.getenv("EMBEDDING_API_KEY_FILE", "")
    EMBEDDING_API_KEY = ""
    AIDB_URL = _require_env("AIDB_URL") if STRICT_ENV else os.getenv("AIDB_URL", "")

    LOCAL_CONFIDENCE_THRESHOLD = float(
        os.getenv("LOCAL_CONFIDENCE_THRESHOLD", HYBRID_SETTINGS.local_confidence_threshold)
    )
    HIGH_VALUE_THRESHOLD = float(os.getenv("HIGH_VALUE_THRESHOLD", HYBRID_SETTINGS.high_value_threshold))
    PATTERN_EXTRACTION_ENABLED = os.getenv(
        "PATTERN_EXTRACTION_ENABLED", str(HYBRID_SETTINGS.pattern_extraction_enabled)
    ).lower() == "true"

    # Token Optimization Flags (Day 1)
    QUERY_EXPANSION_ENABLED = os.getenv("QUERY_EXPANSION_ENABLED", "false").lower() == "true"
    REMOTE_LLM_FEEDBACK_ENABLED = os.getenv("REMOTE_LLM_FEEDBACK_ENABLED", "false").lower() == "true"
    MULTI_TURN_QUERY_EXPANSION = os.getenv("MULTI_TURN_QUERY_EXPANSION", "false").lower() == "true"
    DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "1000"))
    # Canonical name; CONTEXT_COMPRESSION_ENABLED kept as alias below for back-compat.
    AI_CONTEXT_COMPRESSION_ENABLED = os.getenv("AI_CONTEXT_COMPRESSION_ENABLED",
        os.getenv("CONTEXT_COMPRESSION_ENABLED", "true")).lower() == "true"

    FINETUNE_DATA_PATH = os.path.expanduser(
        os.getenv(
            "FINETUNE_DATA_PATH",
            HYBRID_SETTINGS.finetune_data_path
            or "~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl",
        )
    )
    API_KEY_FILE = _require_env("HYBRID_API_KEY_FILE") if STRICT_ENV else os.getenv("HYBRID_API_KEY_FILE", HYBRID_SETTINGS.api_key_file or "")
    API_KEY = ""
    AI_HARNESS_ENABLED = os.getenv("AI_HARNESS_ENABLED", "true").lower() == "true"
    AI_MEMORY_ENABLED = os.getenv("AI_MEMORY_ENABLED", "true").lower() == "true"
    AI_MEMORY_MAX_RECALL_ITEMS = int(os.getenv("AI_MEMORY_MAX_RECALL_ITEMS", "8"))
    AI_TREE_SEARCH_ENABLED = os.getenv("AI_TREE_SEARCH_ENABLED", "true").lower() == "true"
    AI_TREE_SEARCH_MAX_DEPTH = int(os.getenv("AI_TREE_SEARCH_MAX_DEPTH", "2"))
    AI_TREE_SEARCH_BRANCH_FACTOR = int(os.getenv("AI_TREE_SEARCH_BRANCH_FACTOR", "3"))
    AI_HARNESS_EVAL_ENABLED = os.getenv("AI_HARNESS_EVAL_ENABLED", "true").lower() == "true"
    AI_HARNESS_MIN_ACCEPTANCE_SCORE = float(
        os.getenv("AI_HARNESS_MIN_ACCEPTANCE_SCORE", "0.7")
    )
    AI_HARNESS_MAX_LATENCY_MS = int(os.getenv("AI_HARNESS_MAX_LATENCY_MS", "3000"))
    AI_CAPABILITY_DISCOVERY_ENABLED = os.getenv(
        "AI_CAPABILITY_DISCOVERY_ENABLED",
        "true",
    ).lower() == "true"
    AI_CAPABILITY_DISCOVERY_TTL_SECONDS = int(
        os.getenv("AI_CAPABILITY_DISCOVERY_TTL_SECONDS", "1800")
    )
    AI_CAPABILITY_DISCOVERY_MIN_QUERY_CHARS = int(
        os.getenv("AI_CAPABILITY_DISCOVERY_MIN_QUERY_CHARS", "18")
    )
    AI_CAPABILITY_DISCOVERY_MAX_RESULTS = int(
        os.getenv("AI_CAPABILITY_DISCOVERY_MAX_RESULTS", "3")
    )
    AI_CAPABILITY_DISCOVERY_ON_QUERY = os.getenv(
        "AI_CAPABILITY_DISCOVERY_ON_QUERY",
        "true",
    ).lower() == "true"
    AI_AUTONOMY_MAX_EXTERNAL_CALLS = int(
        os.getenv("AI_AUTONOMY_MAX_EXTERNAL_CALLS", "4")
    )
    AI_AUTONOMY_MAX_RETRIES = int(
        os.getenv("AI_AUTONOMY_MAX_RETRIES", "1")
    )
    AI_AUTONOMY_MAX_RETRIEVAL_RESULTS = int(
        os.getenv("AI_AUTONOMY_MAX_RETRIEVAL_RESULTS", "8")
    )
    AI_PROMPT_CACHE_POLICY_ENABLED = os.getenv(
        "AI_PROMPT_CACHE_POLICY_ENABLED",
        "true",
    ).lower() == "true"
    AI_PROMPT_CACHE_STATIC_PREFIX = os.getenv(
        "AI_PROMPT_CACHE_STATIC_PREFIX",
        "You are the NixOS AI stack coordinator. Prefer local-first secure execution.",
    )
    AI_SPECULATIVE_DECODING_ENABLED = os.getenv(
        "AI_SPECULATIVE_DECODING_ENABLED",
        "false",
    ).lower() == "true"
    AI_SPECULATIVE_DECODING_MODE = os.getenv(
        "AI_SPECULATIVE_DECODING_MODE",
        "draft-model",
    )
    AI_CONTEXT_MAX_TOKENS = int(os.getenv("AI_CONTEXT_MAX_TOKENS", "3000"))


def _read_secret(path: str) -> str:
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        return ""


if not Config.QDRANT_API_KEY and Config.QDRANT_API_KEY_FILE:
    Config.QDRANT_API_KEY = _read_secret(Config.QDRANT_API_KEY_FILE)
if not Config.API_KEY and Config.API_KEY_FILE:
    Config.API_KEY = _read_secret(Config.API_KEY_FILE)
if not Config.EMBEDDING_API_KEY and Config.EMBEDDING_API_KEY_FILE:
    Config.EMBEDDING_API_KEY = _read_secret(Config.EMBEDDING_API_KEY_FILE)


# ============================================================================
# Hot-reloadable Routing Config (Phase 2.2.1)
# ============================================================================

@dataclass
class RoutingConfig:
    """Hot-reloadable routing threshold configuration.

    Reads ``~/.local/share/nixos-ai-stack/routing-config.json`` on each call
    to ``get_threshold()`` if the cached value is older than 60 seconds.
    Falls back to the env-var default when the file is absent or malformed.
    """

    threshold: float = field(
        default_factory=lambda: float(
            os.getenv("LOCAL_CONFIDENCE_THRESHOLD", HYBRID_SETTINGS.local_confidence_threshold)
        )
    )
    _path: Path = field(
        default_factory=lambda: Path.home() / ".local/share/nixos-ai-stack/routing-config.json",
        repr=False,
    )
    _loaded_at: float = field(default=0.0, repr=False)
    _ttl: float = field(default=60.0, repr=False)

    async def get_threshold(self) -> float:
        """Return current threshold, reloading from disk if TTL has expired."""
        now = time.monotonic()
        if now - self._loaded_at < self._ttl:
            return self.threshold
        # TTL expired — try to reload from the JSON file
        if self._path.exists():
            try:
                raw = self._path.read_text(encoding="utf-8")
                data = json.loads(raw)
                value = float(data["local_confidence_threshold"])
                self.threshold = value
            except Exception:  # noqa: BLE001
                pass  # keep existing cached value on parse error
        self._loaded_at = now
        return self.threshold

    def write_threshold(self, value: float) -> None:
        """Atomically write a new threshold to the config file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"local_confidence_threshold": value}), encoding="utf-8")
        tmp.replace(self._path)
        self.threshold = value
        self._loaded_at = time.monotonic()


# Module-level singleton used by routing and proposal handlers.
routing_config: RoutingConfig = RoutingConfig()

# TODO Phase 2.2.2: wire routing_threshold_adjustment proposals to routing_config.write_threshold()


# ============================================================================
# Phase 2.2.3 — 7-Day Rolling Performance Window & Auto-Nudge
# ============================================================================

@dataclass
class PerformanceWindow:
    """Track local LLM success/failure per query-type bucket over a rolling 7-day window.

    Records are stored in a JSON file keyed by ISO date → bucket → {success, total}.
    When enough samples are collected, `maybe_nudge` adjusts the routing confidence
    threshold up (if local is performing well) or down (if it is underperforming).

    Wire `record(bucket, success=True/False)` into the feedback endpoint (Phase 3.1).
    Call `maybe_nudge(routing_config)` from a periodic background task or on startup.
    """

    TARGET_SUCCESS_RATE: float = 0.80   # local LLM should get ≥80% of responses right
    NUDGE_AMOUNT: float = 0.05          # threshold change per weekly adjustment
    THRESHOLD_MIN: float = 0.30         # never drop below — prevents runaway local routing
    THRESHOLD_MAX: float = 0.95         # never exceed — preserves some remote fallback
    WINDOW_DAYS: int = 7
    MIN_SAMPLES: int = 10               # require this many samples before nudging

    _path: Path = field(
        default_factory=lambda: Path.home() / ".local/share/nixos-ai-stack/performance-window.json",
        repr=False,
    )
    _data: dict = field(default_factory=dict, repr=False)
    _loaded: bool = field(default=False, repr=False)

    def _load(self) -> None:
        if self._loaded:
            return
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}
        self._loaded = True

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def _today(self) -> str:
        from datetime import date
        return date.today().isoformat()

    def record(self, bucket: str, success: bool) -> None:
        """Record one local-LLM response outcome for the given query-type bucket.

        Call with bucket='nixos', 'code', 'general', etc. based on query classification.
        success=True means user confirmed or heuristic-confirmed the response was useful.
        """
        self._load()
        today = self._today()
        buckets = self._data.setdefault("buckets", {})
        day_data = buckets.setdefault(bucket, {}).setdefault(today, {"success": 0, "total": 0})
        day_data["total"] += 1
        if success:
            day_data["success"] += 1
        self._save()

    def _window_stats(self) -> dict[str, dict[str, int]]:
        """Return aggregated {bucket: {success, total}} over the last WINDOW_DAYS days."""
        from datetime import date, timedelta
        self._load()
        cutoff = (date.today() - timedelta(days=self.WINDOW_DAYS)).isoformat()
        agg: dict[str, dict[str, int]] = {}
        for bucket, days in self._data.get("buckets", {}).items():
            for day, counts in days.items():
                if day >= cutoff:
                    agg.setdefault(bucket, {"success": 0, "total": 0})
                    agg[bucket]["success"] += counts.get("success", 0)
                    agg[bucket]["total"] += counts.get("total", 0)
        return agg

    def maybe_nudge(self, cfg: "RoutingConfig") -> None:  # type: ignore[name-defined]
        """Check 7-day performance and nudge the routing threshold if warranted.

        Call this from a weekly background task. No-op if fewer than MIN_SAMPLES
        total responses have been recorded (avoids nudging on noise).

        Nudge logic:
          - Overall success rate > TARGET: lower threshold → route more to local
          - Overall success rate < TARGET: raise threshold → route more to remote
        """
        stats = self._window_stats()
        total = sum(v["total"] for v in stats.values())
        if total < self.MIN_SAMPLES:
            logger.info(
                "performance_window_nudge_skipped total_samples=%d min_required=%d",
                total, self.MIN_SAMPLES,
            )
            return

        success = sum(v["success"] for v in stats.values())
        rate = success / total if total else 0.0
        current = cfg.threshold
        if rate >= self.TARGET_SUCCESS_RATE:
            new_threshold = max(self.THRESHOLD_MIN, current - self.NUDGE_AMOUNT)
            direction = "down"
        else:
            new_threshold = min(self.THRESHOLD_MAX, current + self.NUDGE_AMOUNT)
            direction = "up"

        if new_threshold != current:
            cfg.write_threshold(new_threshold)
            logger.info(
                "performance_window_nudge direction=%s old=%.3f new=%.3f "
                "success_rate=%.3f samples=%d",
                direction, current, new_threshold, rate, total,
            )
        else:
            logger.info(
                "performance_window_nudge at_limit threshold=%.3f direction=%s success_rate=%.3f",
                current, direction, rate,
            )


performance_window: PerformanceWindow = PerformanceWindow()


# ============================================================================
# Local LLM Liveness Probe + Model Loading Queue (Phase 2.3.1 / 2.4.1)
# ============================================================================

# Cached liveness state — re-checked at most every 10 seconds.
_local_llm_healthy: bool = True
_local_llm_loading: bool = False        # True when llama.cpp returns status="loading"
_local_llm_checked_at: float = 0.0

# Phase 2.4.1 — model-loading request queue.
# asyncio.Event is set when the local model is ready; cleared during loading.
# Callers wait on this event; _model_loading_queue_depth counts waiters.
_model_load_event: asyncio.Event = asyncio.Event()
_model_load_event.set()                 # starts as "ready"
_model_loading_queue_depth: int = 0
_MODEL_QUEUE_MAX: int = int(os.getenv("MODEL_LOADING_QUEUE_MAX", "10"))


async def _check_local_llm_health() -> bool:
    """Check whether the local llama.cpp server is reachable and ready.

    Phase 2.3.1: 500 ms timeout, 10 s cache, logs only on state change.
    Phase 2.4.1: distinguishes 'loading' from 'unreachable'; manages
    _model_load_event so waiting callers are released when load completes.

    Returns True when llama.cpp is reachable (even if still loading).
    Returns False when unreachable/error.
    """
    global _local_llm_healthy, _local_llm_loading, _local_llm_checked_at
    now = time.monotonic()
    if now - _local_llm_checked_at <= 10.0:
        return _local_llm_healthy

    new_healthy = False
    new_loading = False
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            resp = await client.get(f"{Config.LLAMA_CPP_URL}/health")
            new_healthy = resp.is_success
            if new_healthy:
                try:
                    body = resp.json()
                    new_loading = body.get("status") == "loading"
                except Exception:  # noqa: BLE001
                    new_loading = False
    except Exception:  # noqa: BLE001
        new_healthy = False

    _local_llm_checked_at = now

    # Manage the load event — set when ready, cleared when loading.
    if new_healthy and not new_loading:
        if not _model_load_event.is_set():
            logger.info("local_llm_model_ready queue_depth=%d", _model_loading_queue_depth)
        _model_load_event.set()
    elif new_healthy and new_loading:
        _model_load_event.clear()
    else:
        # Unreachable — also clear so waiters don't block forever; they'll
        # time out and be handled by the 503 path.
        _model_load_event.clear()

    if new_healthy != _local_llm_healthy:
        if new_healthy:
            logger.info("local_llm_health_changed healthy=True loading=%s", new_loading)
        else:
            logger.warning("local_llm_fallback_to_remote reason=local_unhealthy")

    if new_loading != _local_llm_loading:
        if new_loading:
            logger.info("local_llm_loading_started model=%s", os.getenv("LLAMA_MODEL_NAME", "unknown"))
        else:
            logger.info("local_llm_loading_finished")

    _local_llm_healthy = new_healthy
    _local_llm_loading = new_loading
    return _local_llm_healthy


async def _wait_for_local_model(timeout: float = 30.0) -> bool:
    """Phase 2.4.1 — Wait for the local model to finish loading.

    Enqueues the caller into the loading-wait pool (up to _MODEL_QUEUE_MAX).
    Returns True when the model becomes ready within `timeout` seconds.
    Returns False immediately if the queue is full (caller should return 503).
    Returns False on timeout (caller falls back to remote).
    """
    global _model_loading_queue_depth
    if _model_load_event.is_set():
        return True                         # fast path — already ready
    if _model_loading_queue_depth >= _MODEL_QUEUE_MAX:
        logger.warning(
            "model_loading_queue_full depth=%d max=%d",
            _model_loading_queue_depth, _MODEL_QUEUE_MAX,
        )
        return False
    _model_loading_queue_depth += 1
    try:
        await asyncio.wait_for(_model_load_event.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        logger.warning("model_loading_wait_timeout timeout=%.1fs", timeout)
        return False
    finally:
        _model_loading_queue_depth -= 1


# ============================================================================
# Qdrant Collection Management
# ============================================================================


COLLECTIONS = {
    "codebase-context": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "file_path": "string",
            "code_snippet": "text",
            "language": "string",
            "framework": "string",
            "purpose": "text",
            "last_accessed": "integer",
            "access_count": "integer",
            "success_rate": "float",
        },
    },
    "skills-patterns": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "skill_name": "string",
            "description": "text",
            "usage_pattern": "text",
            "success_examples": "array",
            "failure_examples": "array",
            "prerequisites": "array",
            "related_skills": "array",
            "value_score": "float",
            "last_updated": "integer",
        },
    },
    "error-solutions": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "error_message": "text",
            "error_type": "string",
            "context": "text",
            "solution": "text",
            "solution_verified": "boolean",
            "success_count": "integer",
            "failure_count": "integer",
            "first_seen": "integer",
            "last_used": "integer",
            "confidence_score": "float",
        },
    },
    "interaction-history": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "query": "text",
            "agent_type": "string",
            "model_used": "string",
            "context_provided": "array",
            "response": "text",
            "outcome": "string",
            "user_feedback": "integer",
            "tokens_used": "integer",
            "latency_ms": "integer",
            "timestamp": "integer",
            "value_score": "float",
        },
    },
    "best-practices": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "category": "string",
            "title": "string",
            "description": "text",
            "examples": "array",
            "anti_patterns": "array",
            "references": "array",
            "endorsement_count": "integer",
            "last_validated": "integer",
        },
    },
    "learning-feedback": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "feedback_id": "string",
            "interaction_id": "string",
            "query": "text",
            "original_response": "text",
            "correction": "text",
            "rating": "integer",
            "tags": "array",
            "timestamp": "integer",
        },
    },
    "agent-memory-episodic": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "memory_type": "string",
            "summary": "text",
            "query": "text",
            "response": "text",
            "outcome": "string",
            "tags": "array",
            "timestamp": "integer",
        },
    },
    "agent-memory-semantic": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "memory_type": "string",
            "summary": "text",
            "content": "text",
            "tags": "array",
            "timestamp": "integer",
        },
    },
    "agent-memory-procedural": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "memory_type": "string",
            "summary": "text",
            "procedure": "text",
            "trigger": "text",
            "tags": "array",
            "timestamp": "integer",
        },
    },
}

MEMORY_COLLECTIONS = {
    "episodic": "agent-memory-episodic",
    "semantic": "agent-memory-semantic",
    "procedural": "agent-memory-procedural",
}

HARNESS_STATS = {
    "total_runs": 0,
    "passed": 0,
    "failed": 0,
    "failure_taxonomy": {},
    "last_run_at": None,
    "scorecards_generated": 0,
}


async def initialize_collections():
    """Initialize Qdrant collections if they don't exist"""
    global qdrant_client

    def _extract_vector_size(info: CollectionInfo) -> Optional[int]:
        try:
            vectors = info.config.params.vectors
            if hasattr(vectors, "size"):
                return int(vectors.size)
            if isinstance(vectors, dict) and vectors:
                first = next(iter(vectors.values()))
                if hasattr(first, "size"):
                    return int(first.size)
                if isinstance(first, dict) and "size" in first:
                    return int(first["size"])
        except Exception:
            return None
        return None

    for collection_name, schema in COLLECTIONS.items():
        try:
            # Check if collection exists
            collections = qdrant_client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)

            if not exists:
                logger.info(f"Creating collection: {collection_name}")
                qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=schema["vector_size"],
                        distance=schema["distance"],
                        hnsw_config=HnswConfigDiff(
                            m=Config.QDRANT_HNSW_M,
                            ef_construct=Config.QDRANT_HNSW_EF_CONSTRUCT,
                            full_scan_threshold=Config.QDRANT_HNSW_FULL_SCAN_THRESHOLD,
                        ),
                    ),
                )
                logger.info(f"✓ Collection created: {collection_name}")
            else:
                info = qdrant_client.get_collection(collection_name)
                current_size = _extract_vector_size(info)
                expected_size = schema["vector_size"]
                points_count = getattr(info, "points_count", 0) or 0
                if current_size is not None and current_size != expected_size:
                    if points_count > 0:
                        logger.error(
                            "Collection dimension mismatch",
                            extra={
                                "collection": collection_name,
                                "current": current_size,
                                "expected": expected_size,
                                "points": points_count,
                            },
                        )
                    else:
                        logger.warning(
                            "Recreating collection due to dimension mismatch",
                            extra={
                                "collection": collection_name,
                                "current": current_size,
                                "expected": expected_size,
                            },
                        )
                        qdrant_client.delete_collection(collection_name=collection_name)
                        qdrant_client.create_collection(
                            collection_name=collection_name,
                            vectors_config=VectorParams(
                                size=expected_size,
                                distance=schema["distance"],
                                hnsw_config=HnswConfigDiff(
                                    m=Config.QDRANT_HNSW_M,
                                    ef_construct=Config.QDRANT_HNSW_EF_CONSTRUCT,
                                    full_scan_threshold=Config.QDRANT_HNSW_FULL_SCAN_THRESHOLD,
                                ),
                            ),
                        )
                        logger.info(f"✓ Collection recreated: {collection_name}")
                else:
                    logger.info(f"✓ Collection exists: {collection_name}")

        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}")


# ============================================================================
# Embedding Functions
# ============================================================================


async def _embed_text_uncached(text: str) -> List[float]:
    """
    Generate embedding via HTTP — no caching. Called only by embed_text().
    Fallback chain: embeddings-service → AIDB → llama.cpp.
    Returns zero vector on all failures.
    """
    global embedding_client

    with TRACER.start_as_current_span(
        "hybrid.embed_text",
        attributes={"text_length": len(text)},
    ) as span:
        try:
            def _extract_embedding(payload: Dict[str, Any]) -> List[float]:
                if "data" in payload:
                    return payload.get("data", [{}])[0].get("embedding", [])
                if "embeddings" in payload:
                    embeddings = payload.get("embeddings") or []
                    return embeddings[0] if embeddings else []
                if isinstance(payload, list):
                    return payload[0] if payload else []
                return []

            async def _request_embedding(
                url: str,
                body: Dict[str, Any],
                headers: Optional[Dict[str, str]] = None,
            ) -> List[float]:
                response = await embedding_client.post(url, json=body, headers=headers or {}, timeout=30.0)
                response.raise_for_status()
                embedding = _extract_embedding(response.json())
                if not embedding:
                    raise ValueError("No embedding returned")
                return embedding

            if Config.EMBEDDING_SERVICE_URL:
                headers: Dict[str, str] = {}
                if Config.EMBEDDING_API_KEY:
                    headers["X-API-Key"] = Config.EMBEDDING_API_KEY
                try:
                    return await _request_embedding(
                        f"{Config.EMBEDDING_SERVICE_URL}/v1/embeddings",
                        {"input": text},
                        headers=headers,
                    )
                except Exception:  # noqa: BLE001
                    logger.warning("Embedding service failed, falling back", exc_info=True)

            if Config.AIDB_URL:
                try:
                    return await _request_embedding(
                        f"{Config.AIDB_URL}/vector/embed",
                        {"texts": [text]},
                    )
                except Exception:  # noqa: BLE001
                    logger.warning("AIDB embedding fallback failed, using llama.cpp", exc_info=True)

            response = await embedding_client.post(
                f"{Config.LLAMA_CPP_URL}/v1/embeddings",
                json={"model": "nomic-embed-text", "input": text},
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("data", [{}])[0].get("embedding", [])

        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error(f"Embedding error: {e}")
            return [0.0] * Config.EMBEDDING_DIM


async def embed_text(text: str) -> List[float]:
    """
    Public embedding entry point with Redis cache.
    Cache hit: returns in < 5 ms. Cache miss: delegates to _embed_text_uncached().
    Zero-vector error fallbacks are not cached.
    """
    global embedding_cache

    # Fast path — Redis cache hit
    if embedding_cache:
        cached = await embedding_cache.get(text)
        if cached is not None:
            logger.info("embed_text cache_hit text_len=%d", len(text))
            return cached

    vector = await _embed_text_uncached(text)

    # Cache only real vectors, never the zero-vector error fallback
    if embedding_cache and vector and any(v != 0.0 for v in vector[:8]):
        await embedding_cache.set(text, vector)

    return vector


# ============================================================================
# Value Scoring Algorithm
# ============================================================================


def compute_value_score(interaction: Dict[str, Any]) -> float:
    """
    Score interaction value (0-1) based on multiple factors
    """
    score = 0.0

    # 1. Outcome quality (40% weight)
    if interaction.get("outcome") == "success":
        score += 0.4
    elif interaction.get("outcome") == "partial":
        score += 0.2

    # 2. User feedback (20% weight)
    user_feedback = interaction.get("user_feedback", 0)
    if user_feedback == 1:
        score += 0.2
    elif user_feedback == 0:
        score += 0.1

    # 3. Reusability potential (20% weight)
    reusability = estimate_reusability(interaction.get("query", ""))
    score += 0.2 * reusability

    # 4. Complexity (10% weight)
    complexity = estimate_complexity(interaction.get("response", ""))
    score += 0.1 * complexity

    # 5. Novelty (10% weight)
    novelty = 0.5  # Simplified for now
    score += 0.1 * novelty

    return min(score, 1.0)


def estimate_reusability(query: str) -> float:
    """Estimate how likely this query pattern will recur"""
    reusable_keywords = ["how to", "best practice", "configure", "setup", "install"]
    keyword_count = sum(1 for kw in reusable_keywords if kw.lower() in query.lower())
    return min(keyword_count * 0.25, 1.0)


def estimate_complexity(response: str) -> float:
    """Estimate response complexity"""
    # Multi-step solutions
    steps = response.count("1.") + response.count("2.") + response.count("3.")

    # Code blocks
    code_blocks = response.count("```")

    # Length-based complexity
    length_score = min(len(response) / 2000, 1.0)

    return min((steps * 0.1 + code_blocks * 0.15 + length_score * 0.5), 1.0)


# ============================================================================
# Context Augmentation
# ============================================================================


async def augment_query_with_context(
    query: str, agent_type: str = "remote"
) -> Dict[str, Any]:
    """
    Enhance query with relevant local context from Qdrant
    """
    global qdrant_client

    with TRACER.start_as_current_span(
        "hybrid.augment_query",
        attributes={"agent_type": agent_type, "query_length": len(query)},
    ) as span:
        # 1. Embed the query
        query_embedding = await embed_text(query)

        context_ids = []
        results_text = []

        # 2. Search codebase context
        try:
            with TRACER.start_as_current_span(
                "hybrid.qdrant.search",
                attributes={"collection": "codebase-context"},
            ):
                codebase_results = qdrant_client.query_points(
                    collection_name="codebase-context",
                    query=query_embedding,
                    limit=5,
                    score_threshold=0.7,
                ).points

            if codebase_results:
                results_text.append("## Relevant Code Context\n")
                for result in codebase_results:
                    context_ids.append(str(result.id))
                    payload = result.payload
                    results_text.append(
                        f"- **{payload.get('file_path', 'Unknown')}** ({payload.get('language', 'unknown')})\n"
                    )
                    results_text.append(f"  {payload.get('purpose', 'No description')}\n")
                    snippet = payload.get("code_snippet", "")
                    if snippet:
                        results_text.append(f"  ```{payload.get('language', '')}\n  {snippet[:200]}...\n  ```\n")
        except Exception as e:
            logger.warning("Error searching codebase-context: %s", e)

        # 3. Search skills/patterns
        try:
            with TRACER.start_as_current_span(
                "hybrid.qdrant.search",
                attributes={"collection": "skills-patterns"},
            ):
                skills_results = qdrant_client.query_points(
                    collection_name="skills-patterns",
                    query=query_embedding,
                    limit=3,
                    score_threshold=0.75,
                ).points

            if skills_results:
                results_text.append("\n## Related Skills & Patterns\n")
                for result in skills_results:
                    context_ids.append(str(result.id))
                    payload = result.payload
                    results_text.append(f"- **{payload.get('skill_name', 'Unknown Skill')}**\n")
                    results_text.append(f"  {payload.get('description', 'No description')}\n")
        except Exception as e:
            logger.warning("Error searching skills-patterns: %s", e)

        # 4. Search error solutions
        try:
            with TRACER.start_as_current_span(
                "hybrid.qdrant.search",
                attributes={"collection": "error-solutions"},
            ):
                error_results = qdrant_client.query_points(
                    collection_name="error-solutions",
                    query=query_embedding,
                    limit=2,
                    score_threshold=0.8,
                ).points

            if error_results:
                results_text.append("\n## Similar Error Solutions\n")
                for result in error_results:
                    context_ids.append(str(result.id))
                    payload = result.payload
                    results_text.append(f"- **Error**: {payload.get('error_type', 'Unknown')}\n")
                    results_text.append(f"  **Solution**: {payload.get('solution', 'No solution')[:200]}...\n")
                    confidence = payload.get('confidence_score', 0)
                    results_text.append(f"  **Confidence**: {confidence:.2f}\n")
        except Exception as e:
            logger.warning("Error searching error-solutions: %s", e)

        # 5. Search best practices
        try:
            with TRACER.start_as_current_span(
                "hybrid.qdrant.search",
                attributes={"collection": "best-practices"},
            ):
                bp_results = qdrant_client.query_points(
                    collection_name="best-practices",
                    query=query_embedding,
                    limit=2,
                    score_threshold=0.75,
                ).points

            if bp_results:
                results_text.append("\n## Best Practices\n")
                for result in bp_results:
                    context_ids.append(str(result.id))
                    payload = result.payload
                    results_text.append(f"- **{payload.get('title', 'Unknown')}** ({payload.get('category', 'general')})\n")
                    results_text.append(f"  {payload.get('description', 'No description')}\n")
        except Exception as e:
            logger.warning("Error searching best-practices: %s", e)

        discovery = await _discover_applicable_resources(query)
        discovery_context = _format_discovery_context(discovery)
        if discovery_context:
            results_text.append(discovery_context)

        if not results_text:
            span.set_attribute("context_found", False)
        else:
            span.set_attribute("context_found", True)
        span.set_attribute("capability_discovery.decision", discovery.get("decision", "unknown"))
        span.set_attribute("capability_discovery.reason", discovery.get("reason", "unknown"))
        span.set_attribute("capability_discovery.cache_hit", bool(discovery.get("cache_hit", False)))

    # 6. Construct augmented prompt
    context_text = "".join(results_text) if results_text else "No relevant context found in local knowledge base."

    augmented_prompt = f"""Query: {query}

Relevant Context from Local Knowledge Base:
{context_text}

Please use this context to provide a more accurate and efficient response.
"""

    record_telemetry_event(
        "context_augmented",
        {
            "agent_type": agent_type,
            "context_count": len(context_ids),
            "collections": list(COLLECTIONS.keys()),
            "capability_discovery": {
                "decision": discovery.get("decision", "unknown"),
                "reason": discovery.get("reason", "unknown"),
                "cache_hit": bool(discovery.get("cache_hit", False)),
                "intent_tags": discovery.get("intent_tags", []),
                "tool_count": len(discovery.get("tools", [])),
                "skill_count": len(discovery.get("skills", [])),
                "server_count": len(discovery.get("servers", [])),
                "dataset_count": len(discovery.get("datasets", [])),
            },
        },
    )
    record_query_stats(agent_type, len(context_ids) > 0)

    return {
        "augmented_prompt": augmented_prompt,
        "context_ids": context_ids,
        "original_query": query,
        "context_count": len(context_ids),
        "capability_discovery": {
            "decision": discovery.get("decision", "unknown"),
            "reason": discovery.get("reason", "unknown"),
            "cache_hit": bool(discovery.get("cache_hit", False)),
            "intent_tags": discovery.get("intent_tags", []),
            "tools": [
                {"name": item.get("name"), "description": item.get("description")}
                for item in discovery.get("tools", [])
            ],
            "skills": [
                {
                    "name": item.get("name", item.get("slug")),
                    "description": item.get("description"),
                }
                for item in discovery.get("skills", [])
            ],
            "servers": [
                {"name": item.get("name"), "description": item.get("description")}
                for item in discovery.get("servers", [])
            ],
            "datasets": [
                {
                    "title": item.get("title", item.get("relative_path")),
                    "project": item.get("project"),
                }
                for item in discovery.get("datasets", [])
            ],
        },
    }


async def hybrid_search(
    query: str,
    collections: Optional[List[str]] = None,
    limit: int = 5,
    keyword_limit: int = 5,
    score_threshold: float = 0.7,
    keyword_pool: int = 60,
) -> Dict[str, Any]:
    """Hybrid search combining vector similarity + keyword matches."""
    global qdrant_client

    collections = collections or list(COLLECTIONS.keys())
    query_embedding = await embed_text(query)
    tokens = _normalize_tokens(query)

    semantic_results: List[Dict[str, Any]] = []
    keyword_results: List[Dict[str, Any]] = []

    for collection in collections:
        try:
            points = _call_with_breaker(
                "qdrant",
                lambda: qdrant_client.query_points(
                    collection_name=collection,
                    query=query_embedding,
                    limit=limit,
                    score_threshold=score_threshold,
                ).points,
            )
            for point in points:
                semantic_results.append(
                    {
                        "collection": collection,
                        "id": str(point.id),
                        "score": point.score,
                        "payload": point.payload,
                        "source": "semantic",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("semantic_search_failed collection=%s error=%s", collection, exc)

        if tokens:
            try:
                points, _ = _call_with_breaker(
                    "qdrant",
                    lambda: qdrant_client.scroll(
                        collection_name=collection,
                        limit=keyword_pool,
                        with_payload=True,
                        with_vectors=False,
                    ),
                )
                for point in points:
                    matched, score = _payload_matches_tokens(point.payload or {}, tokens)
                    if not matched:
                        continue
                    keyword_results.append(
                        {
                            "collection": collection,
                            "id": str(point.id),
                            "score": float(score),
                            "payload": point.payload,
                            "source": "keyword",
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("keyword_search_failed collection=%s error=%s", collection, exc)

    keyword_results.sort(key=lambda item: item["score"], reverse=True)
    keyword_results = keyword_results[:keyword_limit]

    combined: Dict[str, Dict[str, Any]] = {}
    for item in semantic_results + keyword_results:
        key = f"{item['collection']}:{item['id']}"
        if key not in combined:
            combined[key] = {**item, "sources": {item["source"]}}
        else:
            combined[key]["sources"].add(item["source"])
            combined[key]["score"] = max(combined[key]["score"], item["score"])
    combined_results = []
    for item in combined.values():
        item["sources"] = sorted(item["sources"])
        combined_results.append(item)
    combined_results = _rerank_combined_results(query, combined_results)
    max_results = max(1, Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS)
    if len(combined_results) > max_results:
        AUTONOMY_BUDGET_EXCEEDED.labels(budget="retrieval_results").inc()
        combined_results = combined_results[:max_results]

    record_telemetry_event(
        "hybrid_search",
        {
            "query": query[:200],
            "collections": collections,
            "semantic_results": len(semantic_results),
            "keyword_results": len(keyword_results),
        },
    )

    return {
        "query": query,
        "collections": collections,
        "semantic_results": semantic_results,
        "keyword_results": keyword_results,
        "combined_results": combined_results,
        "tokens": tokens,
    }


async def tree_search(
    query: str,
    collections: Optional[List[str]] = None,
    limit: int = 5,
    keyword_limit: int = 5,
    score_threshold: float = 0.7,
) -> Dict[str, Any]:
    """Branch-and-aggregate retrieval over query expansions."""
    collections = collections or list(COLLECTIONS.keys())
    max_depth = max(1, Config.AI_TREE_SEARCH_MAX_DEPTH)
    branch_factor = max(1, Config.AI_TREE_SEARCH_BRANCH_FACTOR)

    branches = [query]
    all_results: Dict[str, Dict[str, Any]] = {}
    branch_runs: List[Dict[str, Any]] = []

    for depth in range(max_depth):
        next_branches: List[str] = []
        for branch_query in branches[:branch_factor]:
            result = await hybrid_search(
                query=branch_query,
                collections=collections,
                limit=limit,
                keyword_limit=keyword_limit,
                score_threshold=score_threshold,
            )
            branch_runs.append(
                {
                    "depth": depth,
                    "query": branch_query,
                    "semantic_results": len(result.get("semantic_results", [])),
                    "keyword_results": len(result.get("keyword_results", [])),
                }
            )
            for item in result.get("combined_results", []):
                key = f"{item.get('collection')}:{item.get('id')}"
                current = all_results.get(key)
                if current is None or float(item.get("score", 0.0)) > float(current.get("score", 0.0)):
                    all_results[key] = item
            next_branches.extend(_tree_expand_queries(branch_query, branch_factor))
        branches = next_branches

    ranked = sorted(all_results.values(), key=lambda item: float(item.get("score", 0.0)), reverse=True)
    ranked = ranked[: max(limit, keyword_limit, Config.AI_MEMORY_MAX_RECALL_ITEMS)]
    return {
        "query": query,
        "search_mode": "tree",
        "depth": max_depth,
        "branch_factor": branch_factor,
        "combined_results": ranked,
        "branches": branch_runs,
    }


async def store_agent_memory(
    memory_type: str,
    summary: str,
    *,
    content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Store agent memory in typed collections."""
    if not Config.AI_MEMORY_ENABLED:
        return {"status": "disabled"}
    collection = MEMORY_COLLECTIONS.get(memory_type)
    if not collection:
        raise ValueError("memory_type must be episodic|semantic|procedural")
    memory_id = str(uuid4())
    payload = {
        "memory_id": memory_id,
        "memory_type": memory_type,
        "summary": summary,
        "content": content or summary,
        "timestamp": int(datetime.now().timestamp()),
    }
    if metadata:
        payload.update(metadata)
    embedding = await embed_text(f"{memory_type}\n{summary}\n{content or ''}")
    qdrant_client.upsert(
        collection_name=collection,
        points=[PointStruct(id=memory_id, vector=embedding, payload=payload)],
    )
    record_telemetry_event(
        "agent_memory_store",
        {"memory_id": memory_id, "memory_type": memory_type, "collection": collection},
    )
    return {"status": "stored", "memory_id": memory_id, "memory_type": memory_type}


async def recall_agent_memory(
    query: str,
    memory_types: Optional[List[str]] = None,
    limit: Optional[int] = None,
    retrieval_mode: str = "hybrid",
) -> Dict[str, Any]:
    """Recall memories using hybrid/tree retrieval."""
    if not Config.AI_MEMORY_ENABLED:
        return {"status": "disabled", "results": []}

    requested_types = memory_types or list(MEMORY_COLLECTIONS.keys())
    collections = [MEMORY_COLLECTIONS[m] for m in requested_types if m in MEMORY_COLLECTIONS]
    if not collections:
        return {"status": "ok", "results": []}

    limit_value = max(1, int(limit or Config.AI_MEMORY_MAX_RECALL_ITEMS))
    use_tree = retrieval_mode == "tree" and Config.AI_TREE_SEARCH_ENABLED

    if use_tree:
        search_result = await tree_search(
            query=query,
            collections=collections,
            limit=limit_value,
            keyword_limit=limit_value,
            score_threshold=0.6,
        )
        raw_results = search_result.get("combined_results", [])
    else:
        search_result = await hybrid_search(
            query=query,
            collections=collections,
            limit=limit_value,
            keyword_limit=limit_value,
            score_threshold=0.6,
        )
        raw_results = search_result.get("combined_results", [])

    memory_rows = []
    for item in raw_results[:limit_value]:
        payload = item.get("payload") or {}
        memory_rows.append(
            {
                "memory_id": payload.get("memory_id") or item.get("id"),
                "memory_type": payload.get("memory_type"),
                "summary": payload.get("summary"),
                "content": payload.get("content"),
                "score": item.get("score"),
                "sources": item.get("sources"),
            }
        )

    record_telemetry_event(
        "agent_memory_recall",
        {
            "query": query[:200],
            "results": len(memory_rows),
            "mode": "tree" if use_tree else "hybrid",
            "memory_types": requested_types,
        },
    )
    return {
        "status": "ok",
        "query": query,
        "mode": "tree" if use_tree else "hybrid",
        "results": memory_rows,
    }


async def run_harness_evaluation(
    query: str,
    *,
    expected_keywords: Optional[List[str]] = None,
    mode: str = "auto",
    max_latency_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Deterministic harness eval scorecard for prompt+retrieval behavior."""
    if not Config.AI_HARNESS_EVAL_ENABLED:
        return {"status": "disabled"}

    start = time.time()
    result = await route_search(
        query=query,
        mode=mode,
        prefer_local=True,
        limit=5,
        keyword_limit=5,
        score_threshold=0.7,
        generate_response=True,
    )
    latency_ms = int((time.time() - start) * 1000)
    response_text = (result.get("response") or "").strip()
    keywords = [kw for kw in (expected_keywords or []) if isinstance(kw, str)]
    relevance_score = _keyword_relevance(response_text, keywords)

    latency_target = int(max_latency_ms or Config.AI_HARNESS_MAX_LATENCY_MS)
    latency_ok = latency_ms <= latency_target
    response_non_empty = bool(response_text)

    # Weighted score keeps failure taxonomy deterministic.
    score = (
        (0.5 * relevance_score)
        + (0.3 * (1.0 if latency_ok else 0.0))
        + (0.2 * (1.0 if response_non_empty else 0.0))
    )
    passed = score >= Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE
    metrics = {
        "relevance_score": round(relevance_score, 4),
        "latency_ms": latency_ms,
        "latency_target_ms": latency_target,
        "latency_ok": latency_ok,
        "response_non_empty": response_non_empty,
        "overall_score": round(score, 4),
    }
    failure_category = None
    if not passed:
        failure_category = _classify_eval_failure(metrics)
        HARNESS_STATS["failure_taxonomy"][failure_category] = (
            HARNESS_STATS["failure_taxonomy"].get(failure_category, 0) + 1
        )

    HARNESS_STATS["total_runs"] += 1
    HARNESS_STATS["passed"] += 1 if passed else 0
    HARNESS_STATS["failed"] += 0 if passed else 1
    HARNESS_STATS["last_run_at"] = datetime.now(timezone.utc).isoformat()

    record_telemetry_event(
        "harness_eval",
        {
            "query": query[:200],
            "mode": mode,
            "score": metrics["overall_score"],
            "passed": passed,
            "failure_category": failure_category,
            "latency_ms": latency_ms,
        },
    )
    return {
        "status": "ok",
        "query": query,
        "mode": mode,
        "passed": passed,
        "min_acceptance_score": Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE,
        "metrics": metrics,
        "failure_category": failure_category,
        "route_result": result,
    }


def build_harness_scorecard() -> Dict[str, Any]:
    total = int(HARNESS_STATS.get("total_runs", 0) or 0)
    passed = int(HARNESS_STATS.get("passed", 0) or 0)
    failed = int(HARNESS_STATS.get("failed", 0) or 0)
    pass_rate = (passed / total) if total else 0.0
    discovery = HYBRID_STATS.get("capability_discovery", {})
    discovery_invoked = int(discovery.get("invoked", 0) or 0)
    discovery_skipped = int(discovery.get("skipped", 0) or 0)
    discovery_hits = int(discovery.get("cache_hits", 0) or 0)
    discovery_errors = int(discovery.get("errors", 0) or 0)
    discovery_total = discovery_invoked + discovery_skipped + discovery_hits + discovery_errors
    discovery_cache_rate = (discovery_hits / discovery_total) if discovery_total else 0.0
    reliability_ok = pass_rate >= Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE
    discovery_error_rate = (discovery_errors / discovery_total) if discovery_total else 0.0
    safety_ok = discovery_error_rate <= 0.05
    HARNESS_STATS["scorecards_generated"] = int(HARNESS_STATS.get("scorecards_generated", 0) or 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acceptance": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(pass_rate, 4),
            "target": Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE,
            "ok": reliability_ok,
        },
        "discovery": {
            "invoked": discovery_invoked,
            "skipped": discovery_skipped,
            "cache_hits": discovery_hits,
            "errors": discovery_errors,
            "cache_hit_rate": round(discovery_cache_rate, 4),
            "error_rate": round(discovery_error_rate, 4),
            "ok": safety_ok,
        },
        "inference_optimizations": {
            "prompt_cache_policy_enabled": Config.AI_PROMPT_CACHE_POLICY_ENABLED,
            "speculative_decoding_enabled": Config.AI_SPECULATIVE_DECODING_ENABLED,
            "speculative_decoding_mode": Config.AI_SPECULATIVE_DECODING_MODE,
            "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
        },
    }


def _summarize_results(items: List[Dict[str, Any]], max_items: int = 3) -> str:
    lines: List[str] = []
    for item in items[:max_items]:
        payload = item.get("payload") or {}
        title = (
            payload.get("title")
            or payload.get("file_path")
            or payload.get("skill_name")
            or payload.get("error_type")
            or payload.get("category")
            or "result"
        )
        sources = item.get("sources") or [item.get("source")] if item.get("source") else []
        source_text = ",".join(sources) if isinstance(sources, list) else str(sources)
        lines.append(f"- {title} (score={item.get('score', 0):.2f}, source={source_text})")
    return "\n".join(lines) if lines else "No results."


def _rerank_combined_results(query: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply a lightweight lexical+source-aware rerank pass over merged retrieval results."""
    tokens = _normalize_tokens(query)
    reranked: List[Dict[str, Any]] = []
    for item in items:
        payload = item.get("payload") or {}
        text = " ".join(
            str(payload.get(key, ""))
            for key in ("title", "description", "content", "solution", "usage_pattern", "summary")
        ).lower()
        lexical_hits = sum(1 for token in tokens if token in text)
        source_bonus = len(item.get("sources", [])) * 0.1
        base_score = float(item.get("score", 0.0))
        rerank_score = base_score + (0.05 * lexical_hits) + source_bonus
        reranked.append({**item, "rerank_score": round(rerank_score, 4)})
    reranked.sort(key=lambda row: float(row.get("rerank_score", 0.0)), reverse=True)
    return reranked


async def select_llm_backend(
    prompt: str,
    context_quality: float,
    force_local: bool = False,
    force_remote: bool = False,
    requires_structured_output: bool = False,
) -> str:
    """Select 'local' or 'remote' LLM backend based on confidence and overrides.

    Phase 2.1.2 / 2.2.1 / 2.3.1 / 2.3.2:
    - Reads threshold from RoutingConfig (hot-reloadable JSON, 60 s TTL).
    - Checks llama.cpp liveness before routing local (cached 10 s).
    - Routes remote if prompt requires structured JSON output and local model
      does not advertise function-calling support via LOCAL_MODEL_SUPPORTS_JSON env.

    Args:
        prompt: The prompt text.
        context_quality: Retrieval confidence score in [0, 1].
        force_local: Always return 'local'.
        force_remote: Always return 'remote'.
        requires_structured_output: Caller signals JSON schema / function-call needed.

    Returns:
        'local' or 'remote'.
    """
    # Phase 2.3.2 — structured output / function-calling check.
    # Local GGUF models rarely support reliable JSON schema enforcement.
    # If the caller needs structured output and the local model hasn't been
    # explicitly marked as supporting it, route to remote.
    _local_supports_json = os.getenv("LOCAL_MODEL_SUPPORTS_JSON", "false").lower() == "true"

    if force_local:
        backend = "local"
        reason = "force_local_override"
        reason_class = "override"
    elif force_remote:
        backend = "remote"
        reason = "force_remote_override"
        reason_class = "override"
    elif requires_structured_output and not _local_supports_json:
        backend = "remote"
        reason = "structured_output_required"
        reason_class = "capability"
        logger.info("routing_override reason=structured_output_required local_supports_json=false")
    elif not await _check_local_llm_health():
        # Unreachable (not just loading) — fall back to remote immediately.
        backend = "remote"
        reason = "local_unhealthy"
        reason_class = "health"
    elif _local_llm_loading:
        # Phase 2.4.1 — model is loading. Queue the request; wait up to 30 s.
        # _wait_for_local_model returns False if queue full → caller returns 503.
        ready = await _wait_for_local_model(timeout=30.0)
        if ready:
            backend = "local"
            reason = "waited_for_model_load"
            reason_class = "loading_queue"
        else:
            backend = "remote"
            reason = "model_loading_queue_full_or_timeout"
            reason_class = "loading_queue"
    else:
        threshold = await routing_config.get_threshold()
        if context_quality >= threshold:
            backend = "local"
            reason = f"context_quality_above_threshold_{threshold:.3f}"
            reason_class = "confidence"
        else:
            backend = "remote"
            reason = f"context_quality_below_threshold_{threshold:.3f}"
            reason_class = "confidence"

    logger.info(
        "llm_backend_selected backend=%s reason=%s local_confidence_score=%.3f",
        backend, reason, context_quality,
    )
    LLM_BACKEND_SELECTIONS.labels(backend=backend, reason_class=reason_class).inc()
    return backend


async def route_search(
    query: str,
    mode: str = "auto",
    prefer_local: bool = True,
    context: Optional[Dict[str, Any]] = None,
    limit: int = 5,
    keyword_limit: int = 5,
    score_threshold: float = 0.7,
    generate_response: bool = False,
) -> Dict[str, Any]:
    """Route query to SQL, semantic, keyword, tree, or hybrid search."""
    start = time.time()
    # Phase 3.1.1 — every query gets a stable interaction_id the user can reference for feedback.
    interaction_id = str(uuid4())
    limit = max(1, min(int(limit), Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS))
    keyword_limit = max(0, min(int(keyword_limit), Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS))
    normalized_mode = (mode or "auto").lower()
    route = normalized_mode

    if normalized_mode == "auto":
        if _looks_like_sql(query):
            route = "sql"
        else:
            token_count = len(_normalize_tokens(query))
            if token_count <= 3:
                route = "keyword"
            elif Config.AI_TREE_SEARCH_ENABLED and token_count >= 8:
                route = "tree"
            else:
                route = "hybrid"

    results: Dict[str, Any] = {}
    response_text = ""
    capability_discovery: Dict[str, Any] = {
        "decision": "skipped",
        "reason": "not-evaluated",
        "cache_hit": False,
        "intent_tags": [],
        "tools": [],
        "skills": [],
        "servers": [],
        "datasets": [],
    }

    try:
        if Config.AI_CAPABILITY_DISCOVERY_ON_QUERY:
            capability_discovery = await _discover_applicable_resources(query)

        if route == "sql":
            response_text = (
                "SQL routing detected. Execution is disabled by default for safety. "
                "Set HYBRID_ALLOW_SQL_EXECUTION=true to enable read-only queries."
            )
        elif route == "keyword":
            hybrid_results = await hybrid_search(
                query=query,
                collections=list(COLLECTIONS.keys()),
                limit=limit,
                keyword_limit=keyword_limit,
                score_threshold=score_threshold,
            )
            results = {"keyword_results": hybrid_results["keyword_results"]}
            response_text = _summarize_results(hybrid_results["keyword_results"])
        elif route == "semantic":
            hybrid_results = await hybrid_search(
                query=query,
                collections=list(COLLECTIONS.keys()),
                limit=limit,
                keyword_limit=0,
                score_threshold=score_threshold,
            )
            results = {"semantic_results": hybrid_results["semantic_results"]}
            response_text = _summarize_results(hybrid_results["semantic_results"])
        elif route == "tree":
            tree_results = await tree_search(
                query=query,
                collections=list(COLLECTIONS.keys()),
                limit=limit,
                keyword_limit=keyword_limit,
                score_threshold=score_threshold,
            )
            results = tree_results
            response_text = _summarize_results(tree_results["combined_results"])
        else:
            hybrid_results = await hybrid_search(
                query=query,
                collections=list(COLLECTIONS.keys()),
                limit=limit,
                keyword_limit=keyword_limit,
                score_threshold=score_threshold,
            )
            results = hybrid_results
            response_text = _summarize_results(hybrid_results["combined_results"])

        # Phase 3.2.1 — Gap tracking: record low-confidence queries to query_gaps table.
        _GAP_THRESHOLD = float(os.getenv("AI_GAP_SCORE_THRESHOLD", "0.4"))
        _all_combined = (
            results.get("combined_results") or
            results.get("semantic_results") or
            results.get("keyword_results") or []
        )
        _best_score = max(
            (r.get("score", 0.0) for r in _all_combined if isinstance(r, dict)),
            default=0.0,
        )
        if _best_score < _GAP_THRESHOLD and postgres_client is not None:
            _query_hash = hashlib.sha256(query.encode()).hexdigest()[:64]
            _collections_hit = ",".join(sorted(set(
                r.get("collection", "") for r in _all_combined if isinstance(r, dict)
            ))) or "unknown"
            asyncio.create_task(_record_query_gap(
                query_hash=_query_hash,
                query_text=query[:500],
                score=_best_score,
                collection=_collections_hit,
            ))

        prompt_prefix = Config.AI_PROMPT_CACHE_STATIC_PREFIX if Config.AI_PROMPT_CACHE_POLICY_ENABLED else ""
        prompt_prefix_hash = hashlib.sha256(prompt_prefix.encode("utf-8")).hexdigest()[:16] if prompt_prefix else ""
        if generate_response and llama_cpp_client:
            discovery_context = _format_discovery_context(capability_discovery)
            combined_context = f"{response_text}\n\n{discovery_context}".strip()
            compressed_context = combined_context
            compressed_tokens = 0
            if Config.AI_CONTEXT_COMPRESSION_ENABLED and context_compressor and combined_context:
                tokens_before = len(combined_context) // 4
                compressed_context, _, compressed_tokens = context_compressor.compress_to_budget(
                    contexts=[{"id": "route-results", "text": combined_context, "score": 1.0}],
                    max_tokens=Config.AI_CONTEXT_MAX_TOKENS,
                    strategy="hybrid",
                )
                logger.info(
                    "context_compression tokens_before=%d tokens_after=%d budget=%d",
                    tokens_before, compressed_tokens, Config.AI_CONTEXT_MAX_TOKENS,
                )
            prompt = (
                f"{prompt_prefix}\n\n"
                f"User query: {query}\n\nContext:\n{compressed_context}\n\n"
                "Provide a concise response using the context."
            )
            # Phase 2: use routing intelligence rather than hardcoding local.
            # Derive context quality from best search result score.
            _all_results = (
                results.get("combined_results") or
                results.get("semantic_results") or
                results.get("keyword_results") or []
            )
            context_quality = max(
                (r.get("score", 0.0) for r in _all_results if isinstance(r, dict)),
                default=0.5,
            )
            backend = await select_llm_backend(
                query, context_quality,
                force_local=prefer_local,
            )
            # Remote generation not yet wired in route_search; fall back to local.
            if backend == "remote" and llama_cpp_client:
                logger.info(
                    "llm_backend_fallback_to_local reason=remote_not_available_in_route_search"
                )
                backend = "local"
            try:
                llm_resp = await llama_cpp_client.post(
                    "/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "max_tokens": 400,
                    },
                    timeout=60.0,
                )
                llm_resp.raise_for_status()
                llm_json = llm_resp.json()
                response_text = llm_json["choices"][0]["message"]["content"]
                usage = llm_json.get("usage", {}) if isinstance(llm_json, dict) else {}
                cached_tokens = int(
                    usage.get("cached_tokens")
                    or (usage.get("prompt_tokens_details", {}) or {}).get("cached_tokens", 0)
                    or 0
                )
                results["prompt_cache"] = {
                    "policy_enabled": Config.AI_PROMPT_CACHE_POLICY_ENABLED,
                    "prefix_hash": prompt_prefix_hash,
                    "cached_tokens": cached_tokens,
                }
                if compressed_tokens:
                    results["context_compression"] = {
                        "enabled": True,
                        "token_budget": Config.AI_CONTEXT_MAX_TOKENS,
                        "compressed_tokens": compressed_tokens,
                    }
            except Exception as exc:  # noqa: BLE001
                logger.warning("route_search_llm_failed error=%s", exc)

        ROUTE_DECISIONS.labels(route=route).inc()
        record_telemetry_event(
            "route_search",
            {
                "query": query[:200],
                "route": route,
                "prefer_local": prefer_local,
                "context_keys": list((context or {}).keys()),
                "prompt_cache_policy": {
                    "enabled": Config.AI_PROMPT_CACHE_POLICY_ENABLED,
                    "prefix_hash": prompt_prefix_hash,
                },
                "inference_optimizations": {
                    "speculative_decoding_enabled": Config.AI_SPECULATIVE_DECODING_ENABLED,
                    "speculative_decoding_mode": Config.AI_SPECULATIVE_DECODING_MODE,
                    "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
                },
                "capability_discovery": {
                    "decision": capability_discovery.get("decision", "unknown"),
                    "reason": capability_discovery.get("reason", "unknown"),
                    "cache_hit": bool(capability_discovery.get("cache_hit", False)),
                    "intent_tags": capability_discovery.get("intent_tags", []),
                    "tool_count": len(capability_discovery.get("tools", [])),
                    "skill_count": len(capability_discovery.get("skills", [])),
                    "server_count": len(capability_discovery.get("servers", [])),
                    "dataset_count": len(capability_discovery.get("datasets", [])),
                },
            },
        )
    except Exception as exc:  # noqa: BLE001
        ROUTE_ERRORS.labels(route=route).inc()
        logger.error("route_search_failed route=%s error=%s", route, exc)
        raise

    latency_ms = int((time.time() - start) * 1000)
    return {
        "route": route,
        "backend": route,
        "response": response_text,
        "results": results,
        "latency_ms": latency_ms,
        "interaction_id": interaction_id,  # Phase 3.1.1: used by POST /feedback/{id}
        "capability_discovery": {
            "decision": capability_discovery.get("decision", "unknown"),
            "reason": capability_discovery.get("reason", "unknown"),
            "cache_hit": bool(capability_discovery.get("cache_hit", False)),
            "intent_tags": capability_discovery.get("intent_tags", []),
            "tools": [
                {"name": item.get("name"), "description": item.get("description")}
                for item in capability_discovery.get("tools", [])
            ],
            "skills": [
                {
                    "name": item.get("name", item.get("slug")),
                    "description": item.get("description"),
                }
                for item in capability_discovery.get("skills", [])
            ],
            "servers": [
                {"name": item.get("name"), "description": item.get("description")}
                for item in capability_discovery.get("servers", [])
            ],
            "datasets": [
                {
                    "title": item.get("title", item.get("relative_path")),
                    "project": item.get("project"),
                }
                for item in capability_discovery.get("datasets", [])
            ],
        },
    }


async def record_learning_feedback(
    query: str,
    correction: str,
    original_response: Optional[str] = None,
    interaction_id: Optional[str] = None,
    rating: Optional[int] = None,
    tags: Optional[List[str]] = None,
    model: Optional[str] = None,
    variant: Optional[str] = None,
) -> str:
    """Store user corrections for learning."""
    global qdrant_client, postgres_client

    feedback_id = str(uuid4())
    resolved_tags = list(tags or [])
    if model:
        resolved_tags.append(f"model:{model}")
    if variant:
        resolved_tags.append(f"variant:{variant}")
    payload = {
        "feedback_id": feedback_id,
        "interaction_id": interaction_id,
        "query": query,
        "original_response": original_response,
        "correction": correction,
        "rating": rating,
        "tags": resolved_tags,
        "model": model,
        "variant": variant,
        "timestamp": int(datetime.now().timestamp()),
    }

    embedding = await embed_text(f"{query}\n{correction}")
    try:
        qdrant_client.upsert(
            collection_name="learning-feedback",
            points=[PointStruct(id=feedback_id, vector=embedding, payload=payload)],
        )
        if Config.AI_MEMORY_ENABLED:
            await store_agent_memory(
                "semantic",
                summary=f"User correction for query: {query[:120]}",
                content=correction,
                metadata={
                    "query": query,
                    "interaction_id": interaction_id,
                    "tags": resolved_tags,
                },
            )
        if postgres_client is not None:
            try:
                await postgres_client.execute(
                    """
                    INSERT INTO learning_feedback (
                        feedback_id,
                        interaction_id,
                        query,
                        original_response,
                        correction,
                        rating,
                        tags,
                        source
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    feedback_id,
                    interaction_id,
                    query,
                    original_response,
                    correction,
                    rating,
                    json.dumps(resolved_tags),
                    "hybrid-coordinator",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("learning_feedback_postgres_failed error=%s", exc)
        record_telemetry_event("learning_feedback", {"feedback_id": feedback_id})
    except Exception as exc:  # noqa: BLE001
        logger.error("learning_feedback_store_failed error=%s", exc)
        return ""

    return feedback_id


# ============================================================================
# Phase 3.1.1 — Simple thumbs-up/thumbs-down feedback
# Phase 3.2.1 — Gap query recording
# ============================================================================

async def record_simple_feedback(
    interaction_id: str,
    rating: int,
    note: str = "",
    query: str = "",
) -> str:
    """Record a simple +1/-1 rating for an interaction to learning_feedback + PerformanceWindow."""
    global postgres_client
    feedback_id = str(uuid4())
    if postgres_client is not None:
        try:
            await postgres_client.execute(
                """
                INSERT INTO learning_feedback (
                    feedback_id, interaction_id, query,
                    correction, rating, source
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                feedback_id,
                interaction_id,
                query[:500] if query else "",
                note[:1000] if note else "",
                rating,
                "user-rating",
            )
        except Exception as exc:
            logger.warning("feedback_postgres_failed error=%s", exc)
    # Wire into 7-day performance window (Phase 2.2.3)
    await performance_window.record("general", success=(rating > 0))
    logger.info(
        "simple_feedback_recorded interaction_id=%s rating=%d",
        interaction_id, rating,
    )
    return feedback_id


async def _record_query_gap(
    query_hash: str,
    query_text: str,
    score: float,
    collection: str = "unknown",
) -> None:
    """Phase 3.2.1 — Insert a low-confidence query into the query_gaps table."""
    global postgres_client
    if postgres_client is None:
        return
    try:
        await postgres_client.execute(
            """
            INSERT INTO query_gaps (query_hash, query_text, score, collection)
            VALUES (%s, %s, %s, %s)
            """,
            query_hash, query_text, score, collection,
        )
        logger.info(
            "query_gap_recorded score=%.3f collection=%s",
            score, collection,
        )
    except Exception as exc:
        logger.debug("query_gap_insert_failed error=%s", exc)


async def get_feedback_variant_stats(tag: str, days: Optional[int] = None) -> Dict[str, Any]:
    """Summarize feedback ratings for a tag (e.g., variant:model-a)."""
    global postgres_client
    if postgres_client is None:
        raise RuntimeError("Postgres client not configured")

    query = """
        SELECT
            COUNT(*) AS total,
            COUNT(rating) AS rated,
            AVG(rating)::float AS avg_rating
        FROM learning_feedback
        WHERE tags ? %s
    """
    params: List[Any] = [tag]
    if days and days > 0:
        query += " AND created_at >= NOW() - (%s || ' days')::interval"
        params.append(str(days))

    rows = await postgres_client.fetch_all(query, *params)
    if not rows:
        return {"tag": tag, "total": 0, "rated": 0, "avg_rating": None}
    row = rows[0]
    return {
        "tag": tag,
        "total": int(row.get("total", 0) or 0),
        "rated": int(row.get("rated", 0) or 0),
        "avg_rating": row.get("avg_rating"),
    }


# ============================================================================
# Interaction Tracking
# ============================================================================


async def track_interaction(
    query: str,
    response: str,
    agent_type: str,
    model_used: str,
    context_ids: List[str],
    outcome: str = "unknown",
    user_feedback: int = 0,
    tokens_used: int = 0,
    latency_ms: int = 0,
) -> str:
    """
    Store interaction in Qdrant for learning
    """
    global qdrant_client

    interaction_id = str(uuid4())
    timestamp = int(datetime.now().timestamp())

    interaction = {
        "query": query,
        "response": response,
        "agent_type": agent_type,
        "model_used": model_used,
        "context_provided": context_ids,
        "outcome": outcome,
        "user_feedback": user_feedback,
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
        "timestamp": timestamp,
        "value_score": 0.0,  # Computed later after outcome
    }

    # Embed the query for future similarity search
    query_embedding = await embed_text(query)

    # Store in Qdrant
    try:
        qdrant_client.upsert(
            collection_name="interaction-history",
            points=[
                PointStruct(
                    id=interaction_id, vector=query_embedding, payload=interaction
                )
            ],
        )
        if Config.AI_MEMORY_ENABLED:
            await store_agent_memory(
                "episodic",
                summary=f"{agent_type} interaction: {query[:120]}",
                content=response[:600],
                metadata={
                    "query": query,
                    "response": response[:2000],
                    "outcome": outcome,
                    "tags": [f"model:{model_used}", f"agent:{agent_type}"],
                },
            )
        logger.info(f"Tracked interaction: {interaction_id}")
        record_telemetry_event(
            "interaction_tracked",
            {
                "interaction_id": interaction_id,
                "agent_type": agent_type,
                "model_used": model_used,
                "tokens_used": tokens_used,
                "latency_ms": latency_ms,
                "context_count": len(context_ids),
            },
        )
        return interaction_id

    except Exception as e:
        logger.error(f"Error tracking interaction: {e}")
        return ""


async def update_interaction_outcome(
    interaction_id: str, outcome: str, user_feedback: int = 0
):
    """
    Update interaction with outcome and compute value score
    """
    global qdrant_client

    try:
        # Fetch interaction
        result = qdrant_client.retrieve(
            collection_name="interaction-history", ids=[interaction_id]
        )

        if not result:
            logger.error(f"Interaction not found: {interaction_id}")
            return

        interaction = result[0].payload

        # Update outcome
        interaction["outcome"] = outcome
        interaction["user_feedback"] = user_feedback

        # Compute value score
        value_score = compute_value_score(interaction)
        interaction["value_score"] = value_score

        # Update in Qdrant
        qdrant_client.set_payload(
            collection_name="interaction-history",
            payload=interaction,
            points=[interaction_id],
        )

        logger.info(
            f"Updated interaction {interaction_id}: outcome={outcome}, value={value_score:.2f}"
        )

        # If high-value, extract patterns
        if value_score >= Config.HIGH_VALUE_THRESHOLD and Config.PATTERN_EXTRACTION_ENABLED:
            await extract_patterns(interaction)
            if Config.AI_MEMORY_ENABLED and outcome == "success":
                await store_agent_memory(
                    "procedural",
                    summary=f"Successful procedure: {interaction.get('query', '')[:120]}",
                    content=interaction.get("response", "")[:1500],
                    metadata={
                        "trigger": interaction.get("query", ""),
                        "procedure": interaction.get("response", "")[:2000],
                        "outcome": outcome,
                        "value_score": value_score,
                    },
                )

        # Update context success rates
        if interaction.get("context_provided"):
            await update_context_metrics(
                interaction["context_provided"], outcome == "success"
            )

    except Exception as e:
        logger.error(f"Error updating interaction outcome: {e}")


async def update_context_metrics(context_ids: List[str], success: bool):
    """
    Update success rates and access counts for context items
    """
    global qdrant_client

    collections_to_update = [
        "codebase-context",
        "skills-patterns",
        "error-solutions",
        "best-practices",
    ]

    for collection_name in collections_to_update:
        for context_id in context_ids:
            try:
                # Fetch current payload
                result = qdrant_client.retrieve(
                    collection_name=collection_name, ids=[context_id]
                )

                if result:
                    payload = result[0].payload

                    # Update metrics
                    access_count = payload.get("access_count", 0) + 1
                    payload["access_count"] = access_count
                    payload["last_accessed"] = int(datetime.now().timestamp())

                    # Update success rate
                    if "success_rate" in payload:
                        current_rate = payload.get("success_rate", 0.5)
                        # Moving average
                        new_rate = (
                            current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
                        )
                        payload["success_rate"] = new_rate

                    # Update in Qdrant
                    qdrant_client.set_payload(
                        collection_name=collection_name,
                        payload=payload,
                        points=[context_id],
                    )

            except Exception as e:
                logger.warning(
                    f"Error updating context {context_id} in {collection_name}: {e}"
                )


# ============================================================================
# Pattern Extraction
# ============================================================================


async def extract_patterns(interaction: Dict[str, Any]):
    """
    Extract reusable patterns from successful interactions using local LLM
    """
    global llama_cpp_client

    prompt = f"""Analyze this successful interaction and extract reusable patterns:

Query: {interaction.get('query', '')}
Response: {interaction.get('response', '')[:500]}...

Extract:
1. What problem was solved?
2. What approach was used?
3. What skills/knowledge were applied?
4. What can be generalized for future use?

Return a JSON object with these fields:
{{
    "problem_type": "brief description",
    "solution_approach": "general approach used",
    "skills_used": ["skill1", "skill2"],
    "generalizable_pattern": "reusable pattern description"
}}

JSON:"""

    try:
        # Use llama.cpp for pattern extraction
        response = await llama_cpp_client.post(
            "/chat/completions",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()

        # Parse LLM response
        content = result["choices"][0]["message"]["content"]

        # Extract JSON from response
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "{" in content:
            json_str = content[content.index("{") : content.rindex("}") + 1]
        else:
            json_str = content

        pattern_data = json.loads(json_str)

        # Store as new skill/pattern
        await store_pattern(pattern_data, interaction)

        logger.info(f"Extracted pattern: {pattern_data.get('problem_type', 'Unknown')}")

    except Exception as e:
        logger.error(f"Error extracting patterns: {e}")


async def store_pattern(pattern_data: Dict[str, Any], source_interaction: Dict[str, Any]):
    """
    Store extracted pattern in skills-patterns collection
    """
    global qdrant_client

    # Create skill/pattern payload
    skill = {
        "skill_name": pattern_data.get("problem_type", "Unknown Skill"),
        "description": pattern_data.get("generalizable_pattern", ""),
        "usage_pattern": pattern_data.get("solution_approach", ""),
        "success_examples": [source_interaction.get("response", "")[:500]],
        "failure_examples": [],
        "prerequisites": [],
        "related_skills": pattern_data.get("skills_used", []),
        "value_score": source_interaction.get("value_score", 0.7),
        "last_updated": int(datetime.now().timestamp()),
    }

    # Embed the description
    embedding = await embed_text(skill["description"])

    # Check if similar pattern exists
    similar = qdrant_client.query_points(
        collection_name="skills-patterns",
        query=embedding,
        limit=1,
        score_threshold=0.9,
    ).points

    if similar:
        # Update existing pattern
        existing_id = str(similar[0].id)
        existing_payload = similar[0].payload

        # Add to success examples
        existing_payload["success_examples"].append(skill["success_examples"][0])

        # Update value score (moving average)
        existing_value = existing_payload.get("value_score", 0.5)
        new_value = existing_value * 0.8 + skill["value_score"] * 0.2
        existing_payload["value_score"] = new_value
        existing_payload["last_updated"] = skill["last_updated"]

        qdrant_client.set_payload(
            collection_name="skills-patterns",
            payload=existing_payload,
            points=[existing_id],
        )

        logger.info(f"Updated existing pattern: {existing_id}")
    else:
        # Create new pattern
        pattern_id = str(uuid4())
        qdrant_client.upsert(
            collection_name="skills-patterns",
            points=[PointStruct(id=pattern_id, vector=embedding, payload=skill)],
        )

        logger.info(f"Created new pattern: {pattern_id}")


# ============================================================================
# Fine-Tuning Data Generation
# ============================================================================


async def generate_fine_tuning_dataset() -> str:
    """
    Generate fine-tuning dataset from high-value interactions
    """
    global qdrant_client

    try:
        # Query high-value successful interactions
        high_value_interactions = qdrant_client.scroll(
            collection_name="interaction-history",
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="value_score", range=Range(gte=Config.HIGH_VALUE_THRESHOLD)
                    ),
                    FieldCondition(key="outcome", match=MatchValue(value="success")),
                ]
            ),
            limit=1000,
        )[0]

        # Format for fine-tuning (OpenAI format)
        training_data = []
        for point in high_value_interactions:
            payload = point.payload
            training_data.append(
                {
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful NixOS and coding assistant specialized in system configuration and development.",
                        },
                        {"role": "user", "content": payload.get("query", "")},
                        {"role": "assistant", "content": payload.get("response", "")},
                    ]
                }
            )

        # Save to JSONL
        os.makedirs(os.path.dirname(Config.FINETUNE_DATA_PATH), exist_ok=True)

        with open(Config.FINETUNE_DATA_PATH, "w") as f:
            for item in training_data:
                f.write(json.dumps(item) + "\n")

        logger.info(
            f"Generated fine-tuning dataset: {len(training_data)} examples at {Config.FINETUNE_DATA_PATH}"
        )

        return Config.FINETUNE_DATA_PATH

    except Exception as e:
        logger.error(f"Error generating fine-tuning dataset: {e}")
        return ""


# ============================================================================
# MCP Tool Definitions
# ============================================================================


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="augment_query",
            description="Augment a query with relevant context from local knowledge base",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to augment with context",
                    },
                    "agent_type": {
                        "type": "string",
                        "description": "Type of agent requesting context (local or remote)",
                        "enum": ["local", "remote"],
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="track_interaction",
            description="Record an interaction for learning and analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "response": {"type": "string"},
                    "agent_type": {"type": "string"},
                    "model_used": {"type": "string"},
                    "context_ids": {"type": "array", "items": {"type": "string"}},
                    "tokens_used": {"type": "integer"},
                    "latency_ms": {"type": "integer"},
                },
                "required": ["query", "response", "agent_type", "model_used"],
            },
        ),
        Tool(
            name="update_outcome",
            description="Update interaction outcome and trigger learning",
            inputSchema={
                "type": "object",
                "properties": {
                    "interaction_id": {"type": "string"},
                    "outcome": {
                        "type": "string",
                        "enum": ["success", "partial", "failure"],
                    },
                    "user_feedback": {"type": "integer", "minimum": -1, "maximum": 1},
                },
                "required": ["interaction_id", "outcome"],
            },
        ),
        Tool(
            name="generate_training_data",
            description="Generate fine-tuning dataset from high-value interactions",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="search_context",
            description="Search specific collection for relevant context",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "collection": {
                        "type": "string",
                        "enum": [
                            "codebase-context",
                            "skills-patterns",
                            "error-solutions",
                            "best-practices",
                        ],
                    },
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query", "collection"],
            },
        ),
        Tool(
            name="hybrid_search",
            description="Run hybrid search combining vector similarity and keyword matching",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "collections": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "default": 5},
                    "keyword_limit": {"type": "integer", "default": 5},
                    "score_threshold": {"type": "number", "default": 0.7},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="route_search",
            description="Route a query to SQL, semantic, keyword, tree, or hybrid search",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "sql", "semantic", "keyword", "tree", "hybrid"],
                        "default": "auto",
                    },
                    "prefer_local": {"type": "boolean", "default": True},
                    "context": {"type": "object"},
                    "limit": {"type": "integer", "default": 5},
                    "keyword_limit": {"type": "integer", "default": 5},
                    "score_threshold": {"type": "number", "default": 0.7},
                    "generate_response": {"type": "boolean", "default": False},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="store_agent_memory",
            description="Store episodic, semantic, or procedural memory items",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "enum": ["episodic", "semantic", "procedural"],
                    },
                    "summary": {"type": "string"},
                    "content": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["memory_type", "summary"],
            },
        ),
        Tool(
            name="recall_agent_memory",
            description="Recall memory using hybrid or tree retrieval mode",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "memory_types": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "default": 8},
                    "retrieval_mode": {
                        "type": "string",
                        "enum": ["hybrid", "tree"],
                        "default": "hybrid",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="run_harness_eval",
            description="Run deterministic harness evaluation with scorecard output",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "sql", "semantic", "keyword", "tree", "hybrid"],
                        "default": "auto",
                    },
                    "expected_keywords": {"type": "array", "items": {"type": "string"}},
                    "max_latency_ms": {"type": "integer"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="harness_stats",
            description="Get cumulative harness evaluation statistics and failure taxonomy",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="learning_feedback",
            description="Store user corrections and feedback for learning",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "correction": {"type": "string"},
                    "original_response": {"type": "string"},
                    "interaction_id": {"type": "string"},
                    "rating": {"type": "integer", "minimum": -1, "maximum": 1},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "model": {"type": "string"},
                    "variant": {"type": "string"},
                },
                "required": ["query", "correction"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls"""

    if name == "augment_query":
        query = arguments.get("query", "")
        agent_type = arguments.get("agent_type", "remote")

        result = await augment_query_with_context(query, agent_type)

        return [
            TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )
        ]

    elif name == "track_interaction":
        interaction_id = await track_interaction(
            query=arguments.get("query", ""),
            response=arguments.get("response", ""),
            agent_type=arguments.get("agent_type", "unknown"),
            model_used=arguments.get("model_used", "unknown"),
            context_ids=arguments.get("context_ids", []),
            tokens_used=arguments.get("tokens_used", 0),
            latency_ms=arguments.get("latency_ms", 0),
        )

        return [
            TextContent(
                type="text",
                text=json.dumps({"interaction_id": interaction_id}),
            )
        ]

    elif name == "update_outcome":
        await update_interaction_outcome(
            interaction_id=arguments.get("interaction_id", ""),
            outcome=arguments.get("outcome", "unknown"),
            user_feedback=arguments.get("user_feedback", 0),
        )

        return [TextContent(type="text", text=json.dumps({"status": "updated"}))]

    elif name == "generate_training_data":
        dataset_path = await generate_fine_tuning_dataset()

        return [
            TextContent(
                type="text",
                text=json.dumps({"dataset_path": dataset_path}),
            )
        ]

    elif name == "search_context":
        query = arguments.get("query", "")
        collection = arguments.get("collection", "codebase-context")
        limit = arguments.get("limit", 5)

        query_embedding = await embed_text(query)

        results = qdrant_client.query_points(
            collection_name=collection,
            query=query_embedding,
            limit=limit,
            score_threshold=0.7,
        ).points

        formatted_results = [
            {"id": str(r.id), "score": r.score, "payload": r.payload} for r in results
        ]

        return [
            TextContent(
                type="text",
                text=json.dumps(formatted_results, indent=2),
            )
        ]

    elif name == "hybrid_search":
        result = await hybrid_search(
            query=arguments.get("query", ""),
            collections=arguments.get("collections"),
            limit=arguments.get("limit", 5),
            keyword_limit=arguments.get("keyword_limit", 5),
            score_threshold=arguments.get("score_threshold", 0.7),
        )

        return [
            TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )
        ]

    elif name == "route_search":
        result = await route_search(
            query=arguments.get("query", ""),
            mode=arguments.get("mode", "auto"),
            prefer_local=arguments.get("prefer_local", True),
            context=arguments.get("context"),
            limit=arguments.get("limit", 5),
            keyword_limit=arguments.get("keyword_limit", 5),
            score_threshold=arguments.get("score_threshold", 0.7),
            generate_response=arguments.get("generate_response", False),
        )

        return [
            TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )
        ]

    elif name == "store_agent_memory":
        result = await store_agent_memory(
            memory_type=arguments.get("memory_type", ""),
            summary=arguments.get("summary", ""),
            content=arguments.get("content"),
            metadata=arguments.get("metadata"),
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "recall_agent_memory":
        result = await recall_agent_memory(
            query=arguments.get("query", ""),
            memory_types=arguments.get("memory_types"),
            limit=arguments.get("limit"),
            retrieval_mode=arguments.get("retrieval_mode", "hybrid"),
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "run_harness_eval":
        result = await run_harness_evaluation(
            query=arguments.get("query", ""),
            expected_keywords=arguments.get("expected_keywords"),
            mode=arguments.get("mode", "auto"),
            max_latency_ms=arguments.get("max_latency_ms"),
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "harness_stats":
        return [TextContent(type="text", text=json.dumps(HARNESS_STATS, indent=2))]

    elif name == "learning_feedback":
        feedback_id = await record_learning_feedback(
            query=arguments.get("query", ""),
            correction=arguments.get("correction", ""),
            original_response=arguments.get("original_response"),
            interaction_id=arguments.get("interaction_id"),
            rating=arguments.get("rating"),
            tags=arguments.get("tags"),
            model=arguments.get("model"),
            variant=arguments.get("variant"),
        )

        return [
            TextContent(
                type="text",
                text=json.dumps({"feedback_id": feedback_id}),
            )
        ]

    else:
        raise ValueError(f"Unknown tool: {name}")


# ============================================================================
# Server Initialization
# ============================================================================


async def initialize_server():
    """Initialize global clients and collections"""
    global qdrant_client, llama_cpp_client, embedding_client, aidb_client, multi_turn_manager, feedback_api, progressive_disclosure, learning_pipeline, postgres_client, context_compressor, embedding_cache

    _enforce_startup_env()
    await _preflight_check()
    logger.info("Initializing Hybrid Agent Coordinator...")

    # Initialize Qdrant client
    qdrant_client = QdrantClient(
        url=Config.QDRANT_URL,
        api_key=Config.QDRANT_API_KEY,
        timeout=30.0,
    )

    # Initialize llama.cpp client (external service, no auth)
    llama_cpp_client = httpx.AsyncClient(
        base_url=Config.LLAMA_CPP_URL,
        timeout=120.0,
    )

    # Initialize embedding client (internal service, with auth)
    embedding_client = create_embeddings_client(timeout=30.0)

    # Initialize embedding cache (Redis, keyed by model fingerprint)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    embedding_cache = EmbeddingCache(
        redis_url=redis_url,
        model_name=Config.EMBEDDING_MODEL,
    )
    await embedding_cache.initialize(flush_on_model_change=True)
    logger.info("✓ Embedding cache initialized (model=%s)", Config.EMBEDDING_MODEL)

    # Initialize AIDB client (optional, for hybrid routing)
    aidb_client = httpx.AsyncClient(
        base_url=Config.AIDB_URL,
        timeout=30.0,
    )

    # Create collections
    await initialize_collections()
    context_compressor = ContextCompressor()

    # Initialize multi-turn context manager
    from multi_turn_context import MultiTurnContextManager
    multi_turn_manager = MultiTurnContextManager(
        qdrant_client=qdrant_client,
        redis_url=_require_env("REDIS_URL"),
        llama_cpp_url=Config.LLAMA_CPP_URL
    )
    await multi_turn_manager.initialize()
    logger.info("✓ Multi-turn context manager initialized")

    # Initialize feedback API (OPTIONAL - disabled by default for token optimization)
    feedback_api = None
    if Config.REMOTE_LLM_FEEDBACK_ENABLED:
        from remote_llm_feedback import RemoteLLMFeedback
        feedback_api = RemoteLLMFeedback(
            qdrant_client=qdrant_client,
            multi_turn_manager=multi_turn_manager,
            llama_cpp_url=Config.LLAMA_CPP_URL
        )
        logger.info("✓ Remote LLM feedback API initialized")
    else:
        logger.info("⚠ Remote LLM feedback DISABLED (token optimization)")

    # Initialize progressive disclosure API
    from progressive_disclosure import ProgressiveDisclosure
    progressive_disclosure = ProgressiveDisclosure(
        qdrant_client=qdrant_client,
        multi_turn_manager=multi_turn_manager,
        feedback_api=feedback_api
    )
    logger.info("✓ Progressive disclosure API initialized")

    # Initialize continuous learning pipeline
    if os.getenv("CONTINUOUS_LEARNING_ENABLED", "true").lower() == "true":
        from continuous_learning import ContinuousLearningPipeline
        from shared.postgres_client import PostgresClient

        pg_password = (
            _read_secret(os.getenv("POSTGRES_PASSWORD_FILE", ""))
            or _read_secret("/run/secrets/postgres_password")
            or ""
        )

        # Initialize PostgreSQL client for learning pipeline
        postgres_client = PostgresClient(
            host=_require_env("POSTGRES_HOST"),
            port=int(_require_env("POSTGRES_PORT")),
            database=_require_env("POSTGRES_DB"),
            user=_require_env("POSTGRES_USER"),
            password=pg_password,
            sslmode=os.getenv("POSTGRES_SSLMODE"),
            sslrootcert=os.getenv("POSTGRES_SSLROOTCERT"),
            sslcert=os.getenv("POSTGRES_SSLCERT"),
            sslkey=os.getenv("POSTGRES_SSLKEY"),
        )
        await postgres_client.connect()

        learning_pipeline = ContinuousLearningPipeline(
            settings=HYBRID_SETTINGS,
            qdrant_client=qdrant_client,
            postgres_client=postgres_client
        )

        # Start background learning task
        asyncio.create_task(learning_pipeline.start())
        logger.info("✓ Continuous learning pipeline started")
    else:
        learning_pipeline = None
        logger.info("⚠ Continuous learning DISABLED")

    logger.info("✓ Hybrid Agent Coordinator initialized successfully")


# ============================================================================
# Main Entry Point
# ============================================================================


async def main():
    """Run the MCP server"""
    await initialize_server()

    # Check if running in HTTP mode (for container deployment)
    mode = _require_env("MCP_SERVER_MODE")

    if mode == "http":
        # Run as HTTP server with health endpoint
        from aiohttp import web

        access_log_format = (
            '{"remote":"%a","request":"%r","status":%s,'
            '"bytes":"%b","agent":"%{User-Agent}i","time":"%t"}'
        )
        access_logger = logging.getLogger("aiohttp.access")
        access_logger.handlers.clear()
        access_handler = logging.StreamHandler()
        access_handler.setFormatter(logging.Formatter("%(message)s"))
        access_logger.addHandler(access_handler)
        access_logger.setLevel(logging.INFO)
        access_logger.propagate = False

        @web.middleware
        async def tracing_middleware(request, handler):
            tracer = trace.get_tracer(SERVICE_NAME)
            span_name = f"{request.method} {request.path}"
            with tracer.start_as_current_span(
                span_name,
                attributes={
                    "http.method": request.method,
                    "http.target": request.path,
                },
            ) as span:
                response = await handler(request)
                span.set_attribute("http.status_code", response.status)
                return response

        @web.middleware
        async def request_id_middleware(request, handler):
            request_id = request.headers.get("X-Request-ID") or uuid4().hex
            request["request_id"] = request_id
            bind_contextvars(request_id=request_id)
            start = time.time()
            response = None
            try:
                response = await handler(request)
                return response
            except Exception:  # noqa: BLE001
                REQUEST_ERRORS.labels(request.path, request.method).inc()
                raise
            finally:
                duration = time.time() - start
                status = str(response.status) if response else "500"
                REQUEST_LATENCY.labels(request.path, request.method).observe(duration)
                REQUEST_COUNT.labels(request.path, status).inc()
                if response:
                    response.headers["X-Request-ID"] = request_id
                clear_contextvars()

        @web.middleware
        async def api_key_middleware(request, handler):
            if request.path in ("/health", "/metrics"):
                return await handler(request)
            if not Config.API_KEY:
                return await handler(request)
            token = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
            if token.startswith("Bearer "):
                token = token.split(" ", 1)[1]
            if token != Config.API_KEY:
                return web.json_response({"error": "unauthorized"}, status=401)
            return await handler(request)

        async def handle_status(request):
            """Phase 2.4.2 — Model loading status endpoint.

            Returns current llama.cpp model state by querying its /health endpoint.
            llama.cpp responds with {"status": "loading"} while a model is being loaded
            and {"status": "ok"} once ready. Also reports the local LLM health cache state
            and current routing threshold.

            Success metric: curl /status returns correct loading: true/false.
            """
            import time as _time
            try:
                async with httpx.AsyncClient(timeout=2.0) as hc:
                    resp = await hc.get(f"{Config.LLAMA_CPP_URL}/health")
                    llama_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    llama_status = llama_data.get("status", "unknown")
                    loading = llama_status == "loading"
            except Exception as exc:
                llama_status = "unreachable"
                loading = False
                logger.debug("handle_status llama.cpp probe failed: %s", exc)

            threshold = await routing_config.get_threshold()
            return web.json_response({
                "service": "hybrid-coordinator",
                "local_llm": {
                    "url": Config.LLAMA_CPP_URL,
                    "status": llama_status,
                    "loading": loading,
                    "healthy": _local_llm_healthy,
                    "model_name": os.getenv("LLAMA_MODEL_NAME", "unknown"),
                    "queue_depth": _model_loading_queue_depth,
                    "queue_max": _MODEL_QUEUE_MAX,
                },
                "routing": {
                    "threshold": threshold,
                    "local_supports_json": os.getenv("LOCAL_MODEL_SUPPORTS_JSON", "false").lower() == "true",
                },
            })

        async def handle_health(request):
            """Health check endpoint with circuit breakers"""
            # Get circuit breaker states from continuous learning
            try:
                from continuous_learning import learning_pipeline
                if learning_pipeline and hasattr(learning_pipeline, 'circuit_breakers'):
                    breakers = {}
                    for name, breaker in learning_pipeline.circuit_breakers._breakers.items():
                        breakers[name] = breaker.state.name
                else:
                    breakers = {}
            except (ImportError, AttributeError) as e:
                logger.debug("Circuit breaker state unavailable: %s", e)
                breakers = {}

            return web.json_response({
                "status": "healthy",
                "service": "hybrid-coordinator",
                "collections": list(COLLECTIONS.keys()),
                "ai_harness": {
                    "enabled": Config.AI_HARNESS_ENABLED,
                    "memory_enabled": Config.AI_MEMORY_ENABLED,
                    "tree_search_enabled": Config.AI_TREE_SEARCH_ENABLED,
                    "eval_enabled": Config.AI_HARNESS_EVAL_ENABLED,
                    "capability_discovery_enabled": Config.AI_CAPABILITY_DISCOVERY_ENABLED,
                    "capability_discovery_ttl_seconds": Config.AI_CAPABILITY_DISCOVERY_TTL_SECONDS,
                    "capability_discovery_on_query": Config.AI_CAPABILITY_DISCOVERY_ON_QUERY,
                    "autonomy_max_external_calls": Config.AI_AUTONOMY_MAX_EXTERNAL_CALLS,
                    "autonomy_max_retrieval_results": Config.AI_AUTONOMY_MAX_RETRIEVAL_RESULTS,
                    "prompt_cache_policy_enabled": Config.AI_PROMPT_CACHE_POLICY_ENABLED,
                    "speculative_decoding_enabled": Config.AI_SPECULATIVE_DECODING_ENABLED,
                    "speculative_decoding_mode": Config.AI_SPECULATIVE_DECODING_MODE,
                    "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
                },
                "capability_discovery": HYBRID_STATS["capability_discovery"],
                "circuit_breakers": breakers or CIRCUIT_BREAKERS.get_all_stats(),
            })

        async def handle_stats(request):
            """Stats endpoint"""
            return web.json_response({
                "status": "ok",
                "service": "hybrid-coordinator",
                "stats": snapshot_stats(),
                "collections": list(COLLECTIONS.keys()),
                "harness_stats": HARNESS_STATS,
                "capability_discovery": HYBRID_STATS["capability_discovery"],
                "circuit_breakers": CIRCUIT_BREAKERS.get_all_stats(),
            })

        async def handle_augment_query(request):
            """HTTP endpoint for query augmentation"""
            try:
                data = await request.json()
                query = data.get("query", "")
                agent_type = data.get("agent_type", "remote")

                result = await augment_query_with_context(query, agent_type)
                return web.json_response(result)
            except Exception as exc:  # noqa: BLE001
                return web.json_response(
                    {"error": "augment_query_failed", "detail": str(exc)},
                    status=500,
                )

        async def handle_query(request):
            """HTTP endpoint for query routing.

            Phase 2.4.1: If the local model is loading and prefer_local=True,
            the request is held in the loading queue (up to MODEL_LOADING_QUEUE_MAX
            concurrent waiters). Returns HTTP 503 immediately when the queue is
            full so callers can retry or escalate.
            """
            try:
                data = await request.json()
                query = data.get("prompt") or data.get("query") or ""
                if not query:
                    return web.json_response({"error": "query required"}, status=400)

                # Phase 2.4.1 — pre-flight: if prefer_local and model loading,
                # queue this request rather than falling through to an immediate 503.
                prefer_local = bool(data.get("prefer_local", True))
                if prefer_local and _local_llm_loading:
                    ready = await _wait_for_local_model(timeout=30.0)
                    if not ready:
                        return web.json_response(
                            {
                                "error": "model_loading",
                                "detail": "Local model is loading and the queue is full or timed out. Retry or set prefer_local=false.",
                                "queue_depth": _model_loading_queue_depth,
                                "queue_max": _MODEL_QUEUE_MAX,
                            },
                            status=503,
                        )

                result = await route_search(
                    query=query,
                    mode=data.get("mode", "auto"),
                    prefer_local=prefer_local,
                    context=data.get("context"),
                    limit=int(data.get("limit", 5)),
                    keyword_limit=int(data.get("keyword_limit", 5)),
                    score_threshold=float(data.get("score_threshold", 0.7)),
                    generate_response=bool(data.get("generate_response", False)),
                )
                # Phase 3.1.2 — persist last interaction_id so `aq-rate last` works.
                iid = result.get("interaction_id", "")
                if iid:
                    try:
                        _last_id_path = os.path.expanduser(
                            "~/.local/share/nixos-ai-stack/last-interaction"
                        )
                        os.makedirs(os.path.dirname(_last_id_path), exist_ok=True)
                        with open(_last_id_path, "w") as _f:
                            _f.write(iid)
                    except OSError:
                        pass  # non-critical
                return web.json_response(result)
            except Exception as exc:  # noqa: BLE001
                return web.json_response(
                    {"error": "route_search_failed", "detail": str(exc)},
                    status=500,
                )

        async def handle_tree_search(request):
            """HTTP endpoint for tree-search retrieval."""
            try:
                data = await request.json()
                query = data.get("query") or data.get("prompt") or ""
                if not query:
                    return web.json_response({"error": "query required"}, status=400)
                result = await tree_search(
                    query=query,
                    collections=data.get("collections"),
                    limit=int(data.get("limit", 5)),
                    keyword_limit=int(data.get("keyword_limit", 5)),
                    score_threshold=float(data.get("score_threshold", 0.7)),
                )
                return web.json_response(result)
            except Exception as exc:  # noqa: BLE001
                return web.json_response({"error": "tree_search_failed", "detail": str(exc)}, status=500)

        async def handle_memory_store(request):
            """HTTP endpoint for agent memory writes."""
            try:
                data = await request.json()
                result = await store_agent_memory(
                    memory_type=data.get("memory_type", ""),
                    summary=data.get("summary", ""),
                    content=data.get("content"),
                    metadata=data.get("metadata"),
                )
                return web.json_response(result)
            except Exception as exc:  # noqa: BLE001
                return web.json_response({"error": "memory_store_failed", "detail": str(exc)}, status=500)

        async def handle_memory_recall(request):
            """HTTP endpoint for agent memory recall."""
            try:
                data = await request.json()
                query = data.get("query") or data.get("prompt") or ""
                if not query:
                    return web.json_response({"error": "query required"}, status=400)
                result = await recall_agent_memory(
                    query=query,
                    memory_types=data.get("memory_types"),
                    limit=data.get("limit"),
                    retrieval_mode=data.get("retrieval_mode", "hybrid"),
                )
                return web.json_response(result)
            except Exception as exc:  # noqa: BLE001
                return web.json_response({"error": "memory_recall_failed", "detail": str(exc)}, status=500)

        async def handle_harness_eval(request):
            """HTTP endpoint for harness scoring."""
            try:
                data = await request.json()
                query = data.get("query") or data.get("prompt") or ""
                if not query:
                    return web.json_response({"error": "query required"}, status=400)
                result = await run_harness_evaluation(
                    query=query,
                    expected_keywords=data.get("expected_keywords"),
                    mode=data.get("mode", "auto"),
                    max_latency_ms=data.get("max_latency_ms"),
                )
                return web.json_response(result)
            except Exception as exc:  # noqa: BLE001
                return web.json_response({"error": "harness_eval_failed", "detail": str(exc)}, status=500)

        async def handle_harness_stats(_request):
            """HTTP endpoint for harness aggregate stats."""
            return web.json_response(HARNESS_STATS)

        async def handle_harness_scorecard(_request):
            """HTTP endpoint for reliability/safety/performance scorecards."""
            return web.json_response(build_harness_scorecard())

        async def handle_multi_turn_context(request):
            """HTTP endpoint for multi-turn context requests"""
            try:
                data = await request.json()
                session_id = data.get("session_id") or str(uuid4())
                query = data.get("query", "")
                context_level = data.get("context_level", "standard")
                previous_context_ids = data.get("previous_context_ids", [])
                max_tokens = data.get("max_tokens", 2000)
                metadata = data.get("metadata")

                response = await multi_turn_manager.get_context(
                    session_id=session_id,
                    query=query,
                    context_level=context_level,
                    previous_context_ids=previous_context_ids,
                    max_tokens=max_tokens,
                    metadata=metadata
                )

                return web.json_response(response.dict())

            except Exception as e:
                return web.json_response(error_payload("internal_error", e), status=500)

        async def handle_feedback(request):
            """HTTP endpoint for feedback ingestion"""
            try:
                data = await request.json()
                interaction_id = data.get("interaction_id")
                outcome = data.get("outcome")
                user_feedback = data.get("user_feedback", 0)
                correction = data.get("correction")
                if correction:
                    feedback_id = await record_learning_feedback(
                        query=data.get("query", ""),
                        correction=correction,
                        original_response=data.get("original_response"),
                        interaction_id=interaction_id,
                        rating=data.get("rating"),
                        tags=data.get("tags"),
                        model=data.get("model"),
                        variant=data.get("variant"),
                    )
                    return web.json_response({"status": "recorded", "feedback_id": feedback_id})

                if interaction_id and outcome:
                    await update_interaction_outcome(
                        interaction_id=interaction_id,
                        outcome=outcome,
                        user_feedback=user_feedback,
                    )
                    return web.json_response({"status": "updated"})

                return web.json_response({"error": "missing_feedback_fields"}, status=400)
            except Exception as e:
                return web.json_response(error_payload("internal_error", e), status=500)

        async def handle_simple_feedback(request):
            """Phase 3.1.1 — POST /feedback/{interaction_id}
            Body: {"rating": 1|-1, "note": "optional text"}
            Returns: {"status": "recorded", "feedback_id": "<uuid>"}
            """
            try:
                interaction_id = request.match_info.get("interaction_id", "")
                if not interaction_id:
                    return web.json_response({"error": "interaction_id required in path"}, status=400)
                data = await request.json()
                rating = data.get("rating")
                if rating not in (1, -1):
                    return web.json_response(
                        {"error": "rating must be 1 (good) or -1 (bad)"}, status=400
                    )
                note = str(data.get("note", ""))[:1000]
                query = str(data.get("query", ""))[:500]
                feedback_id = await record_simple_feedback(
                    interaction_id=interaction_id,
                    rating=rating,
                    note=note,
                    query=query,
                )
                return web.json_response({"status": "recorded", "feedback_id": feedback_id})
            except Exception as exc:
                return web.json_response(error_payload("internal_error", exc), status=500)

        async def handle_feedback_evaluate(request):
            """HTTP endpoint for remote LLM feedback evaluation"""
            try:
                data = await request.json()
                session_id = data.get("session_id", "")
                response_text = data.get("response", "")
                confidence = data.get("confidence", 0.5)
                gaps = data.get("gaps", [])
                metadata = data.get("metadata")

                if not session_id:
                    return web.json_response(
                        {"error": "session_id required"},
                        status=400
                    )

                feedback_response = await feedback_api.evaluate_response(
                    session_id=session_id,
                    response=response_text,
                    confidence=confidence,
                    gaps=gaps,
                    metadata=metadata
                )

                return web.json_response(feedback_response.dict())

            except Exception as e:
                return web.json_response(error_payload("internal_error", e), status=500)

        async def handle_session_info(request):
            """HTTP endpoint to get session information"""
            try:
                session_id = request.match_info.get('session_id')
                if not session_id:
                    return web.json_response(
                        {"error": "session_id required"},
                        status=400
                    )

                session_info = await multi_turn_manager.get_session_info(session_id)

                if not session_info:
                    return web.json_response(
                        {"error": "session not found"},
                        status=404
                    )

                return web.json_response(session_info)

            except Exception as e:
                return web.json_response(error_payload("internal_error", e), status=500)

        async def handle_clear_session(request):
            """HTTP endpoint to clear a session"""
            try:
                session_id = request.match_info.get('session_id')
                if not session_id:
                    return web.json_response(
                        {"error": "session_id required"},
                        status=400
                    )

                await multi_turn_manager.clear_session(session_id)

                return web.json_response({"status": "cleared", "session_id": session_id})

            except Exception as e:
                return web.json_response(error_payload("internal_error", e), status=500)

        async def handle_discover_capabilities(request):
            """HTTP endpoint for progressive capability discovery"""
            try:
                data = await request.json() if request.method == 'POST' else {}
                level = data.get("level", "overview")
                categories = data.get("categories")
                token_budget = data.get("token_budget", 500)

                discovery_response = await progressive_disclosure.discover(
                    level=level,
                    categories=categories,
                    token_budget=token_budget
                )

                return web.json_response(discovery_response.dict())

            except Exception as e:
                return web.json_response(error_payload("internal_error", e), status=500)

        async def handle_token_budget_recommendations(request):
            """HTTP endpoint for token budget recommendations"""
            try:
                data = await request.json() if request.method == 'POST' else {}
                query_type = data.get("query_type", "quick_lookup")
                context_level = data.get("context_level", "standard")

                recommendations = await progressive_disclosure.get_token_budget_recommendations(
                    query_type=query_type,
                    context_level=context_level
                )

                return web.json_response(recommendations)

            except Exception as e:
                return web.json_response(error_payload("internal_error", e), status=500)

        http_app = web.Application(
            middlewares=[tracing_middleware, request_id_middleware, api_key_middleware]
        )
        # Existing endpoints
        http_app.router.add_get('/health', handle_health)
        http_app.router.add_get('/status', handle_status)
        http_app.router.add_get('/stats', handle_stats)
        http_app.router.add_post('/augment_query', handle_augment_query)
        http_app.router.add_post('/query', handle_query)
        http_app.router.add_post('/search/tree', handle_tree_search)
        http_app.router.add_post('/memory/store', handle_memory_store)
        http_app.router.add_post('/memory/recall', handle_memory_recall)
        http_app.router.add_post('/harness/eval', handle_harness_eval)
        http_app.router.add_get('/harness/stats', handle_harness_stats)
        http_app.router.add_get('/harness/scorecard', handle_harness_scorecard)
        http_app.router.add_post('/feedback', handle_feedback)
        http_app.router.add_post('/feedback/{interaction_id}', handle_simple_feedback)  # Phase 3.1.1

        # New RLM endpoints
        http_app.router.add_post('/context/multi_turn', handle_multi_turn_context)
        http_app.router.add_post('/feedback/evaluate', handle_feedback_evaluate)
        http_app.router.add_get('/session/{session_id}', handle_session_info)
        http_app.router.add_delete('/session/{session_id}', handle_clear_session)

        # Progressive disclosure endpoints
        http_app.router.add_post('/discovery/capabilities', handle_discover_capabilities)
        http_app.router.add_get('/discovery/capabilities', handle_discover_capabilities)
        http_app.router.add_post('/discovery/token_budget', handle_token_budget_recommendations)
        async def handle_metrics(_request):
            PROCESS_MEMORY_BYTES.set(_get_process_memory_bytes())
            return web.Response(
                body=generate_latest(),
                headers={"Content-Type": CONTENT_TYPE_LATEST},
            )

        http_app.router.add_get('/metrics', handle_metrics)

        # Learning stats endpoint for dashboard
        async def handle_learning_stats(_request):
            """Return learning system statistics"""
            try:
                stats_path = Path(
                    os.path.expanduser(
                        os.getenv(
                            "CONTINUOUS_LEARNING_STATS_PATH",
                            os.path.join(
                                os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid"),
                                "telemetry",
                                "continuous_learning_stats.json",
                            ),
                        )
                    )
                )
                if stats_path.exists():
                    with open(stats_path, "r") as f:
                        stats = __import__("json").load(f)
                    return web.json_response(stats)
                if learning_pipeline:
                    stats = await learning_pipeline.get_statistics()
                    return web.json_response(stats)
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)

            # Return default stats
            return web.json_response({
                "checkpoints": {"total": 0, "last_checkpoint": None},
                "backpressure": {"unprocessed_mb": 0, "paused": False},
                "backpressure_threshold_mb": 100,
                "deduplication": {"total_patterns": 0, "duplicates_found": 0, "unique_patterns": 0}
            })

        async def handle_learning_process(_request):
            """Trigger a one-off telemetry processing cycle."""
            if not learning_pipeline:
                return web.json_response({"status": "disabled"}, status=503)
            try:
                patterns = await learning_pipeline.process_telemetry_batch()
                examples_count = 0
                if patterns:
                    examples = await learning_pipeline.generate_finetuning_examples(patterns)
                    examples_count = len(examples)
                    await learning_pipeline._save_finetuning_examples(examples)
                    await learning_pipeline._index_patterns(patterns)
                await learning_pipeline._write_stats_snapshot()
                return web.json_response({
                    "status": "ok",
                    "patterns": len(patterns),
                    "examples": examples_count,
                })
            except Exception as e:
                return web.json_response({"status": "error", "detail": str(e)}, status=500)

        async def handle_learning_export(_request):
            """Export the fine-tuning dataset for retraining."""
            try:
                dataset_path = ""
                if learning_pipeline:
                    dataset_path = await learning_pipeline.export_dataset_for_training()
                else:
                    dataset_path = await generate_fine_tuning_dataset()
                count = 0
                if dataset_path and Path(dataset_path).exists():
                    with open(dataset_path, "r") as f:
                        count = sum(1 for _ in f)
                return web.json_response({
                    "status": "ok",
                    "dataset_path": dataset_path,
                    "examples": count,
                })
            except Exception as e:
                return web.json_response({"status": "error", "detail": str(e)}, status=500)

        async def handle_learning_ab_compare(request):
            """Compare feedback ratings between two variants."""
            try:
                data = await request.json()
                tag_prefix = data.get("tag_prefix", "variant:")
                tag_a = data.get("tag_a")
                tag_b = data.get("tag_b")
                variant_a = data.get("variant_a")
                variant_b = data.get("variant_b")
                days = data.get("days")
                if not tag_a and variant_a:
                    tag_a = f"{tag_prefix}{variant_a}"
                if not tag_b and variant_b:
                    tag_b = f"{tag_prefix}{variant_b}"
                if not tag_a or not tag_b:
                    return web.json_response({"error": "variant_a/variant_b or tag_a/tag_b required"}, status=400)

                stats_a = await get_feedback_variant_stats(tag_a, days)
                stats_b = await get_feedback_variant_stats(tag_b, days)
                avg_a = stats_a.get("avg_rating")
                avg_b = stats_b.get("avg_rating")
                delta = None
                if avg_a is not None and avg_b is not None:
                    delta = float(avg_a) - float(avg_b)

                return web.json_response({
                    "status": "ok",
                    "variant_a": stats_a,
                    "variant_b": stats_b,
                    "delta": {"avg_rating": delta},
                })
            except RuntimeError as e:
                return web.json_response({"error": str(e)}, status=503)
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)

        http_app.router.add_get('/learning/stats', handle_learning_stats)
        http_app.router.add_post('/learning/process', handle_learning_process)
        http_app.router.add_post('/learning/export', handle_learning_export)
        http_app.router.add_post('/learning/ab_compare', handle_learning_ab_compare)

        port = int(_require_env("MCP_SERVER_PORT"))
        logger.info(f"Starting HTTP server on port {port}")

        runner = web.AppRunner(
            http_app,
            access_log=access_logger,
            access_log_format=access_log_format,
        )
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()

        logger.info(f"✓ Hybrid Coordinator HTTP server running on http://0.0.0.0:{port}")

        access_logger = logging.getLogger("aiohttp.access")
        access_logger.handlers.clear()
        access_handler = logging.StreamHandler()
        access_handler.setFormatter(logging.Formatter("%(message)s"))
        access_logger.addHandler(access_handler)
        access_logger.setLevel(logging.INFO)
        access_logger.propagate = False

        # Keep server running
        await asyncio.Event().wait()
    else:
        # Run MCP server via stdin/stdout (for local MCP usage)
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
