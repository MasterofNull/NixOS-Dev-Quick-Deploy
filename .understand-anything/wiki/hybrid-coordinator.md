---
doc_type: reference
title: "Wiki: Hybrid Coordinator"
subsystem: hybrid-coordinator
generated: 2026-10-10T08:04:22.471715Z
graph_generated: 2026-10-10T07:31:33Z
graph_nodes: 2795
---

# Hybrid Coordinator

> AI request routing, tool execution, intent classification, progressive disclosure

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `config.py` | Hybrid-coordinator configuration: Config, RoutingConfig, PerformanceWindow, | complex |
| `llm_client.py` | LLM Client for Workflow Execution | complex |
| `route_handler.py` | Route search handler for hybrid-coordinator. | complex |
| `eval_runner.py` | eval_runner.py — Continuous spec-driven evaluation (Phase 54.6 + 60.5) | complex |
| `advanced_features.py` | Advanced Features Integration for Hybrid Coordinator | complex |
| `ai_coordinator.py` | Helpers for the ai-coordinator control and delegation surfaces. | complex |
| `ai_coordinator_handlers.py` | AI coordinator, parity, skill, autoresearch, and research HTTP handlers. | complex |
| `auto_tool_select_handlers.py` | Autonomous tool auto-selection handlers. | complex |
| `continuous_learning.py` | Continuous Learning Pipeline | complex |
| `federation_sync.py` | Federation Sync Service for Hybrid Learning System | complex |
| `harness_sdk.py` | Hybrid Coordinator Harness SDK | complex |
| `interaction_tracker.py` | Interaction tracking, feedback recording, pattern extraction, and training-data archive | complex |
| `mcp_handlers.py` | MCP tool definitions and dispatch for hybrid-coordinator. | complex |
| `model_coordinator.py` | model_coordinator.py — Model Role Classification and Dual-Model Routing (Phase 12.1/12.2) | complex |
| `model_fleet_manager.py` | Model Fleet Manager — Phase 15.1 | complex |
| `model_optimization.py` | Model Optimization Integration for Hybrid Coordinator | complex |
| `openai_a2a_handlers.py` | OpenAI-compat and A2A HTTP handlers for the hybrid-coordinator server. | complex |
| `http_server_impl.py` | HTTP server module for the hybrid-coordinator. | complex |
| `intent_classifier.py` | intent_classifier.py — Semantic intent classification before routing (Phase 54.2) | complex |
| `hints_engine_impl.py` | Core implementation file (2793 lines) containing the HintsEngine class and _detect_file_ty | complex |
| `llm_router.py` | Intelligent LLM Router - Maximize Local/Free, Minimize Paid | complex |
| `memory_manager.py` | Agent memory store/recall module for hybrid-coordinator. | complex |
| `progressive_disclosure.py` | Progressive Disclosure API | complex |
| `search_router.py` | Search routing module for the hybrid-coordinator. | complex |
| `static_rules.py` | knowledge/static_rules.py — Static workflow rules, agent strengths, and routing data. | complex |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `handle_agent_events_post` | `agent_service.py` | POST /api/agent-events — ingest a delegation/lesson/decision event. |
| `_select_route_collections` | `route_handler.py` | Choose a bounded collection subset instead of fanning out across all stores. |
| `route_search` | `route_handler.py` | Route query to SQL, semantic, keyword, tree, or hybrid search. |
| `classify` | `task_classifier.py` | Classify task and return complexity with optional optimized prompt. |
| `route_by_complexity` | `ai_coordinator.py` | Route query to appropriate model based on complexity. |
| `runtime_defaults` | `ai_coordinator.py` | Builds the default runtime registry entries for all supported orchestration lanes with swi |
| `handle_ai_coordinator_delegate` | `ai_coordinator_handlers.py` | Run a bounded delegated task through the selected ai-coordinator lane. |
| `auto_improve_response` | `auto_quality_improver.py` | Automatically improve response quality through iterative refinement. |
| `fetch_browser_research` | `browser_research.py` | fetch_browser_research(*, urls: List[Any], selectors: Optional[List[Any]]=None, max_text_c |
| `ContinuousLearningPipeline.__init__` | `continuous_learning.py` | __init__(self, settings, qdrant_client, postgres_client) |
| `main` | `continuous_learning_daemon.py` | Run continuous learning daemon |
| `run_harness_evaluation` | `harness_eval.py` | Deterministic harness eval scorecard for prompt+retrieval behavior. |
| `dispatch_tool` | `mcp_handlers.py` | Dispatch an MCP tool call by name. |
| `run_qa_check_as_dict` | `mcp_handlers.py` | Executes an aq-qa health check phase via subprocess and returns structured dict results. |
| `ModelCoordinator.classify_and_route` | `model_coordinator.py` | Classify a task and route to appropriate model(s). |
| `run_distillation_pipeline` | `model_optimization.py` | Run a bounded distillation/compression pipeline and persist artifacts. |
| `_session_to_a2a_artifacts` | `openai_a2a_handlers.py` | _session_to_a2a_artifacts(session: Dict[str, Any]) -> List[Dict[str, Any]] |
| `handle_a2a_rpc` | `openai_a2a_handlers.py` | handle_a2a_rpc(request: web.Request) -> web.Response |
| `check_quality_health` | `quality_monitor.py` | Check overall quality health and generate alerts. |
| `run_curated_research_workflow` | `research_workflows.py` | run_curated_research_workflow(*, workflow_slug: str, inputs: Optional[Dict[str, Any]]=None |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `Config` | `config.py` | Hybrid coordinator configuration. |
| `LLMClient` | `llm_client.py` | Unified LLM client interface. |
| `DecisionPointDetector` | `advisor_detector.py` | Detects when executor should consult advisor for guidance. |
| `ContinuousLearningPipeline` | `continuous_learning.py` | Learns from user interactions to improve system performance |
| `FederatedIntegration` | `federated_integration.py` | Integration layer for federated learning in hybrid coordinator. |
| `FederationSyncManager` | `federation_sync.py` | Manages synchronization between federation nodes |
| `GarbageCollector` | `garbage_collector.py` | Manages storage cleanup for continuous learning system. |
| `HarnessClient` | `harness_sdk.py` | class HarnessClient() |
| `ModelCoordinator` | `model_coordinator.py` | Coordinates work distribution across models. |
| `RemoteLLMFeedback` | `remote_llm_feedback.py` | API for remote LLMs to report response quality and request refinement |
| `InferenceParamManager` | `inference_param_manager.py` | InferenceParamManager class in inference_param_manager.py |
| `ContextCompressor` | `context_compression.py` | Compress retrieved context to fit within token budgets |
| `ContextLifecycleManager` | `context_lifecycle_manager.py` | 3-tier session context lifecycle: Hot → Warm → Cold. |
| `EmbeddingCache` | `embedding_cache.py` | Redis-based cache for embeddings |
| `HintsEngine` | `hints_engine_impl.py` | Ranked workflow hints engine for the NixOS AI stack. |

## Related Documentation

- `docs/architecture/AI-STACK-ARCHITECTURE.md`
- `docs/architecture/REQUEST-ROUTING-FLOW.md`
- `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`
- `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md`

## Coverage

- **Nodes**: 2795 total (272 files, 2280 functions, 235 classes)
- **Path prefix**: `ai-stack/mcp-servers/hybrid-coordinator/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-10-10T07:31:33Z)
