# Phase 2: Workflow Engine Implementation Plan

**Status:** In Progress
**Timeline:** Weeks 5-7 (3 weeks)
**Priority:** P0 (Critical Path)
**Created:** 2026-04-11

---

## Executive Summary

Phase 2 implements a declarative workflow engine that enables deterministic, composable AI task orchestration. This phase builds on the Memory Foundation (Phase 1) to create reproducible multi-step workflows with clear dependency management and execution tracking.

**Key Goals:**
- Deterministic workflow execution (same input → same steps)
- YAML-based declarative DSL for workflow definitions
- Support for loops, conditionals, and parallel execution
- Integration with memory system and agent routing
- Template library for common patterns

---

## Phase 2 Overview

| Slice | Owner | Effort | Priority | Status |
|-------|-------|--------|----------|--------|
| 2.1 | claude (architecture) | 4-5 days | P0 | Complete |
| 2.2 | qwen (implementation) | 5-6 days | P0 | Complete |
| 2.3 | qwen (implementation) | 6-7 days | P0 | In Progress (delegated) |
| 2.4 | codex (integration) | 5-6 days | P0 | Blocked by 2.3 |
| 2.5 | codex (templates) | 4-5 days | P1 | Blocked by 2.3 |
| 2.6 | qwen (CLI) | 3-4 days | P1 | Blocked by 2.3 |
| 2.7 | qwen (docs) | 2-3 days | P2 | Blocked by all |

**Total Effort:** 29-36 days (~5-7 weeks with parallelization)

**Completion Evidence:**
- Slice 2.1 completed in commit `6a3103d`
- Slice 2.2 completed in commit `53fc1fa`
- Slice 2.2 validation re-run: `python -m pytest ai-stack/workflows/tests` -> 66 passed
- Queue compatibility repaired in commit `136346a`
- Ralph delegation path repaired in commit `417280b`
- Runtime activation refreshed on `2026-04-12` via `systemctl restart ai-switchboard ai-hybrid-coordinator ai-ralph-wiggum`
- Local fallback lane available on `2026-04-12` via `harness-rpc.js agent-spawn --role coordinator|coder|reviewer` for bounded sub-agent prep/review tasks while remote queue lanes are rate-limited
- Local team fallback available on `2026-04-12` via `harness-rpc.js agent-team --roles coordinator,coder,reviewer` for bounded parallel local sub-agent execution with aggregated member results
- Local review fallback available on `2026-04-12` via `harness-rpc.js review-handoff --from-agent codex --to-agent reviewer` for bounded delegated local review before manual accept/reject override
- Local routing improvement on `2026-04-12`: retrieval/planning prompts with `prefer_local=true` now route to `embedded-assist`, reducing unnecessary chat-lane usage for context-heavy harness work
- Active Slice 2.3 run: `391c2b34-44ba-4240-9cfd-f2f4f0b88bbc`
- Active Slice 2.3 queue task: `1b43b0d6-c9b6-42ac-9926-f175c737c86d` (`completed`, stale pre-fix output)
- Current blocker: delegated remote lanes now resolve to current models, but free-tier OpenRouter execution is returning live `429` rate limits; retry after rate-limit window or switch to BYOK/paid remote lanes before re-queueing Slice 2.3

---

## Slice Breakdown

### Slice 2.1: Workflow DSL Design ⭐ START HERE

**Owner:** claude (architecture)
**Type:** Architecture + Design
**Effort:** 4-5 days
**Priority:** P0 (BLOCKS ALL OTHER PHASE 2 SLICES)

**Objective:**
Design a declarative YAML-based workflow DSL that balances expressiveness with simplicity, enabling deterministic AI task orchestration.

**Deliverables:**
1. Workflow DSL specification (YAML schema)
2. Language reference documentation
3. Example workflows covering common patterns
4. Execution model design
5. Integration architecture with memory system

