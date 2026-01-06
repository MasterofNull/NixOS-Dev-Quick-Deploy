#!/usr/bin/env python3
"""Advanced AIDB MCP server with monitoring, catalog bootstrap, and sandboxing."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from logging.handlers import RotatingFileHandler
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

import httpx
import sqlalchemy as sa
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi import Request
from pydantic import BaseModel
from prometheus_client import Counter, Gauge, Histogram, CONTENT_TYPE_LATEST, generate_latest
from redis import asyncio as redis_asyncio
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker
from websockets import serve
import re
from urllib.parse import urlparse

from pgvector.sqlalchemy import Vector
from sentence_transformers import SentenceTransformer

from middleware.cache import CacheMiddleware
from llm_parallel import run_parallel_inference
from discovery_endpoints import register_discovery_routes
from settings_loader import Settings, load_settings
from skills_loader import ParsedSkill, parse_skill_text, write_skill_file
from ml_engine import MLEngine
import registry_api
import vscode_telemetry

LOGGER = logging.getLogger("aidb.mcp")


def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
    operation_name: str = "operation",
):
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry (can be sync or async)
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to catch and retry
        operation_name: Name for logging

    Returns:
        Result of func() if successful

    Raises:
        Last exception if all retries exhausted
    """
    import asyncio
    import inspect

    is_async = inspect.iscoroutinefunction(func)

    async def async_wrapper():
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                return await func()
            except exceptions as e:
                last_exception = e
                if attempt >= max_retries:
                    LOGGER.error(
                        f"{operation_name} failed after {max_retries} attempts: {e}"
                    )
                    raise

                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                LOGGER.warning(
                    f"{operation_name} attempt {attempt}/{max_retries} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)

        raise last_exception  # Should never reach here, but satisfies type checker

    def sync_wrapper():
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                return func()
            except exceptions as e:
                last_exception = e
                if attempt >= max_retries:
                    LOGGER.error(
                        f"{operation_name} failed after {max_retries} attempts: {e}"
                    )
                    raise

                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                LOGGER.warning(
                    f"{operation_name} attempt {attempt}/{max_retries} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)

        raise last_exception  # Should never reach here, but satisfies type checker

    return async_wrapper() if is_async else sync_wrapper()


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascade failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, fail fast
    - HALF_OPEN: Testing if service recovered

    After failure_threshold failures, circuit opens for recovery_timeout seconds.
    During OPEN state, requests fail immediately without calling service.
    After recovery_timeout, enters HALF_OPEN to test if service recovered.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()

        # Update Prometheus metrics
        self._update_metrics()

    @property
    def state(self) -> str:
        """Get current circuit state"""
        with self._lock:
            if self._state == "OPEN" and self._last_failure_time:
                # Check if recovery timeout has elapsed
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = "HALF_OPEN"
                    self._update_metrics()
                    LOGGER.info(f"Circuit breaker '{self.name}': OPEN → HALF_OPEN (testing recovery)")
            return self._state

    def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args, **kwargs: Arguments to pass to func

        Returns:
            Result of func()

        Raises:
            RuntimeError: If circuit is OPEN
            Exception: If func() raises
        """
        current_state = self.state

        if current_state == "OPEN":
            raise RuntimeError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Service unavailable due to repeated failures. "
                f"Will retry in {self.recovery_timeout - (time.time() - self._last_failure_time):.0f}s"
            )

        try:
            result = func(*args, **kwargs)

            # Success - reset failure count
            with self._lock:
                if self._state == "HALF_OPEN":
                    self._state = "CLOSED"
                    self._update_metrics()
                    LOGGER.info(f"Circuit breaker '{self.name}': HALF_OPEN → CLOSED (service recovered)")

                if self._failure_count > 0:
                    LOGGER.debug(f"Circuit breaker '{self.name}': Reset failure count (was {self._failure_count})")
                self._failure_count = 0

            return result

        except self.expected_exception as e:
            # Failure - increment count and check threshold
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()
                CIRCUIT_BREAKER_FAILURES.labels(service=self.name).inc()

                if self._failure_count >= self.failure_threshold:
                    self._state = "OPEN"
                    self._update_metrics()
                    LOGGER.error(
                        f"Circuit breaker '{self.name}': CLOSED → OPEN "
                        f"({self._failure_count} failures exceeded threshold {self.failure_threshold}). "
                        f"Failing fast for {self.recovery_timeout}s"
                    )
                else:
                    LOGGER.warning(
                        f"Circuit breaker '{self.name}': Failure {self._failure_count}/{self.failure_threshold}: {e}"
                    )

            raise

    def _update_metrics(self):
        """Update Prometheus metrics for current state"""
        state_value = {"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}.get(self._state, 0)
        CIRCUIT_BREAKER_STATE.labels(service=self.name).set(state_value)

    def reset(self):
        """Manually reset circuit breaker to CLOSED state"""
        with self._lock:
            old_state = self._state
            self._state = "CLOSED"
            self._failure_count = 0
            self._last_failure_time = None
            self._update_metrics()
            if old_state != "CLOSED":
                LOGGER.info(f"Circuit breaker '{self.name}': {old_state} → CLOSED (manual reset)")


METADATA = sa.MetaData()
TOOL_REGISTRY = sa.Table(
    "tool_registry",
    METADATA,
    sa.Column("name", sa.String(256), primary_key=True),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("manifest", sa.JSON, nullable=False),
    sa.Column("cost_estimate_tokens", sa.Integer, nullable=False, default=2000),
)

IMPORTED_DOCUMENTS = sa.Table(
    "imported_documents",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("project", sa.String(128), nullable=False),
    sa.Column("relative_path", sa.Text, nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("content_type", sa.String(32), nullable=False),
    sa.Column("checksum", sa.String(64), nullable=False),
    sa.Column("size_bytes", sa.Integer, nullable=False),
    sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("status", sa.String(16), nullable=False, server_default="approved"),
    sa.UniqueConstraint("project", "relative_path", name="uq_imported_documents_path"),
)

OPEN_SKILLS = sa.Table(
    "open_skills",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("slug", sa.String(128), nullable=False, unique=True),
    sa.Column("name", sa.String(256), nullable=False),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("version", sa.String(32), nullable=True),
    sa.Column("tags", sa.JSON, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("metadata", sa.JSON, nullable=False),
    sa.Column("source_path", sa.Text, nullable=False),
    sa.Column("source_url", sa.Text, nullable=True),
    sa.Column("managed_by", sa.String(32), nullable=False, server_default="local"),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    sa.Column("status", sa.String(16), nullable=False, server_default="approved"),
)

SYSTEM_REGISTRY = sa.Table(
    "system_registry",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("resource_type", sa.String(50), nullable=False),
    sa.Column("name", sa.String(100), nullable=False, unique=True),
    sa.Column("version", sa.String(20), nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("location", sa.String(255), nullable=False),
    sa.Column("install_command", sa.Text, nullable=True),
    sa.Column("dependencies", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("added_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
)

POINTS_OF_INTEREST = sa.Table(
    "points_of_interest",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("name", sa.String(256), nullable=False),
    sa.Column("category", sa.String(128), nullable=False),
    sa.Column("url", sa.Text, nullable=True),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("source", sa.Text, nullable=True),
    sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("name", "category", name="uq_points_of_interest_name_category"),
)

TELEMETRY_EVENTS = sa.Table(
    "telemetry_events",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("source", sa.String(64), nullable=False),
    sa.Column("event_type", sa.String(64), nullable=False),
    sa.Column("llm_used", sa.String(32), nullable=True),
    sa.Column("tokens_saved", sa.Integer, nullable=True),
    sa.Column("rag_hits", sa.Integer, nullable=True),
    sa.Column("collections_used", sa.JSON, nullable=True),
    sa.Column("model", sa.String(128), nullable=True),
    sa.Column("latency_ms", sa.Integer, nullable=True),
    sa.Column("cache_hit", sa.Boolean, nullable=True),
    sa.Column("metadata", sa.JSON, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

TOOL_DISCOVERY_COUNTER = Counter(
    "aidb_tool_discovery_total", "Number of tool discovery requests", ["mode"]
)
SANDBOX_RUN_COUNTER = Counter(
    "aidb_sandbox_runs_total", "Sandbox executions by result", ["status"]
)
REQUEST_LATENCY = Histogram(
    "aidb_request_latency_seconds", "Latency for MCP actions", ["action"]
)
CACHE_GAUGE = Gauge("aidb_tool_cache_size", "Number of tools in memory cache")
CIRCUIT_BREAKER_STATE = Gauge(
    "aidb_circuit_breaker_state",
    "Circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)",
    ["service"]
)
CIRCUIT_BREAKER_FAILURES = Counter(
    "aidb_circuit_breaker_failures_total",
    "Circuit breaker failure count",
    ["service"]
)


class EmbeddingService:
    """Lightweight wrapper around SentenceTransformer with async helpers."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None
        self._model_lock = threading.Lock()

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        model = await asyncio.to_thread(self._load_model)
        embeddings = await asyncio.to_thread(
            model.encode,
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        # Ensure pure Python lists for JSON serialization and DB binding
        return [list(map(float, vector)) for vector in embeddings]


class VectorStore:
    """Persist and query document embeddings stored in pgvector."""

    def __init__(self, settings: Settings, engine: sa.Engine):
        self.settings = settings
        self.engine = engine
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.table = sa.Table(
            "document_embeddings",
            METADATA,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "document_id",
                sa.Integer,
                sa.ForeignKey("imported_documents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("chunk_id", sa.String(length=128), nullable=True),
            sa.Column("content", sa.Text, nullable=False),
            sa.Column("embedding", Vector(settings.embedding_dimension), nullable=False),
            sa.Column("metadata", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("score", sa.Float, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
            sa.UniqueConstraint("document_id", "chunk_id", name="uq_document_embeddings_chunk"),
            extend_existing=True,
        )

    def _validate_embedding(self, embedding: List[float]) -> None:
        if len(embedding) != self.settings.embedding_dimension:
            raise ValueError(
                f"Embedding dimension {len(embedding)} does not match configured "
                f"{self.settings.embedding_dimension}"
            )

    def index_embeddings(self, items: List[Dict[str, Any]]) -> int:
        """Insert or update embeddings. Returns count indexed."""
        session = self._session_factory()
        try:
            for item in items:
                embedding = item["embedding"]
                self._validate_embedding(embedding)
                stmt = (
                    insert(self.table)
                    .values(
                        document_id=item["document_id"],
                        chunk_id=item.get("chunk_id"),
                        content=item["content"],
                        embedding=embedding,
                        metadata=item.get("metadata") or {},
                        score=item.get("score"),
                    )
                    .on_conflict_do_update(
                        index_elements=[self.table.c.document_id, self.table.c.chunk_id],
                        set_={
                            "content": sa.cast(sa.literal(item["content"]), sa.Text),
                            "embedding": embedding,
                            "metadata": item.get("metadata") or {},
                            "score": item.get("score"),
                            "updated_at": sa.func.now(),
                        },
                    )
                )
                session.execute(stmt)
            session.commit()
            return len(items)
        finally:
            session.close()

    def search(self, embedding: List[float], limit: int = 5, project: Optional[str] = None) -> List[Dict[str, Any]]:
        """Perform vector similarity search using L2 distance."""
        self._validate_embedding(embedding)

        def _query() -> List[Dict[str, Any]]:
            with self.engine.connect() as conn:
                project_filter = "WHERE docs.project = :project" if project else ""
                stmt = sa.text(
                    f"""
                    SELECT de.id,
                           de.document_id,
                           de.chunk_id,
                           de.content,
                           de.metadata,
                           de.score,
                           docs.project,
                           docs.title,
                           docs.relative_path,
                           de.embedding <-> :query_vec AS distance
                    FROM document_embeddings de
                    JOIN imported_documents docs ON docs.id = de.document_id
                    {project_filter}
                    ORDER BY de.embedding <-> :query_vec
                    LIMIT :limit
                    """
                ).bindparams(sa.bindparam("query_vec", embedding, type_=Vector(self.settings.embedding_dimension)))
                params: Dict[str, Any] = {"limit": limit}
                if project:
                    stmt = stmt.bindparams(sa.bindparam("project", project))
                    params["project"] = project
                result = conn.execute(stmt, params)
                rows = result.mappings().all()
                return [dict(row) for row in rows]

        return _query()


class FederationStore:
    """Minimal file-backed registry for federated MCP servers."""

    def __init__(self, storage_path: Path, sources_dir: Path):
        self.storage_path = storage_path
        self.sources_dir = sources_dir
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _load(self) -> List[Dict[str, Any]]:
        if not self.storage_path.exists():
            return []
        try:
            return json.loads(self.storage_path.read_text())
        except json.JSONDecodeError:
            LOGGER.warning("Federation store is corrupted; reinitializing empty list")
            return []

    def _save(self, servers: List[Dict[str, Any]]) -> None:
        self.storage_path.write_text(json.dumps(servers, indent=2))

    async def list_servers(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return list(self._load())

    async def upsert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        server_url = payload.get("server_url") or payload.get("url")
        if not server_url:
            raise ValueError("server_url is required")

        async with self._lock:
            servers = self._load()
            existing_idx = next(
                (idx for idx, server in enumerate(servers) if server.get("server_url") == server_url),
                None,
            )

            def _inherit(key: str, default: Any = None) -> Any:
                if existing_idx is not None:
                    return servers[existing_idx].get(key, default)
                return default

            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            record = {
                "id": _inherit(
                    "id",
                    (max([s.get("id", 0) for s in servers]) + 1) if servers else 1,
                ),
                "name": payload.get("name") or urlparse(server_url).netloc or server_url,
                "description": payload.get("description") or _inherit("description", ""),
                "server_url": server_url,
                "server_type": payload.get("server_type", _inherit("server_type", "mcp")),
                "auth_type": payload.get("auth_type", _inherit("auth_type", "none")),
                "capabilities": payload.get("capabilities") or _inherit("capabilities", {}),
                "tags": payload.get("tags") or _inherit("tags", []),
                "priority": payload.get("priority") or _inherit("priority", 0),
                "created_at": _inherit("created_at", ts),
                "updated_at": ts,
            }

            if existing_idx is not None:
                servers[existing_idx] = record
            else:
                servers.append(record)

            self._save(servers)
            return record

    def discover_local_sources(self, limit: Optional[int] = None) -> List[str]:
        """Harvest MCP server links from bundled source lists."""
        urls: set[str] = set()
        if not self.sources_dir.exists():
            return []

        for path in self.sources_dir.glob("*.md"):
            try:
                content = path.read_text()
                urls.update(re.findall(r"https?://[^\\s)>\\\"]+", content))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(f"Failed to parse MCP source file {path}: {exc}")

        sorted_urls = sorted(urls)
        if limit is not None:
            return sorted_urls[:limit]
        return sorted_urls


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "skill"


class ToolDefinition(BaseModel):
    name: str
    description: str
    manifest: Dict[str, Any]
    cost_estimate_tokens: int = 2000


class ToolPayload(BaseModel):
    name: str
    description: str
    manifest: Dict[str, Any]


class SkillImportRequest(BaseModel):
    slug: Optional[str] = None
    url: Optional[str] = None
    content: Optional[str] = None
    managed_by: str = "agent"
    name: Optional[str] = None
    source_path: Optional[str] = None
    source_url: Optional[str] = None


class SkillRecord(BaseModel):
    slug: str
    name: str
    description: str
    version: Optional[str]
    tags: List[str]
    content: str
    metadata: Dict[str, Any]
    source_path: str
    updated_at: Optional[str]
    source_url: Optional[str] = None
    managed_by: str = "local"
    status: str = "approved"


class RateLimiter:
    def __init__(self, enabled: bool, rpm: int):
        self.enabled = enabled
        self.limit = rpm
        self._calls: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, client_id: str) -> None:
        if not self.enabled:
            return
        now = time.time()
        window = self._calls[client_id]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.limit:
            raise PermissionError("Rate limit exceeded")
        window.append(now)


class SandboxResult(BaseModel):
    stdout: str
    stderr: str
    returncode: int


class SandboxExecutor:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def run(self, command: List[str], timeout: Optional[int] = None) -> SandboxResult:
        if not self.settings.sandbox_enabled:
            raise RuntimeError("Sandbox execution disabled by configuration")
        sandbox = self.settings.sandbox_runner
        if sandbox not in {"bubblewrap", "firejail"}:
            raise RuntimeError(f"Unsupported sandbox runner: {sandbox}")

        sandbox_command: List[str] = [sandbox]
        sandbox_command += self.settings.sandbox_extra_args

        if sandbox == "bubblewrap":
            sandbox_command += ["--unshare-all", "--ro-bind", "/usr", "/usr"]
        else:
            sandbox_command += ["--quiet", "--private"]
        if self.settings.sandbox_profile:
            sandbox_command += ["--profile", str(self.settings.sandbox_profile)]

        proc = await asyncio.create_subprocess_exec(
            *sandbox_command,
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout or self.settings.sandbox_timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise
        return SandboxResult(
            stdout=stdout_bytes.decode(),
            stderr=stderr_bytes.decode(),
            returncode=proc.returncode or 0,
        )


class ToolRegistry:
    def __init__(self, settings: Settings, engine: sa.Engine, redis: redis_asyncio.Redis):
        self.settings = settings
        self.engine = engine
        self.redis = redis
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._tool_cache: Dict[str, ToolDefinition] = {}
        self._fs_cache_path = settings.tool_schema_cache
        self._fs_cache_path.parent.mkdir(parents=True, exist_ok=True)

    async def warm_cache(self) -> None:
        if self._fs_cache_path.exists():
            try:
                cached = json.loads(self._fs_cache_path.read_text(encoding="utf-8"))
                for payload in cached:
                    tool = ToolDefinition(**payload)
                    self._tool_cache[tool.name] = tool
                LOGGER.info("Loaded %d tools from disk cache", len(cached))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Disk cache hydration failed: %s", exc)

        redis_keys = await self.redis.keys("tool:definition:*")
        if redis_keys:
            async with self.redis.pipeline(transaction=False) as pipe:
                for key in redis_keys:
                    pipe.get(key)
                blobs = await pipe.execute()
            for blob in blobs:
                if not blob:
                    continue
                tool = ToolDefinition.model_validate_json(blob)
                self._tool_cache[tool.name] = tool
            LOGGER.info("Hydrated %d tools from Redis", len(blobs))
        CACHE_GAUGE.set(len(self._tool_cache))

    async def persist_cache(self) -> None:
        payload = [tool.model_dump() for tool in self._tool_cache.values()]
        self._fs_cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        LOGGER.debug("Persisted %d tools to disk cache", len(payload))

    async def get_tools(self, mode: str) -> List[ToolPayload]:
        if mode not in {"minimal", "full"}:
            raise ValueError(f"Unsupported tool discovery mode {mode}")
        if not self._tool_cache:
            await self._refresh_from_database()
        tools: List[ToolPayload] = []
        for tool in self._tool_cache.values():
            manifest = tool.manifest if mode == "full" else {"name": tool.name}
            tools.append(ToolPayload(name=tool.name, description=tool.description, manifest=manifest))
        return tools

    async def _refresh_from_database(self) -> None:
        query = sa.select(
            TOOL_REGISTRY.c.name,
            TOOL_REGISTRY.c.description,
            TOOL_REGISTRY.c.manifest,
            TOOL_REGISTRY.c.cost_estimate_tokens,
        )

        def _fetch() -> List[Dict[str, Any]]:
            session = self._session_factory()
            try:
                result = session.execute(query)
                return [
                    {
                        "name": row.name,
                        "description": row.description,
                        "manifest": row.manifest,
                        "cost_estimate_tokens": row.cost_estimate_tokens,
                    }
                    for row in result
                ]
            finally:
                session.close()

        rows = await asyncio.to_thread(_fetch)
        for row in rows:
            tool = ToolDefinition(**row)
            self._tool_cache[tool.name] = tool
            await self.redis.set(
                f"tool:definition:{tool.name}",
                tool.model_dump_json(),
                ex=self.settings.tool_cache_ttl,
            )
        CACHE_GAUGE.set(len(self._tool_cache))
        LOGGER.info("Loaded %d tool manifests from the database", len(rows))
        await self.persist_cache()


class CatalogBootstrapper:
    def __init__(self, settings: Settings, engine: sa.Engine):
        self.settings = settings
        self.engine = engine

    def sync_catalog(self) -> int:
        path = self.settings.catalog_path
        if not path.exists():
            LOGGER.warning("Catalog file %s missing; skipping bootstrap", path)
            return 0
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        if not entries:
            return 0
        inserted = 0
        with self.engine.begin() as conn:
            for entry in entries:
                manifest = {
                    "url": entry.get("url"),
                    "section": entry.get("section"),
                    "source": entry.get("source_title"),
                    "source_file": entry.get("source_file"),
                }
                stmt = insert(TOOL_REGISTRY).values(
                    name=entry["name"],
                    description=entry.get("description") or "",
                    manifest=manifest,
                    cost_estimate_tokens=2000,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[TOOL_REGISTRY.c.name],
                    set_={
                        "description": stmt.excluded.description,
                        "manifest": stmt.excluded.manifest,
                        "cost_estimate_tokens": stmt.excluded.cost_estimate_tokens,
                    },
                )
                conn.execute(stmt)
                inserted += 1
        LOGGER.info("Bootstrapped %d catalog entries into tool_registry", inserted)
        return inserted


class OpenSkillsRepository:
    def __init__(self, engine: sa.Engine):
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def list_skills(self, include_pending: bool = False) -> List[SkillRecord]:
        session = self._session_factory()
        try:
            query = sa.select(
                OPEN_SKILLS.c.slug,
                OPEN_SKILLS.c.name,
                OPEN_SKILLS.c.description,
                OPEN_SKILLS.c.version,
                OPEN_SKILLS.c.tags,
                OPEN_SKILLS.c.content,
                OPEN_SKILLS.c.metadata,
                OPEN_SKILLS.c.source_path,
                OPEN_SKILLS.c.source_url,
                OPEN_SKILLS.c.managed_by,
                OPEN_SKILLS.c.updated_at,
                OPEN_SKILLS.c.status,
            ).order_by(OPEN_SKILLS.c.slug)
            if not include_pending:
                query = query.where(OPEN_SKILLS.c.status == "approved")
            rows = session.execute(query).all()
            return [
                SkillRecord(
                    slug=row.slug,
                    name=row.name,
                    description=row.description,
                    version=row.version,
                    tags=row.tags or [],
                    content=row.content,
                    metadata=row.metadata or {},
                    source_path=row.source_path,
                    source_url=row.source_url,
                    managed_by=row.managed_by or "local",
                    updated_at=row.updated_at.isoformat() if row.updated_at else None,
                    status=row.status or "pending",
                )
                for row in rows
            ]
        finally:
            session.close()

    def get_skill(self, slug: str, include_pending: bool = False) -> Optional[SkillRecord]:
        session = self._session_factory()
        try:
            query = sa.select(
                OPEN_SKILLS.c.slug,
                OPEN_SKILLS.c.name,
                OPEN_SKILLS.c.description,
                OPEN_SKILLS.c.version,
                OPEN_SKILLS.c.tags,
                OPEN_SKILLS.c.content,
                OPEN_SKILLS.c.metadata,
                OPEN_SKILLS.c.source_path,
                OPEN_SKILLS.c.source_url,
                OPEN_SKILLS.c.managed_by,
                OPEN_SKILLS.c.updated_at,
                OPEN_SKILLS.c.status,
            ).where(OPEN_SKILLS.c.slug == slug)
            if not include_pending:
                query = query.where(OPEN_SKILLS.c.status == "approved")
            row = session.execute(query).one_or_none()
            if not row:
                return None
            return SkillRecord(
                slug=row.slug,
                    name=row.name,
                    description=row.description,
                    version=row.version,
                    tags=row.tags or [],
                    content=row.content,
                metadata=row.metadata or {},
                source_path=row.source_path,
                source_url=row.source_url,
                managed_by=row.managed_by or "local",
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
                status=row.status or "pending",
            )
        finally:
            session.close()


class MonitoringServer:
    def __init__(self, settings: Settings, mcp_server: "MCPServer"):
        self.settings = settings
        self.mcp_server = mcp_server
        self.app = FastAPI(title="AIDB MCP Monitor")
        self.app.state.mcp_server = mcp_server
        self.app.add_middleware(CacheMiddleware, redis_url=self.settings.redis_url)
        self.app.include_router(registry_api.router)
        self.app.include_router(vscode_telemetry.router)  # VSCode extension telemetry
        register_discovery_routes(self.app, self.mcp_server)
        self._server: Optional[uvicorn.Server] = None
        self._register_routes()

    def _require_api_key(self, request: Request) -> None:
        expected = self.settings.api_key
        if not expected:
            return
        header_token = request.headers.get("x-api-key")
        auth_header = request.headers.get("authorization") or ""
        bearer = auth_header.split()
        token = header_token or (bearer[1] if len(bearer) == 2 and bearer[0].lower() == "bearer" else None)
        if token != expected:
            raise HTTPException(status_code=401, detail="invalid_api_key")

    def _register_routes(self) -> None:
        @self.app.get("/health")
        async def health() -> Dict[str, Any]:
            return await self.mcp_server.health_status()

        @self.app.get("/health/fast")
        async def health_fast() -> Dict[str, Any]:
            return await self.mcp_server.health_status_fast()

        @self.app.get("/api/v1/health")
        async def api_health() -> Dict[str, Any]:
            return await self.mcp_server.health_status()

        @self.app.get("/readyz")
        async def ready() -> Dict[str, Any]:
            status = await self.mcp_server.health_status()
            if status.get("status") != "ok":
                raise HTTPException(status_code=503, detail=status)
            return status

        @self.app.get("/metrics")
        async def metrics() -> Response:
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

        @self.app.get("/telemetry/summary")
        async def telemetry_summary() -> Dict[str, Any]:
            return await self.mcp_server.telemetry_summary()

        @self.app.post("/telemetry/probe")
        async def telemetry_probe(payload: Dict[str, Any]) -> Dict[str, Any]:
            prompt = payload.get("prompt", "Telemetry probe: confirm local LLM route.")
            start = time.time()
            response = await self.mcp_server._llama_cpp_client.post(
                "/v1/chat/completions",
                json={
                    "model": payload.get("model", "local-telemetry-probe"),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": payload.get("max_tokens", 64),
                    "temperature": payload.get("temperature", 0.2),
                },
            )
            response.raise_for_status()
            latency_ms = int((time.time() - start) * 1000)
            await self.mcp_server.record_telemetry(
                event_type="telemetry_probe",
                source="aidb",
                llm_used="local",
                model=payload.get("model", "local-telemetry-probe"),
                latency_ms=latency_ms,
                metadata={"prompt_chars": len(prompt)},
            )
            return {
                "status": "ok",
                "latency_ms": latency_ms,
                "response": response.json(),
            }

        @self.app.get("/skills")
        async def list_skills(include_pending: bool = False) -> List[Dict[str, Any]]:
            skills = await self.mcp_server.list_skills(include_pending=include_pending)
            await self.mcp_server.record_telemetry(
                event_type="skills_list",
                source="aidb",
                metadata={"include_pending": include_pending, "count": len(skills)},
            )
            return [skill.model_dump() for skill in skills]

        @self.app.get("/skills/discover")
        async def discover_skills(repo: str = "numman-ali/openskills", path: str = "skills", branch: str = "main", limit: int = 25) -> Dict[str, Any]:
            skills = await self.mcp_server.discover_remote_skills(repo, path, branch, limit)
            return {"repo": repo, "branch": branch, "path": path, "skills": skills}

        @self.app.get("/skills/{slug}")
        async def get_skill(slug: str, include_pending: bool = False) -> Dict[str, Any]:
            skill = await self.mcp_server.get_skill(slug, include_pending=include_pending)
            if not skill:
                raise HTTPException(status_code=404, detail={"error": "skill_not_found"})
            await self.mcp_server.record_telemetry(
                event_type="skill_get",
                source="aidb",
                metadata={"slug": slug, "include_pending": include_pending},
            )
            return skill.model_dump()

        @self.app.post("/skills/import")
        async def import_skill(payload: SkillImportRequest, request: Request) -> Dict[str, Any]:
            self._require_api_key(request)
            self.mcp_server.check_rate_limit(request)
            try:
                self.mcp_server.validate_skill_import(payload)
                record = await self.mcp_server.import_skill(payload)
            except ValueError as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=str(exc))
            await self.mcp_server.record_telemetry(
                event_type="skill_import",
                source="aidb",
                metadata={"slug": payload.slug, "source": payload.source_url},
            )
            return record.model_dump()

        @self.app.get("/tools")
        async def list_tools(mode: Optional[str] = None, request: Request = None) -> Dict[str, Any]:
            """List available tools from the tool registry."""
            requested_mode = mode or self.settings.default_tool_mode
            if requested_mode not in {"minimal", "full"}:
                raise HTTPException(status_code=400, detail="mode must be 'minimal' or 'full'")
            if (
                requested_mode == "full"
                and self.settings.full_tool_disclosure_requires_key
            ):
                self._require_api_key(request)
            try:
                tools = await self.mcp_server._tool_registry.get_tools(requested_mode)
                await self.mcp_server.record_telemetry(
                    event_type="tools_list",
                    source="aidb",
                    metadata={"mode": requested_mode, "count": len(tools)},
                )
                return {
                    "tools": [tool.model_dump() for tool in tools],
                    "count": len(tools),
                    "mode": requested_mode
                }
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=500, detail=f"Failed to retrieve tools: {str(exc)}")

        @self.app.post("/tools/execute")
        async def execute_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
            """Execute a supported tool (currently limited to curated integrations)."""
            tool_name = payload.get("tool_name")
            parameters = payload.get("parameters") or {}
            if not tool_name:
                raise HTTPException(status_code=400, detail="tool_name is required")
            try:
                result = await self.mcp_server.execute_tool(tool_name, parameters)
                await self.mcp_server.record_telemetry(
                    event_type="tool_execute",
                    source="aidb",
                    metadata={"tool_name": tool_name},
                )
                return result
            except PermissionError as exc:  # configuration / auth errors
                raise HTTPException(status_code=403, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=502, detail=f"Tool execution failed: {exc}")

        @self.app.get("/documents")
        async def list_documents(
            project: Optional[str] = None,
            limit: int = 100,
            include_content: bool = False,
            include_pending: bool = False,
        ) -> Dict[str, Any]:
            """List imported documents, optionally filtered by project."""
            columns = [
                IMPORTED_DOCUMENTS.c.id,
                IMPORTED_DOCUMENTS.c.project,
                IMPORTED_DOCUMENTS.c.relative_path,
                IMPORTED_DOCUMENTS.c.title,
                IMPORTED_DOCUMENTS.c.content_type,
                IMPORTED_DOCUMENTS.c.size_bytes,
                IMPORTED_DOCUMENTS.c.imported_at,
                IMPORTED_DOCUMENTS.c.status,
            ]
            if include_content:
                columns.append(IMPORTED_DOCUMENTS.c.content)

            query = sa.select(*columns).order_by(IMPORTED_DOCUMENTS.c.imported_at.desc()).limit(limit)

            if project:
                query = query.where(IMPORTED_DOCUMENTS.c.project == project)
            if not include_pending:
                query = query.where(IMPORTED_DOCUMENTS.c.status == "approved")

            def _fetch():
                with self.mcp_server._engine.connect() as conn:
                    result = conn.execute(query)
                    return [
                        {
                            "id": row.id,
                            "project": row.project,
                            "relative_path": row.relative_path,
                            "title": row.title,
                            "content_type": row.content_type,
                            "size_bytes": row.size_bytes,
                            "imported_at": row.imported_at.isoformat() if row.imported_at else None,
                            "status": row.status,
                            **({"content": row.content} if include_content else {}),
                        }
                        for row in result
                    ]

            documents = await asyncio.to_thread(_fetch)
            await self.mcp_server.record_telemetry(
                event_type="documents_list",
                source="aidb",
                metadata={"project": project, "count": len(documents), "include_content": include_content},
            )
            return {"documents": documents, "total": len(documents), "project": project}

        @self.app.post("/documents")
        async def import_document(doc: Dict[str, Any], request: Request) -> Dict[str, Any]:
            self._require_api_key(request)
            self.mcp_server.check_rate_limit(request)
            try:
                self.mcp_server.validate_document(doc)
            except ValueError as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=str(exc))
            """Import a single document into the database."""
            def _insert():
                stmt = insert(IMPORTED_DOCUMENTS).values(
                    project=doc.get("project", "default"),
                    relative_path=doc.get("relative_path", ""),
                    title=doc.get("title", doc.get("relative_path", "Untitled")),
                    content_type=doc.get("content_type", "text/plain"),
                    checksum=doc.get("checksum", ""),
                    size_bytes=len(doc.get("content", "")),
                    modified_at=sa.func.now(),
                    content=doc.get("content", ""),
                    status=doc.get("status", "approved"),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["project", "relative_path"],
                    set_={"content": stmt.excluded.content, "modified_at": sa.func.now()},
                )
                with self.mcp_server._engine.begin() as conn:
                    conn.execute(stmt)

            await asyncio.to_thread(_insert)
            await self.mcp_server.record_telemetry(
                event_type="document_import",
                source="aidb",
                metadata={"project": doc.get("project", "default"), "title": doc.get("title")},
            )
            return {"status": "ok", "message": "Document imported successfully"}

        @self.app.post("/vector/embed")
        async def embed_text(payload: Dict[str, Any]) -> Dict[str, Any]:
            texts = payload.get("texts") or []
            if not texts:
                raise HTTPException(status_code=400, detail="texts required")
            try:
                embeddings = await self.mcp_server.embed_texts(texts)
                return {
                    "model": self.settings.embedding_model,
                    "dimension": self.settings.embedding_dimension,
                    "embeddings": embeddings,
                }
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Embedding generation failed")
                raise HTTPException(status_code=500, detail=str(exc))

        @self.app.post("/vector/index")
        async def index_vectors(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
            self._require_api_key(request)
            self.mcp_server.check_rate_limit(request)
            items = payload.get("items")
            if not items:
                raise HTTPException(status_code=400, detail="items required")
            try:
                count = await self.mcp_server.index_embeddings(items)
            except ValueError as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=str(exc))
            return {"status": "ok", "indexed": count}

        @self.app.post("/vector/search")
        async def vector_search(payload: Dict[str, Any]) -> Dict[str, Any]:
            query_text = payload.get("query")
            embedding = payload.get("embedding")
            limit = int(payload.get("limit", 5))
            if not query_text and not embedding:
                raise HTTPException(status_code=400, detail="query or embedding required")
            try:
                results = await self.mcp_server.search_vectors(
                    query_text=query_text,
                    embedding=embedding,
                    limit=limit,
                    project=payload.get("project"),
                )
            except ValueError as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Vector search failed")
                raise HTTPException(status_code=500, detail=str(exc))
            return {"results": results, "limit": limit}

        # ML endpoints
        @self.app.get("/ml/models")
        async def list_ml_models() -> Dict[str, Any]:
            """List all trained ML models."""
            if not self.mcp_server._ml_engine:
                raise HTTPException(status_code=503, detail="ML Engine not available")
            models = await self.mcp_server._ml_engine.list_models()
            return {"models": models}

        @self.app.get("/ml/models/{model_name}")
        async def get_ml_model_metrics(model_name: str) -> Dict[str, Any]:
            """Get metrics for a specific ML model."""
            if not self.mcp_server._ml_engine:
                raise HTTPException(status_code=503, detail="ML Engine not available")
            try:
                metrics = await self.mcp_server._ml_engine.get_model_metrics(model_name)
                return metrics
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.app.post("/ml/models/train")
        async def train_ml_model(request: Dict[str, Any]) -> Dict[str, Any]:
            """Train a new ML model (forecast or anomaly detection)."""
            if not self.mcp_server._ml_engine:
                raise HTTPException(status_code=503, detail="ML Engine not available")

            model_type = request.get("model_type")
            model_name = request.get("model_name")

            if not model_type or not model_name:
                raise HTTPException(status_code=400, detail="model_type and model_name required")

            try:
                if model_type == "forecast":
                    result = await self.mcp_server._ml_engine.train_forecast_model(
                        model_name=model_name,
                        table_name=request.get("table_name", "market_data"),
                        target_column=request.get("target_column", "close"),
                        feature_columns=request.get("feature_columns", ["open", "high", "low", "volume"]),
                        lookback_hours=request.get("lookback_hours", 24),
                        forecast_horizon=request.get("forecast_horizon", 1),
                    )
                elif model_type == "anomaly_detection":
                    result = await self.mcp_server._ml_engine.train_anomaly_detector(
                        model_name=model_name,
                        table_name=request.get("table_name", "rf_signals"),
                        feature_columns=request.get("feature_columns", ["frequency", "power_dbm"]),
                        contamination=request.get("contamination", 0.1),
                    )
                else:
                    raise HTTPException(status_code=400, detail=f"Unknown model_type: {model_type}")

                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/ml/predict")
        async def ml_predict(request: Dict[str, Any]) -> Dict[str, Any]:
            """Make predictions using a trained ML model."""
            if not self.mcp_server._ml_engine:
                raise HTTPException(status_code=503, detail="ML Engine not available")

            model_name = request.get("model_name")
            input_data = request.get("input_data")

            if not model_name or not input_data:
                raise HTTPException(status_code=400, detail="model_name and input_data required")

            try:
                result = await self.mcp_server._ml_engine.predict(model_name, input_data)
                return result
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        # Deprecated /vllm endpoints: respond with 410 and redirect callers to llama.cpp.
        def _vllm_gone() -> None:
            raise HTTPException(
                status_code=410,
                detail="/vllm endpoints removed; use llama.cpp (/chat/completions) via LLAMA_CPP_BASE_URL",
            )

        @self.app.get("/vllm/health")
        async def vllm_health() -> Dict[str, Any]:
            _vllm_gone()

        @self.app.get("/vllm/models")
        async def vllm_models() -> Dict[str, Any]:
            _vllm_gone()

        @self.app.post("/vllm/generate")
        async def vllm_generate(request: Dict[str, Any]) -> Dict[str, Any]:
            _vllm_gone()

        @self.app.post("/vllm/chat")
        async def vllm_chat(request: Dict[str, Any]) -> Dict[str, Any]:
            _vllm_gone()

        @self.app.post("/vllm/nix")
        async def vllm_nix_generate(request: Dict[str, Any]) -> Dict[str, Any]:
            _vllm_gone()

        @self.app.post("/vllm/explain")
        async def vllm_explain_code(request: Dict[str, Any]) -> Dict[str, Any]:
            _vllm_gone()

        @self.app.post("/vllm/review")
        async def vllm_review_code(request: Dict[str, Any]) -> Dict[str, Any]:
            _vllm_gone()

        @self.app.post("/vllm/tests")
        async def vllm_generate_tests(request: Dict[str, Any]) -> Dict[str, Any]:
            _vllm_gone()

        @self.app.post("/vllm/refactor")
        async def vllm_refactor_code(request: Dict[str, Any]) -> Dict[str, Any]:
            _vllm_gone()

        # Federation compatibility endpoints (documented for AIDB API)
        @self.app.get("/api/v1/federation/servers")
        async def list_federated_servers() -> Dict[str, Any]:
            servers = await self.mcp_server.list_federated_servers()
            return {"servers": servers, "total": len(servers)}

        @self.app.post("/api/v1/federation/servers")
        async def register_federated_server(server: Dict[str, Any], request: Request) -> Dict[str, Any]:
            self._require_api_key(request)
            self.mcp_server.check_rate_limit(request)
            try:
                record = await self.mcp_server.register_federated_server(server)
            except ValueError as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=str(exc))
            return record

        @self.app.post("/api/v1/federation/spider/crawl")
        async def crawl_federation(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
            self._require_api_key(request)
            self.mcp_server.check_rate_limit(request)
            result = await self.mcp_server.crawl_federation(payload)
            return result

        @self.app.post("/api/v1/admin/approve")
        async def approve_resource(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
            self._require_api_key(request)
            resource = payload.get("resource")
            identifier = payload.get("id") or payload.get("slug")
            status = payload.get("status", "approved")
            try:
                updated = await self.mcp_server.approve_resource(resource, identifier, status)
            except ValueError as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=str(exc))
            return {"status": "ok", "updated": updated}

    async def start(self) -> None:
        config = uvicorn.Config(
            self.app,
            host=self.settings.server_host,
            port=self.settings.api_port,
            log_level="info",
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self) -> None:
        if self._server:
            self._server.should_exit = True


class MCPServer:
    def __init__(self, settings: Settings):
        self.settings = settings

        # Create database engine with retry logic
        def _create_engine():
            engine = sa.create_engine(self.settings.postgres_dsn, future=True)
            # Test connection immediately
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
            LOGGER.info("Database connection established")
            return engine

        self._engine = retry_with_backoff(
            _create_engine,
            max_retries=5,
            base_delay=2.0,
            exceptions=(sa.exc.OperationalError, Exception),
            operation_name="Database connection"
        )

        # Create Redis connection (will be tested on first use)
        self._redis = redis_asyncio.Redis.from_url(self.settings.redis_url)
        LOGGER.info("Redis client created")

        self._tool_registry = ToolRegistry(settings, self._engine, self._redis)
        self._sandbox = SandboxExecutor(settings)
        self._external_http = httpx.AsyncClient(timeout=20.0)
        self._monitoring = MonitoringServer(settings, self)
        self._catalog = CatalogBootstrapper(settings, self._engine)
        self._skills = OpenSkillsRepository(self._engine)
        self._repo_root = Path(__file__).resolve().parents[1]
        self._server_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._embedding_service = EmbeddingService(settings.embedding_model)
        self._vector_store = VectorStore(settings, self._engine)
        self._rate_limiter = RateLimiter(
            enabled=self.settings.rate_limit_enabled,
            rpm=self.settings.rate_limit_rpm,
        )
        self._federation = FederationStore(
            storage_path=self._repo_root / "data" / "federation" / "servers.json",
            sources_dir=self._repo_root / "data" / "mcp_sources",
        )

        # ML Engine integration
        try:
            self._ml_engine = MLEngine(self._engine)
            LOGGER.info("ML Engine initialized successfully")
        except Exception as e:
            LOGGER.warning(f"ML Engine initialization failed: {e}")
            self._ml_engine = None

        # llama.cpp client (OpenAI-compatible API)
        self._llama_cpp_client = httpx.AsyncClient(
            base_url=settings.llama_cpp_url, timeout=120.0
        )
        LOGGER.info(f"llama.cpp client configured for {settings.llama_cpp_url}")
        self._telemetry_path = Path(self.settings.telemetry_path)
        self._telemetry_enabled = self.settings.telemetry_enabled

        # Circuit breakers for external services
        self._circuit_breakers = {
            "embeddings": CircuitBreaker(
                name="embeddings-service",
                failure_threshold=5,
                recovery_timeout=60.0,
                expected_exception=(httpx.HTTPError, httpx.TimeoutException, ConnectionError)
            ),
            "qdrant": CircuitBreaker(
                name="qdrant-vector-db",
                failure_threshold=5,
                recovery_timeout=60.0,
                expected_exception=(httpx.HTTPError, httpx.TimeoutException, ConnectionError)
            ),
            "llama_cpp": CircuitBreaker(
                name="llama-cpp-inference",
                failure_threshold=3,  # Lower threshold for LLM (expensive)
                recovery_timeout=120.0,  # Longer recovery for model loading
                expected_exception=(httpx.HTTPError, httpx.TimeoutException, ConnectionError)
            ),
        }
        LOGGER.info("Circuit breakers initialized for external services")

    def _require_api_key(self, request: Request) -> None:
        expected = self.settings.api_key
        if not expected:
            return
        header_token = request.headers.get("x-api-key")
        auth_header = request.headers.get("authorization") or ""
        bearer = auth_header.split()
        token = header_token or (bearer[1] if len(bearer) == 2 and bearer[0].lower() == "bearer" else None)
        if token != expected:
            raise HTTPException(status_code=401, detail="invalid_api_key")

    async def record_telemetry(
        self,
        event_type: str,
        source: str,
        llm_used: Optional[str] = None,
        tokens_saved: int = 0,
        rag_hits: int = 0,
        collections_used: Optional[List[str]] = None,
        model: Optional[str] = None,
        latency_ms: Optional[int] = None,
        cache_hit: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._telemetry_enabled:
            return

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "event_type": event_type,
            "llm_used": llm_used,
            "tokens_saved": tokens_saved,
            "rag_hits": rag_hits,
            "collections_used": collections_used or [],
            "model": model,
            "latency_ms": latency_ms,
            "cache_hit": cache_hit,
            "metadata": metadata or {},
        }

        def _write_jsonl() -> None:
            self._telemetry_path.parent.mkdir(parents=True, exist_ok=True)
            with self._telemetry_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event) + "\n")

        def _insert_db() -> None:
            with self._engine.begin() as conn:
                conn.execute(
                    insert(TELEMETRY_EVENTS).values(
                        source=event["source"],
                        event_type=event["event_type"],
                        llm_used=event["llm_used"],
                        tokens_saved=event["tokens_saved"],
                        rag_hits=event["rag_hits"],
                        collections_used=event["collections_used"],
                        model=event["model"],
                        latency_ms=event["latency_ms"],
                        cache_hit=event["cache_hit"],
                        metadata=event["metadata"],
                    )
                )

        await asyncio.to_thread(_write_jsonl)
        await asyncio.to_thread(_insert_db)

    async def telemetry_summary(self) -> Dict[str, Any]:
        def _query() -> Dict[str, Any]:
            with self._engine.connect() as conn:
                total = conn.execute(sa.text("SELECT COUNT(*) FROM telemetry_events")).scalar() or 0
                local = conn.execute(
                    sa.text("SELECT COUNT(*) FROM telemetry_events WHERE llm_used = 'local'")
                ).scalar() or 0
                remote = conn.execute(
                    sa.text("SELECT COUNT(*) FROM telemetry_events WHERE llm_used = 'remote'")
                ).scalar() or 0
                tokens_saved = conn.execute(
                    sa.text("SELECT COALESCE(SUM(tokens_saved), 0) FROM telemetry_events")
                ).scalar() or 0
                last_event = conn.execute(
                    sa.text("SELECT MAX(created_at) FROM telemetry_events")
                ).scalar()
            return {
                "total_events": int(total),
                "local_events": int(local),
                "remote_events": int(remote),
                "tokens_saved": int(tokens_saved),
                "last_event_at": last_event.isoformat() if last_event else None,
            }

        summary = await asyncio.to_thread(_query)
        summary["telemetry_path"] = str(self._telemetry_path)
        summary["enabled"] = self._telemetry_enabled
        if summary["total_events"] > 0:
            summary["local_usage_rate"] = summary["local_events"] / summary["total_events"]
        else:
            summary["local_usage_rate"] = 0.0
        return summary

    async def _ingest_points_of_interest(self) -> None:
        LOGGER.info("Ingesting points of interest...")
        COMMUNITIES = [
            {"category": "Core Model & Provider Hubs", "name": "/r/OpenAI", "description": "For official news and high-level discussion.", "url": "https://www.reddit.com/r/OpenAI", "source": "Gemini CLI conversation"},
            {"category": "Core Model & Provider Hubs", "name": "/r/ChatGPT", "description": "The largest community for general use, creative prompting, and API usage.", "url": "https://www.reddit.com/r/ChatGPT", "source": "Gemini CLI conversation"},
            {"category": "Core Model & Provider Hubs", "name": "/r/GPT_Programming", "description": "Developer-focused subreddit for using GPT models in coding workflows.", "url": "https://www.reddit.com/r/GPT_Programming", "source": "Gemini CLI conversation"},
            {"category": "Core Model & Provider Hubs", "name": "/r/ChatGPTCoding", "description": "Developer-focused subreddit for using GPT models in coding workflows.", "url": "https://www.reddit.com/r/ChatGPTCoding", "source": "Gemini CLI conversation"},
            {"category": "Core Model & Provider Hubs", "name": "/r/Claude", "description": "The central hub for everything related to Claude models, from advanced prompting techniques to tool development.", "url": "https://www.reddit.com/r/Claude", "source": "Gemini CLI conversation"},
            {"category": "Core Model & Provider Hubs", "name": "/r/GoogleGemini", "description": "The primary community for developers and users working with the Gemini family of models.", "url": "https://www.reddit.com/r/GoogleGemini", "source": "Gemini CLI conversation"},
            {"category": "Core Model & Provider Hubs", "name": "/r/deepmind", "description": "For discussions on the cutting-edge research that powers Google's AI.", "url": "https://www.reddit.com/r/deepmind", "source": "Gemini CLI conversation"},
            {"category": "Open-Source & Alternative Models", "name": "/r/Deepseek", "description": "The dedicated community for DeepSeek models.", "url": "https://www.reddit.com/r/Deepseek", "source": "Gemini CLI conversation"},
            {"category": "Open-Source & Alternative Models", "name": "/r/MistralAI", "description": "For discussions around Mistral's influential open-source models.", "url": "https://www.reddit.com/r/MistralAI", "source": "Gemini CLI conversation"},
            {"category": "Open-Source & Alternative Models", "name": "/r/Llama_2", "description": "Focused on Meta's Llama models and fine-tuning.", "url": "https://www.reddit.com/r/Llama_2", "source": "Gemini CLI conversation"},
            {"category": "Local AI & Self-Hosting", "name": "/r/LocalLLaMA", "description": "The definitive and most active community for running LLMs locally. Essential for hardware advice, setup guides (for tools like Ollama), and performance benchmarks.", "url": "https://www.reddit.com/r/LocalLLaMA", "source": "Gemini CLI conversation"},
            {"category": "Local AI & Self-Hosting", "name": "/r/Ollama", "description": "The official community for the Ollama platform, which has made running open-source models incredibly accessible.", "url": "https://www.reddit.com/r/Ollama", "source": "Gemini CLI conversation"},
            {"category": "Local AI & Self-Hosting", "name": "/r/selfhosted", "description": "A broad but invaluable resource for the infrastructure side—discussing the servers, networking, and security practices needed to host your own AI tools.", "url": "https://www.reddit.com/r/selfhosted", "source": "Gemini CLI conversation"},
            {"category": "AI Agent & Framework Development", "name": "/r/AI_Agents", "description": "Focused subreddit for the theory and practice of building AI agents.", "url": "https://www.reddit.com/r/AI_Agents", "source": "Gemini CLI conversation"},
            {"category": "AI Agent & Framework Development", "name": "/r/AgenticAI", "description": "Focused subreddit for the theory and practice of building AI agents.", "url": "https://www.reddit.com/r/AgenticAI", "source": "Gemini CLI conversation"},
            {"category": "AI Agent & Framework Development", "name": "/r/LangChain", "description": "The main hub for the LangChain framework, essential for anyone building applications that require chaining LLM calls or giving agents access to tools.", "url": "https://www.reddit.com/r/LangChain", "source": "Gemini CLI conversation"},
            {"category": "AI Agent & Framework Development", "name": "/r/AutoGenAI", "description": "The community for Microsoft's AutoGen, a powerful framework for creating multi-agent conversational systems.", "url": "https://www.reddit.com/r/AutoGenAI", "source": "Gemini CLI conversation"},
            {"category": "AI-Enhanced Development", "name": "/r/commandline", "description": "For discovering new AI-powered CLI tools and shell integrations.", "url": "https://www.reddit.com/r/commandline", "source": "Gemini CLI conversation"},
            {"category": "AI-Enhanced Development", "name": "/r/devcontainers", "description": "A community focused on developing inside Docker containers, a core technology for reproducible and collaborative development environments (CED).", "url": "https://www.reddit.com/r/devcontainers", "source": "Gemini CLI conversation"},
            {"category": "AI-Enhanced Development", "name": "/r/neovim", "description": "The main community for this editor, where you'll find extensive discussions on integrating AI for code completion, chat, and custom tooling.", "url": "https://www.reddit.com/r/neovim", "source": "Gemini CLI conversation"},
            {"category": "AI-Enhanced Development", "name": "/r/vscode", "description": "The main community for this editor, where you'll find extensive discussions on integrating AI for code completion, chat, and custom tooling.", "url": "https://www.reddit.com/r/vscode", "source": "Gemini CLI conversation"},
        ]
        
        points_of_interest_table = METADATA.tables.get("points_of_interest")
        if points_of_interest_table is None:
            LOGGER.warning("Could not find 'points_of_interest' table. Skipping ingestion.")
            return

        def _insert():
            with self._engine.connect() as connection:
                stmt = insert(points_of_interest_table).values(COMMUNITIES)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=['name', 'category']
                )
                result = connection.execute(stmt)
                connection.commit()
                LOGGER.info(f"Inserted {result.rowcount} new points of interest.")

        await asyncio.to_thread(_insert)

    async def startup(self) -> None:
        LOGGER.info("Starting MCP server")
        await asyncio.to_thread(self._ensure_pgvector_extension)
        METADATA.create_all(self._engine)
        await self._ingest_points_of_interest()
        await self._tool_registry.warm_cache()
        await asyncio.to_thread(self._catalog.sync_catalog)

    def _ensure_pgvector_extension(self) -> None:
        try:
            with self._engine.begin() as conn:
                conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
            LOGGER.info("pgvector extension ensured")
        except Exception:  # noqa: BLE001
            LOGGER.exception("Failed to ensure pgvector extension")
            raise

    async def shutdown(self) -> None:
        LOGGER.info("Stopping MCP server")
        await self._tool_registry.persist_cache()
        await self._redis.close()
        await self._external_http.aclose()
        await self._llama_cpp_client.aclose()
        self._engine.dispose()

    async def health_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {"status": "ok"}
        try:
            def _check_db() -> None:
                with self._engine.connect() as conn:
                    conn.execute(sa.text("SELECT 1"))

            await asyncio.to_thread(_check_db)
            status["database"] = "ok"
        except Exception as exc:  # noqa: BLE001
            status["status"] = "error"
            status["database"] = str(exc)
        try:
            await self._redis.ping()
            status["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            status["status"] = "error"
            status["redis"] = str(exc)

        # ML Engine status
        if self._ml_engine:
            status["ml_engine"] = "ok"
        else:
            status["ml_engine"] = "disabled"

        # pgvector status
        try:
            def _check_vector() -> bool:
                with self._engine.connect() as conn:
                    result = conn.execute(
                        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                    ).scalar()
                    return bool(result)

            vector_enabled = await asyncio.to_thread(_check_vector)
            status["pgvector"] = "ok" if vector_enabled else "missing"
        except Exception as exc:  # noqa: BLE001
            status["pgvector"] = f"unavailable: {exc}"

        # llama.cpp status
        try:
            # Health endpoint is at root, not under /api/v1
            health_url = self.settings.llama_cpp_url.replace("/api/v1", "") + "/health"
            response = await self._external_http.get(health_url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                loaded = data.get("model_loaded") or data.get("checkpoint_loaded")
                status["llama_cpp"] = (
                    f"ok (model: {loaded})" if loaded else "ok (no model loaded)"
                )
            else:
                status["llama_cpp"] = f"error: HTTP {response.status_code}"
        except Exception as exc:  # noqa: BLE001
            status["llama_cpp"] = f"unavailable: {exc}"

        try:
            servers = await self._federation.list_servers()
            status["federation"] = f"{len(servers)} servers cached"
        except Exception as exc:  # noqa: BLE001
            status["federation"] = f"unavailable: {exc}"

        # Circuit breaker states
        status["circuit_breakers"] = {
            name: breaker.state
            for name, breaker in self._circuit_breakers.items()
        }

        return status

    async def health_status_fast(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {"status": "ok"}
        try:
            def _check_db() -> None:
                with self._engine.connect() as conn:
                    conn.execute(sa.text("SELECT 1"))

            await asyncio.to_thread(_check_db)
            status["database"] = "ok"
        except Exception as exc:  # noqa: BLE001
            status["status"] = "error"
            status["database"] = str(exc)

        try:
            await self._redis.ping()
            status["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            status["status"] = "error"
            status["redis"] = str(exc)

        return status

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return await self._embedding_service.embed(texts)

    def _get_document_content(self, document_id: int) -> str:
        with self._engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT content FROM imported_documents WHERE id = :doc_id"),
                {"doc_id": document_id},
            ).one_or_none()
            if not row:
                raise ValueError(f"Document {document_id} not found")
            return row.content

    async def index_embeddings(self, items: List[Dict[str, Any]]) -> int:
        prepared: List[Dict[str, Any]] = []
        for item in items:
            document_id = item.get("document_id")
            if not document_id:
                raise ValueError("document_id is required for indexing")
            content = item.get("content") or self._get_document_content(document_id)
            embedding = item.get("embedding")
            if embedding is None:
                embedding = (await self.embed_texts([content]))[0]
            prepared.append(
                {
                    "document_id": document_id,
                    "chunk_id": item.get("chunk_id"),
                    "content": content,
                    "embedding": embedding,
                    "metadata": item.get("metadata") or {},
                    "score": item.get("score"),
                }
            )

        return await asyncio.to_thread(self._vector_store.index_embeddings, prepared)

    async def search_vectors(
        self,
        *,
        query_text: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        limit: int = 5,
        project: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query_embedding = embedding
        if query_embedding is None:
            if not query_text:
                raise ValueError("Either query_text or embedding must be provided")
            query_embedding = (await self.embed_texts([query_text]))[0]
        results = await asyncio.to_thread(self._vector_store.search, query_embedding, limit, project)
        return results

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch execution to supported tools."""
        normalized = (tool_name or "").strip().lower()
        if not normalized:
            raise ValueError("tool_name must be provided")

        if "google" in normalized and "search" in normalized:
            payload = await self._execute_google_websearch(tool_name, parameters)
            return {"tool": tool_name, **payload}

        raise ValueError(f"Tool '{tool_name}' is not yet supported for execution")

    async def _execute_google_websearch(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Google Custom Search query."""
        api_key = self.settings.google_api_key or os.environ.get("GOOGLE_SEARCH_API_KEY")
        cse_id = self.settings.google_cse_id or os.environ.get("GOOGLE_SEARCH_CX")
        if not api_key or not cse_id:
            raise PermissionError(
                "Google Custom Search credentials are not configured. "
                "Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX in the environment."
            )

        query = parameters.get("query") or parameters.get("q")
        if not query:
            raise ValueError("Google websearch requires a 'query' parameter")

        try:
            num = int(parameters.get("limit") or parameters.get("num") or 5)
        except (TypeError, ValueError):
            num = 5
        num = max(1, min(num, 10))

        try:
            start = int(parameters.get("start") or 1)
        except (TypeError, ValueError):
            start = 1
        start = max(1, start)

        request_params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": num,
            "start": start,
        }

        safe = parameters.get("safe")
        if safe:
            request_params["safe"] = safe
        gl = parameters.get("gl") or parameters.get("country")
        if gl:
            request_params["gl"] = gl
        lr = parameters.get("lr") or parameters.get("language")
        if lr:
            request_params["lr"] = lr

        response = await self._external_http.get(
            "https://www.googleapis.com/customsearch/v1",
            params=request_params,
            timeout=20.0,
        )

        try:
            data = response.json()
        except ValueError:
            raise ValueError("Google search returned an unexpected response")

        if response.status_code != 200:
            message = data.get("error", {}).get("message") or response.text
            raise ValueError(f"Google search failed: {message}")

        items = []
        for item in data.get("items", []):
            pagemap = item.get("pagemap") or {}
            thumbnails = pagemap.get("cse_thumbnail") or pagemap.get("thumbnail") or []
            first_thumb = thumbnails[0] if thumbnails else {}
            items.append(
                {
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "display_link": item.get("displayLink"),
                    "snippet": item.get("snippet"),
                    "mime": item.get("mime"),
                    "thumbnail": first_thumb.get("src"),
                }
            )

        search_info = data.get("searchInformation", {})
        try:
            total_results = int(search_info.get("totalResults", 0))
        except (TypeError, ValueError):
            total_results = 0
        return {
            "query": query,
            "limit": num,
            "start": start,
            "total_results": total_results,
            "search_time": search_info.get("searchTime"),
            "results": items,
        }

    async def list_federated_servers(self) -> List[Dict[str, Any]]:
        return await self._federation.list_servers()

    async def register_federated_server(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._federation.upsert(payload)

    async def crawl_federation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        max_pages = int(payload.get("max_pages", 120))
        discovered = await asyncio.to_thread(self._federation.discover_local_sources, max_pages)

        registered: List[Dict[str, Any]] = []
        for url in discovered:
            try:
                record = await self.register_federated_server(
                    {
                        "server_url": url,
                        "name": urlparse(url).netloc or url,
                        "tags": ["mcp", "discovered"],
                        "capabilities": {
                            "source": "curated",
                            "content": "imported from local mcp_sources",
                        },
                        "priority": payload.get("priority", 5),
                    }
                )
                registered.append(record)
            except ValueError:
                continue

        return {
            "status": "ok",
            "discovered": len(discovered),
            "registered": len(registered),
            "sample": registered[:5],
        }

    async def approve_resource(self, resource: str, identifier: Any, status: str = "approved") -> int:
        if resource not in {"skill", "skills", "document", "documents"}:
            raise ValueError("resource must be one of: skill, skills, document, documents")
        if status not in {"approved", "pending", "rejected"}:
            raise ValueError("status must be approved|pending|rejected")
        target = OPEN_SKILLS if resource.startswith("skill") else IMPORTED_DOCUMENTS
        column = target.c.slug if resource.startswith("skill") else target.c.id
        if identifier is None:
            raise ValueError("identifier required")

        def _update() -> int:
            with self._engine.begin() as conn:
                result = conn.execute(
                    sa.update(target).where(column == identifier).values(status=status)
                )
                return result.rowcount

        updated = await asyncio.to_thread(_update)
        if updated == 0:
            raise ValueError("resource not found")
        return updated

    def check_rate_limit(self, request: Request) -> None:
        client_id = request.headers.get("x-api-key") or request.client.host
        try:
            self._rate_limiter.check(client_id)
        except PermissionError as exc:
            raise HTTPException(status_code=429, detail=str(exc))

    async def parallel_generate(self, prompt: str, max_tokens: int = 256) -> Dict[str, Any]:
        if not self.settings.parallel_processing_enabled:
            raise HTTPException(status_code=400, detail="Parallel processing disabled in config")
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "simple_model": self.settings.parallel_simple_model,
            "complex_model": self.settings.parallel_complex_model,
        }
        start = time.time()
        responses = await run_parallel_inference(
            client=self._llama_cpp_client,
            prompt=prompt,
            simple_model=self.settings.parallel_simple_model,
            complex_model=self.settings.parallel_complex_model,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.time() - start) * 1000)
        await self.record_telemetry(
            event_type="parallel_generate",
            source="aidb",
            llm_used="local",
            model=self.settings.parallel_complex_model,
            latency_ms=latency_ms,
            metadata={"prompt_chars": len(prompt), "max_tokens": max_tokens},
        )
        responses.update({"diversity_mode": self.settings.parallel_diversity_mode})
        return payload | responses

    async def list_skills(self, include_pending: bool = False) -> List[SkillRecord]:
        return await asyncio.to_thread(self._skills.list_skills, include_pending)

    async def get_skill(self, slug: str, include_pending: bool = False) -> Optional[SkillRecord]:
        return await asyncio.to_thread(self._skills.get_skill, slug, include_pending)

    async def _persist_skill(self, skill: ParsedSkill) -> SkillRecord:
        def _write_and_insert() -> None:
            path = write_skill_file(skill, self._repo_root)
            try:
                skill.source_path = str(path.relative_to(self._repo_root))
            except ValueError:
                skill.source_path = str(path)
            payload = {
                "slug": skill.slug,
                "name": skill.name,
                "description": skill.description,
                "version": skill.version,
                "tags": skill.tags,
                "content": skill.content,
                "metadata": skill.metadata,
                "source_path": skill.source_path,
                "source_url": skill.source_url,
                "managed_by": skill.managed_by,
                "status": "pending",
            }
            stmt = insert(OPEN_SKILLS).values(**payload)
            stmt = stmt.on_conflict_do_update(
                index_elements=[OPEN_SKILLS.c.slug],
                set_={
                    "name": stmt.excluded.name,
                    "description": stmt.excluded.description,
                    "version": stmt.excluded.version,
                    "tags": stmt.excluded.tags,
                    "content": stmt.excluded.content,
                    "metadata": stmt.excluded.metadata,
                    "source_path": stmt.excluded.source_path,
                    "source_url": stmt.excluded.source_url,
                    "managed_by": stmt.excluded.managed_by,
                },
            )
            with self._engine.begin() as conn:
                conn.execute(stmt)

        await asyncio.to_thread(_write_and_insert)
        record = await self.get_skill(skill.slug, include_pending=True)
        if not record:
            raise RuntimeError("Failed to persist skill")  # pragma: no cover
        return record

    async def import_skill(self, payload: SkillImportRequest) -> SkillRecord:
        managed_by = payload.managed_by or "agent"
        if not payload.content and not payload.url:
            raise ValueError("Either content or url must be provided")

        if payload.content:
            slug = slugify(payload.slug or payload.name or "skill")
            return await self.import_skill_from_text(
                slug=slug,
                text=payload.content,
                source_path=payload.source_path or f".agent/skills/{slug}/SKILL.md",
                source_url=payload.source_url,
                managed_by=managed_by,
            )

        parsed = urlparse(payload.url)
        path = Path(parsed.path)
        guess_slug = payload.slug or path.parent.name or path.stem or "skill"
        return await self.import_skill_from_url(
            url=payload.url,
            slug=slugify(guess_slug),
            managed_by=managed_by,
        )

    async def import_skill_from_text(
        self,
        *,
        slug: str,
        text: str,
        source_path: str,
        source_url: Optional[str],
        managed_by: str,
    ) -> SkillRecord:
        skill = parse_skill_text(
            slug=slugify(slug),
            text=text,
            source_path=source_path,
            source_url=source_url,
            managed_by=managed_by,
        )
        return await self._persist_skill(skill)

    async def import_skill_from_url(self, url: str, slug: Optional[str] = None, managed_by: str = "agent") -> SkillRecord:
        response = await self._external_http.get(url)
        response.raise_for_status()
        parsed = urlparse(url)
        path = Path(parsed.path)
        guess_slug = slug or slugify(path.parent.name or path.stem or "skill")
        return await self.import_skill_from_text(
            slug=guess_slug,
            text=response.text,
            source_path=f".agent/skills/{guess_slug}/SKILL.md",
            source_url=url,
            managed_by=managed_by,
        )

    def validate_skill_import(self, payload: SkillImportRequest) -> None:
        content = payload.content or ""
        if payload.url and not payload.url.lower().endswith(".md"):
            raise ValueError("Skill URL must point to a markdown file")
        if content and len(content) > 100_000:
            raise ValueError("Skill content exceeds 100KB limit")
        if "\0" in content:
            raise ValueError("Skill content contains binary data")

    def validate_document(self, doc: Dict[str, Any]) -> None:
        content = doc.get("content") or ""
        if not content:
            raise ValueError("content is required")
        if len(content) > 1_000_000:
            raise ValueError("content exceeds 1MB limit")
        if "\0" in content:
            raise ValueError("binary content not allowed")
        secret_patterns = [
            r"AKIA[0-9A-Z]{16}",
            r"-----BEGIN (RSA|PRIVATE) KEY-----",
            r"aws_secret_access_key",
        ]
        for pattern in secret_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise ValueError("potential secret detected; import blocked")

    async def discover_remote_skills(self, repo: str, base_path: str, branch: str, limit: int) -> List[Dict[str, Any]]:
        base_path = base_path.strip("/")
        tree_url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
        resp = await self._external_http.get(tree_url, headers={"Accept": "application/vnd.github+json"})
        resp.raise_for_status()
        data = resp.json()
        tree = data.get("tree", [])
        discoveries: List[Dict[str, Any]] = []
        for node in tree:
            if node.get("type") != "blob":
                continue
            node_path = node.get("path", "")
            if not node_path.endswith("SKILL.md"):
                continue
            if base_path and not node_path.startswith(base_path + "/"):
                continue
            slug = Path(node_path).parent.name
            download_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{node_path}"
            discoveries.append(
                {
                    "slug": slug,
                    "path": node_path,
                    "download_url": download_url,
                    "repo": repo,
                    "branch": branch,
                }
            )
            if len(discoveries) >= limit:
                break
        return discoveries

    def _authenticate(self, message: Dict[str, Any]) -> None:
        if not self.settings.api_key:
            return
        token = message.get("api_key")
        if token != self.settings.api_key:
            raise PermissionError("Invalid API key")

    def _validate_tool_disclosure(self, mode: str, api_key: Optional[str]) -> str:
        if mode not in {"minimal", "full"}:
            raise ValueError(f"Unsupported tool discovery mode {mode}")
        if (
            mode == "full"
            and self.settings.full_tool_disclosure_requires_key
            and self.settings.api_key
            and api_key != self.settings.api_key
        ):
            raise PermissionError("Full tool disclosure requires a valid API key")
        return mode

    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        self._authenticate(message)
        client_id = message.get("client_id", "default")
        self._rate_limiter.check(client_id)

        action = message.get("action")
        with REQUEST_LATENCY.labels(action=action or "unknown").time():
            if action == "discover_tools":
                mode = message.get("mode", self.settings.default_tool_mode)
                mode = self._validate_tool_disclosure(mode, message.get("api_key"))
                tools = await self._tool_registry.get_tools(mode)
                TOOL_DISCOVERY_COUNTER.labels(mode=mode).inc()
                return {"type": "tools", "tools": [tool.model_dump() for tool in tools], "mode": mode}

            if action == "run_sandboxed":
                command = message.get("command", [])
                result = await self._sandbox.run(command)
                status = "ok" if result.returncode == 0 else "error"
                SANDBOX_RUN_COUNTER.labels(status=status).inc()
                return result.model_dump()

            if action == "semantic_search":
                query = message["query"]
                results = await self.search_vectors(
                    query_text=query.get("text") or query.get("query"),
                    embedding=query.get("embedding"),
                    limit=query.get("limit", 5),
                    project=message.get("project") or query.get("project"),
                )
                return {"results": results}

            if action == "discover_skills":
                repo = message.get("repo", "numman-ali/openskills")
                base_path = message.get("path", "skills")
                branch = message.get("branch", "main")
                limit = int(message.get("limit", 25))
                skills = await self.discover_remote_skills(repo, base_path, branch, limit)
                return {"repo": repo, "branch": branch, "path": base_path, "skills": skills}

            if action == "import_skill":
                payload = {
                    "slug": message.get("slug"),
                    "url": message.get("url"),
                    "content": message.get("content"),
                    "managed_by": message.get("managed_by", "agent"),
                    "name": message.get("name"),
                    "source_path": message.get("source_path"),
                    "source_url": message.get("source_url"),
                }
                record = await self.import_skill(SkillImportRequest(**payload))
                return record.model_dump()

            if action == "list_skills":
                skills = await self.list_skills()
                return {"skills": [skill.model_dump() for skill in skills]}

            if action == "get_skill":
                slug = message.get("slug")
                if not slug:
                    raise ValueError("Missing slug for get_skill action")
                skill = await self.get_skill(slug)
                if not skill:
                    raise ValueError(f"Skill not found: {slug}")
                return skill.model_dump()

            raise ValueError(f"Unsupported action: {action}")

    async def _connection_handler(self, websocket) -> None:
        async for raw_message in websocket:
            try:
                payload = json.loads(raw_message)
                response = await self.handle_message(payload)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Failed to process message")
                response = {"error": str(exc)}
            await websocket.send(json.dumps(response))

    async def _run_websocket(self, stop_event: asyncio.Event) -> None:
        async with serve(self._connection_handler, self.settings.server_host, self.settings.server_port):
            LOGGER.info("WebSocket server listening on %s:%s", self.settings.server_host, self.settings.server_port)
            await stop_event.wait()

    async def serve(self) -> None:
        await self.startup()
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        self._monitor_task = asyncio.create_task(self._monitoring.start())
        websocket_task = asyncio.create_task(self._run_websocket(stop_event))

        await stop_event.wait()
        await self._monitoring.stop()
        await websocket_task
        if self._monitor_task:
            await self._monitor_task
        await self.shutdown()


async def self_test(settings: Settings) -> int:
    server = MCPServer(settings)
    await server.startup()
    try:
        tools = await server._tool_registry.get_tools(settings.default_tool_mode)
        LOGGER.info("Loaded %d tools for verification", len(tools))
        health = await server.health_status()
        LOGGER.info("Health check response: %s", health)
        try:
            await server._sandbox.run(["python3", "-c", "print('sandbox-ok')"], timeout=5)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Sandbox check failed: %s", exc)
    finally:
        await server.shutdown()
    return 0


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level)
    root.handlers.clear()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    file_handler = RotatingFileHandler(
        settings.log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Path to config YAML file")
    parser.add_argument("--mode", help="Override default tool discovery mode")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    settings = load_settings(args.config)
    if args.mode:
        settings.default_tool_mode = args.mode
    configure_logging(settings)

    if args.self_test:
        return asyncio.run(self_test(settings))

    server = MCPServer(settings)
    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user")
    return 0


if __name__ == "__main__":
    sys.exit(main())
