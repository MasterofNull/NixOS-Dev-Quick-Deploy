# hybrid-coordinator Module Map
**Created:** 2026-05-08 (Phase B.1)  
**Author:** Claude Sonnet 4.6  
**Total modules:** 111 Python files  
**Target:** Reorganize into core/ workflow/ knowledge/ extensions/ + move tests out

---

## Module Classification

### CORE — Route handling, HTTP server, config (must stay lean, no optional deps)
| Module | Notes |
|---|---|
| http_server.py | aiohttp app + route registration |
| server.py | MCP server mode entrypoint |
| route_handler.py | Primary routing logic + search metrics |
| route_aliases.py | Alternate route mappings |
| routing_contract.py | Route contract types |
| config.py | Service configuration + OptimizationProposal |
| metrics.py | OpenTelemetry metrics emission |
| auth_middleware.py | API key validation middleware |
| circuit_breaker.py | Resilience pattern for downstream calls |
| llm_client.py | Raw LLM HTTP client (no routing logic) |
| session_builders.py | Session construction helpers |
| task_classifier.py | Task type classification |
| domain_router.py | Domain-based routing decisions |

### WORKFLOW — Session lifecycle, UAG FSM, planning, safety gating
| Module | Notes |
|---|---|
| lifecycle_fsm.py | UAG FSM (Phase 26) |
| intake_gateway.py | UAG HTTP handlers |
| evidence_safety_handlers.py | Safety hook registration (Phase 28 target) |
| safe_command_executor.py | Command safety gate |
| runtime_manager.py | Runtime state management |
| runtime_control_handlers.py | Runtime control HTTP handlers |
| workflow_executor.py | Workflow step execution |
| workflow_planning.py | Workflow plan construction |
| workflow_session_handlers.py | Workflow session HTTP handlers |
| yaml_workflow_handlers.py | YAML workflow parsing/execution |
| ops_handlers.py | Operational endpoints |
| prsi_handlers.py | PRSI approval queue handlers |
| orchestration_handlers.py | Orchestration HTTP handlers |
| orchestration_utils.py | Orchestration shared utilities |
| coordinator.py | High-level coordinator logic |
| delegation_handlers.py | Task delegation HTTP handlers |
| delegation_feedback.py | Delegation result processing |
| agents_task_handlers.py | Agent task management |
| agent_registry.py | Agent registration and discovery |
| agent_capability_registry.py | Per-agent capability tracking |

### KNOWLEDGE — Search, hints, memory, context, RAG, cache
| Module | Notes |
|---|---|
| hints_engine.py | Ranked workflow hints (3350 LOC) |
| hints_handlers.py | Hints HTTP handlers |
| search_router.py | Multi-source search routing |
| query_expansion.py | Query enrichment |
| memory_manager.py | Canonical memory system |
| memory_context_handlers.py | Memory HTTP handlers (may overlap with memory_manager) |
| agentic_memory_journal.py | Agent memory journal (may overlap — see duplicates) |
| semantic_cache.py | Semantic query cache |
| context_compression.py | Context token compression |
| context_summary_handlers.py | Context summary HTTP handlers |
| multi_turn_context.py | Multi-turn conversation context |
| embedder.py | Embedding generation |
| embedding_cache.py | Embedding result cache |
| llm_router.py | LLM model selection and routing |
| llm_router_handlers.py | LLM router HTTP handlers |
| rag_reflection.py | RAG quality reflection |
| progressive_disclosure.py | Context progressive loading |
| tooling_manifest.py | Tool catalog and manifest |
| capability_discovery.py | Capability enumeration |
| collections_config.py | Qdrant collection configuration |

