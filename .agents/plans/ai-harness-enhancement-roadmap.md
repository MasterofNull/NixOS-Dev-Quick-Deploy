# AI Harness Enhancement Roadmap

**Based on:** Parity analysis with MemPalace and Archon
**Document Type:** Multi-phase implementation plan for concurrent agent execution
**Status:** Ready for execution
**Created:** 2026-04-09
**Target Completion:** 12 weeks from start date

---

## Overview

This roadmap implements selected features from MemPalace (memory system) and Archon (workflow engine) into our NixOS-Dev-Quick-Deploy AI harness. Each phase is designed for concurrent execution by multiple agents.

**Key Principles:**
- Maintain declarative-first philosophy
- Preserve local-first AI capabilities
- Enable concurrent agent work via clear slice boundaries
- Validate at each phase before proceeding

## Recommended Avenue: Harness-Native Context Offload

**Decision:** Use the existing harness session, context-card, memory recall, progressive disclosure, and compaction surfaces as the primary long-running memory path. Do **not** introduce a second standalone history store unless the current harness path proves insufficient under measurement.

**Why this is the best avenue:**
- The repo already has the core primitives: `aq-context-card`, `aq-context-bootstrap`, `aq-context-manage`, `aq-memory`, workflow sessions, intent contracts, and progressive context injection in the hybrid coordinator.
- This keeps one source of truth for prior work: workflow run state plus local memory retrieval, instead of duplicating state across prompts, agent clients, and a new persistence tier.
- It matches the existing progressive-disclosure model: send only compact intent plus the active slice to remote models, then rehydrate prior context from the harness on demand.

**Target operating pattern:**
1. Start long-running work through harness bootstrap plus a workflow run with an explicit context-offload contract.
2. Store durable discoveries, decisions, blockers, and evidence in harness memory rather than relying on transcript replay.
3. Trigger remote compaction frequently, preserving only summary state and next actions.
4. On later turns, recall context from local memory/session state first; widen retrieval breadth only when recall is insufficient.
5. Re-measure latency, retrieval quality, and token savings before adding new storage mechanisms.

**Preferred integration points:**
- `scripts/ai/aq-context-bootstrap` for routing into a context-offload workflow
- `config/agent-context-cards.json` for the compact operator contract
- `config/workflow-blueprints.json` for long-running run defaults
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` for default intent-contract pressure toward retrieval-first context reuse
- `scripts/ai/harness-rpc.js` for caller-side defaults that keep runs aligned with the same contract

## Phase 0: Layer 1 Front-Door Routing

**Objective:** Make the local harness the stable first contact point for human-to-LLM requests while translating OpenClaude-style route names onto existing harness profiles.

**Success Criteria:**
- [ ] `Explore`, `Plan`, and `default` aliases map cleanly onto harness profiles
- [ ] Local orchestrator enables front-door routing by default
- [ ] Implementation, reasoning, and tool-calling routes remain bounded to existing coordinator lanes
- [ ] Validation covers alias mapping and route selection

**Initial Route Map:**
- `default` -> `default`
- `Explore` -> `default`
- `Plan` -> `default`
- `Implementation` -> `remote-coding`
- `Reasoning` -> `remote-reasoning`
- `ToolCalling` -> `local-tool-calling`
- `Continuation` -> `default`

**Notes:**
- This preserves one routing system: the harness profiles remain the source of truth.
- OpenClaude-compatible route names are treated as compatibility aliases, not a separate policy layer.
- Remote route targets stay configurable through existing switchboard aliases and budget controls.

---

## Phase 1: Memory Foundation (Weeks 1-3)

**Objective:** Extend AIDB with structured memory, temporal validity, and recall benchmarks

**Success Criteria:**
- [ ] Temporal facts stored and retrieved correctly
- [ ] Metadata filtering improves recall accuracy by 20%+
- [ ] Benchmark suite operational with baseline metrics
- [ ] Documentation complete
- [ ] `aq-memory` CLI operational

**Dependencies:**
- AIDB currently operational
- PostgreSQL available
- ChromaDB access (existing)

### Slice 1.1: Schema Design & Architecture

**Owner:** claude (architecture)
**Type:** Architecture + Documentation
**Estimated Effort:** 3-4 days
**Priority:** P0 (blocks other slices)

**Scope:**
1. Design enhanced AIDB schema for temporal facts
2. Define memory organization taxonomy (wings/rooms/halls or project/topic/type)
3. Design metadata filtering strategy
4. Create architecture diagrams

**Deliverables:**
- [ ] `docs/architecture/memory-system-design.md` - Architecture doc
- [ ] SQL schema for temporal facts table
- [ ] Metadata organization taxonomy definition
- [ ] Migration plan from current AIDB to enhanced version

**Validation:**
- Schema review by codex (reviewer)
- No breaking changes to existing AIDB queries
- Backward compatibility verified

**Rollback:**
- Architecture is docs-only, no code changes

**Files:**
- Create: `docs/architecture/memory-system-design.md`
- Create: `ai-stack/aidb/schema/temporal-facts-v2.sql`
- Update: `ai-stack/aidb/README.md`

---

### Slice 1.2: Temporal Validity Implementation

**Owner:** qwen (implementation)
**Type:** Code implementation
**Estimated Effort:** 5-6 days
**Priority:** P0 (core feature)
**Depends on:** Slice 1.1

**Scope:**
1. Implement temporal fact storage in AIDB
2. Add validity window tracking (valid_from, valid_until)
3. Create staleness detection queries
4. Implement temporal query API

**Deliverables:**
- [ ] `ai-stack/aidb/temporal_facts.py` - Temporal fact storage
- [ ] `ai-stack/aidb/temporal_query.py` - Query API with time awareness
- [ ] Unit tests for temporal operations
- [ ] Integration tests with existing AIDB

**Validation:**
- All tests pass
- Temporal queries return correct results
- No regression in existing AIDB functionality
- Performance: < 100ms for temporal queries

**Rollback:**
- Feature flag: `ENABLE_TEMPORAL_FACTS=false`
- Graceful degradation to current AIDB behavior

**Files:**
- Create: `ai-stack/aidb/temporal_facts.py`
- Create: `ai-stack/aidb/temporal_query.py`
- Create: `ai-stack/aidb/tests/test_temporal_facts.py`
- Update: `ai-stack/aidb/api.py`

**Commands:**
```bash
# Test
python -m pytest ai-stack/aidb/tests/test_temporal_facts.py -v

