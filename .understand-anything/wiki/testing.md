---
doc_type: reference
title: "Wiki: Testing"
subsystem: testing
generated: 2026-10-10T08:04:22.602254Z
graph_generated: 2026-10-10T07:31:33Z
graph_nodes: 6947
---

# Testing

> Test harness scripts, inference budget tests, slot scheduling tests

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `bench-local-agent.py` | Local agent benchmark — 13 tests across reasoning / tool-use / code-gen / coherence. | complex |
| `process_lifecycle.py` | Pure, bounded ownership for deterministic QA probe subprocesses. | complex |
| `phase0.py` | Phase 0 — Pre-flight smoke tests. | complex |
| `execution-cell-perf-harness.py` | C3b R4 execution-cell performance-measurement harness (NON-ENFORCEMENT). | complex |
| `qa-provider-probe.py` | Bounded aggregate owner for the four fixed flagship CLI probes. | complex |
| `test-agent-ops-projection.py` | Executable M0 contract tests for the read-only Agent Ops projector. | complex |
| `test-approval-signer.py` | Acceptance tests for the Approval Control Plane P1 signing service core | complex |
| `test-aq-approve-headless.py` | Acceptance tests for the Approval Control Plane P4 headless CLI | complex |
| `test-c2-gate-dispatch-wiring.py` | Offline hermetic tests — Foundation C, C2-SCI subslice B3: the | complex |
| `test-capability-lease-gate.py` | Offline acceptance tests — Foundation C2 capability-lease enforcement gate. | complex |
| `test-dashboard-program-progress.py` | Focused contract tests for the canonical AQ-OS program tracker. | complex |
| `test-deployment-causality-clustering.py` | Test Suite: Causality Clustering and Scoring (Phase 3.2 Knowledge Graph) | complex |
| `test-deployment-monitoring-alerting-e2e.py` | End-to-end test suite for deployment monitoring and alerting workflow. | complex |
| `test-edit-verify.py` | Regression test for the POST-EDIT VERIFY-AND-COACH gate (2026-08-25). | complex |
| `test-enforce-asymmetric-verify.py` | Offline acceptance tests — ALA-ENFORCE (enforce-asymmetric-verify). | complex |
| `test-execution-cell-adapter.py` | Offline acceptance tests — Foundation C C3b R5 execution-cell-adapter. | complex |
| `test-execution-cell-clone.py` | Offline acceptance tests — Foundation C C3b R2 self-contained clone | complex |
| `test-execution-cell-runner.py` | Offline acceptance tests — Foundation C C3b R3 execution-cell-runner. | complex |
| `test-factory-gate-readiness.py` | Focused FT-5 proof for the metadata-only factory readiness preflight. | complex |
| `test-llm-cassette.py` | Tests for the LLM record/replay cassette harness. | complex |
| `test-local-delegation-artifact.py` | Phase 159 regression: local delegation artifact persistence. | complex |
| `test-local-inference-l2b.py` | Focused L2B-A shadow transport contract checks. | complex |
| `test-multi-agent-collaboration.py` | Test Suite for Multi-Agent Collaboration System | complex |
| `test-operator-retrieval-guidance.py` | Test Suite: Operator Retrieval Guidance (Phase 3.2 Knowledge Graph - P1) | complex |
| `test-orchestration-comprehensive.py` | Comprehensive test coverage for orchestration framework - targeting 90%+ coverage. | complex |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `main` | `bench-local-agent.py` | main() -> int |
| `run_owned_process` | `process_lifecycle.py` | Run one local fixture command with descriptor-bound process-session ownership. |
| `_check_golden_eval_parity` | `phase0.py` | Phase 152: golden eval set size + static checks for workflow/role/cross-model parity. |
| `_check_phase86_attention_queue` | `phase0.py` | Phase 86: Human-in-the-Loop Alert Queue. |
| `run_revocation_under_load` | `execution-cell-perf-harness.py` | Design §5: at the configured cap, with cells actively running, bump |
| `test_agent_status_formatting` | `test-agent-status-reporting.py` | Test the agent status formatting logic. |
| `main` | `test-ai-coordinator.py` | main() -> int |
| `main` | `test-ai-insights-roadmap-surfaces.py` | main() -> int |
| `main` | `test-ai-stack-health-monitor.py` | main() -> int |
| `main` | `test-antigravity-inbox.py` | main() |
| `main` | `test-aq-editor-rescue.py` | main() -> int |
| `main` | `test-aq-report-runtime-actions.py` | main() -> int |
| `main` | `test-boot-stability-regressions.py` | main() -> int |
| `validate_c6_p0_trust_anchors` | `test-c6-p0-trust-anchors.py` | Validate C6-P0 declarative trust anchors. |
| `test_mock_registry_checks` | `test-capability-intake.py` | test_mock_registry_checks() -> None |
| `main` | `test-curated-web-research.py` | main() -> int |
| `main` | `test-dashboard-advanced-runtime-summary.py` | main() -> int |
| `main` | `test-dashboard-agent-replay.py` | main() -> int |
| `main` | `test-dashboard-deployment-execution.py` | main() -> int |
| `main` | `test-dashboard-runtime-controls.py` | main() -> int |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `AgentOpsProjectionC05B` | `test-agent-ops-projection.py` | C0.5B pure injected review/feedback health contract. |
| `AgentOpsProjectionM0` | `test-agent-ops-projection.py` | class AgentOpsProjectionM0(unittest.TestCase) |
| `AgentOpsProjectionM2A` | `test-agent-ops-projection.py` | M2A adversarial tests: transactional writer, queued grace, barrier, and privacy. |
| `RegistryCompatibilityR01` | `test-agent-ops-projection.py` | R0.1 compatibility reader, CLI, pure projection, and TUI contract. |
| `AIInsightsTests` | `test-ai-insights-dashboard.py` | Test suite for AI insights API. |
| `HealthMonitoringTests` | `test-ai-service-health-monitoring.py` | Test suite for health monitoring API. |
| `MockCachePrewarmer` | `test-cache-prewarm-effectiveness.py` | Mock implementation of cache prewarmer. |
| `DeploymentDashboardTests` | `test-deployment-dashboard.py` | class DeploymentDashboardTests() |
| `MockRollbackSystem` | `test-deployment-operations-rollback.py` | Mock deployment rollback system. |
| `IntegrationTester` | `test-integration-completeness.py` | Test suite for integration completeness |
| `ReliabilityR0` | `test-local-delegation-reliability.py` | class ReliabilityR0(unittest.TestCase) |
| `PromptEffectivenessTest` | `test-prompt-effectiveness.py` | Test framework for system prompt effectiveness. |
| `AdoptionTests` | `test-qa-provider-probe-adoption.py` | class AdoptionTests(unittest.TestCase) |
| `ContractTests` | `test-qa-provider-probe-lifecycle.py` | class ContractTests(unittest.TestCase) |
| `MockQueryAgentStorageLearningLoop` | `test-query-agent-storage-learning-loop.py` | Mock implementation of learning loop. |

## Coverage

- **Nodes**: 6947 total (668 files, 5635 functions, 473 classes)
- **Path prefix**: `scripts/testing/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-10-10T07:31:33Z)