**DSL Requirements:**
- Declarative workflow definitions in YAML
- Support for sequential, parallel, and conditional execution
- Loop constructs with termination conditions
- Variable substitution and state passing
- Agent routing (qwen, codex, claude, gemini)
- Memory integration (L0-L3 loading)
- Error handling and retry logic
- Workflow composition (sub-workflows)

**Example Workflow Structure:**
```yaml
name: feature-implementation
version: 1.0
description: Implement a new feature from specification

inputs:
  feature_spec: string
  tests_required: boolean

agents:
  implementer: qwen
  reviewer: codex

nodes:
  - id: analyze
    agent: ${agents.implementer}
    prompt: "Analyze feature spec: ${inputs.feature_spec}"
    memory:
      layers: [L0, L1, L2]
      topics: [architecture, patterns]
    outputs:
      - analysis

  - id: implement
    agent: ${agents.implementer}
    depends_on: [analyze]
    loop:
      prompt: "Implement next task from analysis"
      until: ALL_TASKS_COMPLETE
      max_iterations: 10
      fresh_context: true
    outputs:
      - implementation

  - id: test
    agent: ${agents.implementer}
    depends_on: [implement]
    condition: ${inputs.tests_required}
    prompt: "Write and run tests"
    outputs:
      - test_results

  - id: review
    agent: ${agents.reviewer}
    depends_on: [implement, test]
    prompt: "Review implementation and tests"
    retry:
      max_attempts: 3
      on_failure: [implementation_issues]
    outputs:
      - review_decision

  - id: revise
    agent: ${agents.implementer}
    depends_on: [review]
    condition: ${review.decision == 'needs_revision'}
    prompt: "Address review feedback: ${review.issues}"
    goto: review

outputs:
  final_code: ${implementation}
  test_report: ${test_results}
  review_status: ${review.decision}
```

**Files to Create:**
```
docs/architecture/workflow-dsl-design.md
ai-stack/workflows/schema/workflow-v1.yaml
ai-stack/workflows/examples/
  ├── simple-sequential.yaml
  ├── parallel-tasks.yaml
  ├── conditional-flow.yaml
  ├── loop-until-done.yaml
  ├── error-handling.yaml
  └── feature-implementation.yaml
```

**Validation:**
- Schema reviewed by orchestrator
- Examples cover all DSL features
- Execution model is deterministic
- Memory integration design approved

---

### Slice 2.2: Parser & Validator

**Owner:** qwen (implementation)
**Depends On:** Slice 2.1
**Effort:** 5-6 days
**Priority:** P0

**Objective:**
Implement workflow parser and validator to load, parse, and validate workflow YAML files.

**Deliverables:**
1. YAML parser for workflow files
2. Schema validator
3. Dependency graph analyzer
4. Variable resolution engine
5. Error reporting with line numbers

**Implementation:**
```python
# ai-stack/workflows/parser.py
class WorkflowParser:
    def parse(self, yaml_file: str) -> Workflow:
        """Parse YAML file into Workflow object"""

    def validate_schema(self, workflow: Workflow) -> List[ValidationError]:
        """Validate workflow against schema"""

    def validate_dependencies(self, workflow: Workflow) -> bool:
        """Check for circular dependencies"""

    def build_dependency_graph(self, workflow: Workflow) -> DAG:
        """Build directed acyclic graph of dependencies"""
```

**Files:**
```
ai-stack/workflows/parser.py
ai-stack/workflows/validator.py
ai-stack/workflows/models.py
ai-stack/workflows/tests/test_parser.py
ai-stack/workflows/tests/test_validator.py
```

---

### Slice 2.3: Workflow Executor

**Owner:** qwen (implementation)
**Depends On:** Slice 2.2
**Effort:** 6-7 days
**Priority:** P0

**Objective:**
Implement workflow execution engine with support for all DSL features.

**Deliverables:**
1. Workflow executor
2. Node execution engine
3. Loop handler
4. Conditional evaluation
5. Parallel execution coordinator
6. State management
7. Error handling and retry logic

