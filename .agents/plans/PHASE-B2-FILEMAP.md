# Phase B.2 File Map — hybrid-coordinator Python modules
**Generated:** 2026-05-15 (Claude, Q-4 completion after Qwen delegation failure)
**Source:** `ai-stack/mcp-servers/hybrid-coordinator/*.py` — 121 files
**Subdirs:** `core/` · `workflow/` · `knowledge/` · `extensions/` · `tests/`

---

## core/ — Server startup, auth, config, health, LLM client/router, routing

| File | Reason |
|------|--------|
| `server.py` | Entry point, startup wiring |
| `http_server.py` | HTTP handler + route registration |
| `config.py` | Config loading |
| `auth_middleware.py` | Auth + loopback bypass |
| `metrics.py` | Prometheus metrics definitions |
| `circuit_breaker.py` | Resilience — request circuit breaker |
| `rate_limiter.py` (if present) | Rate limiting |
| `llm_client.py` | Outbound LLM calls (switchboard) |
| `llm_router.py` | LLM routing logic |
| `llm_router_handlers.py` | LLM router HTTP handlers |
| `route_handler.py` | Core query route handler |
| `route_aliases.py` | Route alias registrations |
| `routing_contract.py` | Canonical tier taxonomy (RoutingTier/RoutingDecision) |
| `domain_router.py` | Domain-level routing |
| `capability_discovery.py` | Capability probing + discovery |
| `coordinator.py` | Top-level coordinator class |
| `collections_config.py` | Qdrant collection config |
| `embedder.py` | Embedding helper |
| `embedding_cache.py` | Embedding result cache |
| `semantic_cache.py` | Semantic cache (query dedup) |
| `context_compression.py` | Context compression utilities |
| `multi_turn_context.py` | Multi-turn session context |
| `safe_command_executor.py` | Sandboxed command execution |
| `query_expansion.py` | Query expansion for retrieval |
| `search_router.py` | Multi-source search dispatcher |
| `task_classifier.py` | Task type classification |
| `intent_classifier.py` | Intent classification + routing |
| `trace_collector.py` | End-to-end query tracing |
| `quality_cache.py` | Quality-scored cache |
| `quality_monitor.py` | Quality monitoring |
| `model_loader.py` | Model loading helpers |
| `model_probe.py` | Model health probing |
| `progressive_disclosure.py` | Progressive context disclosure |
| `session_builders.py` | Session construction helpers |
| `tooling_manifest.py` (if present) | Tool injection manifest |
| `prompt_injection.py` | Prompt injection detection |
| `blast_radius_classifier.py` | Safety — blast radius scoring |

---

## workflow/ — Workflow execution, DAG, planning, scheduling, orchestration

| File | Reason |
|------|--------|
| `workflow_executor.py` | DAG executor + retry/backoff |
| `workflow_planning.py` | Workflow plan generation |
| `workflow_session_handlers.py` | Workflow session HTTP handlers |
| `orchestration_graph_runner.py` | Graph-based orchestration runner |
| `orchestration_handlers.py` | Orchestration HTTP handlers |
| `orchestration_utils.py` | Orchestration helper utilities |
| `yaml_workflow_handlers.py` | YAML-defined workflow handlers |
| `lifecycle_fsm.py` | UAG lifecycle FSM (Phase 26) |
| `intake_gateway.py` | UAG intake HTTP handlers |
| `runtime_manager.py` | Runtime lifecycle management |
| `runtime_control_handlers.py` | Runtime control HTTP handlers |
| `ops_handlers.py` | Agent-ops profile + drift handlers |
| `prsi_handlers.py` | PRSI action queue handlers |
| `remediation_tracker.py` | Remediation action tracking |
| `delegation_handlers.py` | Delegation HTTP handlers |
| `delegation_feedback.py` | Delegation feedback loop |
| `agents_task_handlers.py` | Agent task dispatch handlers |
| `openai_a2a_handlers.py` | OpenAI agent-to-agent handlers |
| `auto_tool_select_handlers.py` | Auto tool selection handlers |
| `context_summary_handlers.py` | Context summary + offload handlers |
| `research_workflows.py` | Research workflow execution |
| `web_research.py` | Web research step handler |
| `browser_research.py` | Browser-based research (shim) |
| `model_opt_handlers.py` | Model optimization HTTP handlers |
| `model_optimization.py` | Model optimization logic |
| `model_fleet_manager.py` | Fleet model management |
| `harness_sdk.py` | Harness SDK surface |
| `harness_eval.py` | Harness evaluation runner |
| `eval_runner.py` | Continuous eval + trend (Phase 54) |

---

## knowledge/ — Memory, hints, RAG, learning, crystallization, patterns

