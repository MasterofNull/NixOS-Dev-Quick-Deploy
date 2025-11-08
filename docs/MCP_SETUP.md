# MCP (Model Context Protocol) Setup Guide

This guide helps you build production-ready MCP systems as described in [Anthropic's Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp).

## Overview

The NixOS-Dev-Quick-Deploy system is now equipped with a comprehensive MCP development stack including:

- **Progressive Tool Discovery**: On-demand tool loading via filesystem navigation
- **Token Optimization**: 98.7% token savings (150,000 → 2,000 tokens)
- **Data Filtering**: Process large datasets in execution environment before returning to model
- **Secure Sandboxing**: bubblewrap/firejail isolation for code execution
- **State Management**: Filesystem and database-backed persistence
- **Multi-Database Support**: PostgreSQL, Redis, and Qdrant

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude/AI Model                        │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ MCP Protocol
                 │
┌────────────────▼────────────────────────────────────────────┐
│                     MCP Server                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Tool       │  │    Data      │  │    State     │     │
│  │  Discovery   │  │  Filtering   │  │  Management  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────┬────────────────────────────────────────────┘
                 │
    ┌────────────┼────────────┬─────────────────┐
    │            │            │                 │
┌───▼───┐   ┌───▼───┐   ┌───▼────┐      ┌────▼────┐
│ PostgreSQL│  │ Redis │   │ Qdrant │      │ Sandbox │
│  (Data)   │  │(Cache)│   │(Vector)│      │(Execution)│
└───────────┘  └───────┘   └────────┘      └─────────┘
```

## Database Stack

### PostgreSQL (Relational Data)
- **Purpose**: Tool metadata, execution logs, structured data
- **Port**: 5432
- **Databases**: `mcp`, `mcp_tools`, `mcp_logs`
- **User**: `mcp`
- **Connection**: `postgresql://mcp@127.0.0.1:5432/mcp`

**Start PostgreSQL**:
```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql  # Auto-start on boot
```

### Redis (High-Speed Cache)
- **Purpose**: Caching, state management, job queues
- **Port**: 6379
- **Password**: `mcp-dev-password-change-in-production` (⚠️ change in production!)
- **Connection**: `redis://:mcp-dev-password-change-in-production@127.0.0.1:6379`

**Start Redis**:
```bash
sudo systemctl start redis-mcp
sudo systemctl enable redis-mcp
```

### Qdrant (Vector Database)
- **Purpose**: Semantic search, embeddings, RAG pipelines
- **Ports**: 6333 (HTTP), 6334 (gRPC)
- **Connection**: `http://127.0.0.1:6333`

**Start Qdrant**:
```bash
sudo systemctl start qdrant
sudo systemctl enable qdrant
```

### Verify All Databases

Run the setup checker:
```bash
mcp-db-setup
```

Expected output:
```
===================================================================
MCP Database Setup
===================================================================

→ Checking PostgreSQL...
  ✓ PostgreSQL is running
→ Checking Redis...
  ✓ Redis is running
→ Checking Qdrant...
  ✓ Qdrant is running

→ Testing PostgreSQL connection...
  ✓ PostgreSQL connection successful
→ Testing Redis connection...
  ✓ Redis connection successful

===================================================================
✓ All MCP databases are ready!
===================================================================
```

## Quick Start

### 1. Create Your First MCP Server

```bash
# Initialize new MCP server
mcp-server init my-tools

# Navigate to server directory
cd ~/mcp-servers/my-tools
```

This creates:
```
~/mcp-servers/my-tools/
├── server.py          # Python MCP server
├── server.ts          # TypeScript/Deno MCP server
├── servers/           # Tool definitions
│   └── example.py     # Example tool
├── state/             # Persistent state
└── README.md          # Documentation
```

### 2. Add Custom Tools

Create a new tool in `servers/`:

```python
# servers/google_drive.py
"""Google Drive integration tool"""

name = "google_drive.search"
description = "Search for files in Google Drive"

input_schema = {
    "query": {"type": "string", "description": "Search query"},
    "max_results": {"type": "integer", "default": 10}
}

output_schema = {
    "files": {"type": "array", "items": {"type": "object"}}
}

def execute(params):
    query = params.get("query", "")
    max_results = params.get("max_results", 10)

    # Implementation here
    # This runs in the execution environment
    # Filter large datasets before returning to model

    return {
        "files": [
            {"name": "doc.txt", "id": "123", "size": 1024}
        ]
    }
```

### 3. Start the Server

```bash
mcp-server start my-tools
```

Output:
```
Starting MCP server: my-tools
  ✓ Server started (PID: 12345)
  ✓ Listening on http://127.0.0.1:8000/mcp
```

### 4. Test the Server

```bash
mcp-server test my-tools
```

Or use curl:
```bash
# List all tools (minimal mode for token efficiency)
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"action": "list_tools", "params": {"detail_level": "minimal"}}'

# Search for specific tools
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"action": "search_tools", "params": {"query": "google"}}'

# Get full tool definition
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"action": "get_tool", "params": {"tool_name": "google_drive.search"}}'
```

## Advanced Features

### Progressive Tool Discovery

MCP servers support two detail levels:

1. **Minimal** (default): Only tool names, maximum token efficiency
2. **Full**: Complete tool definitions with schemas

```python
# Request minimal tool list (2,000 tokens)
{"action": "list_tools", "params": {"detail_level": "minimal"}}

# Request full details only when needed (150,000 tokens)
{"action": "list_tools", "params": {"detail_level": "full"}}
```

This achieves the **98.7% token savings** described in the article.

### Data Filtering

Process large datasets in the execution environment:

```python
# servers/spreadsheet.py
def execute(params):
    # Load 10,000 rows in execution environment
    data = load_large_spreadsheet()  # 10,000 rows

    # Filter locally (NOT in model context)
    filtered = [row for row in data if row['status'] == 'active']

    # Return only relevant rows to model
    return {"rows": filtered[:100]}  # Only 100 rows to model
```

**Result**: Model only sees 100 rows instead of 10,000 (99% reduction).

### Sandboxed Code Execution

Execute untrusted code safely with bubblewrap:

```python
from templates.mcp_server_template import execute_code

result = await execute_code("""
import os
print("Hello from sandbox!")
# os.system("rm -rf /")  # Blocked by sandbox
""", sandbox=True)

print(result["stdout"])  # "Hello from sandbox!"
```

Sandbox provides:
- Read-only system directories
- Isolated /tmp
- No access to host filesystem
- Process isolation
- Network access (configurable)

### State Management

MCP servers support stateful operations:

```python
from templates.mcp_server_template import save_state, load_state

# Save intermediate results
await save_state("last_search", {
    "query": "important docs",
    "results": [...],
    "timestamp": "2025-11-08T10:00:00Z"
})

# Load state in future requests
previous = await load_state("last_search")
```

State is persisted to:
1. **Redis**: Fast in-memory access
2. **Filesystem**: Durable storage in `state/`

### Vector Search with Qdrant

Use Qdrant for semantic tool discovery:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host="127.0.0.1", port=6333)

