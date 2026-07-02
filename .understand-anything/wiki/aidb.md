---
doc_type: reference
title: "Wiki: Aidb"
subsystem: aidb
generated: 2026-07-02T01:49:23.500565Z
graph_generated: 2026-07-01T16:10:40Z
graph_nodes: 95
---

# Aidb

> AIDB RAG server, Qdrant collections, knowledge ingestion, semantic retrieval

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*  
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `cve_endpoints.py` | FastAPI route registration for kernel CVE database: list CVEs, fetch details, scan hosts,  | complex |
| `discovery_api.py` | Agent-facing capability discovery API: enumerates AIDB system capabilities, endpoints, and | complex |
| `health_check.py` | Kubernetes-style health probe system (liveness, readiness, startup) for the AIDB service;  | complex |
| `ml_engine.py` | ML engine providing semantic similarity, clustering, anomaly detection, and quick helper m | complex |
| `query_validator.py` | Validates and sanitizes vector search requests: enforces collection allowlist, rate limiti | complex |
| `tool_discovery.py` | Discovers and indexes MCP tool definitions from running MCP servers: probes endpoints, cac | complex |
| `vscode_telemetry.py` | Collects and scrubs VSCode extension telemetry events: enforces PII redaction, maintains r | complex |
| `codemachine_client.py` | codemachine_client.py (362 lines) in aidb. | complex |
| `garbage_collector.py` | garbage_collector.py (448 lines) in aidb. | complex |
| `kernelorg_client.py` | kernelorg_client.py (330 lines) in aidb. | complex |
| `llama_cpp_tool_agent.py` | llama_cpp_tool_agent.py (474 lines) in aidb. | complex |
| `nvd_client.py` | nvd_client.py (443 lines) in aidb. | complex |
| `parallel_inference.py` | parallel_inference.py (285 lines) in aidb. | complex |
| `discovery_endpoints.py` | FastAPI route handlers that expose AgentDiscoveryAPI over HTTP: system info, quickstart, c | moderate |
| `interaction_history.py` | Stores and retrieves agent interaction history records backed by the schema module's docum | moderate |
| `cache.py` | Starlette middleware that caches GET responses in-memory with TTL, reducing redundant comp | moderate |
| `pipeline.py` | RAG pipeline: configures retrieval-augmented generation flow with Qdrant vector search, em | moderate |
| `registry_api.py` | In-memory MCP resource registry: register, list, and search resources exposed by the AIDB  | moderate |
| `schema.py` | SQLAlchemy table definitions for AIDB: document embeddings, CVEs, kernel releases, and CVE | moderate |
| `server.py` | Main AIDB MCP server: 3892-line core orchestrating vector store, tool registry, sandbox ex | moderate |
| `settings_loader.py` | Loads and validates AIDB service configuration from env vars, YAML config files, and SOPS  | moderate |
| `tool_discovery_daemon.py` | Background daemon that periodically triggers ToolDiscoveryEngine to refresh MCP tool index | moderate |
| `circuit_breaker.py` | circuit_breaker.py (191 lines) in aidb. | moderate |
| `document_importer.py` | document_importer.py (579 lines) in aidb. | moderate |
| `issue_tracker.py` | issue_tracker.py (611 lines) in aidb. | moderate |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `register_cve_routes` | `cve_endpoints.py` | Registers all CVE-related FastAPI routes on the app: list CVEs, get details, sync NVD, lis |
| `register_discovery_routes` | `discovery_endpoints.py` | Registers discovery HTTP routes: root, system-info, quickstart, capability list, and per-c |
| `run_gc_pass_sync` | `gc_worker.py` | Synchronous GC pass: identifies vector embeddings with no active document references older |
| `main` | `server.py` | Entry point: parses args, configures logging and tracing, initializes MCPServer, and start |
| `load_settings` | `settings_loader.py` | Loads Settings by merging YAML config file, env vars, and SOPS secrets; validates required |
| `main` | `tool_discovery_daemon.py` | Daemon entrypoint: loads settings and secrets, instantiates ToolDiscoveryEngine, runs peri |
| `create_health_endpoints` | `health_check.py` | Registers /health/live, /health/ready, /health/startup FastAPI routes using HealthChecker  |
| `run_parallel_inference` | `llm_parallel.py` | Fans out a list of prompts to the local LLM endpoint concurrently using asyncio.gather; re |
| `validate_collection_name` | `query_validator.py` | Validates collection name against ALLOWED_COLLECTIONS allowlist; raises HTTP 403 on unknow |
| `get_allowed_collections` | `query_validator.py` | Returns current ALLOWED_COLLECTIONS set; reads from env var AIDB_ALLOWED_COLLECTIONS. |
| `sanitize_query` | `query_validator.py` | Strips potential injection patterns and excessive whitespace from raw query strings before |
| `register_resource` | `registry_api.py` | Adds a new RegistryResource to the in-memory registry; idempotent on name collision. |
| `search_resources` | `registry_api.py` | Full-text search over registry resource names and descriptions; returns ranked matches. |
| `document_embeddings_table` | `schema.py` | Returns SQLAlchemy Table definition for document_embeddings; lazily creates table object b |
| `parse_skill_file` | `skills_loader.py` | Reads a skill markdown file from disk and returns a ParsedSkill; handles missing frontmatt |
| `collect_event` | `vscode_telemetry.py` | Receives a VscodeEvent, scrubs PII, appends to rolling buffer; drops oldest if buffer full |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `AgentDiscoveryAPI` | `discovery_api.py` | Main discovery class: compiles system info, enumerates capabilities by category/level, and |
| `HealthChecker` | `health_check.py` | Central health-check orchestrator: runs liveness, readiness, and startup probes; checks Po |
| `MLEngine` | `ml_engine.py` | ML engine for AIDB: semantic similarity scoring, clustering, anomaly detection over embedd |
| `VectorStore` | `server.py` | Abstraction over Qdrant + PostgreSQL: upsert, search, delete, and federated-query across c |
| `ToolRegistry` | `server.py` | Registry of MCP tool definitions: load, validate, and dispatch tool calls with risk-tier e |
| `SandboxExecutor` | `server.py` | Sandbox for safe tool execution: runs commands in restricted subprocess with timeout, reso |
| `FederationStore` | `server.py` | Federated search across multiple vector stores or remote AIDB instances; aggregates and re |
| `ToolDiscoveryEngine` | `tool_discovery.py` | Probes running MCP server endpoints to discover available tools; caches ToolMetadata and M |
| `InteractionHistoryStore` | `interaction_history.py` | Stores and queries agent interaction history records in PostgreSQL using schema-defined ta |
| `CacheMiddleware` | `cache.py` | Starlette BaseHTTPMiddleware: caches successful GET responses in a TTL dict; bypasses cach |
| `RateLimiter` | `query_validator.py` | Token-bucket rate limiter for AIDB query endpoints; enforces per-client request limits. |
| `RAGPipeline` | `pipeline.py` | RAG pipeline orchestrator: retrieves relevant documents from Qdrant, prepends them to cont |
| `MCPServer` | `server.py` | Core AIDB MCP server class: wires FastAPI app, VectorStore, ToolRegistry, SandboxExecutor, |
| `CircuitBreaker` | `server.py` | Circuit breaker pattern for external service calls: tracks failures, opens circuit on thre |
| `TieredRateLimiter` | `server.py` | Multi-tier rate limiter: enforces per-key, per-tier, and global request budgets for the AI |

## Related Documentation

- `docs/architecture/memory-system-design.md`
- `docs/agent-guides/62-MEMORY-SYSTEM.md`

## Coverage

- **Nodes**: 95 total (33 files, 16 functions, 34 classes)
- **Path prefix**: `ai-stack/mcp-servers/aidb/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-07-01T16:10:40Z)