| File | Reason |
|------|--------|
| `hints_engine.py` | Workflow hints generation |
| `hints_handlers.py` | Hints HTTP handlers |
| `memory_broker.py` | Unified typed memory (Phase 54) |
| `memory_manager.py` | Memory management |
| `memory_crystallizer.py` | Memory crystallization (Phase 55) |
| `memory_superseder.py` | Memory supersede lifecycle (Phase 55) |
| `memory_context_handlers.py` | Memory HTTP handlers |
| `agentic_memory_journal.py` | Agent memory journal |
| `rag_augmentor.py` | RAG augmentation pre-LLM (Phase 54) |
| `rag_reflection.py` | RAG result reflection + reranking |
| `real_time_learning_engine.py` | Runtime learning singletons (canonical) |
| `continuous_learning.py` | Batch learning pipeline (deprecated top-level) |
| `continuous_learning_daemon.py` | CL daemon shim → extensions/ |
| `learning_lifecycle.py` | Learning state lifecycle |
| `lesson_effectiveness_tracker.py` | Lesson quality tracking |
| `interaction_tracker.py` | Interaction history tracking |
| `drift_analyzer.py` | Query drift detection (Phase 55) |
| `pattern_integration.py` | Pattern library integration (shim) |
| `auto_quality_improver.py` | Automated quality improvement |
| `generator_critic.py` | Generator-critic improvement loop |
| `remote_llm_feedback.py` | Remote LLM feedback ingestion |
| `skill_validator.py` | Skill registry validation |
| `skill_usage_tracker.py` | Skill usage telemetry (shim) |
| `advisor_detector.py` | Advisor/hint quality detection |

---

## extensions/ — Feature integrations, AGI scaffold, specialized handlers

| File | Reason |
|------|--------|
| `advanced_features.py` | Advanced feature shim → extensions/ |
| `affective_handlers.py` | Affective state AGI handlers (shim) |
| `ai_coordinator.py` | AI coordinator delegation |
| `ai_coordinator_handlers.py` | AI coordinator HTTP handlers (shim) |
| `agent_registry.py` | Agent registry management |
| `agent_capability_registry.py` | Agent capability catalog |
| `model_coordinator.py` | Model coordinator shim → extensions/ |
| `garbage_collector.py` | DB/vector GC (shim → extensions/) |
| `federated_integration.py` | Federated learning integration (shim) |
| `federated_mcp_handlers.py` | Federated MCP handlers |
| `federation_sync.py` | Federation sync utilities |
| `identity_handlers.py` | Identity kernel handlers (AGI, Phase 16) |
| `mcp_handlers.py` | MCP protocol handlers |
| `trading_handlers.py` | Trading analysis handlers |
| `evidence_safety_handlers.py` | Evidence + safety gate hooks (Phase 28) |

---

## tests/ — All test files

| File | Reason |
|------|--------|
| `test_advisor_detector.py` | |
| `test_advisor_fallback_chains.py` | |
| `test_ai_coordinator_model_awareness.py` | |
| `test_config_local_system_prompt.py` | |
| `test_harness_eval_scorecard.py` | |
| `test_http_query_runtime_optimization.py` | |
| `test_http_server_delegated_message_optimization.py` | |
| `test_llm_client.py` | |
| `test_llm_router.py` | |
| `test_optimizations_simple.py` | |
| `test_qdrant_client_compat.py` | |
| `test_reasoning_profiles.py` | |
| `test_route_handler_optimizations.py` | |
| `test_search_router_reranking.py` | |
| `test_workflow_executor.py` | |
| `test_workflow_plan_optimization_watch.py` | |
| `test_workflow_run_blueprint_auto_selection.py` | |

---

## Counts

| Subdir | Files |
|--------|-------|
| core/ | 36 |
| workflow/ | 30 |
| knowledge/ | 24 |
| extensions/ | 15 |
| tests/ | 17 |
| **total** | **122** |

> One file count discrepancy vs 121 expected — likely one shim counted in two categories above. Resolve during actual Phase B.2 migration.

---

## Notes for Phase B.2 Migration

- Files in extensions/ that are shims (e.g. `from extensions.X import *`) stay as shims pointing to their new subdir home.
- `continuous_learning.py` — top-level deprecated per G-2; move content to `knowledge/batch_pipeline.py` before deleting.
- `garbage_collector.py` — wired into `server.py` startup (Phase 56 / Round 4); keep in extensions/.
- `routing_contract.py` — canonical, goes to `core/`; all routing taxonomy must converge here.
- Tests must stay co-located as `tests/` subdir OR alongside the module (one or the other — pick one convention in Phase B.2 PRD).