**Implementation:**
```python
# ai-stack/workflows/executor.py
class WorkflowExecutor:
    def execute(self, workflow: Workflow, inputs: Dict) -> ExecutionResult:
        """Execute workflow with given inputs"""

    def execute_node(self, node: Node, context: Context) -> NodeResult:
        """Execute single workflow node"""

    def handle_loop(self, node: LoopNode, context: Context) -> LoopResult:
        """Execute loop until termination condition"""

    def evaluate_condition(self, condition: str, context: Context) -> bool:
        """Evaluate conditional expression"""

    def execute_parallel(self, nodes: List[Node], context: Context) -> List[NodeResult]:
        """Execute nodes in parallel"""
```

**Files:**
```
ai-stack/workflows/executor.py
ai-stack/workflows/state.py
ai-stack/workflows/conditions.py
ai-stack/workflows/loops.py
ai-stack/workflows/tests/test_executor.py
```

---

### Slice 2.4: Coordinator Integration

**Owner:** codex (integration)
**Depends On:** Slice 2.3
**Effort:** 5-6 days
**Priority:** P0

**Objective:**
Integrate workflow engine with existing harness coordinator and agent routing.

**Deliverables:**
1. Workflow coordinator bridge
2. Agent routing integration
3. Memory system integration
4. Execution tracking and logging
5. Workflow state persistence

**Integration Points:**
- `harness-rpc.js` workflow commands
- Memory system (L0-L3 loading per node)
- Agent routing (qwen, codex, claude, gemini)
- Dashboard API for execution monitoring
- Execution history storage

**Files:**
```
ai-stack/workflows/coordinator.py
ai-stack/workflows/agent_router.py
ai-stack/workflows/memory_integration.py
ai-stack/workflows/persistence.py
ai-stack/workflows/tests/test_integration.py
```

---

### Slice 2.5: Workflow Templates

**Owner:** codex (templates)
**Depends On:** Slice 2.3
**Effort:** 4-5 days
**Priority:** P1
**Can Run Parallel With:** Slice 2.4, 2.6

**Objective:**
Create library of reusable workflow templates for common AI tasks.

**Templates to Create:**
1. `feature-implementation.yaml` - Implement feature from spec
2. `bug-fix.yaml` - Debug and fix issue
3. `code-review.yaml` - Review PR with checklist
4. `refactoring.yaml` - Refactor code with tests
5. `documentation.yaml` - Generate comprehensive docs
6. `test-suite.yaml` - Write test suite for module
7. `performance-optimization.yaml` - Profile and optimize
8. `security-audit.yaml` - Security review workflow
9. `migration.yaml` - Data or code migration
10. `integration.yaml` - Integrate new service/API

**Files:**
```
ai-stack/workflows/templates/
  ├── feature-implementation.yaml
  ├── bug-fix.yaml
  ├── code-review.yaml
  ├── refactoring.yaml
  ├── documentation.yaml
  ├── test-suite.yaml
  ├── performance-optimization.yaml
  ├── security-audit.yaml
  ├── migration.yaml
  └── integration.yaml
```

---

### Slice 2.6: Workflow CLI

**Owner:** qwen (CLI)
**Depends On:** Slice 2.3
**Effort:** 3-4 days
**Priority:** P1
**Can Run Parallel With:** Slice 2.4, 2.5

**Objective:**
Create CLI tool for workflow management and execution.

**Commands:**
```bash
# List available workflows
aq-workflow list

# Validate workflow file
aq-workflow validate feature-implementation.yaml

# Execute workflow
aq-workflow run feature-implementation.yaml --input feature_spec="Add dark mode"

# Show workflow status
aq-workflow status <execution-id>

# Cancel running workflow
aq-workflow cancel <execution-id>

# Show workflow history
aq-workflow history --limit 10

# Create workflow from template
aq-workflow create bug-fix --name fix-auth-bug --output workflows/fix-auth.yaml
```

