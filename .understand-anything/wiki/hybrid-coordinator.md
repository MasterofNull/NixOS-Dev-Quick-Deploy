---
doc_type: reference
title: "Wiki: Hybrid Coordinator"
subsystem: hybrid-coordinator
generated: 2026-07-02T01:49:23.496619Z
graph_generated: 2026-07-01T16:10:40Z
graph_nodes: 685
---

# Hybrid Coordinator

> AI request routing, tool execution, intent classification, progressive disclosure

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*  
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `session_builders.py` | Builds and validates workflow run sessions; resolves orchestration teams, isolation profil | complex |
| `status_service.py` | Provides HTTP status and health endpoints that aggregate metrics from all coordinator subs | complex |
| `ai_coordinator.py` | Core AI coordinator routing engine: infers routing profiles, detects query complexity, man | complex |
| `ai_coordinator_handlers.py` | Primary HTTP request handlers for the AI coordinator covering SSE streaming, model routing | complex |
| `auto_tool_select_handlers.py` | Handles automatic tool selection for agent tasks including catalog management, plan enrich | complex |
| `generator_critic.py` | Implements the generator-critic pattern to evaluate LLM responses across completeness, acc | complex |
| `model_coordinator.py` | Coordinates multi-model task routing by classifying task types into archetypes and selecti | complex |
| `model_fleet_manager.py` | Manages a fleet of LLM model instances tracking health state, success/error rates, and ret | complex |
| `openai_a2a_handlers.py` | Implements OpenAI-compatible agent-to-agent (A2A) HTTP handlers that proxy chat/completion | complex |
| `http_server_impl.py` | Central aiohttp HTTP server implementation for the hybrid-coordinator: registers all route | complex |
| `tooling_manifest.py` | Builds the full workflow tool catalog and tooling manifest for agent task planning. | complex |
| `memory_broker.py` | Central memory broker managing typed agent memory with write/read/contradiction detection  | complex |
| `core/config.py` | Central coordinator configuration (937 lines). Defines Config (env-driven settings for lla | complex |
| `core/llm_client.py` | Async LLM HTTP client (707 lines) with circuit-breaker and retry integration. LLMClient wr | complex |
| `core/route_handler.py` | Core routing engine (2209 lines). Orchestrates query dispatch: classifies task complexity, | complex |
| `extensions/advanced_features.py` | Comprehensive advanced capabilities module (2186 lines). Implements AgentPoolManager (mult | complex |
| `extensions/continuous_learning.py` | Continuous learning pipeline (1511 lines). ContinuousLearningPipeline captures interaction | complex |
| `ContinuousLearningPipeline` | End-to-end continuous learning orchestrator. Ingests interaction data, filters for high-qu | complex |
| `route_search` | Top-level query routing function. Classifies complexity, checks backend cache, selects loc | complex |
| `mcp_handlers.py` | Core MCP tool dispatch handler for the hybrid coordinator — routes 40+ tools including QA  | complex |
| `model_optimization.py` | Training data capture, PII detection/anonymization, fine-tuning job tracking, distillation | complex |
| `context_compression.py` | Context compression engine — reduces token usage in conversation history while preserving  | complex |
| `context_lifecycle_manager.py` | Manages the full lifecycle of LLM context windows — eviction, scoring, and route registrat | complex |
| `memory_context_handlers.py` | HTTP route handlers for memory and context operations — store/recall memories, harness eva | complex |
| `memory_manager.py` | Core agent memory persistence in Qdrant — stores/recalls typed memories with duplicate det | complex |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `_build_workflow_run_session` | `session_builders.py` | Constructs a fully populated workflow run session dict from blueprint, orchestration conte |
| `_ensure_session_runtime_fields` | `session_builders.py` | Ensures all required runtime fields (safety mode, budgets, team, consensus) are present an |
| `_build_orchestration_runtime_contract` | `session_builders.py` | Builds the runtime contract object encoding isolation profile, workspace mode, delegation  |
| `handle_status` | `status_service.py` | Aggregates health and performance metrics from all coordinator subsystems into a single JS |
| `route_by_complexity` | `ai_coordinator.py` | Routes a query to the optimal orchestration lane (local, remote, tool-calling, etc.) based |
| `infer_profile` | `ai_coordinator.py` | Infers the best routing profile for a task using task keywords, requested profile, and fal |
| `detect_query_complexity` | `ai_coordinator.py` | Analyzes a query to detect its complexity archetype (planning, retrieval, implementation,  |
| `runtime_defaults` | `ai_coordinator.py` | Builds the default runtime registry entries for all supported orchestration lanes with swi |
| `init` | `ai_coordinator_handlers.py` | Initializes the coordinator handler module by loading model catalog, routing policy, and w |
| `handle_auto_select` | `auto_tool_select_handlers.py` | Selects the best tools for an incoming task by scoring tool catalog entries against task k |
| `critique_response` | `generator_critic.py` | Evaluates an LLM response across all critic dimensions and assembles a CriticEvaluation wi |
| `_proxy_openai_request_via_coordinator` | `openai_a2a_handlers.py` | Core proxy function that translates an OpenAI chat completion request into a coordinator d |
| `handle_trading_tools` | `trading_handlers.py` | handle_trading_tools() in trading_handlers.py |
| `init` | `http_server_impl.py` | init() in http_server_impl.py |
| `_inject_semantic_tooling` | `http_server_impl.py` | _inject_semantic_tooling() in http_server_impl.py |
| `_execute_query_search` | `http_server_impl.py` | _execute_query_search() in http_server_impl.py |
| `run_http_mode` | `http_server_impl.py` | run_http_mode() in http_server_impl.py |
| `handle_hints` | `hints_handlers.py` | handle_hints() in hints_handlers.py |
| `reflect_on_retrieval` | `rag_reflection.py` | reflect_on_retrieval() in rag_reflection.py |
| `workflow_tool_catalog` | `tooling_manifest.py` | workflow_tool_catalog() in tooling_manifest.py |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `ModelCoordinator` | `model_coordinator.py` | Singleton coordinator that classifies tasks and routes them to appropriate model profiles  |
| `InferenceParamManager` | `inference_param_manager.py` | InferenceParamManager class in inference_param_manager.py |
| `IntentClassifier` | `intent_classifier.py` | Semantic intent classifier using embeddings and routing map |
| `MemoryBroker` | `memory_broker.py` | Central memory broker with typed storage, contradiction detection, and temporal validation |
| `MemorySuperseder` | `memory_superseder.py` | Memory supersession engine for invalidating outdated facts |
| `MLFQScheduler` | `mlfq_scheduler.py` | MLFQ task scheduler with thermal-aware concurrency control |
| `TrainingDataCapture` | `model_optimization.py` | Captures high-quality agent interactions as JSONL training examples with PII filtering and |
| `PromptInjectionScanner` | `prompt_injection.py` | Regex + heuristic scanner that detects prompt injection patterns (role override, jailbreak |
| `ContextCompressor` | `context_compression.py` | Compresses LLM context by summarizing older turns and removing low-signal content to stay  |
| `ContextLifecycleManager` | `context_lifecycle_manager.py` | Manages context window lifecycle across sessions — evicts stale context, scores relevance, |
| `MultiTurnContextManager` | `multi_turn_context.py` | Stateful manager for multi-turn conversations — stores SessionState per session, applies c |
| `QueryExpander` | `query_expansion.py` | Expands user queries with synonyms, related terms, and contextual signals to improve recal |
| `ResultReranker` | `query_expansion.py` | Reranks search results using BM25 + semantic similarity blend after initial retrieval. |
| `QueryExpansionReranking` | `query_expansion.py` | Orchestrates query expansion followed by multi-stage reranking pipeline. |
| `SearchRouter` | `search_router.py` | Routes hybrid search queries across Qdrant collections — selects collections, adjusts scor |

## Related Documentation

- `docs/architecture/AI-STACK-ARCHITECTURE.md`
- `docs/architecture/REQUEST-ROUTING-FLOW.md`
- `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`
- `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md`

## Coverage

- **Nodes**: 685 total (272 files, 310 functions, 88 classes)
- **Path prefix**: `ai-stack/mcp-servers/hybrid-coordinator/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-07-01T16:10:40Z)
