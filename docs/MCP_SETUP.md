# MCP Production Environment Setup

This guide provisions a production-ready Model Context Protocol (MCP) stack that
matches the architecture outlined in Anthropic's engineering blog. It covers
infrastructure requirements, helper tooling, and workflow conventions for both
Python and TypeScript/Deno MCP servers.

## Architecture Overview

```
+--------------------------------------------------------------+
|                        MCP Orchestration                     |
|                                                              |
|  +-----------------+      +-------------------+              |
|  | Progressive     | ---> | Tool Registry     |              |
|  | Discovery       |      | (PostgreSQL +     |              |
|  | (minimal/full)  | <--- | Redis cache)      |              |
|  +-----------------+      +-------------------+              |
|            |                            |                    |
|            v                            v                    |
|   +-----------------+        +-------------------------+     |
|   | Sandboxed Tool  | -----> | Vector Search (Qdrant)  |     |
|   | Execution       |        +-------------------------+     |
|   +-----------------+                                        |
|            |                                                 |
|            v                                                 |
|   Filesystem State + Redis session cache                     |
+--------------------------------------------------------------+
```

**Key capabilities**

- Progressive tool discovery (minimal/full) for token efficiency (~150k → 2k).
- Data filtering before responses return to the model.
- Sandboxed tool execution with `bubblewrap` or `firejail`.
- Unified state management across PostgreSQL, Redis, Qdrant, and the filesystem.

## Database Stack

| Service    | Purpose                              | Default Port | Notes |
|------------|--------------------------------------|--------------|-------|
| PostgreSQL | Persistent registry, tool metadata   | 5432         | Databases: `mcp`, `mcp_tools`, `mcp_logs` (user `mcp`). |
| Redis      | Cache, session state, job queues     | 6379         | Instance name `redis-mcp`, 512 MB with LRU eviction. |
| Qdrant     | Vector search & embeddings           | 6333 (HTTP), 6334 (gRPC) | Ready for semantic/RAG workloads. |

### Service management

```
sudo systemctl start postgresql
sudo systemctl start redis-mcp
sudo systemctl start qdrant
```

### Health checks

Use the `scripts/mcp-db-setup` helper to verify connectivity, credentials, and
configuration:

```
./scripts/mcp-db-setup
```

The script reports service status and validates each PostgreSQL database,
Redis configuration, and the Qdrant readiness endpoint.

## Python Environment (`pythonAiEnv`)

The Nix `pythonAiEnv` now includes MCP-focused libraries:

- `httpx`, `aiohttp`, `websockets` for high-performance HTTP/WebSocket stacks.
- `pydantic` for tool schema validation.
- `sqlalchemy`, `alembic`, `psycopg2` for relational workflows.
- `redis` for async caching and state management.

These packages complement the existing AI/LLM toolchain defined in
`templates/home.nix` and are available everywhere the environment is activated.

## Runtime & Sandboxing Tooling

Install the following utilities on the host to mirror the production reference
stack:

- `deno` – secure TypeScript runtime with built-in permission model.
- `bun` – fast JavaScript runtime suited for lightweight tooling.
- `bubblewrap`, `firejail` – Linux sandboxes used for tool execution isolation.
- `criu` – process checkpoint/restore for long-running jobs.
- `postgresql`, `redis` – CLI clients for direct database access.

## MCP Server Templates

Two ready-to-customise templates live in `templates/`:

1. **`mcp-server-template.py`** – Async Python template featuring:
   - Progressive tool disclosure with Redis + filesystem caching.
   - Automatic SQL schema creation and SQLAlchemy session management.
   - Redis-backed manifest cache (maintains 98.7 % token savings).
   - Bubblewrap/firejail sandbox integration for tool execution.
   - Qdrant semantic search helper via `httpx`.
   - Built-in `--self-test` for environment validation.

2. **`mcp-server-template.ts`** – TypeScript/Deno variant with:
   - Native Deno `WebSocket` server and secure permissions.
   - PostgreSQL + Redis integration using Deno ecosystem clients.
   - Sandboxed execution through `Deno.Command` wrappers.
   - Qdrant search utilities and readiness verification.
   - Shared configuration model with the Python template.

### Creating a new server

Use the lifecycle helper to scaffold a project:

```
./scripts/mcp-server init my-tools           # default python template
./scripts/mcp-server init -t deno rag-stack  # deno template
```

Start, stop, inspect logs, and run self-tests:

```
./scripts/mcp-server start my-tools
./scripts/mcp-server logs -f my-tools
./scripts/mcp-server test my-tools
./scripts/mcp-server stop my-tools
```

All generated servers live under `mcp-servers/` by default. Override with the
`MCP_SERVER_HOME` environment variable if you prefer a different location.

## Workflow Recommendations

1. **Progressive disclosure** – default to `minimal` mode, loading tool
   manifests lazily; switch to `full` only when necessary.
2. **Token budgets** – persist manifest caches (`.mcp_cache`) between runs to
   sustain the 98.7 % reduction described by Anthropic.
3. **Sandboxing** – configure `MCP_SANDBOX_RUNNER=bubblewrap` or `firejail` per
   deployment, and provide custom profiles when additional mounts are needed.
4. **State management** – store long-lived state in PostgreSQL, ephemeral data
   in Redis, and semantic artifacts in Qdrant collections (e.g. `semantic-search`).
5. **Observability** – pipe server logs through `scripts/mcp-server logs` and
   aggregate database metrics via `pg_stat_statements`, Redis INFO, and Qdrant
   telemetry endpoints.

## Troubleshooting

| Symptom | Resolution |
|---------|------------|
| `mcp-db-setup` reports PostgreSQL failures | Ensure the `mcp` role exists with access to `mcp`, `mcp_tools`, and `mcp_logs`. Check local `pg_hba.conf` rules. |
| Redis reports incorrect eviction policy | Update `/etc/redis/redis-mcp.conf` with `maxmemory-policy allkeys-lru` and restart the service. |
| Qdrant readiness endpoint fails | Confirm the service is enabled (`sudo systemctl enable --now qdrant`) and that TLS/firewall rules permit local traffic. |
| Sandboxed tool execution fails | Verify `bubblewrap`/`firejail` installation and adjust sandbox profiles for required mounts/network access. |
| Self-test cannot reach Qdrant | Populate the `semantic-search` collection or update the URL via `MCP_QDRANT_URL`. |

## Next Steps

- Extend the templates with organisation-specific tools and authentication.
- Configure CI pipelines to run `scripts/mcp-db-setup` and `scripts/mcp-server test`.
- Integrate telemetry (OpenTelemetry, Prometheus) for production monitoring.
- Harden sandbox profiles by whitelisting required binaries and paths only.

With these components in place, your environment is ready to build and deploy
robust MCP toolchains with confidence.
