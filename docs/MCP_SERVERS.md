# MCP Servers Guide

**Purpose:** Comprehensive guide to Model Context Protocol (MCP) servers
**Benefit:** Faster development through specialized, pre-built capabilities

---

## What is MCP?

**Model Context Protocol (MCP)** is a standardized way for AI agents to interact with external services and tools. Instead of agents making raw API calls or shell commands, they use MCP servers that provide:

- **Consistent interfaces** across different services
- **Built-in error handling** and retry logic
- **Type-safe operations** with validation
- **Context management** for stateful operations
- **Reduced token usage** through efficient protocols

---

## Architecture

```
┌─────────────────┐
│   AI Agent      │
│  (You)          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MCP Client     │
│  (SDK)          │
└────────┬────────┘
         │
    ┌────┴────┬─────────┬─────────┐
    ▼         ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│ File  │ │  DB   │ │  Web  │ │Custom │
│Server │ │Server │ │Server │ │Server │
└───────┘ └───────┘ └───────┘ └───────┘
```

---

## Common MCP Server Types

### 1. File System Server

**Capabilities:**
- Read/write files
- List directories
- Search files
- Watch for changes

**Example Usage:**

```python
# Read a file
content = mcp.read_file("src/main.py")

# Write a file
mcp.write_file("output.txt", "Hello, world!")

# List directory
files = mcp.list_directory("src/", pattern="*.py")

# Search
results = mcp.search_files(pattern="TODO", directory="src/")
```

**Benefits:**
- Handles encoding automatically
- Validates paths
- Manages permissions
- Atomic writes

---

### 2. Database Server

**Capabilities:**
- Execute SQL queries
- Schema introspection
- Migrations
- Connection pooling

**Example Usage:**

```python
# Query database
users = mcp.query("SELECT * FROM users WHERE active = true")

# Get schema
schema = mcp.get_schema("users")

# Execute migration
mcp.execute_migration("001_add_email_column.sql")

# Transaction support
with mcp.transaction():
    mcp.execute("INSERT INTO users ...")
    mcp.execute("UPDATE profiles ...")
```

**Benefits:**
- Automatic SQL injection prevention
- Connection pooling
- Transaction management
- Schema versioning

---

### 3. Web/HTTP Server

**Capabilities:**
- Make HTTP requests
- Handle authentication
- Parse responses
- Rate limiting

**Example Usage:**

```python
# GET request
response = mcp.http_get("https://api.example.com/users")

# POST with JSON
response = mcp.http_post(
    "https://api.example.com/users",
    json={"name": "John", "email": "john@example.com"}
)

# With authentication
mcp.set_auth_header("Bearer", token)
response = mcp.http_get("https://api.example.com/protected")
```

**Benefits:**
- Handles retries automatically
- Manages rate limits
- Parses JSON/XML
- Cookie management

---

### 4. Git Server

**Capabilities:**
- Repository operations
- Commit history
- Branch management
- Diff generation

**Example Usage:**

```python
# Get commit history
commits = mcp.git_log(limit=10)

# Get diff
diff = mcp.git_diff("main", "feature-branch")

# Create branch
mcp.git_create_branch("new-feature")

# Commit changes
mcp.git_commit("Add new feature", files=["src/main.py"])
```

**Benefits:**
- Handles git complexity
- Validates operations
- Manages conflicts
- Branch strategies

---

### 5. Search Server

**Capabilities:**
- Full-text search
- Code search
- Semantic search
- Vector similarity

**Example Usage:**

```python
# Text search
results = mcp.search("authentication", scope="codebase")

# Code search with filters
results = mcp.code_search(
    pattern="def authenticate",
    language="python",
    directory="src/"
)

# Semantic search (RAG)
results = mcp.semantic_search(
    query="How do I implement caching?",
    top_k=5
)
```

**Benefits:**
- Fast indexed search
- Language-aware parsing
- Relevance ranking
- Context extraction

---

### 6. Container/Docker Server

**Capabilities:**
- Manage containers
- Build images
- Container logs
- Health checks

**Example Usage:**

```python
# List containers
containers = mcp.docker_ps()

# Start container
mcp.docker_start("app-container")

# Get logs
logs = mcp.docker_logs("app-container", tail=100)

# Build image
mcp.docker_build(".", tag="myapp:latest")
```

**Benefits:**
- Handles Docker API
- Container orchestration
- Resource management
- Log streaming

---

### 7. Monitoring Server

**Capabilities:**
- Query metrics
- Check health
- View dashboards
- Alerting

**Example Usage:**

```python
# Query Prometheus
metrics = mcp.prometheus_query(
    'rate(http_requests_total[5m])'
)

# Check service health
health = mcp.health_check("database")

# Get alerts
alerts = mcp.get_active_alerts()
```

**Benefits:**
- Unified monitoring interface
- Metric aggregation
- Alert correlation
- Dashboard generation

