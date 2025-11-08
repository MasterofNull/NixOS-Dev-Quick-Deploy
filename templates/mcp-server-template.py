"""
MCP Server Template (Python)

This template provides a starting point for building MCP servers
as described in https://www.anthropic.com/engineering/code-execution-with-mcp

Key Features:
- Progressive tool discovery via filesystem navigation
- Data filtering in execution environment
- Secure sandboxing with bubblewrap/firejail
- State management through filesystem
- Token optimization (on-demand loading)
- Database integration (PostgreSQL, Redis, Qdrant)
"""

import asyncio
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import aiohttp
from aiohttp import web
import psycopg2
import redis
from qdrant_client import QdrantClient
from pydantic import BaseModel


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class Config:
    port: int = int(os.getenv("MCP_SERVER_PORT", "8000"))
    tools_dir: Path = Path(os.getenv("MCP_TOOLS_DIR", "./servers"))
    state_dir: Path = Path(os.getenv("MCP_STATE_DIR", "./state"))
    enable_sandbox: bool = os.getenv("MCP_ENABLE_SANDBOX", "false").lower() == "true"

    # Database connections
    postgres_host: str = os.getenv("POSTGRES_HOST", "127.0.0.1")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "mcp")
    postgres_user: str = os.getenv("POSTGRES_USER", "mcp")

    redis_host: str = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "mcp-dev-password-change-in-production")

    qdrant_host: str = os.getenv("QDRANT_HOST", "127.0.0.1")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))


CONFIG = Config()


# ============================================================================
# Models (Pydantic for validation)
# ============================================================================

class ToolDefinition(BaseModel):
    name: str
    description: str
    path: str
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class MCPRequest(BaseModel):
    action: Literal["list_tools", "search_tools", "execute", "get_tool"]
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


# ============================================================================
# Database Clients
# ============================================================================

class DatabaseClients:
    """Singleton database clients for MCP server"""

    _postgres_conn: Optional[psycopg2.extensions.connection] = None
    _redis_client: Optional[redis.Redis] = None
    _qdrant_client: Optional[QdrantClient] = None

    @classmethod
    def get_postgres(cls) -> psycopg2.extensions.connection:
        """Get PostgreSQL connection (for structured data)"""
        if cls._postgres_conn is None:
            cls._postgres_conn = psycopg2.connect(
                host=CONFIG.postgres_host,
                port=CONFIG.postgres_port,
                database=CONFIG.postgres_db,
                user=CONFIG.postgres_user,
            )
        return cls._postgres_conn

    @classmethod
    def get_redis(cls) -> redis.Redis:
        """Get Redis client (for caching and state)"""
        if cls._redis_client is None:
            cls._redis_client = redis.Redis(
                host=CONFIG.redis_host,
                port=CONFIG.redis_port,
                password=CONFIG.redis_password,
                decode_responses=True,
            )
        return cls._redis_client

    @classmethod
    def get_qdrant(cls) -> QdrantClient:
        """Get Qdrant client (for vector search)"""
        if cls._qdrant_client is None:
            cls._qdrant_client = QdrantClient(
                host=CONFIG.qdrant_host,
                port=CONFIG.qdrant_port,
            )
        return cls._qdrant_client


# ============================================================================
# Tool Discovery (Progressive Disclosure)
# ============================================================================

async def discover_tools(detail_level: Literal["minimal", "full"] = "minimal") -> List[ToolDefinition]:
    """
    Discover tools from filesystem with progressive disclosure.

    - minimal: Only load tool names (token efficient)
    - full: Load complete tool definitions
    """
    tools: List[ToolDefinition] = []

    # Check cache first (Redis)
    cache_key = f"tools:discovery:{detail_level}"
    redis_client = DatabaseClients.get_redis()

    try:
        cached = redis_client.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            return [ToolDefinition(**tool) for tool in cached_data]
    except Exception as e:
        print(f"Cache miss: {e}")

    # Walk tools directory
    for tool_file in CONFIG.tools_dir.rglob("*.py"):
        if tool_file.stem.startswith("_"):
            continue  # Skip private modules

        relative_path = tool_file.relative_to(CONFIG.tools_dir)
        tool_name = str(relative_path.with_suffix("")).replace(os.sep, ".")

        if detail_level == "minimal":
            # Only return tool name for token efficiency
            tools.append(ToolDefinition(
                name=tool_name,
                description="",
                path=str(tool_file),
            ))
        else:
            # Load full tool definition
            definition = await load_tool_definition(tool_file)
            tools.append(definition)

    # Cache results (expire after 5 minutes)
    try:
        redis_client.setex(
            cache_key,
            300,
            json.dumps([tool.dict() for tool in tools])
        )
    except Exception as e:
        print(f"Cache write failed: {e}")

    return tools


async def search_tools(
    query: str,
    detail_level: Literal["minimal", "full"] = "minimal"
) -> List[ToolDefinition]:
    """
    Search for tools matching query.
    Can be enhanced with vector search via Qdrant for semantic matching.
    """
    all_tools = await discover_tools(detail_level)

    # Simple text search (can be enhanced with Qdrant embeddings)
    query_lower = query.lower()
    return [
        tool for tool in all_tools
        if query_lower in tool.name.lower() or
           query_lower in tool.description.lower()
    ]