# Create collection for tool embeddings
client.create_collection(
    collection_name="tools",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
)

# Index tool descriptions
# Search semantically instead of keyword matching
```

## Development Tools

### Available Runtimes

Choose your preferred runtime:

1. **Python** (recommended for ML/data workflows)
   ```bash
   python3 ~/mcp-servers/my-tools/server.py
   ```

2. **Deno** (recommended for TypeScript, secure by default)
   ```bash
   deno run --allow-net --allow-read ~/mcp-servers/my-tools/server.ts
   ```

3. **Bun** (fast JavaScript runtime)
   ```bash
   bun ~/mcp-servers/my-tools/server.ts
   ```

### Sandboxing Tools

Two sandboxing options are available:

1. **bubblewrap** (lightweight, used by Flatpak)
   ```bash
   bwrap --ro-bind /usr /usr --tmpfs /tmp -- python3 script.py
   ```

2. **firejail** (comprehensive security profiles)
   ```bash
   firejail --noprofile python3 script.py
   ```

### Monitoring

Monitor MCP server processes:

```bash
# List all servers
mcp-server list

# View server logs
mcp-server logs my-tools

# Check database status
mcp-db-setup
```

## Package Reference

### Python Packages (MCP-specific)

All available in `pythonAiEnv`:

```python
import httpx           # Modern HTTP client for MCP
import aiohttp         # Async HTTP for MCP servers
import websockets      # WebSocket support
from pydantic import BaseModel  # Data validation
import psycopg2        # PostgreSQL client
import redis           # Redis client
from sqlalchemy import create_engine  # ORM
from qdrant_client import QdrantClient  # Vector search
```

### CLI Tools

Available system-wide:

```bash
deno           # TypeScript/JavaScript runtime
bun            # Fast JavaScript runtime
bubblewrap     # Lightweight sandboxing
firejail       # Application sandbox
psql           # PostgreSQL client
redis-cli      # Redis client
```

### Helper Scripts

Custom MCP management scripts:

```bash
mcp-db-setup   # Verify database configuration
mcp-server     # Manage MCP servers (init/start/stop/logs/test)
```

## Best Practices

### 1. Token Optimization

Always use progressive disclosure:
```python
# ❌ Bad: Load all tool definitions upfront
tools = await discover_tools("full")  # 150,000 tokens

