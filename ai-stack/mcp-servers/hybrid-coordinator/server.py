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
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
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


def configure_tracing() -> None:
    if os.getenv("OTEL_TRACING_ENABLED", "true").lower() != "true":
        return
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
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

HYBRID_STATS = {
    "total_queries": 0,
    "context_hits": 0,
    "last_query_at": None,
    "agent_types": {},
}

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
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **payload,
    }
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


# ============================================================================
# Configuration
# ============================================================================


class Config:
    """Hybrid coordinator configuration"""

    QDRANT_URL = os.getenv("QDRANT_URL", HYBRID_SETTINGS.qdrant_url)
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
    QDRANT_HNSW_M = int(os.getenv("QDRANT_HNSW_M", HYBRID_SETTINGS.qdrant_hnsw_m))
    QDRANT_HNSW_EF_CONSTRUCT = int(os.getenv("QDRANT_HNSW_EF_CONSTRUCT", HYBRID_SETTINGS.qdrant_hnsw_ef_construct))
    QDRANT_HNSW_FULL_SCAN_THRESHOLD = int(
        os.getenv("QDRANT_HNSW_FULL_SCAN_THRESHOLD", HYBRID_SETTINGS.qdrant_hnsw_full_scan_threshold)
    )
    LLAMA_CPP_URL = os.getenv("LLAMA_CPP_BASE_URL", HYBRID_SETTINGS.llama_cpp_url)
    LLAMA_CPP_CODER_URL = os.getenv(
        "LLAMA_CPP_CODER_URL", HYBRID_SETTINGS.llama_cpp_url
    )
    LLAMA_CPP_DEEPSEEK_URL = os.getenv(
        "LLAMA_CPP_DEEPSEEK_URL", HYBRID_SETTINGS.llama_cpp_url
    )

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", HYBRID_SETTINGS.embedding_model)
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSIONS", HYBRID_SETTINGS.embedding_dimensions))
    EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "")
    EMBEDDING_API_KEY_FILE = os.getenv("EMBEDDING_API_KEY_FILE", "")
    EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
    AIDB_URL = os.getenv("AIDB_URL", os.getenv("AIDB_BASE_URL", "http://aidb:8091"))

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
    CONTEXT_COMPRESSION_ENABLED = os.getenv("CONTEXT_COMPRESSION_ENABLED", "true").lower() == "true"

    FINETUNE_DATA_PATH = os.path.expanduser(
        os.getenv(
            "FINETUNE_DATA_PATH",
            HYBRID_SETTINGS.finetune_data_path
            or "~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl",
        )
    )
    API_KEY_FILE = os.getenv("HYBRID_API_KEY_FILE", HYBRID_SETTINGS.api_key_file or "")
    API_KEY = os.getenv("HYBRID_API_KEY", "")


def _read_secret(path: str) -> str:
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        return ""


if not Config.API_KEY and Config.API_KEY_FILE:
    Config.API_KEY = _read_secret(Config.API_KEY_FILE)
if not Config.EMBEDDING_API_KEY and Config.EMBEDDING_API_KEY_FILE:
    Config.EMBEDDING_API_KEY = _read_secret(Config.EMBEDDING_API_KEY_FILE)


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


