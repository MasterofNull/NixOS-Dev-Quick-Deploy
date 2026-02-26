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
import random
import re
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from uuid import uuid4

from enum import Enum
from pydantic import BaseModel, Field

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

from shared.auth_http_client import create_embeddings_client
from shared.circuit_breaker import CircuitBreakerError, CircuitBreakerRegistry, CircuitState
from shared.telemetry_privacy import scrub_telemetry_payload
from context_compression import ContextCompressor
from embedding_cache import EmbeddingCache
# Phase 6.1 — extracted modules
from metrics import (
    REQUEST_COUNT, REQUEST_ERRORS, REQUEST_LATENCY, PROCESS_MEMORY_BYTES,
    ROUTE_DECISIONS, ROUTE_ERRORS, DISCOVERY_DECISIONS, DISCOVERY_LATENCY,
    AUTONOMY_BUDGET_EXCEEDED, LLM_BACKEND_LATENCY, LLM_BACKEND_SELECTIONS,
)
from config import (
    HYBRID_SETTINGS, STRICT_ENV, _require_env, _enforce_startup_env,
    Config, RoutingConfig, routing_config,
    OptimizationProposalType, OptimizationProposal, apply_proposal,
    PerformanceWindow, performance_window,
)
import capability_discovery
import interaction_tracker
from interaction_tracker import (
    compute_value_score, track_interaction, update_interaction_outcome,
    update_context_metrics, extract_patterns, store_pattern,
    generate_fine_tuning_dataset, record_simple_feedback,
    _record_query_gap, get_feedback_variant_stats,
)
from search_router import (
    looks_like_sql as _looks_like_sql,
    normalize_tokens as _normalize_tokens,
    payload_matches_tokens as _payload_matches_tokens,
    rerank_combined_results as _rerank_combined_results,
    tree_expand_queries as _tree_expand_queries,
)
SERVICE_NAME = "hybrid-coordinator"
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")


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
# STRICT_ENV, _require_env, _enforce_startup_env → imported from config


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

# Prometheus metrics → imported from metrics.py


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


# Config, RoutingConfig, OptimizationProposal, PerformanceWindow → imported from config.py


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


async def embed_text(text: str, variant_tag: str = "") -> List[float]:
    """
    Public embedding entry point with Redis cache.
    Cache hit: returns in < 5 ms. Cache miss: delegates to _embed_text_uncached().
    Zero-vector error fallbacks are not cached.

    variant_tag: optional A/B test tag included in the cache key so that
                 variant A and B never share cached embeddings.
    """
    global embedding_cache

    # Assign A/B variant if caller did not specify one
    if not variant_tag:
        fraction = Config.AB_TEST_VARIANT_B_FRACTION
        variant_tag = "B" if (fraction > 0.0 and random.random() < fraction) else "A"
        if variant_tag == "B":
            logger.info("embed_text ab_variant=B fraction=%.2f", fraction)

    # Fast path — Redis cache hit
    if embedding_cache:
        cached = await embedding_cache.get(text, variant_tag=variant_tag)
        if cached is not None:
            logger.info("embed_text cache_hit text_len=%d variant=%s", len(text), variant_tag)
            return cached

    vector = await _embed_text_uncached(text)

    # Cache only real vectors, never the zero-vector error fallback
    if embedding_cache and vector and any(v != 0.0 for v in vector[:8]):
        await embedding_cache.set(text, vector, variant_tag=variant_tag)

    return vector


# ============================================================================
# Value Scoring Algorithm
# ============================================================================


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

        discovery = await capability_discovery.discover(query)
        discovery_context = capability_discovery.format_context(discovery)
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
    _cap_disc: Dict[str, Any] = {
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
            _cap_disc = await capability_discovery.discover(query)

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
            discovery_context = capability_discovery.format_context(_cap_disc)
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
                    "decision": _cap_disc.get("decision", "unknown"),
                    "reason": _cap_disc.get("reason", "unknown"),
                    "cache_hit": bool(_cap_disc.get("cache_hit", False)),
                    "intent_tags": _cap_disc.get("intent_tags", []),
                    "tool_count": len(_cap_disc.get("tools", [])),
                    "skill_count": len(_cap_disc.get("skills", [])),
                    "server_count": len(_cap_disc.get("servers", [])),
                    "dataset_count": len(_cap_disc.get("datasets", [])),
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
            "decision": _cap_disc.get("decision", "unknown"),
            "reason": _cap_disc.get("reason", "unknown"),
            "cache_hit": bool(_cap_disc.get("cache_hit", False)),
            "intent_tags": _cap_disc.get("intent_tags", []),
            "tools": [
                {"name": item.get("name"), "description": item.get("description")}
                for item in _cap_disc.get("tools", [])
            ],
            "skills": [
                {
                    "name": item.get("name", item.get("slug")),
                    "description": item.get("description"),
                }
                for item in _cap_disc.get("skills", [])
            ],
            "servers": [
                {"name": item.get("name"), "description": item.get("description")}
                for item in _cap_disc.get("servers", [])
            ],
            "datasets": [
                {
                    "title": item.get("title", item.get("relative_path")),
                    "project": item.get("project"),
                }
                for item in _cap_disc.get("datasets", [])
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
            description="Export high-value interactions to JSONL interaction archive",
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
        cache_epoch=Config.CACHE_EPOCH,
    )
    await embedding_cache.initialize(flush_on_model_change=True)
    logger.info("✓ Embedding cache initialized (model=%s)", Config.EMBEDDING_MODEL)

    # Initialize AIDB client (optional, for hybrid routing)
    aidb_client = httpx.AsyncClient(
        base_url=Config.AIDB_URL,
        timeout=30.0,
    )
    # Phase 6.1 — wire extracted capability_discovery module
    capability_discovery.init(
        aidb_client=aidb_client,
        stats=HYBRID_STATS["capability_discovery"],
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

    # Phase 6.1 — wire extracted interaction_tracker module
    interaction_tracker.init(
        qdrant_client=qdrant_client,
        postgres_client=postgres_client,
        llama_cpp_client=llama_cpp_client,
        embed_fn=embed_text,
        store_memory_fn=store_agent_memory,
        record_telemetry_fn=record_telemetry_event,
        performance_window=performance_window,
        collections=COLLECTIONS,
    )

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

        async def handle_apply_proposal(request: web.Request) -> web.Response:
            """Apply a validated OptimizationProposal. Requires API key."""
            key = request.headers.get("X-API-Key", "")
            if Config.API_KEY and key != Config.API_KEY:
                return web.json_response({"error": "unauthorized"}, status=401)
            try:
                body = await request.json()
                proposal = OptimizationProposal(**body)
            except Exception as exc:
                return web.json_response({"error": "invalid_proposal", "detail": str(exc)}, status=400)
            result = await apply_proposal(proposal)
            return web.json_response(result)

        http_app.router.add_post('/proposals/apply', handle_apply_proposal)

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