### EXTENSIONS — AGI features, learning, federation, monitoring (optional-load)
**Rule: core/ and workflow/ MUST NOT import from extensions/**
| Module | Notes |
|---|---|
| continuous_learning.py | Primary learning system |
| continuous_learning_daemon.py | **DUPLICATE** — daemon wrapper around continuous_learning |
| real_time_learning_engine.py | **OVERLAPS** — imported by http_server; may supersede continuous_learning |
| affective_handlers.py | Affective signal processing handlers |
| identity_handlers.py | Identity kernel handlers |
| federated_integration.py | Federated learning integration layer |
| federated_mcp_handlers.py | Federated MCP tool handlers |
| federation_sync.py | Federation data sync |
| model_optimization.py | Model optimization logic |
| model_coordinator.py | Multi-model coordination |
| model_fleet_manager.py | Model fleet management |
| model_loader.py | Model loading utilities |
| model_probe.py | Model capability probing |
| model_opt_handlers.py | Model optimization HTTP handlers |
| openai_a2a_handlers.py | OpenAI agent-to-agent handlers |
| advanced_features.py | Miscellaneous advanced features (2186 LOC — refactor candidate) |
| quality_cache.py | Query quality caching |
| quality_monitor.py | Quality monitoring |
| auto_quality_improver.py | Automated quality improvement |
| generator_critic.py | Generator-critic pattern |
| harness_eval.py | Harness evaluation scoring |
| interaction_tracker.py | User interaction tracking |
| skill_usage_tracker.py | Skill usage analytics |
| skill_validator.py | Skill validation |
| lesson_effectiveness_tracker.py | Lesson learning tracker |
| remediation_tracker.py | Remediation action tracking |
| pattern_integration.py | Pattern library integration |
| auto_tool_select_handlers.py | Automatic tool selection |
| mcp_handlers.py | MCP tool handlers |
| ai_coordinator.py | AI coordinator logic |
| ai_coordinator_handlers.py | AI coordinator HTTP handlers |
| trading_handlers.py | Trading analysis handlers |
| web_research.py | Web research utilities |
| browser_research.py | Browser-based research |
| research_workflows.py | Research workflow patterns |
| remote_llm_feedback.py | Remote LLM feedback collection |
| harness_sdk.py | Python SDK for harness |
| advisor_detector.py | Advisor pattern detection |
| garbage_collection.py | **PRIMARY** garbage collection |
| garbage_collector.py | **DUPLICATE** of garbage_collection.py |
| prompt_injection.py | Prompt injection detection |

### TESTS — Should move to tests/ subdirectory
| Module | Notes |
|---|---|
| test_advisor_detector.py | Unit tests |
| test_advisor_fallback_chains.py | Unit tests |
| test_ai_coordinator_model_awareness.py | Integration tests |
| test_config_local_system_prompt.py | Config tests |
| test_harness_eval_scorecard.py | Eval tests |
| test_http_query_runtime_optimization.py | HTTP perf tests |
| test_http_server_delegated_message_optimization.py | HTTP perf tests |
| test_llm_client.py | LLM client tests |
| test_llm_router.py | Router tests |
| test_optimizations_simple.py | Optimization tests |
| test_qdrant_client_compat.py | Qdrant compat tests |
| test_reasoning_profiles.py | Reasoning profile tests |
| test_route_handler_optimizations.py | Route handler tests (1500 LOC) |
| test_search_router_reranking.py | Search ranking tests |
| test_workflow_executor.py | Workflow tests |
| test_workflow_plan_optimization_watch.py | Workflow plan tests |
| test_workflow_run_blueprint_auto_selection.py | Blueprint selection tests |

---

## Confirmed Duplicate Pairs (Phase B.2 targets)

| Primary (keep) | Duplicate (merge/remove) | Evidence |
|---|---|---|
| `garbage_collection.py` | `garbage_collector.py` | Same purpose, investigate which is called |
| `continuous_learning.py` | `continuous_learning_daemon.py` | Daemon is a wrapper — merge daemon mode |
| `memory_manager.py` | `agentic_memory_journal.py` | Overlapping memory stores — audit before merge |

**Special case:** `real_time_learning_engine.py` is imported directly by `http_server.py` and `ai_coordinator_handlers.py`. Whether it supersedes `continuous_learning.py` needs an audit of each module's exported symbols before merging.

**Non-Python SDK files** (`harness_sdk.ts`, `harness_sdk.js`, `harness_sdk.d.ts`):  
Run `grep -rl "harness_sdk" --include="*.ts" --include="*.js"` in the repo to confirm usage before removing.

---

## Import Boundary Rule

After Phase B.3 domain split, enforce this rule:
```bash
# Validation script — add to tier0 gate
if grep -r "from extensions\." ai-stack/mcp-servers/hybrid-coordinator/core/ 2>/dev/null | grep -v test; then
  echo "FAIL: core/ imports from extensions/"
  exit 1
fi
```

---

## Phase B.2 Execution Plan

1. **garbage_collection vs garbage_collector**: diff both; confirm which is actually called by GC trigger; remove the other
2. **continuous_learning_daemon**: check if it adds any logic beyond continuous_learning; if just a daemon launcher, convert to a flag/mode in continuous_learning.py
3. **agentic_memory_journal vs memory_manager**: check import graph; if journal is only used by memory_manager, inline it
4. **real_time_learning_engine**: audit exported symbols vs continuous_learning; if fully superseded, deprecate continuous_learning

**Do not merge before confirming with grep which callers import each module.**