async def embed_text(text: str) -> List[float]:
    """
    Generate embedding for text using local embedding model
    (prefers embeddings service, falls back to AIDB, then llama.cpp)
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

        if not results_text:
            span.set_attribute("context_found", False)
        else:
            span.set_attribute("context_found", True)

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
        },
    )
    record_query_stats(agent_type, len(context_ids) > 0)

    return {
        "augmented_prompt": augmented_prompt,
        "context_ids": context_ids,
        "original_query": query,
        "context_count": len(context_ids),
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


async def route_query(
    query: str,
    mode: str = "auto",
    prefer_local: bool = True,
    context: Optional[Dict[str, Any]] = None,
    limit: int = 5,
    keyword_limit: int = 5,
    score_threshold: float = 0.7,
    generate_response: bool = False,
) -> Dict[str, Any]:
    """Route query to SQL, semantic, keyword, or hybrid search."""
    start = time.time()
    normalized_mode = (mode or "auto").lower()
    route = normalized_mode

    if normalized_mode == "auto":
        if _looks_like_sql(query):
            route = "sql"
        else:
            token_count = len(_normalize_tokens(query))
            if token_count <= 3:
                route = "keyword"
            else:
                route = "hybrid"

    results: Dict[str, Any] = {}
    response_text = ""

    try:
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

        if generate_response and llama_cpp_client:
            prompt = (
                f"User query: {query}\n\nContext:\n{response_text}\n\n"
                "Provide a concise response using the context."
            )
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
            except Exception as exc:  # noqa: BLE001
                logger.warning("route_query_llm_failed error=%s", exc)

        ROUTE_DECISIONS.labels(route=route).inc()
        record_telemetry_event(
            "route_query",
            {
                "query": query[:200],
                "route": route,
                "prefer_local": prefer_local,
                "context_keys": list((context or {}).keys()),
            },
        )
    except Exception as exc:  # noqa: BLE001
        ROUTE_ERRORS.labels(route=route).inc()
        logger.error("route_query_failed route=%s error=%s", route, exc)
        raise

    latency_ms = int((time.time() - start) * 1000)
    return {
        "route": route,
        "backend": route,
        "response": response_text,
        "results": results,
        "latency_ms": latency_ms,
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
            name="route_query",
            description="Route a query to SQL, semantic, keyword, or hybrid search",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "sql", "semantic", "keyword", "hybrid"],
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

    elif name == "route_query":
        result = await route_query(
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
    global qdrant_client, llama_cpp_client, embedding_client, aidb_client, multi_turn_manager, feedback_api, progressive_disclosure, learning_pipeline, postgres_client

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

    # Initialize AIDB client (optional, for hybrid routing)
    aidb_client = httpx.AsyncClient(
        base_url=Config.AIDB_URL,
        timeout=30.0,
    )

    # Create collections
    await initialize_collections()

    # Initialize multi-turn context manager
    from multi_turn_context import MultiTurnContextManager
    multi_turn_manager = MultiTurnContextManager(
        qdrant_client=qdrant_client,
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
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

        # Initialize PostgreSQL client for learning pipeline
        postgres_client = PostgresClient(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "aidb"),
            user=os.getenv("POSTGRES_USER", "mcp"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
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
    mode = os.getenv("MCP_SERVER_MODE", "stdio")

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
                "circuit_breakers": breakers or CIRCUIT_BREAKERS.get_all_stats(),
            })

        async def handle_stats(request):
            """Stats endpoint"""
            return web.json_response({
                "status": "ok",
                "service": "hybrid-coordinator",
                "stats": snapshot_stats(),
                "collections": list(COLLECTIONS.keys()),
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
            """HTTP endpoint for query routing"""
            try:
                data = await request.json()
                query = data.get("prompt") or data.get("query") or ""
                if not query:
                    return web.json_response({"error": "query required"}, status=400)
                result = await route_query(
                    query=query,
                    mode=data.get("mode", "auto"),
                    prefer_local=bool(data.get("prefer_local", True)),
                    context=data.get("context"),
                    limit=int(data.get("limit", 5)),
                    keyword_limit=int(data.get("keyword_limit", 5)),
                    score_threshold=float(data.get("score_threshold", 0.7)),
                    generate_response=bool(data.get("generate_response", False)),
                )
                return web.json_response(result)
            except Exception as exc:  # noqa: BLE001
                return web.json_response(
                    {"error": "route_query_failed", "detail": str(exc)},
                    status=500,
                )

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
        http_app.router.add_get('/stats', handle_stats)
        http_app.router.add_post('/augment_query', handle_augment_query)
        http_app.router.add_post('/query', handle_query)
        http_app.router.add_post('/feedback', handle_feedback)

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
                    os.getenv(
                        "CONTINUOUS_LEARNING_STATS_PATH",
                        "/data/telemetry/continuous_learning_stats.json",
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

        port = int(os.getenv("MCP_SERVER_PORT", "8092"))
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