# Smoke test
curl "http://localhost:8002/temporal/facts?valid_at=2026-04-09T00:00:00Z"
```

---

### Slice 1.3: Metadata Filtering System

**Owner:** qwen (implementation)
**Type:** Code implementation
**Estimated Effort:** 4-5 days
**Priority:** P1 (enhances core feature)
**Depends on:** Slice 1.1

**Scope:**
1. Implement metadata tagging system (project, topic, type)
2. Add filtering to vector search queries
3. Create metadata indexing for performance
4. Implement combined filtering (metadata + semantic)

**Deliverables:**
- [ ] `ai-stack/aidb/metadata_filter.py` - Metadata filtering implementation
- [ ] Enhanced search API with metadata parameters
- [ ] Metadata indexing in PostgreSQL
- [ ] Performance tests for filtered queries

**Validation:**
- Metadata filtering improves precision by 20%+
- Query performance: < 500ms with metadata filters
- All existing queries continue to work
- Integration tests pass

**Rollback:**
- Metadata filtering is additive, can be disabled via API parameters
- Default behavior unchanged

**Files:**
- Create: `ai-stack/aidb/metadata_filter.py`
- Create: `ai-stack/aidb/tests/test_metadata_filter.py`
- Update: `ai-stack/aidb/api.py`
- Update: `ai-stack/aidb/schema/migrations/002_add_metadata.sql`

**Commands:**
```bash
# Test
python -m pytest ai-stack/aidb/tests/test_metadata_filter.py -v

# Benchmark
python scripts/testing/benchmark-aidb-metadata-filtering.py
```

---

### Slice 1.4: Memory CLI Tool Suite

**Owner:** qwen (implementation)
**Type:** CLI tool development
**Estimated Effort:** 3-4 days
**Priority:** P1 (user-facing)
**Depends on:** Slice 1.2, Slice 1.3

**Scope:**
1. Create `aq-memory` CLI tool
2. Commands: search, store, recall, list, benchmark
3. Interactive and scriptable modes
4. Integration with existing `aq-*` tooling

**Deliverables:**
- [ ] `scripts/ai/aq-memory` - CLI tool
- [ ] Bash completion for aq-memory
- [ ] Man page / help documentation
- [ ] Integration with aq-session-zero

**Validation:**
- All commands functional
- Bash completion works
- Help text complete
- Integration tests pass

**Rollback:**
- CLI is new tool, no existing dependencies
- Can be removed without affecting system

**Files:**
- Create: `scripts/ai/aq-memory`
- Create: `scripts/ai/completions/aq-memory-completion.sh`
- Update: `scripts/ai/bash-completion.sh`
- Update: `docs/operations/reference/QUICK-REFERENCE.md`

**Commands:**
```bash
# Usage examples
aq-memory search "authentication decisions" --project=ai-stack --topic=security
aq-memory store "Using JWT with 7-day expiry" --project=ai-stack --topic=auth
aq-memory recall --project=ai-stack --since=7d
aq-memory benchmark --corpus=test-data/memory-benchmark.json
```

---

### Slice 1.5: Memory Benchmark Harness

**Owner:** codex (testing + integration)
**Type:** Testing infrastructure
**Estimated Effort:** 4-5 days
**Priority:** P1 (quality assurance)
**Depends on:** Slice 1.2, Slice 1.3, Slice 1.4

**Scope:**
1. Create memory benchmark corpus (500+ fact-query pairs)
2. Implement recall accuracy measurement
3. Build performance benchmarking suite
4. Compare with baseline (current AIDB)
5. Document baseline metrics

**Deliverables:**
- [ ] `test-data/memory-benchmark-corpus.json` - Test data
- [ ] `scripts/testing/benchmark-memory-recall.py` - Benchmark script
- [ ] Baseline metrics document
- [ ] CI integration for regression testing

**Validation:**
- Recall accuracy: Target 85%+ (baseline), 90%+ (with metadata)
- Query latency: < 500ms p95
- Storage efficiency: < 2x current AIDB size
- Benchmark reproducible

**Rollback:**
- Benchmarks are testing-only, no production impact

**Files:**
- Create: `test-data/memory-benchmark-corpus.json`
- Create: `scripts/testing/benchmark-memory-recall.py`
- Create: `docs/benchmarks/memory-recall-baseline.md`
- Update: `.github/workflows/memory-benchmarks.yml`

**Commands:**
```bash
# Run benchmark
python scripts/testing/benchmark-memory-recall.py --corpus=test-data/memory-benchmark-corpus.json