async def load_tool_definition(path: Path) -> ToolDefinition:
    """Load tool definition from Python module"""
    try:
        # Read tool metadata from module docstring and exports
        # In production, use importlib or ast parsing
        return ToolDefinition(
            name=path.stem,
            description=f"Tool from {path.name}",
            path=str(path),
        )
    except Exception as e:
        print(f"Failed to load tool from {path}: {e}")
        return ToolDefinition(
            name=path.stem,
            description="",
            path=str(path),
        )


# ============================================================================
# Code Execution (Sandboxed)
# ============================================================================

async def execute_code(code: str, sandbox: bool = CONFIG.enable_sandbox) -> Dict[str, Any]:
    """
    Execute Python code in a sandboxed environment.

    Uses bubblewrap for isolation:
    - Read-only system directories
    - Temporary /tmp
    - Network access (can be disabled)
    - Process isolation
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_file = f.name

    try:
        if sandbox:
            # Execute with bubblewrap sandboxing
            cmd = [
                "bwrap",
                "--ro-bind", "/usr", "/usr",
                "--ro-bind", "/lib", "/lib",
                "--ro-bind", "/lib64", "/lib64",
                "--ro-bind", "/bin", "/bin",
                "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf",
                "--tmpfs", "/tmp",
                "--proc", "/proc",
                "--dev", "/dev",
                "--unshare-all",
                "--share-net",
                "--die-with-parent",
                "python3", temp_file,
            ]
        else:
            cmd = ["python3", temp_file]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "exit_code": process.returncode,
        }
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file)
        except:
            pass


# ============================================================================
# Data Filtering (Pre-processing)
# ============================================================================

def filter_large_dataset(
    data: List[Any],
    filter_fn: callable,
    max_rows: int = 100
) -> List[Any]:
    """
    Filter data in execution environment to reduce tokens.

    Example: 10,000 rows filtered to only relevant rows before
    returning to model (98.7% token savings as per article).
    """
    return [item for item in data if filter_fn(item)][:max_rows]


# ============================================================================
# State Management
# ============================================================================

async def save_state(key: str, value: Any) -> None:
    """Save state to filesystem and Redis"""
    # Filesystem (persistent)
    CONFIG.state_dir.mkdir(parents=True, exist_ok=True)
    state_path = CONFIG.state_dir / f"{key}.json"

    with open(state_path, 'w') as f:
        json.dump(value, f, indent=2)

    # Redis (fast access)
    try:
        redis_client = DatabaseClients.get_redis()
        redis_client.set(f"state:{key}", json.dumps(value))
    except Exception as e:
        print(f"Redis state save failed: {e}")


async def load_state(key: str) -> Optional[Any]:
    """Load state from Redis (fast) or filesystem (fallback)"""
    # Try Redis first
    try:
        redis_client = DatabaseClients.get_redis()
        cached = redis_client.get(f"state:{key}")
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"Redis state load failed: {e}")

    # Fallback to filesystem
    state_path = CONFIG.state_dir / f"{key}.json"
    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)

    return None


# ============================================================================
# HTTP Handlers
# ============================================================================

async def handle_request(request: web.Request) -> web.Response:
    """Handle MCP protocol requests"""
    try:
        data = await request.json()
        mcp_request = MCPRequest(**data)

        if mcp_request.action == "list_tools":
            detail_level = mcp_request.params.get("detail_level", "minimal") if mcp_request.params else "minimal"
            tools = await discover_tools(detail_level)
            response = MCPResponse(success=True, data=[tool.dict() for tool in tools])

        elif mcp_request.action == "search_tools":
            if not mcp_request.params or "query" not in mcp_request.params:
                response = MCPResponse(success=False, error="Query parameter required")
            else:
                detail_level = mcp_request.params.get("detail_level", "minimal")
                tools = await search_tools(mcp_request.params["query"], detail_level)
                response = MCPResponse(success=True, data=[tool.dict() for tool in tools])

        elif mcp_request.action == "get_tool":
            if not mcp_request.params or "tool_name" not in mcp_request.params:
                response = MCPResponse(success=False, error="Tool name required")
            else:
                tools = await discover_tools("full")
                tool = next((t for t in tools if t.name == mcp_request.params["tool_name"]), None)
                if tool:
                    response = MCPResponse(success=True, data=tool.dict())
                else:
                    response = MCPResponse(success=False, error="Tool not found")

        elif mcp_request.action == "execute":
            response = MCPResponse(success=False, error="Not implemented yet")

        else:
            response = MCPResponse(success=False, error="Unknown action")

        return web.json_response(response.dict())

    except Exception as e:
        return web.json_response(
            MCPResponse(success=False, error=str(e)).dict(),
            status=500
        )


# ============================================================================
# Main
# ============================================================================

async def main():
    """Start MCP server"""
    app = web.Application()
    app.router.add_post('/mcp', handle_request)

    print(f"MCP Server starting on port {CONFIG.port}...")
    print(f"Tools directory: {CONFIG.tools_dir}")
    print(f"State directory: {CONFIG.state_dir}")
    print(f"Sandbox enabled: {CONFIG.enable_sandbox}")
    print(f"PostgreSQL: {CONFIG.postgres_host}:{CONFIG.postgres_port}/{CONFIG.postgres_db}")
    print(f"Redis: {CONFIG.redis_host}:{CONFIG.redis_port}")
    print(f"Qdrant: {CONFIG.qdrant_host}:{CONFIG.qdrant_port}")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', CONFIG.port)
    await site.start()

    print(f"\n✓ MCP Server ready at http://0.0.0.0:{CONFIG.port}/mcp")

    # Keep server running
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