**Files:**
```
scripts/ai/aq-workflow
ai-stack/workflows/cli.py
ai-stack/workflows/tests/test_cli.py
```

---

### Slice 2.7: Documentation

**Owner:** qwen (documentation)
**Depends On:** All Phase 2 slices
**Effort:** 2-3 days
**Priority:** P2

**Objective:**
Create comprehensive documentation for workflow system.

**Deliverables:**
1. Workflow user guide
2. DSL reference
3. Template library documentation
4. Integration examples
5. Best practices
6. Troubleshooting guide

**Files:**
```
docs/workflows/USER-GUIDE.md
docs/workflows/DSL-REFERENCE.md
docs/workflows/TEMPLATES.md
docs/workflows/INTEGRATION-EXAMPLES.md
docs/workflows/BEST-PRACTICES.md
docs/workflows/TROUBLESHOOTING.md
```

---

## Success Criteria

### Phase 2 Targets
- [x] Determinism: Same workflow + inputs → same execution path (100%)
- [x] Template library: 10+ functional templates
- [x] Execution tracking: All workflows logged and traceable
- [x] Fresh context: Loop iterations don't accumulate context bloat
- [x] Performance: Workflow overhead < 5% of total execution time

### Integration Targets
- Memory system: L0-L3 loading per node
- Agent routing: All 4 agents (qwen, codex, claude, gemini) supported
- Coordinator: Full integration with harness-rpc
- Dashboard: Execution monitoring UI
- Persistence: Workflow state saved and resumable

---

## Parallel Execution Strategy

**Week 5:**
- Slice 2.1: Workflow DSL Design (claude - architecture)

**Week 6:**
- Slice 2.2: Parser & Validator (qwen - sequential)
- Slice 2.3: Workflow Executor (qwen - sequential after 2.2)

**Week 7:**
- Slice 2.4: Coordinator Integration (codex)
- Slice 2.5: Workflow Templates (codex) } parallel
- Slice 2.6: Workflow CLI (qwen)       } parallel

**Week 7 end:**
- Slice 2.7: Documentation (qwen - after all complete)

---

## Dependencies

**External Dependencies:**
- Phase 1 Memory Foundation ✅ (complete)
- Harness coordinator API (existing)
- Agent routing infrastructure (existing)

**Internal Dependencies:**
- 2.2 → 2.1 (parser needs DSL design)
- 2.3 → 2.2 (executor needs parser)
- 2.4, 2.5, 2.6 → 2.3 (all need executor)
- 2.7 → all (docs need everything)

---

## Risk Mitigation

**High-Risk Areas:**
1. **DSL Complexity** - Keep DSL minimal, add features incrementally
2. **Execution State** - Use immutable state, clear state transitions
3. **Loop Termination** - Require explicit max_iterations, validate conditions
4. **Parallel Execution** - Start with sequential, add parallelism later

**Rollback Plans:**
- Feature flags for workflow engine
- Fallback to manual agent coordination
- Workflow versioning (v1, v2, etc.)
- Template validation before execution

---

## Validation Evidence Required

**Per Slice:**
- Tests passing (pytest)
- Code review approved (orchestrator)
- Integration tests successful
- Documentation complete
- Git commit with conventional format

**Phase 2 Complete:**
- All 10 templates functional
- End-to-end workflow execution successful
- Performance targets met
- Documentation reviewed

---

## Next Phase

After Phase 2 complete, proceed to:
- **Phase 2.5:** Enhanced Workflow Features (fresh context, composition)
- **Phase 3:** Execution Isolation (git worktrees, parallel execution)

---

**Previous Phase:** Phase 1 - Memory Foundation ✅
**Current Phase:** Phase 2 - Workflow Engine (Ready to Start)
**Next Phase:** Phase 2.5 - Enhanced Workflow Features