# CI integration
pytest scripts/testing/test_memory_recall_regression.py
```

---

### Slice 1.6: Documentation & Integration

**Owner:** qwen (documentation)
**Type:** Documentation
**Estimated Effort:** 2-3 days
**Priority:** P2 (enabling)
**Depends on:** All Phase 1 slices

**Scope:**
1. Write comprehensive memory system documentation
2. Create usage examples and tutorials
3. Update AGENTS.md with memory system guidance
4. Document API reference

**Deliverables:**
- [ ] `docs/architecture/memory-system-design.md` - Architecture (from 1.1)
- [ ] `docs/operations/memory-system-guide.md` - Operations guide
- [ ] `docs/development/memory-api-reference.md` - API docs
- [ ] Updated `AGENTS.md` and `docs/AGENTS.md`

**Validation:**
- Documentation complete and accurate
- Examples tested and working
- No broken links
- Reviewed by codex

**Rollback:**
- Documentation updates, no code impact

**Files:**
- Update: `AGENTS.md`
- Update: `docs/AGENTS.md`
- Create: `docs/operations/memory-system-guide.md`
- Create: `docs/development/memory-api-reference.md`

---

### Phase 1 Integration Checklist

**Before Phase 1 Sign-off:**
- [ ] All slices validated individually
- [ ] Integration tests pass
- [ ] Memory benchmark meets targets (85%+ recall)
- [ ] Documentation complete
- [ ] No regressions in existing functionality
- [ ] Code review complete (codex)
- [ ] Security review complete (no hardcoded secrets)
- [ ] Tier 0 validation passes

**Integration Commands:**
```bash
# Full validation
scripts/governance/tier0-validation-gate.sh --pre-commit
scripts/testing/benchmark-memory-recall.py
aq-memory benchmark --corpus=test-data/memory-benchmark-corpus.json
aq-qa --phase=memory-system
```

---

## Phase 2: Workflow Engine (Weeks 4-6)

**Objective:** Implement YAML-based workflow definitions with deterministic execution

**Success Criteria:**
- [ ] YAML workflows execute deterministically
- [ ] 10+ workflow templates operational
- [ ] Integration with hybrid coordinator complete
- [ ] `aq-workflow` CLI functional
- [ ] Documentation complete

**Dependencies:**
- Phase 1 complete (memory system enhances workflow context)
- Hybrid coordinator operational

### Slice 2.1: Workflow DSL Design

**Owner:** claude (architecture)
**Type:** Architecture + Specification
**Estimated Effort:** 3-4 days
**Priority:** P0 (blocks other slices)

**Scope:**
1. Design YAML workflow schema
2. Define node types (agent, bash, approval, loop)
3. Specify dependency resolution (DAG)
4. Design loop constructs and conditions
5. Integration points with hybrid coordinator

**Deliverables:**
- [ ] `docs/architecture/workflow-engine-design.md` - Architecture doc
- [ ] `schemas/workflow-v1.yaml` - JSON Schema for workflows
- [ ] Example workflows (5+ patterns)
- [ ] Integration architecture diagram

**Validation:**
- Schema reviewed by codex
- Examples cover common patterns
- No conflicts with existing harness APIs

**Rollback:**
- Architecture is docs-only

**Files:**
- Create: `docs/architecture/workflow-engine-design.md`
- Create: `schemas/workflow-v1.yaml`
- Create: `examples/workflows/feature-implementation.yaml`
- Create: `examples/workflows/bug-fix.yaml`
- Create: `examples/workflows/pr-review.yaml`

---

### Slice 2.2: Workflow Parser & Validator

**Status:** Complete
**Completion Evidence:** Commit `53fc1fa`; `python -m pytest ai-stack/workflows/tests` -> 66 passed

**Owner:** qwen (implementation)
**Type:** Code implementation
**Estimated Effort:** 4-5 days
**Priority:** P0 (core feature)
**Depends on:** Slice 2.1

**Scope:**
1. Implement YAML parser with schema validation
2. Build DAG validator (cycle detection, dependency resolution)
3. Create workflow AST (abstract syntax tree)
4. Implement topological sorting for execution order

**Deliverables:**
- [x] `ai-stack/workflows/parser.py` - YAML parser
- [x] `ai-stack/workflows/validator.py` - Schema + DAG validator
- [x] `ai-stack/workflows/models.py` - Workflow data models
- [x] Unit tests for all edge cases

**Validation:**
- Parses valid workflows correctly
- Rejects invalid workflows with clear errors
- Cycle detection works
- All tests pass

**Rollback:**
- Parser is new module, no existing dependencies

**Files:**
- Create: `ai-stack/workflows/parser.py`
- Create: `ai-stack/workflows/validator.py`
- Create: `ai-stack/workflows/models.py`
- Create: `ai-stack/workflows/tests/test_parser.py`
- Create: `ai-stack/workflows/tests/test_validator.py`

**Commands:**
```bash
# Test
python -m pytest ai-stack/workflows/tests/ -v

# Validate workflow
python -m ai_stack.workflows.validator examples/workflows/feature-implementation.yaml
```

---

### Slice 2.3: Workflow Executor

**Status:** Ready to Delegate

**Owner:** qwen (implementation)
**Type:** Code implementation
**Estimated Effort:** 6-7 days
**Priority:** P0 (core feature)
**Depends on:** Slice 2.2

**Scope:**
1. Implement workflow executor
2. Node type handlers (agent, bash, approval, loop)
3. Context passing between nodes
4. Loop iteration with conditions
5. Error handling and recovery
6. Run state persistence

**Deliverables:**
- [ ] `ai-stack/workflows/executor.py` - Main executor
- [ ] `ai-stack/workflows/nodes.py` - Node handlers
- [ ] `ai-stack/workflows/context.py` - Context management
- [ ] `ai-stack/workflows/persistence.py` - Run state storage
- [ ] Integration tests

**Validation:**
- Workflows execute in correct order
- Loops iterate correctly
- Errors handled gracefully
- State persists across failures
- All tests pass

**Rollback:**
- Feature flag: `ENABLE_WORKFLOWS=false`
- Graceful degradation to manual execution

**Files:**
- Create: `ai-stack/workflows/executor.py`
- Create: `ai-stack/workflows/nodes.py`
- Create: `ai-stack/workflows/context.py`
- Create: `ai-stack/workflows/persistence.py`
- Create: `ai-stack/workflows/tests/test_executor.py`

**Commands:**
```bash
# Test
python -m pytest ai-stack/workflows/tests/test_executor.py -v

# Execute workflow
python -m ai_stack.workflows.executor examples/workflows/feature-implementation.yaml
```

---

### Slice 2.4: Hybrid Coordinator Integration

**Owner:** codex (integration)
**Type:** Integration
**Estimated Effort:** 4-5 days
**Priority:** P0 (critical path)
**Depends on:** Slice 2.3

**Scope:**
1. Integrate workflow executor with hybrid coordinator
2. Map workflow agent profiles to coordinator lanes
3. Add workflow endpoints to harness RPC
4. Implement workflow-based delegation
5. Update delegation protocol for workflow context

**Deliverables:**
- [ ] `ai-stack/mcp-servers/hybrid-coordinator/workflow_integration.py`
- [ ] Updated harness RPC with workflow commands
- [ ] Integration tests with full stack
- [ ] Performance tests

**Validation:**
- Workflows execute through coordinator correctly
- Agent routing works via profiles
- No regression in existing delegation
- Performance acceptable (< 10% overhead)

**Rollback:**
- Workflow integration is additive
- Can disable via feature flag

**Files:**
- Create: `ai-stack/mcp-servers/hybrid-coordinator/workflow_integration.py`
- Update: `scripts/ai/harness-rpc.js` (add workflow commands)
- Update: `ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator.py`
- Create: `ai-stack/workflows/tests/test_coordinator_integration.py`

**Commands:**
```bash
# Test integration
python -m pytest ai-stack/workflows/tests/test_coordinator_integration.py -v

