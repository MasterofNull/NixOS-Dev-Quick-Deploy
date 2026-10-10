---
doc_type: reference
title: "Wiki: Aidb"
subsystem: aidb
generated: 2026-10-10T08:04:22.514180Z
graph_generated: 2026-10-10T07:31:33Z
graph_nodes: 488
---

# Aidb

> AIDB RAG server, Qdrant collections, knowledge ingestion, semantic retrieval

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `issue_tracker.py` | Issue Tracking System for Production Errors | complex |
| `server.py` | Advanced AIDB MCP server with monitoring, catalog bootstrap, and sandboxing. | complex |
| `circuit_breaker.py` | Circuit Breaker Implementation for AIDB → Hybrid Coordinator calls | moderate |
| `codemachine_client.py` | CodeMachine-CLI Integration Client for AIDB MCP | moderate |
| `cve_endpoints.py` | Kernel CVE API Endpoints | moderate |
| `discovery_api.py` | Progressive Disclosure Discovery API | moderate |
| `discovery_endpoints.py` | Discovery Endpoints Integration for AIDB MCP Server | moderate |
| `document_importer.py` | Document Importer for RAG Knowledge Base | moderate |
| `garbage_collector.py` | Garbage Collection System for Hybrid Coordinator | moderate |
| `health_check.py` | Comprehensive Health Check System | moderate |
| `kernelorg_client.py` | kernel.org Release Tracker | moderate |
| `llama_cpp_tool_agent.py` | llama.cpp Tool-Enabled Agent | moderate |
| `mindsdb_client.py` | MindsDB Integration Client for AIDB MCP | moderate |
| `ml_engine.py` | ML Engine - Integrated Machine Learning Capabilities | moderate |
| `nvd_client.py` | NVD (National Vulnerability Database) API Client | moderate |
| `parallel_inference.py` | Constraint-Engineered Development (CED) Parallel Inference Framework | moderate |
| `query_validator.py` | Query Validation Module for AIDB | moderate |
| `pipeline.py` | Reusable RAG pipeline helpers for AIDB. | moderate |
| `schema.py` | SQLAlchemy table definitions for AIDB: document embeddings, CVEs, kernel releases, and CVE | moderate |
| `settings_loader.py` | Loads and validates AIDB service configuration from env vars, YAML config files, and SOPS  | moderate |
| `tool_discovery.py` | Tool Discovery Engine | moderate |
| `vector_sync.py` | Postgres <-> Qdrant vector sync primitives for AIDB (pure, import-light). | moderate |
| `vscode_telemetry.py` | VSCode Extension Telemetry Router for AIDB MCP Server | moderate |
| `__init__.py` | AIDB MCP server package. | simple |
| `gc_worker.py` | AIDB stale-vector garbage-collection worker (Phase 6.2.3). | simple |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `register_cve_routes` | `cve_endpoints.py` | Register kernel CVE API routes on FastAPI app. |
| `AgentDiscoveryAPI.list_capabilities` | `discovery_api.py` | List available capabilities at specified disclosure level |
| `register_discovery_routes` | `discovery_endpoints.py` | Register discovery API routes in AIDB MCP server |
| `LlamaCppToolAgent.generate_with_tools` | `llama_cpp_tool_agent.py` | Generate response with tool calling capability |
| `MCPServer.__init__` | `server.py` | __init__(self, settings: Settings) |
| `MonitoringServer._register_routes` | `server.py` | _register_routes(self) -> None |
| `load_settings` | `settings_loader.py` | Loads Settings by merging YAML config file, env vars, and SOPS secrets; validates required |
| `store_workflow_in_db` | `codemachine_client.py` | Store CodeMachine workflow in AIDB PostgreSQL for persistence |
| `AgentDiscoveryAPI.get_capability` | `discovery_api.py` | Get detailed information about a specific capability |
| `AgentDiscoveryAPI.get_quickstart` | `discovery_api.py` | Level 0: Quick start guide for agents |
| `ChunkingStrategy.chunk_by_paragraphs` | `document_importer.py` | Chunk text by paragraphs with overlap |
| `ChunkingStrategy.chunk_code_by_functions` | `document_importer.py` | Chunk code by logical blocks (functions, classes) |
| `ChunkingStrategy.split_oversized_chunk` | `document_importer.py` | Split an oversized chunk into bounded subchunks. |
| `DocumentImporter.import_directory` | `document_importer.py` | Import all supported files from directory |
| `DocumentImporter.import_file` | `document_importer.py` | Import a single file |
| `MetadataExtractor.extract_from_code` | `document_importer.py` | Extract metadata from code files |
| `GarbageCollector.cleanup_qdrant_orphans` | `garbage_collector.py` | Remove vectors from Qdrant that have no corresponding database entry. |
| `GarbageCollector.deduplicate_solutions` | `garbage_collector.py` | Remove near-duplicate solutions based on embedding similarity. |
| `GarbageCollector.prune_low_value_solutions` | `garbage_collector.py` | Prune low-value solutions when approaching max_solutions limit. |
| `GarbageCollector.run_full_gc` | `garbage_collector.py` | Run complete garbage collection cycle. |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `AgentDiscoveryAPI` | `discovery_api.py` | Progressive disclosure API for AI agents |
| `GarbageCollector` | `garbage_collector.py` | Manages storage cleanup for continuous learning system. |
| `HealthChecker` | `health_check.py` | Comprehensive health check system |
| `IssueTracker` | `issue_tracker.py` | Track and manage production issues |
| `LlamaCppToolAgent` | `llama_cpp_tool_agent.py` | Enhanced llama.cpp agent with full tool access |
| `MindsDBClient` | `mindsdb_client.py` | Client for interacting with MindsDB AI data platform |
| `MLEngine` | `ml_engine.py` | Integrated ML capabilities for AIDB MCP. |
| `NVDClient` | `nvd_client.py` | Client for NIST National Vulnerability Database API 2.0. |
| `MCPServer` | `server.py` | Core AIDB MCP server class: wires FastAPI app, VectorStore, ToolRegistry, SandboxExecutor, |
| `MonitoringServer` | `server.py` | Prometheus-compatible metrics server sidecar: exposes /metrics endpoint with AIDB request  |
| `ToolDiscoveryEngine` | `tool_discovery.py` | Autonomous tool and skill discovery system |
| `CircuitBreaker` | `circuit_breaker.py` | Circuit Breaker Pattern Implementation |
| `CodeMachineClient` | `codemachine_client.py` | Client for interacting with CodeMachine-CLI orchestration engine |
| `ChunkingStrategy` | `document_importer.py` | Strategies for chunking different document types |
| `DocumentImporter` | `document_importer.py` | Import documents into Qdrant knowledge base |

## Related Documentation

- `docs/architecture/memory-system-design.md`
- `docs/agent-guides/62-MEMORY-SYSTEM.md`

## Coverage

- **Nodes**: 488 total (33 files, 364 functions, 88 classes)
- **Path prefix**: `ai-stack/mcp-servers/aidb/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-10-10T07:31:33Z)