---

## Project-Specific MCP Servers

> **Customize this section** for your project's MCP servers.

### Example: AIDB MCP Server

**Location:** `mcp_server/server.py`
**Port:** 8091
**Purpose:** RAG queries, inference, database access

**Capabilities:**

```python
# RAG queries
context = mcp.rag_query("How do I add authentication?")

# Inference with multiple models
response = mcp.parallel_inference(
    prompt="Write a binary search function",
    models=["qwen", "coder", "deepseek"]
)

# Database queries
results = mcp.db_query("SELECT * FROM design_decisions")

# Tool access
tools = mcp.list_available_tools()
```

**Configuration:**

```yaml
# .mcp/aidb-config.yaml
server:
  name: aidb-mcp
  host: localhost
  port: 8091

capabilities:
  rag_enabled: true
  parallel_inference: true
  database_access: true

models:
  - name: qwen3-4b
    endpoint: http://localhost:8000
  - name: qwen2.5-coder
    endpoint: http://localhost:8001
  - name: deepseek-coder
    endpoint: http://localhost:8003

---

### Planned: Code Migration MCP Tools (Python → TypeScript)

As part of the language‑modernization plan, this project will gradually introduce MCP tools that help agents reason about and migrate Python helpers to TypeScript without manual, ad‑hoc shell scripting.

**Conceptual capabilities (to be implemented later):**

- `code.search_python_targets`  
  - Find Python functions and scripts matching a given name or pattern across this repository.
  - Return locations, signatures, and brief summaries suitable for AIDB ingestion.

- `code.summarize_contract`  
  - Analyze a Python function or CLI entry point.
  - Emit a JSON schema describing inputs/outputs (for use as a shared contract between Python and TypeScript twins).

- `code.propose_ts_port`  
  - Given a contract and representative examples, draft a TypeScript implementation (CLI or module) that mirrors the Python behavior.
  - Designed to plug into local models (Lemonade/vLLM) and AIDB for context.

These tools will sit alongside existing servers (AIDB MCP, mcp-nixos, github-mcp, postgres-mcp) and act as the “glue layer” for codebase modernization. Implementation details will live in dedicated MCP server repos; this document remains the high‑level guide to their intended use.
```

---

## Using MCP Servers

### Basic Pattern

```python
# 1. Import MCP client
from mcp import Client

# 2. Initialize
mcp = Client(server_url="http://localhost:8091")

# 3. Use capabilities
result = mcp.capability_name(parameters)

# 4. Handle results
if result.success:
    print(result.data)
else:
    print(f"Error: {result.error}")
```

### Error Handling

```python
from mcp import Client, MCPError

mcp = Client(server_url="http://localhost:8091")

try:
    result = mcp.query_database("SELECT * FROM users")
except MCPError as e:
    # Handle MCP-specific errors
    print(f"MCP Error: {e.code} - {e.message}")
except Exception as e:
    # Handle general errors
    print(f"Error: {e}")
```

### Async Usage

```python
import asyncio
from mcp import AsyncClient

async def main():
    mcp = AsyncClient(server_url="http://localhost:8091")

    # Parallel operations
    results = await asyncio.gather(
        mcp.read_file("file1.txt"),
        mcp.read_file("file2.txt"),
        mcp.read_file("file3.txt")
    )

    return results

# Run
results = asyncio.run(main())
```

---

## Configuration

### Server Discovery

MCP servers can be discovered through:

1. **Configuration file:** `.mcp/config.yaml`
2. **Environment variables:** `MCP_SERVER_URL`
3. **Auto-discovery:** Network scanning (if enabled)

### Example Configuration

```yaml
# .mcp/config.yaml
version: "1.0"

servers:
  # File system operations
  - name: filesystem
    type: filesystem
    enabled: true
    root_directory: /project

  # Database access
  - name: database
    type: postgresql
    enabled: true
    connection:
      host: localhost
      port: 5432
      database: appdb
      user: app_user
      # Password from environment: $DB_PASSWORD

  # Custom application server
  - name: aidb-mcp
    type: custom
    enabled: true
    url: http://localhost:8091
    capabilities:
      - rag_query
      - parallel_inference
      - database_access

  # Monitoring
  - name: prometheus
    type: metrics
    enabled: true
    url: http://localhost:9090

# Global settings
settings:
  timeout: 30
  retry_attempts: 3
  retry_delay: 1
```

---

## Best Practices

### 1. Use MCP Instead of Raw Commands

**❌ Don't:**
```python
import subprocess
output = subprocess.run(["grep", "-r", "pattern", "."], capture_output=True)
```

**✅ Do:**
```python
results = mcp.search_files(pattern="pattern", directory=".")
```

**Why:** MCP provides error handling, validation, and cleaner interfaces.

### 2. Batch Operations

