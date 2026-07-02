---
doc_type: reference
title: "Wiki: Testing"
subsystem: testing
generated: 2026-07-02T01:49:23.505256Z
graph_generated: 2026-07-01T16:10:40Z
graph_nodes: 689
---

# Testing

> Test harness scripts, inference budget tests, slot scheduling tests

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*  
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `run` | Main entry point for phase 0; orchestrates all checks and returns a ResultSet. | complex |
| `_check_phase172_delegation_health` | Phase 172: delegation health including rate, latency, and error patterns. | complex |
| `_check_golden_eval_parity` | Extensive golden eval parity checks across multiple agent capabilities. | complex |
| `_check_graphrag` | Check GraphRAG endpoint and graph data integrity. | complex |
| `_check_nsjail_sandbox` | Verify nsjail sandbox binary and policy files. | complex |
| `_check_ragas_eval` | Full RAGAS evaluation pipeline check including faithfulness scoring. | complex |
| `_check_phase146_identity_coverage` | Phase 146: identity coverage across auth surfaces. | complex |
| `_check_s2_tool_auth_policy` | Check S2 tool auth policy configuration. | complex |
| `_check_phase86_attention_queue` | Phase 86: attention queue processing check. | complex |
| `test-route-handler-classifier-context-cap.py` | Unit tests for context cap enforcement in the route handler classifier. Tests that message | complex |
| `test-route-handler-collection-policy.py` | Unit tests for AIDB collection selection policy in the route handler. Covers _select_route | complex |
| `benchmark-acceleration-backends.sh` | benchmark-acceleration-backends.sh (450 lines) in testing. | complex |
| `benchmark-collaboration.sh` | benchmark-collaboration.sh (341 lines) in testing. | complex |
| `benchmark-query-performance.sh` | benchmark-query-performance.sh (306 lines) in testing. | complex |
| `benchmark-workflow-automation.sh` | benchmark-workflow-automation.sh (340 lines) in testing. | complex |
| `check-context-bootstrap.sh` | check-context-bootstrap.sh (203 lines) in testing. | complex |
| `drill-rollback.sh` | drill-rollback.sh (225 lines) in testing. | complex |
| `maeah-acceptance-tests.sh` | maeah-acceptance-tests.sh (277 lines) in testing. | complex |
| `smoke-agent-harness-parity.sh` | smoke-agent-harness-parity.sh (210 lines) in testing. | complex |
| `smoke-ide-adapter-compat.sh` | smoke-ide-adapter-compat.sh (258 lines) in testing. | complex |
| `smoke-integration-complete.sh` | smoke-integration-complete.sh (227 lines) in testing. | complex |
| `smoke-local-model.sh` | smoke-local-model.sh (312 lines) in testing. | complex |
| `smoke-query-task-classes.sh` | smoke-query-task-classes.sh (221 lines) in testing. | complex |
| `validate-query-agent-storage-learning.sh` | validate-query-agent-storage-learning.sh (343 lines) in testing. | complex |
| `benchmark-quality-performance.py` | benchmark-quality-performance.py (273 lines) in testing. | complex |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `load_route_handler` | `test-route-handler-adaptive-timeouts.py` | Bootstraps the route handler module for isolated unit testing by injecting sys.modules stu |
| `load_route_handler` | `test-route-handler-backend-audit.py` | Bootstraps the route handler for backend-audit tests by stub-injecting aiohttp, prometheus |
| `load_route_handler` | `test-route-handler-classifier-context-cap.py` | Bootstraps the route handler for classifier-context-cap tests. Injects stubs for aiohttp,  |
| `main_async` | `test-route-handler-classifier-context-cap.py` | Async test body covering three classifier context-cap scenarios: initial request (full con |
| `load_route_handler` | `test-route-handler-collection-policy.py` | Bootstraps the route handler for collection-policy tests by injecting mock dependencies an |
| `main` | `test-route-handler-collection-policy.py` | Test entry point for AIDB collection selection policy. Validates _select_route_collections |
| `load_route_handler` | `test-route-handler-context-budget.py` | Bootstraps the route handler for context-budget tests by injecting mock dependencies and d |
| `load_route_handler` | `test-route-handler-discovery-gating.py` | Bootstraps the route handler for discovery-gating tests by injecting mock dependencies and |
| `main_async` | `test-route-handler-discovery-gating.py` | Async test body for discovery gating. Verifies that Qdrant collection discovery is skipped |
| `load_route_handler` | `test-route-handler-local-synthesis-budget.py` | Bootstraps the route handler for local-synthesis-budget tests by injecting mock dependenci |
| `main` | `test-route-handler-adaptive-timeouts.py` | Test entry point that calls load_route_handler and asserts calculate_adaptive_timeout beha |
| `_run` | `test-route-handler-backend-audit.py` | Async test body for backend audit. Constructs mock request and response objects, invokes r |
| `main_async` | `test-route-handler-context-budget.py` | Async test body for context-budget enforcement. Sets up _RecordingClient and _RecordingCom |
| `main_async` | `test-route-handler-local-synthesis-budget.py` | Async test body for local synthesis token budget. Injects recording HTTP clients for local |
| `_svc_url` | `_mock_config.py` | Constructs a service base URL by checking an explicit URL env var first, then falling back |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `_FakeResponse` | `test-route-handler-classifier-context-cap.py` | Test stub for aiohttp ClientResponse. No-ops raise_for_status and returns a fixed JSON pay |
| `_RecordingClient` | `test-route-handler-classifier-context-cap.py` | Test stub for aiohttp ClientSession. Records all POST calls (URL, headers, JSON body) in a |
| `_FakeResponse` | `test-route-handler-context-budget.py` | Test stub for aiohttp ClientResponse used in context-budget tests. Returns a fixed JSON pa |
| `_RecordingClient` | `test-route-handler-context-budget.py` | Minimal test stub for aiohttp ClientSession in context-budget tests. Returns a fixed _Fake |
| `_RecordingCompressor` | `test-route-handler-context-budget.py` | Test stub for the context compressor. Records compress_to_budget calls and returns a fixed |
| `_FakeResponse` | `test-route-handler-local-synthesis-budget.py` | Test stub for aiohttp ClientResponse in local-synthesis-budget tests. |
| `_RecordingClient` | `test-route-handler-local-synthesis-budget.py` | Test stub for aiohttp ClientSession in local-synthesis-budget tests. Records POST calls in |

## Coverage

- **Nodes**: 689 total (667 files, 15 functions, 7 classes)
- **Path prefix**: `scripts/testing/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-07-01T16:10:40Z)