# ✅ Good: Load minimally, expand on-demand
tools = await discover_tools("minimal")  # 2,000 tokens
tool_detail = await load_tool_definition(selected_tool)  # Only when needed
```

### 2. Data Filtering

Process data before returning to model:
```python
# ❌ Bad: Return entire dataset
return {"data": all_10000_rows}

# ✅ Good: Filter in execution environment
filtered = filter_data(all_10000_rows, criteria)
return {"data": filtered[:100]}  # Only relevant subset
```

### 3. Security

Always sandbox untrusted code:
```python
# ❌ Bad: Direct execution
exec(user_code)

# ✅ Good: Sandboxed execution
result = await execute_code(user_code, sandbox=True)
```

### 4. Caching

Use Redis for frequently accessed data:
```python
# Check cache first
cached = redis_client.get(f"result:{query}")
if cached:
    return json.loads(cached)

# Expensive operation
result = expensive_computation()

# Cache for future requests
redis_client.setex(f"result:{query}", 300, json.dumps(result))
```

## Troubleshooting

### PostgreSQL not starting

```bash
# Check logs
sudo journalctl -u postgresql -n 50

# Initialize database if needed
sudo -u postgres initdb -D /var/lib/postgresql/data
```

### Redis connection refused

```bash
# Check if Redis is running
systemctl status redis-mcp

# Check Redis logs
sudo journalctl -u redis-mcp -n 50

# Test connection
redis-cli -h 127.0.0.1 -p 6379 -a "mcp-dev-password-change-in-production" PING
```

### Qdrant not accessible

```bash
# Check if running
systemctl status qdrant

# Check logs
sudo journalctl -u qdrant -n 50

# Test HTTP endpoint
curl http://127.0.0.1:6333/collections
```

### MCP server won't start

```bash
# Check if port is in use
sudo lsof -i :8000

# Check Python environment
which python3
python3 --version

# Test imports
python3 -c "import aiohttp, psycopg2, redis, qdrant_client"
```

## Performance Metrics

Based on Anthropic's article, expect:

- **Token Usage**: 98.7% reduction (150,000 → 2,000 tokens)
- **Data Transfer**: 99% reduction for large datasets
- **Latency**: <100ms for tool discovery (Redis cache)
- **Throughput**: 1000+ requests/sec (depending on hardware)

## Next Steps

1. **Read the Article**: [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
2. **Create Your First Server**: `mcp-server init my-project`
3. **Add Tools**: Create tool files in `servers/`
4. **Integrate with AI**: Connect Claude Code, Cursor, or Continue
5. **Scale**: Add more servers, databases, monitoring

## Resources

- **Anthropic Article**: https://www.anthropic.com/engineering/code-execution-with-mcp
- **MCP Templates**: `/etc/nixos/templates/mcp-server-template.{py,ts}`
- **Database Docs**:
  - PostgreSQL: https://www.postgresql.org/docs/
  - Redis: https://redis.io/docs/
  - Qdrant: https://qdrant.tech/documentation/

## Contributing

Have improvements? Submit issues or PRs to:
https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy

---

**Happy MCP Development!** 🚀
