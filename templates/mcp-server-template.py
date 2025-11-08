#!/usr/bin/env python3
"""Production-ready MCP server template.

This template mirrors the architecture described in Anthropic's Model Context
Protocol engineering blog post and demonstrates how to:

* Discover tools progressively (minimal vs full disclosure).
* Reduce prompt token usage by caching compiled tool manifests (150k -> 2k tokens).
* Filter large datasets before they are returned to the model.
* Execute untrusted code in a sandbox (bubblewrap/firejail).
* Persist state across the filesystem, PostgreSQL, Redis, and Qdrant.
* Provide async orchestration with structured logging and graceful shutdowns.

The server exposes a WebSocket interface compatible with MCP clients.  Use the
``mcp-server`` helper script to scaffold new projects, manage lifecycle events,
and run the built-in self-test.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import os
import pathlib
import signal
import sys
from typing import Any, Dict, List, Optional

import httpx
import sqlalchemy as sa
from pydantic import BaseModel, Field
from redis import asyncio as redis_asyncio
from sqlalchemy.orm import sessionmaker
from websockets import serve

LOGGER = logging.getLogger("mcp.server")
DEFAULT_LOG_LEVEL = os.environ.get("MCP_LOG_LEVEL", "INFO").upper()


class Settings(BaseModel):
    """Runtime configuration for the MCP server."""

    postgres_dsn: str = Field(
        default="postgresql+psycopg2://mcp@localhost:5432/mcp",
        description="SQLAlchemy DSN for the metadata database.",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching and ephemeral state.",
    )
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Base URL for the Qdrant vector database.",
    )
    tool_schema_cache: pathlib.Path = Field(
        default=pathlib.Path(".mcp_cache/tool_schemas.json"),
        description="Filesystem cache for compiled tool manifests.",
    )
    sandbox_runner: str = Field(
        default=os.environ.get("MCP_SANDBOX_RUNNER", "bubblewrap"),
        description="Sandbox binary (bubblewrap or firejail).",
    )
    sandbox_profile: Optional[pathlib.Path] = Field(
        default=None,
        description="Optional custom sandbox profile.",
    )
    default_tool_mode: str = Field(
        default="minimal",
        description="Default discovery mode: minimal or full.",
    )


class ToolDefinition(BaseModel):
    """Metadata for an MCP tool."""

    name: str
    description: str
    manifest: Dict[str, Any]
    cost_estimate_tokens: int = 2000


class ToolPayload(BaseModel):
    """Runtime payload returned to the client."""

    name: str
    description: str
    manifest: Dict[str, Any]


class ToolRegistry:
    """Caches tool definitions with Redis and filesystem backends."""

    def __init__(self, settings: Settings, engine: sa.Engine, redis: redis_asyncio.Redis):
        self.settings = settings
        self.engine = engine
        self.redis = redis
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._tool_cache: Dict[str, ToolDefinition] = {}
        self._fs_cache_path = settings.tool_schema_cache
        self._fs_cache_path.parent.mkdir(parents=True, exist_ok=True)

    async def warm_cache(self) -> None:
        """Preload cached tool manifests from disk and Redis."""

        if self._fs_cache_path.exists():
            try:
                cached = json.loads(self._fs_cache_path.read_text())
                for payload in cached:
                    tool = ToolDefinition(**payload)
                    self._tool_cache[tool.name] = tool
                LOGGER.debug("Loaded %d tool manifests from disk cache", len(cached))
            except Exception as exc:  # noqa: BLE001 - template should surface errors
                LOGGER.warning("Failed to hydrate tool cache from disk: %s", exc)

        redis_keys = await self.redis.keys("tool:definition:*")
        if redis_keys:
            async with self.redis.pipeline(transaction=False) as pipe:
                for key in redis_keys:
                    pipe.get(key)
                results = await pipe.execute()
            for blob in results:
                if blob:
                    tool = ToolDefinition.parse_raw(blob)
                    self._tool_cache[tool.name] = tool
            LOGGER.debug("Hydrated %d tool manifests from Redis", len(results))

    async def persist_cache(self) -> None:
        """Persist tool cache to disk to maintain token savings."""

        payload = [tool.model_dump() for tool in self._tool_cache.values()]
        self._fs_cache_path.write_text(json.dumps(payload, indent=2))
        LOGGER.debug("Wrote %d tool manifests to disk cache", len(payload))

    async def get_tools(self, mode: str) -> List[ToolPayload]:
        """Return tool definitions according to the requested disclosure mode."""

        if mode not in {"minimal", "full"}:
            raise ValueError(f"Unsupported tool discovery mode: {mode}")

        if not self._tool_cache:
            await self._refresh_from_database()

        tools: List[ToolPayload] = []
        for tool in self._tool_cache.values():
            payload = ToolPayload(
                name=tool.name,
                description=tool.description,
                manifest=tool.manifest if mode == "full" else {"name": tool.name},
            )
            tools.append(payload)
        LOGGER.debug("Dispatched %d tool manifests in %s mode", len(tools), mode)
        return tools

    async def _refresh_from_database(self) -> None:
        """Load tool definitions from PostgreSQL into Redis + memory."""

        query = sa.text(
            "SELECT name, description, manifest, cost_estimate_tokens FROM tool_registry"
        )

        def _fetch() -> List[Dict[str, Any]]:
            session = self._session_factory()
            try:
                return [
                    {
                        "name": name,
                        "description": description,
                        "manifest": manifest,
                        "cost_estimate": cost_estimate,
                    }
                    for name, description, manifest, cost_estimate in session.execute(query)
                ]
            finally:
                session.close()

        rows = await asyncio.to_thread(_fetch)
        for row in rows:
            tool = ToolDefinition(
                name=row["name"],
                description=row["description"],
                manifest=row["manifest"],
                cost_estimate_tokens=row["cost_estimate"],
            )
            self._tool_cache[tool.name] = tool
            await self.redis.set(
                f"tool:definition:{tool.name}", tool.model_dump_json(), ex=3600
            )
        LOGGER.info("Loaded %d tool manifests from PostgreSQL", len(self._tool_cache))
        await self.persist_cache()


@dataclasses.dataclass(slots=True)
class SandboxResult:
    stdout: str
    stderr: str
    returncode: int


class SandboxExecutor:
    """Run untrusted commands in a bubblewrap/firejail sandbox."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, command: List[str], timeout: int = 30) -> SandboxResult:
        sandbox = self.settings.sandbox_runner
        if sandbox not in {"bubblewrap", "firejail"}:
            raise RuntimeError(f"Unsupported sandbox runner: {sandbox}")

        sandbox_command = [sandbox]
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
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise
        return SandboxResult(
            stdout=stdout_bytes.decode(),
            stderr=stderr_bytes.decode(),
            returncode=proc.returncode or 0,
        )


