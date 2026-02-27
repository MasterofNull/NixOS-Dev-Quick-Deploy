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
    _read_secret,
    Config, RoutingConfig, routing_config,
    OptimizationProposalType, OptimizationProposal, apply_proposal,
    PerformanceWindow, performance_window,
)
from shared.ssrf_protection import assert_safe_outbound_url  # for user-supplied URL validation
import capability_discovery
import collections_config
import embedder
import harness_eval
import http_server
import interaction_tracker
import memory_manager
import mcp_handlers
import model_loader
import route_handler
from semantic_cache import SemanticCache
from interaction_tracker import (
    compute_value_score, track_interaction, update_interaction_outcome,
    update_context_metrics, extract_patterns, store_pattern,
    generate_fine_tuning_dataset, record_simple_feedback,
    _record_query_gap, get_feedback_variant_stats,
)
from search_router import (
    SearchRouter,
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


# Config, RoutingConfig, OptimizationProposal, PerformanceWindow → imported from config.py


# ============================================================================
# ============================================================================
# Local LLM Liveness Probe + Model Loading Queue
# (state and logic moved to model_loader.py — Phase 6.1)
# ============================================================================

async def _check_local_llm_health() -> bool:
    return await model_loader.check_local_llm_health()


async def _wait_for_local_model(timeout: float = 30.0) -> bool:
    return await model_loader.wait_for_local_model(timeout=timeout)



# ============================================================================
# Qdrant Collection Management — see collections_config.py
COLLECTIONS = collections_config.COLLECTIONS
MEMORY_COLLECTIONS = collections_config.MEMORY_COLLECTIONS

HARNESS_STATS = {
    "total_runs": 0,
    "passed": 0,
    "failed": 0,
    "failure_taxonomy": {},
    "last_run_at": None,
    "scorecards_generated": 0,
}


async def _embed_text_uncached(text: str) -> List[float]:
    return await embedder.embed_text_uncached(text)


async def embed_text(text: str, variant_tag: str = "") -> List[float]:
    return await embedder.embed_text(text, variant_tag=variant_tag)


# ============================================================================
# Value Scoring Algorithm
# ============================================================================


# ============================================================================
# Context Augmentation
# ============================================================================


# SemanticCache instance (instantiated in initialize_server())
_semantic_cache: Optional[Any] = None


async def augment_query_with_context(
    query: str, agent_type: str = "remote"
) -> Dict[str, Any]:
    """Delegate to SemanticCache.augment."""
    return await _semantic_cache.augment(query, agent_type)



# SearchRouter instance (instantiated in initialize_server())
_search_router: Optional["SearchRouter"] = None


async def hybrid_search(
    query: str,
    collections: Optional[List[str]] = None,
    limit: int = 5,
    keyword_limit: int = 5,
    score_threshold: float = 0.7,
    keyword_pool: int = 60,
) -> Dict[str, Any]:
    return await _search_router.hybrid_search(
        query, collections=collections, limit=limit,
        keyword_limit=keyword_limit, score_threshold=score_threshold,
        keyword_pool=keyword_pool,
    )


async def tree_search(
    query: str,
    collections: Optional[List[str]] = None,
    limit: int = 5,
    keyword_limit: int = 5,
    score_threshold: float = 0.7,
) -> Dict[str, Any]:
    return await _search_router.tree_search(
        query, collections=collections, limit=limit,
        keyword_limit=keyword_limit, score_threshold=score_threshold,
    )


async def select_llm_backend(
    prompt: str,
    context_quality: float,
    force_local: bool = False,
    force_remote: bool = False,
    requires_structured_output: bool = False,
) -> str:
    return await _search_router.select_backend(
        prompt, context_quality,
        force_local=force_local,
        force_remote=force_remote,
        requires_structured_output=requires_structured_output,
    )




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
    """Delegate to route_handler.route_search."""
    return await route_handler.route_search(
        query=query, mode=mode, prefer_local=prefer_local, context=context,
        limit=limit, keyword_limit=keyword_limit, score_threshold=score_threshold,
        generate_response=generate_response,
    )


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
    return await interaction_tracker.record_learning_feedback(
        query=query, correction=correction, original_response=original_response,
        interaction_id=interaction_id, rating=rating, tags=tags,
        model=model, variant=variant,
    )


@app.list_tools()
async def list_tools() -> List[Tool]:
    return mcp_handlers.TOOL_DEFINITIONS


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    return await mcp_handlers.dispatch_tool(name, arguments)


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

    # Initialize llama.cpp client (system-configured loopback service; no SSRF check needed)
    llama_cpp_client = httpx.AsyncClient(base_url=Config.LLAMA_CPP_URL, timeout=120.0)

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

    # Wire embedder module
    embedder.init(
        embedding_client=embedding_client,
        embedding_cache_ref=lambda: embedding_cache,
    )

    # Initialize AIDB client (system-configured loopback service; no SSRF check needed)
    aidb_client = httpx.AsyncClient(base_url=Config.AIDB_URL, timeout=30.0)
    # Phase 6.1 — wire extracted capability_discovery module
    capability_discovery.init(
        aidb_client=aidb_client,
        stats=HYBRID_STATS["capability_discovery"],
    )

    # Create collections
    await collections_config.initialize_collections(qdrant_client)
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
        store_memory_fn=memory_manager.store_agent_memory,
        record_telemetry_fn=record_telemetry_event,
        performance_window=performance_window,
        collections=COLLECTIONS,
    )

    # Phase 6.1 — wire extracted http_server module
    http_server.init(
        augment_query_fn=augment_query_with_context,
        route_search_fn=route_search,
        tree_search_fn=tree_search,
        store_memory_fn=memory_manager.store_agent_memory,
        recall_memory_fn=memory_manager.recall_agent_memory,
        run_harness_eval_fn=harness_eval.run_harness_evaluation,
        build_scorecard_fn=harness_eval.build_harness_scorecard,
        record_learning_feedback_fn=record_learning_feedback,
        record_simple_feedback_fn=record_simple_feedback,
        update_outcome_fn=update_interaction_outcome,
        get_variant_stats_fn=get_feedback_variant_stats,
        generate_dataset_fn=generate_fine_tuning_dataset,
        get_process_memory_fn=_get_process_memory_bytes,
        snapshot_stats_fn=snapshot_stats,
        error_payload_fn=error_payload,
        wait_for_model_fn=_wait_for_local_model,
        multi_turn_manager=multi_turn_manager,
        progressive_disclosure=progressive_disclosure,
        feedback_api=feedback_api,
        learning_pipeline=learning_pipeline,
        collections=COLLECTIONS,
        hybrid_stats=HYBRID_STATS,
        harness_stats=HARNESS_STATS,
        circuit_breakers=CIRCUIT_BREAKERS,
        service_name=SERVICE_NAME,
        local_llm_healthy_ref=lambda: model_loader._local_llm_healthy,
        local_llm_loading_ref=lambda: model_loader._local_llm_loading,
        queue_depth_ref=lambda: model_loader._model_loading_queue_depth,
        queue_max_ref=lambda: model_loader._MODEL_QUEUE_MAX,
    )

    # Phase 6.1 — wire model_loader (health check + loading queue)
    model_loader.init(llama_cpp_url=Config.LLAMA_CPP_URL)

    # Phase 6.1 — instantiate SemanticCache (backs augment_query_with_context)
    global _semantic_cache
    _semantic_cache = SemanticCache(
        qdrant_client=qdrant_client,
        embed_fn=embed_text,
        discovery_fn=capability_discovery.discover,
        format_context_fn=capability_discovery.format_context,
        record_telemetry_fn=record_telemetry_event,
        record_stats_fn=record_query_stats,
        tracer=TRACER,
        collections=COLLECTIONS,
    )

    # Phase 6.1 — instantiate SearchRouter (backs hybrid_search, tree_search, select_llm_backend)
    global _search_router
    _search_router = SearchRouter(
        qdrant_client=qdrant_client,
        embed_fn=embed_text,
        call_breaker_fn=_call_with_breaker,
        check_local_health_fn=_check_local_llm_health,
        wait_for_model_fn=_wait_for_local_model,
        get_local_loading_fn=lambda: model_loader._local_llm_loading,
        routing_config=routing_config,
        record_telemetry_fn=record_telemetry_event,
        collections=COLLECTIONS,
    )

    # Phase 6.1 — wire extracted route_handler module
    route_handler.init(
        hybrid_search_fn=hybrid_search,
        tree_search_fn=tree_search,
        select_backend_fn=select_llm_backend,
        record_query_gap_fn=_record_query_gap,
        record_telemetry_fn=record_telemetry_event,
        summarize_fn=harness_eval._summarize_results,
        context_compressor_ref=lambda: context_compressor,
        llama_cpp_client_ref=lambda: llama_cpp_client,
        postgres_client_ref=lambda: postgres_client,
        collections=COLLECTIONS,
    )

    # Phase 6.1 — wire extracted memory_manager module
    memory_manager.init(
        qdrant_client=qdrant_client,
        embed_fn=embed_text,
        record_telemetry_fn=record_telemetry_event,
        hybrid_search_fn=hybrid_search,
        tree_search_fn=tree_search,
        memory_collections=MEMORY_COLLECTIONS,
    )

    # Phase 6.1 — wire extracted harness_eval module
    harness_eval.init(
        route_search_fn=route_search,
        record_telemetry_fn=record_telemetry_event,
        harness_stats=HARNESS_STATS,
        hybrid_stats=HYBRID_STATS,
    )

    # Phase 6.1 — wire extracted mcp_handlers module
    mcp_handlers.init(
        augment_query_fn=augment_query_with_context,
        route_search_fn=route_search,
        hybrid_search_fn=hybrid_search,
        store_memory_fn=memory_manager.store_agent_memory,
        recall_memory_fn=memory_manager.recall_agent_memory,
        run_harness_eval_fn=harness_eval.run_harness_evaluation,
        record_learning_feedback_fn=record_learning_feedback,
        track_interaction_fn=track_interaction,
        update_outcome_fn=update_interaction_outcome,
        generate_dataset_fn=generate_fine_tuning_dataset,
        embed_fn=embed_text,
        qdrant_client=qdrant_client,
        harness_stats=HARNESS_STATS,
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
        port = int(_require_env("MCP_SERVER_PORT"))
        logger.info("Starting HTTP server on port %d", port)
        await http_server.run_http_mode(port=port)
    else:
        # Run MCP server via stdin/stdout (for local MCP usage)
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