# Execute via harness
harness-rpc.js workflow execute examples/workflows/feature-implementation.yaml
```

---

### Slice 2.5: Workflow Templates

**Owner:** codex (patterns)
**Type:** Template development
**Estimated Effort:** 3-4 days
**Priority:** P1 (user-facing)
**Depends on:** Slice 2.3

**Scope:**
1. Create 10+ common workflow templates
2. Cover major use cases (feature, bug, refactor, review, etc.)
3. Test each template end-to-end
4. Document template parameters and customization

**Deliverables:**
- [ ] 10+ workflow templates in `.agent/workflows/definitions/`
- [ ] Template documentation
- [ ] Parameter validation
- [ ] E2E tests for each template

**Templates to Create:**
1. `feature-implementation.yaml` - Standard feature development
2. `bug-fix.yaml` - Bug investigation and fix
3. `refactor.yaml` - Code refactoring with tests
4. `pr-review.yaml` - Pull request review
5. `comprehensive-pr-review.yaml` - Multi-agent review
6. `security-audit.yaml` - Security review workflow
7. `performance-optimization.yaml` - Performance improvements
8. `documentation.yaml` - Documentation updates
9. `dependency-update.yaml` - Dependency upgrades
10. `architecture-decision.yaml` - ADR creation workflow

**Validation:**
- Each template executes successfully
- Templates cover 80%+ of common tasks
- Documentation clear
- All tests pass

**Rollback:**
- Templates are data files, no code impact

**Files:**
- Create: `.agent/workflows/definitions/*.yaml` (10+ files)
- Create: `docs/workflows/template-guide.md`
- Create: `ai-stack/workflows/tests/test_templates.py`

**Commands:**
```bash
# List templates
aq-workflow list

# Execute template
aq-workflow execute feature-implementation --params="name=auth-flow"

# Test all templates
python -m pytest ai-stack/workflows/tests/test_templates.py -v
```

---

### Slice 2.6: Workflow CLI Tool

**Owner:** qwen (implementation)
**Type:** CLI tool development
**Estimated Effort:** 3-4 days
**Priority:** P1 (user-facing)
**Depends on:** Slice 2.3, Slice 2.5

**Scope:**
1. Create `aq-workflow` CLI tool
2. Commands: list, execute, status, logs, validate
3. Template management (list, show, execute)
4. Integration with harness-rpc

**Deliverables:**
- [ ] `scripts/ai/aq-workflow` - CLI tool
- [ ] Bash completion
- [ ] Help documentation
- [ ] Integration tests

**Validation:**
- All commands functional
- Bash completion works
- Help text complete
- Integration tests pass

**Rollback:**
- CLI is new tool, no existing dependencies

**Files:**
- Create: `scripts/ai/aq-workflow`
- Create: `scripts/ai/completions/aq-workflow-completion.sh`
- Update: `scripts/ai/bash-completion.sh`
- Update: `docs/operations/reference/QUICK-REFERENCE.md`

**Commands:**
```bash
# Usage examples
aq-workflow list                           # List available workflows
aq-workflow execute feature-implementation # Execute workflow
aq-workflow status <run-id>                # Check workflow status
aq-workflow logs <run-id>                  # View workflow logs
aq-workflow validate my-workflow.yaml      # Validate custom workflow
```

---

### Slice 2.7: Documentation

**Owner:** qwen (documentation)
**Type:** Documentation
**Estimated Effort:** 2-3 days
**Priority:** P2 (enabling)
**Depends on:** All Phase 2 slices

**Scope:**
1. Write workflow system documentation
2. Create template customization guide
3. Document workflow DSL reference
4. Update AGENTS.md with workflow guidance

**Deliverables:**
- [ ] `docs/workflows/workflow-engine-guide.md` - User guide
- [ ] `docs/workflows/template-guide.md` - Template docs (from 2.5)
- [ ] `docs/workflows/dsl-reference.md` - DSL specification
- [ ] Updated `AGENTS.md` and `docs/AGENTS.md`

**Validation:**
- Documentation complete and accurate
- Examples tested and working
- No broken links
- Reviewed by codex

**Rollback:**
- Documentation updates, no code impact

**Files:**
- Create: `docs/workflows/workflow-engine-guide.md`
- Create: `docs/workflows/dsl-reference.md`
- Update: `AGENTS.md`
- Update: `docs/AGENTS.md`

---

### Phase 2 Integration Checklist

**Before Phase 2 Sign-off:**
- [ ] All slices validated individually
- [ ] Integration tests pass
- [ ] 10+ templates tested and working
- [ ] Documentation complete
- [ ] No regressions in existing functionality
- [ ] Code review complete (codex)
- [ ] Security review complete
- [ ] Tier 0 validation passes

**Integration Commands:**
```bash
# Full validation
scripts/governance/tier0-validation-gate.sh --pre-commit
python -m pytest ai-stack/workflows/tests/ -v
aq-workflow validate .agent/workflows/definitions/*.yaml
aq-qa --phase=workflow-engine
```

---

## Phase 3: Execution Isolation (Weeks 7-9)

**Objective:** Implement git worktree isolation for parallel workflow execution

**Success Criteria:**
- [ ] Parallel workflows execute without conflicts
- [ ] Worktree lifecycle management automatic
- [ ] Cleanup success rate 99%+
- [ ] Integration with nixos-quick-deploy
- [ ] Documentation complete

**Dependencies:**
- Phase 2 complete (workflow engine required)
- Git worktree support available

### Slice 3.1: Worktree Lifecycle Design

**Owner:** claude (architecture)
**Type:** Architecture + Specification
**Estimated Effort:** 2-3 days
**Priority:** P0 (blocks other slices)

**Scope:**
1. Design worktree creation and cleanup strategy
2. Define naming conventions and directory structure
3. Specify conflict detection and resolution
4. Design integration with workflow executor
5. Plan rollback and recovery mechanisms

**Deliverables:**
- [ ] `docs/architecture/worktree-isolation-design.md` - Architecture doc
- [ ] Worktree lifecycle diagrams
- [ ] Conflict resolution strategy
- [ ] Recovery procedures

**Validation:**
- Architecture reviewed by codex
- No conflicts with existing git operations
- Cleanup strategy robust

**Rollback:**
- Architecture is docs-only

**Files:**
- Create: `docs/architecture/worktree-isolation-design.md`

---

### Slice 3.2: Worktree Manager Implementation

**Owner:** qwen (implementation)
**Type:** Code implementation
**Estimated Effort:** 5-6 days
**Priority:** P0 (core feature)
**Depends on:** Slice 3.1

**Scope:**
1. Implement worktree creation/deletion
2. Build automatic cleanup (success, failure, timeout)
3. Add conflict detection
4. Implement orphan worktree detection and cleanup
5. Create health monitoring for active worktrees

**Deliverables:**
- [ ] `ai-stack/execution/worktree_manager.py` - Worktree management
- [ ] `ai-stack/execution/cleanup.py` - Cleanup automation
- [ ] Unit tests for all scenarios
- [ ] Integration tests

**Validation:**
- Worktrees created and cleaned up correctly
- Orphan detection works
- Cleanup success rate 99%+
- All tests pass

**Rollback:**
- Worktree management is opt-in via `--isolated` flag

**Files:**
- Create: `ai-stack/execution/worktree_manager.py`
- Create: `ai-stack/execution/cleanup.py`
- Create: `ai-stack/execution/tests/test_worktree_manager.py`

**Commands:**
```bash
# Test
python -m pytest ai-stack/execution/tests/test_worktree_manager.py -v

# Manual worktree operations
python -m ai_stack.execution.worktree_manager create workflow-123
python -m ai_stack.execution.worktree_manager cleanup workflow-123
```

---

### Slice 3.3: Parallel Execution Coordinator

**Owner:** qwen (implementation)
**Type:** Code implementation
**Estimated Effort:** 4-5 days
**Priority:** P0 (core feature)
**Depends on:** Slice 3.2

**Scope:**
1. Implement parallel workflow scheduler
2. Add resource limits (max concurrent worktrees)
3. Build conflict detection across parallel executions
4. Create execution queue with priority
5. Implement cancellation and timeout handling

**Deliverables:**
- [ ] `ai-stack/execution/parallel_coordinator.py` - Parallel execution
- [ ] `ai-stack/execution/scheduler.py` - Workflow scheduler
- [ ] Resource limit enforcement
- [ ] Integration tests for parallel scenarios

**Validation:**
- Parallel workflows execute correctly
- No conflicts between concurrent executions
- Resource limits respected
- All tests pass

**Rollback:**
- Parallel execution is opt-in
- Default to sequential execution

**Files:**
- Create: `ai-stack/execution/parallel_coordinator.py`
- Create: `ai-stack/execution/scheduler.py`
- Create: `ai-stack/execution/tests/test_parallel_coordinator.py`

**Commands:**
```bash
# Test
python -m pytest ai-stack/execution/tests/test_parallel_coordinator.py -v

# Execute parallel workflows
aq-workflow execute feature-a --isolated &
aq-workflow execute feature-b --isolated &
wait
```

---

### Slice 3.4: Workflow Executor Integration

**Owner:** codex (integration)
**Type:** Integration
**Estimated Effort:** 3-4 days
**Priority:** P0 (critical path)
**Depends on:** Slice 3.2, Slice 3.3

**Scope:**
1. Integrate worktree manager with workflow executor
2. Add `--isolated` flag to workflow execution
3. Update context management for isolated execution
4. Ensure proper cleanup on all exit paths

**Deliverables:**
- [ ] Updated workflow executor with isolation support
- [ ] Context management for worktree paths
- [ ] Cleanup hooks for all exit paths
- [ ] Integration tests

**Validation:**
- Isolated workflows execute correctly
- Cleanup happens on success and failure
- Context paths correct within worktrees
- All tests pass

**Rollback:**
- Default behavior unchanged (non-isolated)
- Feature flag: `ENABLE_WORKTREE_ISOLATION=false`

**Files:**
- Update: `ai-stack/workflows/executor.py`
- Update: `ai-stack/workflows/context.py`
- Create: `ai-stack/workflows/tests/test_isolated_execution.py`

**Commands:**
```bash
# Test
python -m pytest ai-stack/workflows/tests/test_isolated_execution.py -v

# Execute isolated workflow
aq-workflow execute feature-implementation --isolated
```

---

### Slice 3.5: nixos-quick-deploy Integration

**Owner:** codex (integration)
**Type:** Integration
**Estimated Effort:** 3-4 days
**Priority:** P1 (deployment integration)
**Depends on:** Slice 3.4

**Scope:**
1. Integrate worktree execution with quick-deploy
2. Support deploy testing in isolated worktrees
3. Add validation before merging worktree changes
4. Create rollback procedures

**Deliverables:**
- [ ] Updated `nixos-quick-deploy.sh` with worktree support
- [ ] Isolated deploy testing capability
- [ ] Validation gates before merge
- [ ] Rollback procedures

**Validation:**
- Deploy testing works in isolated worktrees
- Changes merge correctly after validation
- Rollback procedures work
- All tests pass

**Rollback:**
- Quick-deploy works without isolation (current behavior)

**Files:**
- Update: `scripts/deploy/nixos-quick-deploy.sh`
- Create: `scripts/deploy/isolated-deploy-test.sh`
- Create: `scripts/testing/test-isolated-deploy.sh`

**Commands:**
```bash
# Test deploy in isolation
scripts/deploy/isolated-deploy-test.sh --workflow=<run-id>

# Merge validated changes
scripts/deploy/merge-worktree-changes.sh --workflow=<run-id>
```

---

### Slice 3.6: Documentation

**Owner:** qwen (documentation)
**Type:** Documentation
**Estimated Effort:** 2-3 days
**Priority:** P2 (enabling)
**Depends on:** All Phase 3 slices

**Scope:**
1. Write worktree isolation documentation
2. Create parallel execution guide
3. Document troubleshooting and recovery
4. Update AGENTS.md with isolation guidance

**Deliverables:**
- [ ] `docs/workflows/isolation-guide.md` - Isolation docs
- [ ] `docs/workflows/parallel-execution.md` - Parallel execution guide
- [ ] `docs/troubleshooting/worktree-issues.md` - Troubleshooting
- [ ] Updated `AGENTS.md` and `docs/AGENTS.md`

**Validation:**
- Documentation complete and accurate
- Examples tested and working
- No broken links
- Reviewed by codex

**Rollback:**
- Documentation updates, no code impact

**Files:**
- Create: `docs/workflows/isolation-guide.md`
- Create: `docs/workflows/parallel-execution.md`
- Create: `docs/troubleshooting/worktree-issues.md`
- Update: `AGENTS.md`
- Update: `docs/AGENTS.md`

---

### Phase 3 Integration Checklist

**Before Phase 3 Sign-off:**
- [ ] All slices validated individually
- [ ] Integration tests pass
- [ ] Parallel execution tested (2-3 concurrent workflows)
- [ ] Cleanup success rate 99%+
- [ ] Documentation complete
- [ ] No regressions in existing functionality
- [ ] Code review complete (codex)
- [ ] Security review complete
- [ ] Tier 0 validation passes

**Integration Commands:**
```bash
# Full validation
scripts/governance/tier0-validation-gate.sh --pre-commit
python -m pytest ai-stack/execution/tests/ -v
scripts/testing/test-isolated-deploy.sh
aq-qa --phase=execution-isolation
```

---

## Phase 4: Enhanced Tooling (Weeks 10-12)

**Objective:** Build tool discovery UI, enhance monitoring, add conversation mining

**Success Criteria:**
- [ ] Tool discovery functional (< 30s to find tool)
- [ ] Dashboard shows workflow runs
- [ ] Conversation mining operational
- [ ] Benchmarks documented
- [ ] Documentation complete

**Dependencies:**
- Phase 1 complete (memory system)
- Phase 2 complete (workflows)

### Slice 4.1: Tool Discovery System

**Status:** Delegated
**Active Run:** `aed542ba-eef7-4d0e-8f6d-dc7030ea6e24`
**Active Queue Task:** `20ac6d89-49d1-4e95-b0c3-008dbef34b30` (`stale pre-fix queue task`)
**Execution Note (2026-04-12):** Harness queue compatibility (`136346a`) and Ralph delegation (`417280b`) are fixed, but remote free lanes are currently blocked by live OpenRouter `429` rate limits after alias refresh. Do not restart this stale task; re-queue after rate-limit recovery or with a BYOK/paid remote lane.
**Local Fallback (2026-04-12):** Use `harness-rpc.js agent-spawn` for bounded local sub-agent prep/review tasks, `harness-rpc.js agent-team` for bounded parallel local team execution, `harness-rpc.js review-handoff` for delegated local review, and `harness-rpc.js runtime-deploy --execute true` / `runtime-rollback --execute true` for allowlisted switchboard-backed runtime verification while the remote queue lanes recover.

**Owner:** qwen (implementation)
**Type:** CLI + Web UI
**Estimated Effort:** 4-5 days
**Priority:** P1 (user-facing)

**Scope:**
1. Create `aq-tools list` command
2. Categorize tools (skills, MCP, APIs, bash)
3. Add search and filtering
4. Build interactive TUI browser
5. Integration with existing tool registry

**Deliverables:**
- [ ] `scripts/ai/aq-tools` - CLI tool
- [ ] Interactive TUI for tool browsing
- [ ] Tool metadata database
- [ ] Search and filter capabilities

**Validation:**
- All tools discoverable
- Search works correctly
- Categories accurate
- TUI functional

**Rollback:**
- New tool, no existing dependencies

**Files:**
- Create: `scripts/ai/aq-tools`
- Create: `ai-stack/tools/registry.py`
- Create: `ai-stack/tools/tui.py`
- Create: `data/tool-metadata.json`

**Commands:**
```bash
# List all tools
aq-tools list

# Search tools
aq-tools search "memory"

# Browse interactively
aq-tools browse

# Show tool details
aq-tools show mempalace_search
```

---

### Slice 4.2: Dashboard Workflow Integration

**Owner:** qwen (frontend)
**Type:** Frontend development
**Estimated Effort:** 5-6 days
**Priority:** P1 (monitoring)

**Scope:**
1. Add workflow run tracking to dashboard
2. Real-time status updates via WebSocket
3. Run history and analytics
4. Session aggregation across agent types
5. Performance metrics visualization

**Deliverables:**
- [ ] Updated dashboard with workflow views
- [ ] Real-time status WebSocket endpoint
- [ ] Run history page
- [ ] Analytics and metrics views

**Validation:**
- Workflow runs visible in dashboard
- Real-time updates work
- History complete and accurate
- Performance acceptable

**Rollback:**
- Dashboard enhancement is additive
- Existing dashboard functionality preserved

**Files:**
- Update: `dashboard/frontend/src/pages/Workflows.tsx` (create if needed)
- Update: `dashboard/backend/api/workflows.py`
- Create: `dashboard/backend/api/websocket.py`
- Update: `dashboard/frontend/src/components/WorkflowStatus.tsx`

**Commands:**
```bash
# Start dashboard
cd dashboard && npm run dev

# Test WebSocket
wscat -c ws://localhost:5173/api/ws/workflows
```

---

### Slice 4.3: Conversation Mining Tool

**Status:** Delegated
**Active Run:** `f5205439-39ad-4d3a-bff9-06f1d8dbe849`
**Active Queue Task:** `f911847c-34c0-457b-a0f9-0c86439c6210` (`stale pre-fix queue task`)
**Execution Note (2026-04-12):** Blocked by the same remote free-lane `429` limit observed during post-fix delegation smoke tests. Re-queue only after rate-limit recovery or alternate remote credentials are available.
**Local Fallback (2026-04-12):** Use `harness-rpc.js agent-spawn` for bounded local sub-agent prep/review tasks, `harness-rpc.js agent-team` for bounded parallel local team execution, `harness-rpc.js review-handoff` for delegated local review, and `harness-rpc.js runtime-deploy --execute true` / `runtime-rollback --execute true` for allowlisted switchboard-backed runtime verification while the remote queue lanes recover.

**Owner:** qwen (implementation)
**Type:** Data processing
**Estimated Effort:** 4-5 days
**Priority:** P2 (nice-to-have)

**Scope:**
1. Import Claude.ai conversation exports
2. Parse session logs into AIDB
3. Extract facts and decisions
4. Build searchable conversation history
5. Integration with memory system

**Deliverables:**
- [ ] `scripts/ai/aq-import` - Import tool
- [ ] Session log parser
- [ ] Fact extraction pipeline
- [ ] Integration with AIDB

**Validation:**
- Imports work correctly
- Facts extracted accurately
- Searchable via memory system
- All tests pass

**Rollback:**
- Import tool is standalone, no dependencies

**Files:**
- Create: `scripts/ai/aq-import`
- Create: `ai-stack/import/claude_parser.py`
- Create: `ai-stack/import/fact_extractor.py`
- Create: `ai-stack/import/tests/test_import.py`

**Commands:**
```bash
# Import Claude conversation
aq-import --source=claude-export conversation-export.json

# Import session logs
aq-import --source=session-logs docs/archive/session-*.md

# Verify imported data
aq-memory search "imported conversations" --imported=true
```

---

### Slice 4.4: Memory System Benchmarking

**Status:** Complete
**Completion Evidence:**
- Benchmark harness fixed to run from repo root
- Added `docs/testing/memory-system-performance.md`
- Added `scripts/testing/memory-regression-tests.py`
- Added `.github/workflows/memory-benchmarks.yml`
- Validation: `python scripts/testing/memory-regression-tests.py`

**Owner:** codex (testing)
**Type:** Performance testing
**Estimated Effort:** 3-4 days
**Priority:** P1 (quality)
**Depends on:** Phase 1 complete

**Scope:**
1. Run comprehensive memory benchmarks
2. Compare with MemPalace baseline
3. Identify performance bottlenecks
4. Document optimization opportunities
5. Create performance regression tests

**Deliverables:**
- [x] Benchmark results document
- [x] Comparison with MemPalace
- [x] Performance regression tests
- [x] Optimization recommendations

**Validation:**
- Benchmarks complete
- Results documented
- Regression tests in CI
- Recommendations clear

**Rollback:**
- Benchmarking only, no production impact

**Files:**
- Create: `docs/testing/memory-system-performance.md`
- Create: `scripts/testing/memory-regression-tests.py`
- Update: `.github/workflows/memory-benchmarks.yml`

**Commands:**
```bash
# Run benchmark suite
python ai-stack/aidb/benchmarks/aq-benchmark recall --all --corpus ai-stack/aidb/benchmarks/memory-benchmark-corpus.json
python ai-stack/aidb/benchmarks/aq-benchmark perf --latency --throughput --storage --memory --corpus ai-stack/aidb/benchmarks/memory-benchmark-corpus.json --queries 100 --duration 3
python scripts/testing/memory-regression-tests.py

# Review baseline report
sed -n '1,200p' docs/testing/memory-system-performance.md
```

---

### Slice 4.5: Documentation

**Owner:** qwen (documentation)
**Type:** Documentation
**Estimated Effort:** 2-3 days
**Priority:** P2 (enabling)
**Depends on:** All Phase 4 slices

**Scope:**
1. Document tool discovery system
2. Create dashboard user guide
3. Document conversation mining
4. Update AGENTS.md with tooling guidance

**Deliverables:**
- [ ] `docs/tools/discovery-guide.md` - Tool discovery docs
- [ ] `docs/dashboard/user-guide.md` - Dashboard docs
- [ ] `docs/operations/conversation-mining.md` - Mining guide
- [ ] Updated `AGENTS.md` and `docs/AGENTS.md`

**Validation:**
- Documentation complete and accurate
- Examples tested and working
- No broken links
- Reviewed by codex

**Rollback:**
- Documentation updates, no code impact

**Files:**
- Create: `docs/tools/discovery-guide.md`
- Create: `docs/dashboard/user-guide.md`
- Create: `docs/operations/conversation-mining.md`
- Update: `AGENTS.md`
- Update: `docs/AGENTS.md`

---

### Phase 4 Integration Checklist

**Before Phase 4 Sign-off:**
- [ ] All slices validated individually
- [ ] Integration tests pass
- [ ] Tool discovery functional
- [ ] Dashboard enhancements working
- [ ] Benchmarks complete
- [ ] Documentation complete
- [ ] No regressions in existing functionality
- [ ] Code review complete (codex)
- [ ] Security review complete
- [ ] Tier 0 validation passes

**Integration Commands:**
```bash
# Full validation
scripts/governance/tier0-validation-gate.sh --pre-commit
aq-tools list --verify
scripts/testing/memory-regression-tests.py
aq-qa --phase=enhanced-tooling
```

---

## Cross-Phase Considerations

### Security Requirements (All Phases)

**Mandatory for all slices:**
- [ ] No hardcoded secrets, API keys, or passwords
- [ ] Load credentials from env/secrets providers only
- [ ] Validate all user inputs at boundaries
- [ ] Audit logging for security-relevant operations
- [ ] Permission checks for file operations

**Security validation:**
```bash
# Check for hardcoded secrets
git diff | grep -i "password\|secret\|key\|token"

# Run security scanner
aq-qa --check=security
```

### Performance Requirements (All Phases)

**Target metrics:**
- Memory queries: < 500ms p95
- Workflow execution overhead: < 10%
- Dashboard load time: < 2s
- CLI command responsiveness: < 100ms

**Performance validation:**
```bash
# Benchmark suite
scripts/testing/performance-benchmarks.py

# Profiling
python -m cProfile -o profile.stats <command>
python -m pstats profile.stats
```

### Documentation Requirements (All Phases)

**Documentation deliverables per phase:**
- Architecture documents (claude)
- API reference (auto-generated + manual)
- User guides (qwen)
- Troubleshooting guides (based on issues)
- Updated AGENTS.md (all relevant changes)

**Documentation validation:**
```bash
# Check for broken links
scripts/testing/check-doc-links.sh

# Verify examples work
scripts/testing/test-doc-examples.sh
```

---

## Resource Allocation

### Agent Profiles & Responsibilities

**claude (architecture):**
- Design decisions and architecture
- Risk analysis
- Long-form synthesis
- Review and approval

**qwen (implementation):**
- Code implementation
- Unit tests
- Documentation writing
- Bug fixes

**codex (orchestration + integration):**
- Integration across components
- Code review and acceptance
- Performance optimization
- CI/CD coordination

**gemini (research):**
- Technology research
- Option analysis
- Documentation research
- Background investigation

### Concurrent Work Patterns

**Phase 1 Parallelization:**
- Slice 1.1 (claude) → blocks 1.2, 1.3
- Slices 1.2 and 1.3 can run in parallel (both depend on 1.1)
- Slice 1.4 can start when 1.2 OR 1.3 completes (partial dependency)
- Slice 1.5 needs 1.2 + 1.3 + 1.4 complete
- Slice 1.6 runs last (documentation)

**Phase 2 Parallelization:**
- Slice 2.1 (claude) → blocks all others
- Slices 2.2 and 2.5 can run in parallel after 2.1
- Slice 2.3 depends on 2.2
- Slice 2.4 depends on 2.3
- Slice 2.6 depends on 2.3 + 2.5
- Slice 2.7 runs last (documentation)

**Maximum Concurrency:**
- Phase 1: Up to 2 agents in parallel (slices 1.2 + 1.3)
- Phase 2: Up to 2 agents in parallel (slices 2.2 + 2.5)
- Phase 3: Up to 2 agents in parallel (slices 3.2 + design review)
- Phase 4: Up to 3 agents in parallel (4.1 + 4.2 + 4.3)

---

## Risk Management

### High-Risk Areas

**1. Memory System Performance**
- Risk: Memory queries too slow for real-time use
- Mitigation: Benchmark early, optimize indexes, add caching
- Fallback: Simpler memory implementation without temporal features

**2. Workflow Determinism**
- Risk: AI agents behave non-deterministically despite workflow structure
- Mitigation: Clear prompts, validation gates, retry logic
- Fallback: Hybrid mode (workflow + freeform)

**3. Worktree Complexity**
- Risk: Git worktree management becomes fragile
- Mitigation: Extensive testing, robust cleanup, monitoring
- Fallback: Make isolation optional, default to current behavior

**4. Integration Conflicts**
- Risk: New features conflict with existing harness
- Mitigation: Feature flags, phased rollout, comprehensive testing
- Fallback: Rollback plan for each phase

### Mitigation Strategies

**Feature Flags:**
```bash
# .env or config
ENABLE_TEMPORAL_FACTS=true
ENABLE_WORKFLOWS=true
ENABLE_WORKTREE_ISOLATION=false
ENABLE_TOOL_DISCOVERY=true
```

**Gradual Rollout:**
1. Test in development environment
2. Deploy to staging with feature flags off
3. Enable one feature at a time
4. Monitor for regressions
5. Full rollout after validation

**Rollback Procedures:**
- Each slice has documented rollback procedure
- Feature flags allow disabling without code changes
- Database migrations reversible
- Configuration changes tracked in git

---

## Success Criteria & Acceptance

### Phase 1 Acceptance Criteria
- [ ] Memory recall accuracy: 85%+ (90%+ with metadata)
- [ ] Query latency: < 500ms p95
- [ ] Storage overhead: < 2x current AIDB
- [ ] Zero regressions in existing AIDB functionality
- [ ] CLI tools operational
- [ ] Documentation complete

### Phase 2 Acceptance Criteria
- [ ] Workflow execution: 100% deterministic (same input → same steps)
- [ ] 10+ templates functional
- [ ] Execution overhead: < 10% vs manual
- [ ] Zero regressions in coordinator
- [ ] CLI tools operational
- [ ] Documentation complete

### Phase 3 Acceptance Criteria
- [ ] Parallel workflows: 2-3x speedup for independent work
- [ ] Cleanup success: 99%+
- [ ] Conflict rate: < 1%
- [ ] Zero regressions in workflow execution
- [ ] Quick-deploy integration functional
- [ ] Documentation complete

### Phase 4 Acceptance Criteria
- [ ] Tool discovery: < 30s to find relevant tool
- [ ] Dashboard load: < 2s
- [ ] Conversation mining: > 100 messages/minute
- [ ] Benchmarks documented
- [ ] Documentation complete

### Overall Project Acceptance
- [ ] All phases complete
- [ ] All acceptance criteria met
- [ ] Zero critical bugs
- [ ] Performance targets met
- [ ] Security review passed
- [ ] Documentation complete and accurate
- [ ] User feedback positive

---

## Monitoring & Metrics

### Key Performance Indicators (KPIs)

**Memory System:**
- Recall accuracy (target: 90%+)
- Query latency p50, p95, p99
- Storage growth rate
- Cache hit rate

**Workflow Engine:**
- Workflow success rate
- Average execution time
- Determinism score (repeatability)
- Template usage distribution

**Execution Isolation:**
- Parallel speedup factor
- Worktree cleanup success rate
- Conflict rate
- Resource utilization

**Overall System:**
- End-to-end task completion time
- Agent token usage (local vs remote)
- Cost per task
- User satisfaction score

### Monitoring Tools

**Existing:**
- `aq-qa` - Health checks
- `aq-report` - Analytics
- Dashboard - Real-time metrics
- `aq-llm-monitor` - LLM usage tracking

**New (Phase 4):**
- Memory system dashboard
- Workflow execution tracking
- Real-time WebSocket updates
- Performance regression alerts

---

## Appendix: Slice Template

**For creating new slices, use this template:**

### Slice X.Y: <Name>

**Owner:** <agent-profile> (<role>)
**Type:** <architecture|implementation|integration|documentation|testing>
**Estimated Effort:** <N-M days>
**Priority:** <P0|P1|P2>
**Depends on:** <Slice dependencies>

**Scope:**
1. <Task 1>
2. <Task 2>
3. <Task 3>

**Deliverables:**
- [ ] <Deliverable 1>
- [ ] <Deliverable 2>
- [ ] <Deliverable 3>

**Validation:**
- <Validation criterion 1>
- <Validation criterion 2>
- <Validation criterion 3>

**Rollback:**
- <Rollback procedure>

**Files:**
- Create: <file-path>
- Update: <file-path>
- Delete: <file-path>

**Commands:**
```bash
# Test
<test-command>

# Validate
<validation-command>
```

---

**Document Version:** 1.0.0
**Last Updated:** 2026-04-09
**Next Review:** After each phase completion
**Owner:** AI Stack Architecture Team