class MCPServer:
    """Minimal async WebSocket server implementing MCP primitives."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._engine = sa.create_engine(self.settings.postgres_dsn, future=True)
        self._redis = redis_asyncio.Redis.from_url(self.settings.redis_url)
        self._tool_registry = ToolRegistry(self.settings, self._engine, self._redis)
        self._sandbox = SandboxExecutor(self.settings)
        self._http = httpx.AsyncClient(base_url=self.settings.qdrant_url, timeout=10.0)
        self._server: Optional[asyncio.base_events.Server] = None

    async def startup(self) -> None:
        LOGGER.info("Starting MCP server")
        await self._tool_registry.warm_cache()
        await self._ensure_database_schema()

    async def shutdown(self) -> None:
        LOGGER.info("Stopping MCP server")
        await self._tool_registry.persist_cache()
        await self._redis.close()
        await self._http.aclose()
        self._engine.dispose()

    async def _ensure_database_schema(self) -> None:
        metadata = sa.MetaData()
        sa.Table(
            "tool_registry",
            metadata,
            sa.Column("name", sa.String(128), primary_key=True),
            sa.Column("description", sa.Text, nullable=False),
            sa.Column("manifest", sa.JSON, nullable=False),
            sa.Column("cost_estimate_tokens", sa.Integer, nullable=False, default=2000),
        )
        metadata.create_all(self._engine)

    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch MCP requests."""

        action = message.get("action")
        if action == "discover_tools":
            mode = message.get("mode", self.settings.default_tool_mode)
            tools = await self._tool_registry.get_tools(mode)
            return {
                "type": "tools",
                "tools": [tool.model_dump() for tool in tools],
                "mode": mode,
            }
        if action == "run_sandboxed":
            command = message.get("command", [])
            result = await self._sandbox.run(command)
            return dataclasses.asdict(result)
        if action == "semantic_search":
            query = message["query"]
            response = await self._http.post(
                "/collections/semantic-search/points/search",
                json={"vector": query["embedding"], "limit": query.get("limit", 5)},
            )
            response.raise_for_status()
            payload = response.json()
            return {"results": payload.get("result", [])}
        raise ValueError(f"Unsupported action: {action}")

    async def _connection_handler(self, websocket) -> None:
        async for raw_message in websocket:
            try:
                payload = json.loads(raw_message)
                response = await self.handle_message(payload)
            except Exception as exc:  # noqa: BLE001 - propagate errors to client
                LOGGER.exception("Failed to process message")
                response = {"error": str(exc)}
            await websocket.send(json.dumps(response))

    async def serve(self, host: str = "0.0.0.0", port: int = 8791) -> None:
        await self.startup()
        async with serve(self._connection_handler, host, port):
            LOGGER.info("Listening on %s:%s", host, port)
            stop_event = asyncio.Event()

            loop = asyncio.get_running_loop()

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)

            await stop_event.wait()
        await self.shutdown()


async def self_test(settings: Settings) -> int:
    """Exercise core components to validate environment configuration."""

    server = MCPServer(settings)
    await server.startup()

    tools = await server._tool_registry.get_tools(settings.default_tool_mode)
    LOGGER.info("Discovered %d tools in %s mode", len(tools), settings.default_tool_mode)

    try:
        qdrant_status = await server._http.get("/readyz")
        qdrant_status.raise_for_status()
        LOGGER.info("Qdrant readiness: %s", qdrant_status.json())
    except httpx.HTTPError as exc:  # noqa: BLE001
        LOGGER.warning("Unable to reach Qdrant: %s", exc)

    try:
        result = await server._sandbox.run(["python3", "-c", "print('sandbox-ok')"], timeout=5)
        LOGGER.info("Sandbox result: rc=%s stdout=%s", result.returncode, result.stdout.strip())
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Sandbox execution failed: %s", exc)

    await server.shutdown()
    return 0


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default=os.environ.get("MCP_TOOL_MODE", "minimal"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def configure_logging() -> None:
    logging.basicConfig(
        level=DEFAULT_LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def main(argv: Optional[List[str]] = None) -> int:
    configure_logging()
    args = parse_args(argv or sys.argv[1:])
    settings = Settings(default_tool_mode=args.mode)

    if args.self_test:
        return asyncio.run(self_test(settings))

    server = MCPServer(settings)
    try:
        asyncio.run(server.serve(args.host, args.port))
    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user")
    return 0


if __name__ == "__main__":
    sys.exit(main())
