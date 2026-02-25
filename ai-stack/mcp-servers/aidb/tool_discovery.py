#!/usr/bin/env python3
"""
Tool Discovery Engine
Automatic discovery and indexing of system capabilities

Features:
- Scans MCP servers for available tools
- Indexes tools in Qdrant for semantic search
- Auto-generates tool usage examples
- Monitors for new MCP server deployments
- Real-time registry updates
"""

import asyncio
import json
import httpx
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pathlib import Path
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ToolMetadata(BaseModel):
    """Metadata for a discovered tool"""
    tool_id: str
    name: str
    description: str
    category: str
    server_url: str
    server_name: str
    endpoint: str
    method: str = "POST"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified: Optional[datetime] = None
    is_available: bool = True
    cost_estimate: str = "unknown"  # free, low, medium, high
    requires_auth: bool = False


class MCPServerInfo(BaseModel):
    """Information about an MCP server"""
    name: str
    url: str
    health_endpoint: str = "/health"
    capabilities_endpoint: str = "/api/v1/capabilities"
    is_healthy: bool = False
    last_check: Optional[datetime] = None


class ToolDiscoveryEngine:
    """
    Autonomous tool and skill discovery system

    Usage:
        engine = ToolDiscoveryEngine(qdrant_client, settings)
        await engine.start()  # Begins background discovery

        # Manual discovery
        tools = await engine.discover_all_tools()

        # Semantic search
        results = await engine.search_tools("search documents")
    """

    def __init__(self, qdrant_client, postgres_client, settings):
        self.qdrant = qdrant_client
        self.postgres = postgres_client
        self.settings = settings
        self.http_client = httpx.AsyncClient(timeout=30.0)
        aidb_url = (os.getenv("AIDB_URL") or "").strip()
        hybrid_url = (os.getenv("HYBRID_COORDINATOR_URL") or "").strip()
        ralph_url = (os.getenv("RALPH_URL") or "").strip()
        if not aidb_url or not hybrid_url or not ralph_url:
            raise ValueError("AIDB_URL, HYBRID_COORDINATOR_URL, and RALPH_URL must be set for tool discovery")

        # Known MCP servers
        self.mcp_servers: List[MCPServerInfo] = [
            MCPServerInfo(
                name="aidb",
                url=aidb_url,
                capabilities_endpoint="/api/v1/discovery/capabilities"
            ),
            MCPServerInfo(
                name="hybrid-coordinator",
                url=hybrid_url,
                capabilities_endpoint="/api/v1/capabilities"
            ),
            MCPServerInfo(
                name="ralph-wiggum",
                url=ralph_url,
                capabilities_endpoint="/api/v1/capabilities"
            ),
        ]

        # Tool cache
        self.tool_cache: Dict[str, ToolMetadata] = {}
        self.discovery_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background discovery task"""
        logger.info("tool_discovery_starting")
        await self._ensure_postgres_schema()
        self.discovery_task = asyncio.create_task(self._discovery_loop())

    async def stop(self):
        """Stop background discovery"""
        if self.discovery_task:
            self.discovery_task.cancel()
            try:
                await self.discovery_task
            except asyncio.CancelledError:
                pass
        logger.info("tool_discovery_stopped")

    async def _discovery_loop(self):
        """Background loop for continuous discovery"""
        while True:
            try:
                await self.discover_all_tools()
                await asyncio.sleep(300)  # Discover every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("discovery_loop_error", error=str(e))
                await asyncio.sleep(60)  # Retry after error

    async def discover_all_tools(self) -> List[ToolMetadata]:
        """
        Discover tools from all known MCP servers

        Returns:
            List of discovered tools
        """
        logger.info("discovering_tools", servers=len(self.mcp_servers))

        all_tools: List[ToolMetadata] = []

        for server in self.mcp_servers:
            try:
                # Check server health
                is_healthy = await self._check_server_health(server)
                server.is_healthy = is_healthy
                server.last_check = datetime.now(timezone.utc)

                if not is_healthy:
                    logger.warning("server_unhealthy", server=server.name)
                    continue

                # Discover tools from this server
                tools = await self._discover_from_server(server)
                all_tools.extend(tools)

                logger.info(
                    "server_tools_discovered",
                    server=server.name,
                    count=len(tools)
                )

            except Exception as e:
                logger.error(
                    "server_discovery_failed",
                    server=server.name,
                    error=str(e)
                )

        # Index tools in Qdrant
        await self._index_tools(all_tools)

        # Update cache
        for tool in all_tools:
            self.tool_cache[tool.tool_id] = tool

        # Persist discovery metadata (best effort)
        await self._persist_discovery_snapshot(all_tools)

        logger.info("tool_discovery_complete", total_tools=len(all_tools))
        return all_tools

    async def _ensure_postgres_schema(self) -> None:
        """Create optional Postgres tables used by discovery persistence."""
        if not self.postgres:
            return
        try:
            await self.postgres.execute(
                """
                CREATE TABLE IF NOT EXISTS aidb_tool_discovery_runs (
                    id BIGSERIAL PRIMARY KEY,
                    discovered_count INTEGER NOT NULL,
                    healthy_servers INTEGER NOT NULL,
                    unhealthy_servers INTEGER NOT NULL,
                    server_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await self.postgres.execute(
                """
                CREATE TABLE IF NOT EXISTS aidb_discovered_tools (
                    tool_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    server_name TEXT NOT NULL,
                    server_url TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
                    examples JSONB NOT NULL DEFAULT '[]'::jsonb,
                    cost_estimate TEXT NOT NULL,
                    requires_auth BOOLEAN NOT NULL DEFAULT FALSE,
                    discovered_at TIMESTAMPTZ NOT NULL,
                    last_verified TIMESTAMPTZ NULL,
                    is_available BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        except Exception as exc:
            logger.warning("tool_discovery_postgres_schema_failed", error=str(exc))

    async def _persist_discovery_snapshot(self, tools: List[ToolMetadata]) -> None:
        """Persist run telemetry + latest discovered tool catalog to Postgres."""
        if not self.postgres:
            return

        try:
            healthy = [s.name for s in self.mcp_servers if s.is_healthy]
            unhealthy = [s.name for s in self.mcp_servers if not s.is_healthy]
            await self.postgres.execute(
                """
                INSERT INTO aidb_tool_discovery_runs (
                    discovered_count,
                    healthy_servers,
                    unhealthy_servers,
                    server_snapshot
                ) VALUES (%s, %s, %s, %s::jsonb)
                """,
                len(tools),
                len(healthy),
                len(unhealthy),
                json.dumps({"healthy": healthy, "unhealthy": unhealthy}),
            )

            for tool in tools:
                payload = tool.model_dump(mode="json")
                await self.postgres.execute(
                    """
                    INSERT INTO aidb_discovered_tools (
                        tool_id, name, description, category,
                        server_name, server_url, endpoint, method,
                        parameters, examples, cost_estimate, requires_auth,
                        discovered_at, last_verified, is_available, updated_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s, %s,
                        %s::timestamptz, %s::timestamptz, %s, NOW()
                    )
                    ON CONFLICT (tool_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        server_name = EXCLUDED.server_name,
                        server_url = EXCLUDED.server_url,
                        endpoint = EXCLUDED.endpoint,
                        method = EXCLUDED.method,
                        parameters = EXCLUDED.parameters,
                        examples = EXCLUDED.examples,
                        cost_estimate = EXCLUDED.cost_estimate,
                        requires_auth = EXCLUDED.requires_auth,
                        discovered_at = EXCLUDED.discovered_at,
                        last_verified = EXCLUDED.last_verified,
                        is_available = EXCLUDED.is_available,
                        updated_at = NOW()
                    """,
                    payload["tool_id"],
                    payload["name"],
                    payload["description"],
                    payload["category"],
                    payload["server_name"],
                    payload["server_url"],
                    payload["endpoint"],
                    payload["method"],
                    json.dumps(payload.get("parameters") or {}),
                    json.dumps(payload.get("examples") or []),
                    payload.get("cost_estimate", "unknown"),
                    bool(payload.get("requires_auth", False)),
                    payload.get("discovered_at"),
                    payload.get("last_verified"),
                    bool(payload.get("is_available", True)),
                )
        except Exception as exc:
            logger.warning("tool_discovery_postgres_persist_failed", error=str(exc))

    async def _check_server_health(self, server: MCPServerInfo) -> bool:
        """Check if MCP server is healthy"""
        try:
            response = await self.http_client.get(
                f"{server.url}{server.health_endpoint}"
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug("health_check_failed", server=server.name, error=str(e))
            return False

    async def _discover_from_server(
        self, server: MCPServerInfo
    ) -> List[ToolMetadata]:
        """Discover tools from a specific MCP server"""
        tools: List[ToolMetadata] = []

        try:
            # Query capabilities endpoint
            response = await self.http_client.get(
                f"{server.url}{server.capabilities_endpoint}"
            )

            if response.status_code != 200:
                return tools

            capabilities = response.json()

            # Extract tools
            raw_tools = capabilities.get("tools", [])

            for raw_tool in raw_tools:
                tool = self._parse_tool(raw_tool, server)
                if tool:
                    tools.append(tool)

        except Exception as e:
            logger.error("server_capability_query_failed", error=str(e))

        return tools

    def _parse_tool(
        self, raw_tool: Dict[str, Any], server: MCPServerInfo
    ) -> Optional[ToolMetadata]:
        """Parse tool from server response"""
        try:
            tool_id = f"{server.name}.{raw_tool.get('name', 'unknown')}"

            return ToolMetadata(
                tool_id=tool_id,
                name=raw_tool.get("name", "Unknown"),
                description=raw_tool.get("description", ""),
                category=raw_tool.get("category", "general"),
                server_url=server.url,
                server_name=server.name,
                endpoint=raw_tool.get("endpoint", "/"),
                method=raw_tool.get("method", "POST"),
                parameters=raw_tool.get("parameters", {}),
                examples=raw_tool.get("examples", []),
                cost_estimate=raw_tool.get("cost_estimate", "unknown"),
                requires_auth=raw_tool.get("requires_auth", False),
            )
        except Exception as e:
            logger.warning("tool_parse_failed", error=str(e))
            return None

    async def _index_tools(self, tools: List[ToolMetadata]):
        """Index tools in Qdrant for semantic search"""
        if not tools:
            return

        try:
            from qdrant_client.models import PointStruct

            # Prepare points for Qdrant
            points = []

            for tool in tools:
                # Create searchable text
                searchable_text = (
                    f"{tool.name} {tool.description} "
                    f"{tool.category} {' '.join(tool.parameters.keys())}"
                )

                # Generate embedding (via llama.cpp)
                embedding = await self._generate_embedding(searchable_text)

                if not embedding:
                    continue

                # Create point
                point = PointStruct(
                    id=hash(tool.tool_id) % (10 ** 8),  # Convert to int
                    vector=embedding,
                    payload={
                        "tool_id": tool.tool_id,
                        "name": tool.name,
                        "description": tool.description,
                        "category": tool.category,
                        "server_name": tool.server_name,
                        "server_url": tool.server_url,
                        "endpoint": tool.endpoint,
                        "method": tool.method,
                        "cost_estimate": tool.cost_estimate,
                        "requires_auth": tool.requires_auth,
                        "discovered_at": tool.discovered_at.isoformat(),
                    },
                )

                points.append(point)

            # Upsert to Qdrant
            if points:
                await self.qdrant.upsert(
                    collection_name="mcp-semantic-search",
                    points=points,
                    wait=True,
                )

                logger.info("tools_indexed", count=len(points))

        except Exception as e:
            logger.error("tool_indexing_failed", error=str(e))

    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using llama.cpp"""
        try:
            # Call llama.cpp embedding endpoint
            response = await self.http_client.post(
                f"{self.settings.llama_cpp_base_url}/embeddings",
                json={"input": text},
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("embedding", [])
        except Exception as e:
            logger.debug("embedding_generation_failed", error=str(e))

        return None

    async def search_tools(
        self, query: str, limit: int = 5
    ) -> List[ToolMetadata]:
        """
        Semantic search for tools

        Args:
            query: Search query (e.g., "search documents", "create user")
            limit: Maximum number of results

        Returns:
            List of matching tools
        """
        try:
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)

            if not query_embedding:
                return []

            # Search Qdrant
            results = await self.qdrant.search(
                collection_name="mcp-semantic-search",
                query_vector=query_embedding,
                limit=limit,
            )

            # Convert to ToolMetadata
            tools = []
            for result in results:
                payload = result.payload
                tool = ToolMetadata(
                    tool_id=payload["tool_id"],
                    name=payload["name"],
                    description=payload["description"],
                    category=payload["category"],
                    server_url=payload["server_url"],
                    server_name=payload["server_name"],
                    endpoint=payload["endpoint"],
                    method=payload["method"],
                    cost_estimate=payload["cost_estimate"],
                    requires_auth=payload["requires_auth"],
                    discovered_at=datetime.fromisoformat(
                        payload["discovered_at"]
                    ),
                )
                tools.append(tool)

            logger.info("tool_search_complete", query=query, results=len(tools))
            return tools

        except Exception as e:
            logger.error("tool_search_failed", error=str(e))
            return []

    async def get_tool_by_id(self, tool_id: str) -> Optional[ToolMetadata]:
        """Get tool by ID from cache or database"""
        # Check cache first
        if tool_id in self.tool_cache:
            return self.tool_cache[tool_id]

        # Query from database if implemented
        # For now, return None
        return None

    async def register_mcp_server(self, server: MCPServerInfo):
        """Manually register a new MCP server for discovery"""
        self.mcp_servers.append(server)
        logger.info("mcp_server_registered", name=server.name)

        # Trigger immediate discovery for this server
        tools = await self._discover_from_server(server)
        await self._index_tools(tools)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get discovery statistics"""
        total_servers = len(self.mcp_servers)
        healthy_servers = sum(1 for s in self.mcp_servers if s.is_healthy)
        total_tools = len(self.tool_cache)

        # Count tools by category
        categories: Dict[str, int] = {}
        for tool in self.tool_cache.values():
            categories[tool.category] = categories.get(tool.category, 0) + 1

        return {
            "total_servers": total_servers,
            "healthy_servers": healthy_servers,
            "total_tools": total_tools,
            "tools_by_category": categories,
            "last_discovery": max(
                (s.last_check for s in self.mcp_servers if s.last_check),
                default=None,
            ),
        }