**❌ Don't:**
```python
for file in files:
    content = mcp.read_file(file)
    process(content)
```

**✅ Do:**
```python
contents = mcp.read_files_batch(files)
for content in contents:
    process(content)
```

**Why:** Batch operations reduce round trips and improve performance.

### 3. Handle Errors Gracefully

**❌ Don't:**
```python
result = mcp.query_database("SELECT * FROM users")
print(result[0]['name'])  # May crash
```

**✅ Do:**
```python
result = mcp.query_database("SELECT * FROM users")
if result.success and result.data:
    print(result.data[0]['name'])
else:
    print(f"Query failed: {result.error}")
```

### 4. Use Context Managers

**❌ Don't:**
```python
mcp = Client("http://localhost:8091")
result = mcp.query(...)
# May not clean up properly
```

**✅ Do:**
```python
with Client("http://localhost:8091") as mcp:
    result = mcp.query(...)
# Automatically closes connection
```

---

## Security Considerations

### Authentication

```python
# Token-based
mcp = Client(
    server_url="http://localhost:8091",
    auth_token="your-api-token"
)

# Certificate-based
mcp = Client(
    server_url="https://localhost:8091",
    cert_file="client.crt",
    key_file="client.key"
)
```

### Rate Limiting

```python
# Configure rate limits
mcp = Client(
    server_url="http://localhost:8091",
    rate_limit=100,  # requests per minute
    burst=10          # burst size
)
```

### Sandboxing

```python
# Restrict file access
mcp = Client(
    server_url="http://localhost:8091",
    allowed_paths=["/project", "/tmp"],
    denied_paths=["/etc", "/root"]
)
```

---

## Troubleshooting

### Connection Issues

```bash
# Check if server is running
curl http://localhost:8091/health

# Check server logs
docker logs mcp-server

# Test network connectivity
nc -zv localhost 8091
```

### Permission Errors

```bash
# Check file permissions
ls -la /path/to/file

# Check user running MCP server
ps aux | grep mcp-server

# Verify configuration
cat .mcp/config.yaml
```

### Performance Issues

```python
# Enable debugging
mcp = Client(
    server_url="http://localhost:8091",
    debug=True,
    log_level="DEBUG"
)

# Monitor response times
import time
start = time.time()
result = mcp.query(...)
print(f"Query took {time.time() - start:.2f}s")
```

---

## Advanced Features

### Streaming Responses

```python
# Stream large file
for chunk in mcp.read_file_stream("large-file.log"):
    process(chunk)

# Stream query results
for row in mcp.query_stream("SELECT * FROM large_table"):
    process(row)
```

### Caching

```python
# Enable response caching
mcp = Client(
    server_url="http://localhost:8091",
    cache_enabled=True,
    cache_ttl=300  # 5 minutes
)

# Query will use cache if available
result = mcp.query("SELECT * FROM static_data")
```

### Transactions

```python
# Database transactions
with mcp.transaction() as tx:
    tx.execute("INSERT INTO users ...")
    tx.execute("UPDATE profiles ...")
    tx.commit()  # or tx.rollback()
```

---

## Creating Custom MCP Servers

### Basic Server Structure

```python
from mcp import MCPServer, capability

class CustomMCPServer(MCPServer):
    def __init__(self):
        super().__init__(name="custom-server")

    @capability("custom_query")
    def custom_query(self, param1, param2):
        """Custom capability implementation."""
        result = self.process(param1, param2)
        return {"success": True, "data": result}

    @capability("batch_operation")
    async def batch_operation(self, items):
        """Async batch operation."""
        results = await asyncio.gather(
            *[self.process_item(item) for item in items]
        )
        return {"success": True, "data": results}

# Run server
if __name__ == "__main__":
    server = CustomMCPServer()
    server.run(host="localhost", port=8092)
```

---

## Reference

### MCP Client API

```python
# Connection
Client(server_url, auth_token=None, timeout=30)

# Common methods
.read_file(path)
.write_file(path, content)
.list_directory(path, pattern=None)
.query(sql)
.execute(sql, params)
.http_get(url, headers=None)
.http_post(url, data=None, json=None)
.search(query, scope="all")
```

### Configuration Schema

```yaml
version: string              # Config version
servers: []                  # List of servers
  - name: string            # Server name
    type: string            # Server type
    enabled: boolean        # Enable/disable
    url: string             # Server URL
    capabilities: []        # List of capabilities
settings:                    # Global settings
  timeout: int              # Request timeout
  retry_attempts: int       # Retry count
  retry_delay: int          # Retry delay (seconds)
```

---

## Resources

- **MCP Specification:** https://modelcontextprotocol.io
- **Server Implementations:** https://github.com/modelcontextprotocol/servers
- **Client SDKs:** Available for Python, JavaScript, Go, Rust

---

**Last Updated:** 2025-12-03
**Maintainer:** [Your Team]
