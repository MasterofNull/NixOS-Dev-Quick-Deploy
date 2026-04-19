# Phase 2 Slice 2.1: Workflow DSL Design

**Status:** Ready for Execution
**Owner:** claude (architecture)
**Effort:** 4-5 days
**Priority:** P0 (BLOCKS ALL OTHER PHASE 2 SLICES)
**Created:** 2026-04-11

---

## Objective

Design a declarative YAML-based workflow DSL (Domain-Specific Language) that enables deterministic, reproducible AI task orchestration while remaining simple and intuitive for developers.

## Success Criteria

- [x] Workflow DSL specification complete
- [x] YAML schema defined and validated
- [x] Language reference documentation written
- [x] Example workflows cover all features
- [x] Execution model designed
- [x] Memory integration architecture defined
- [x] Reviewed and approved by orchestrator

---

## Background

### Problem Statement

Current AI task orchestration relies on:
- Manual agent coordination (error-prone)
- Imperative scripts (not reproducible)
- Unclear dependency management
- No standard execution model
- Limited composability

### Solution

A declarative workflow DSL that:
- Defines tasks as workflows in YAML
- Ensures deterministic execution
- Supports loops, conditionals, parallelism
- Integrates with memory system (L0-L3)
- Enables workflow composition
- Provides clear error handling

---

## Design Requirements

### Functional Requirements

1. **Declarative Syntax**
   - YAML-based for readability
   - No embedded code execution
   - Clear, self-documenting structure

2. **Core Features**
   - Sequential execution (default)
   - Parallel execution (explicit)
   - Conditional branching
   - Loop constructs with termination
   - Variable substitution
   - State passing between nodes

3. **Agent Integration**
   - Route to specific agents (qwen, codex, claude, gemini)
   - Support for agent preferences
   - Fallback agents

4. **Memory Integration**
   - L0-L3 layer specification per node
   - Topic-based memory loading
   - Memory isolation options

5. **Error Handling**
   - Retry logic with max attempts
   - Error handlers
   - Graceful degradation

6. **Workflow Composition**
   - Sub-workflow calls
   - Parameter passing
   - Output aggregation

### Non-Functional Requirements

1. **Determinism**
   - Same workflow + inputs → same execution path
   - No hidden state dependencies
   - Reproducible across runs

2. **Performance**
   - Fast parsing (< 100ms for typical workflow)
   - Minimal execution overhead (< 5%)
   - Efficient state management

3. **Usability**
   - Intuitive syntax
   - Clear error messages
   - Good defaults, minimal boilerplate

4. **Extensibility**
   - Version-able schema
   - Plugin architecture for future features
   - Backward compatibility

---

## DSL Specification

### Workflow Structure

```yaml
# Workflow metadata
name: string                    # Unique workflow identifier
version: string                 # Semantic version (1.0, 2.1, etc.)
description: string             # Human-readable description

# Input parameters
inputs:
  param_name: type             # Type: string, number, boolean, object, array
  optional_param:
    type: string
    default: "value"
    description: "Parameter description"

# Agent definitions (optional, can be referenced in nodes)
agents:
  role_name: agent_id           # qwen, codex, claude, gemini

# Workflow execution nodes
nodes:
  - id: string                  # Unique node identifier
    agent: string               # Agent to execute (qwen, codex, claude, gemini, ${agents.role})
    prompt: string              # Task prompt (supports variable substitution)
    depends_on: [string]        # List of node IDs that must complete first
    condition: string           # Boolean expression (optional)
    memory:                     # Memory configuration (optional)
      layers: [L0, L1, L2, L3]  # Memory layers to load
      topics: [string]          # Topic filters for L2
      max_tokens: number        # Token budget
    loop:                       # Loop configuration (optional)
      prompt: string            # Prompt for each iteration
      until: condition          # Termination condition
      max_iterations: number    # Safety limit
      fresh_context: boolean    # Reset context each iteration
    retry:                      # Retry configuration (optional)
      max_attempts: number      # Maximum retry attempts
      on_failure: [string]      # Error types to retry
      backoff: exponential      # Backoff strategy
    parallel: boolean           # Execute in parallel (default: false)
    outputs:                    # Output variable names
      - variable_name

# Workflow outputs
outputs:
  output_name: ${node.variable}  # Reference to node outputs
```

### Example: Feature Implementation Workflow

```yaml
name: feature-implementation
version: 1.0
description: Implement a new feature from specification with tests and review

inputs:
  feature_spec:
    type: string
    description: "Feature specification or description"
  tests_required:
    type: boolean
    default: true
  review_required:
    type: boolean
    default: true

agents:
  implementer: qwen
  reviewer: codex

nodes:
  # Step 1: Analyze feature specification
  - id: analyze
    agent: ${agents.implementer}
    prompt: |
      Analyze the following feature specification and create an implementation plan.
      Break it down into concrete, testable tasks.

      Feature Spec: ${inputs.feature_spec}
    memory:
      layers: [L0, L1, L2]
      topics: [architecture, patterns, conventions]
      max_tokens: 500
    outputs:
      - analysis
      - task_list

  # Step 2: Implement tasks in loop
  - id: implement
    agent: ${agents.implementer}
    depends_on: [analyze]
    loop:
      prompt: |
        Implement the next task from the plan.
        Completed tasks: ${state.completed_tasks}
        Remaining tasks: ${state.remaining_tasks}
      until: ALL_TASKS_COMPLETE
      max_iterations: 20
      fresh_context: true
    memory:
      layers: [L0, L1, L2]
      topics: [coding, ${analyze.relevant_topics}]
    outputs:
      - implementation
      - files_changed

  # Step 3: Write tests (conditional)
  - id: test
    agent: ${agents.implementer}
    depends_on: [implement]
    condition: ${inputs.tests_required}
    prompt: |
      Write comprehensive tests for the implemented feature.
      Files changed: ${implement.files_changed}
    retry:
      max_attempts: 3
      on_failure: [test_failure]
    outputs:
      - test_results
      - coverage

  # Step 4: Review (conditional)
  - id: review
    agent: ${agents.reviewer}
    depends_on: [implement, test]
    condition: ${inputs.review_required}
    prompt: |
      Review the implementation and tests.

      Implementation: ${implement.implementation}
      Tests: ${test.test_results}
      Coverage: ${test.coverage}

      Check for:
      - Code quality
      - Security issues
      - Performance concerns
      - Test coverage
    outputs:
      - decision  # approve, needs_revision, reject
      - feedback

  # Step 5: Revise based on feedback (conditional loop)
  - id: revise
    agent: ${agents.implementer}
    depends_on: [review]
    condition: ${review.decision == 'needs_revision'}
    prompt: |
      Address the review feedback:
      ${review.feedback}
    outputs:
      - revision
    goto: review  # Re-run review after revision

  # Step 6: Final validation
  - id: validate
    agent: ${agents.implementer}
    depends_on: [review]
    condition: ${review.decision == 'approve'}
    prompt: |
      Run final validation checks:
      - All tests passing
      - Linter checks passing
      - Documentation updated
    outputs:
      - validation_status

outputs:
  final_implementation: ${implement.implementation}
  test_report: ${test.test_results}
  review_status: ${review.decision}
  files_changed: ${implement.files_changed}
```

### Example: Parallel Task Execution

```yaml
name: parallel-analysis
version: 1.0
description: Analyze codebase from multiple perspectives in parallel

inputs:
  codebase_path: string

nodes:
  # Run these in parallel
  - id: security-scan
    agent: claude
    prompt: "Security audit of ${inputs.codebase_path}"
    parallel: true
    outputs:
      - security_issues

  - id: performance-scan
    agent: qwen
    prompt: "Performance analysis of ${inputs.codebase_path}"
    parallel: true
    outputs:
      - performance_issues

  - id: code-quality-scan
    agent: codex
    prompt: "Code quality review of ${inputs.codebase_path}"
    parallel: true
    outputs:
      - quality_issues

  # Aggregate results after all parallel tasks complete
  - id: aggregate
    agent: claude
    depends_on: [security-scan, performance-scan, code-quality-scan]
    prompt: |
      Aggregate findings from all scans:
      Security: ${security-scan.security_issues}
      Performance: ${performance-scan.performance_issues}
      Quality: ${code-quality-scan.quality_issues}
    outputs:
      - consolidated_report

outputs:
  report: ${aggregate.consolidated_report}
```

---

## Execution Model

### State Management

**Workflow State:**
```python
class WorkflowState:
    workflow_id: str
    status: str  # pending, running, completed, failed
    inputs: Dict[str, Any]
    node_states: Dict[str, NodeState]
    outputs: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
```

**Node State:**
```python
class NodeState:
    node_id: str
    status: str  # pending, running, completed, failed, skipped
    agent: str
    outputs: Dict[str, Any]
    error: Optional[str]
    attempts: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

### Execution Flow

1. **Parse & Validate**
   - Load YAML workflow
   - Validate schema
   - Build dependency graph
   - Check for cycles

2. **Initialize State**
   - Create workflow execution record
   - Initialize node states
   - Resolve input variables

3. **Execute Nodes**
   - Topological sort by dependencies
   - For each node:
     - Check dependencies satisfied
     - Evaluate condition (if any)
     - Load memory (L0-L3)
     - Execute agent task
     - Store outputs
     - Update state

4. **Handle Loops**
   - Execute loop body
   - Evaluate termination condition
   - Check max_iterations
   - Optionally reset context

5. **Aggregate Outputs**
   - Collect outputs from completed nodes
   - Resolve output expressions
   - Return final workflow result

### Determinism Guarantees

1. **No Hidden State**
   - All state explicit in workflow YAML
   - No ambient environment dependencies
   - Clear variable scoping

2. **Reproducible Agent Execution**
   - Same prompt + context → same agent behavior (best effort)
   - Memory loading deterministic (L0-L3)
   - No random sampling (temperature=0 recommended)

3. **Clear Execution Order**
   - Dependency graph determines order
   - Parallel nodes have undefined interleaving but deterministic aggregation
   - No race conditions in state updates

---

## Memory Integration

### Layer Loading Per Node

```yaml
nodes:
  - id: example
    memory:
      layers: [L0, L1, L2]      # Load identity, critical facts, topic-specific
      topics: [architecture]    # Filter L2 by topic
      max_tokens: 500           # Budget constraint
```

**Loading Strategy:**
1. Always load L0 (identity, 50 tokens)
2. Always load L1 (critical facts, 170 tokens)
3. Load L2 if topics specified (variable tokens)
4. Load L3 only if explicitly requested (heavy)
5. Respect max_tokens budget

### Memory Isolation

```yaml
nodes:
  - id: private-task
    memory:
      isolation: agent          # Only load agent's own memories
      diary_only: true          # Only agent diary, no shared facts
```

---

## Error Handling

### Retry Logic

```yaml
nodes:
  - id: flaky-task
    retry:
      max_attempts: 3
      on_failure: [api_timeout, network_error]
      backoff: exponential      # 1s, 2s, 4s
      backoff_base: 1
```

### Error Handlers

```yaml
nodes:
  - id: critical-task
    on_error:
      handler: fallback-task
      continue: false           # Stop workflow on error

  - id: fallback-task
    prompt: "Handle error: ${critical-task.error}"
```

---

## Validation Rules

1. **Schema Validation**
   - All required fields present
   - Type correctness
   - Valid enum values

2. **Dependency Validation**
   - No circular dependencies
   - Referenced nodes exist
   - Dependencies form DAG

3. **Variable Validation**
   - All variables referenced are defined
   - Output variables unique per node
   - Correct variable syntax

4. **Agent Validation**
   - Agent IDs valid (qwen, codex, claude, gemini)
   - Agent routing configured

5. **Memory Validation**
   - Valid layer specifications
   - Topics exist in memory system
   - Token budgets reasonable

---

## Deliverables

### 1. DSL Specification Document

**File:** `docs/architecture/workflow-dsl-design.md`

**Contents:**
- DSL syntax specification
- Execution model
- Memory integration
- Error handling
- Best practices
- Migration path

### 2. YAML Schema

**File:** `ai-stack/workflows/schema/workflow-v1.yaml`

JSON Schema for workflow validation.

### 3. Example Workflows

**Directory:** `ai-stack/workflows/examples/`

- `simple-sequential.yaml` - Basic sequential execution
- `parallel-tasks.yaml` - Parallel task execution
- `conditional-flow.yaml` - Conditional branching
- `loop-until-done.yaml` - Loop with termination
- `error-handling.yaml` - Retry and error handling
- `feature-implementation.yaml` - Complete feature workflow
- `sub-workflow.yaml` - Workflow composition

### 4. Language Reference

**File:** `docs/workflows/DSL-REFERENCE.md`

Complete reference documentation for all DSL features.

---

## Implementation Guidance

### Parser Implementation (Slice 2.2)

Use `pyyaml` for parsing:
```python
import yaml
from typing import Dict, Any

def parse_workflow(yaml_path: str) -> Dict[str, Any]:
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)
```

### Validator Implementation (Slice 2.2)

Use `jsonschema` for validation:
```python
import jsonschema

def validate_workflow(workflow: Dict, schema: Dict) -> List[str]:
    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(workflow))
    return [e.message for e in errors]
```

### Executor Implementation (Slice 2.3)

```python
class WorkflowExecutor:
    def execute(self, workflow: Workflow, inputs: Dict) -> WorkflowResult:
        state = self.initialize_state(workflow, inputs)
        dag = self.build_dag(workflow)

        for node in dag.topological_sort():
            if self.should_execute(node, state):
                result = self.execute_node(node, state)
                state.update(node.id, result)

        return self.aggregate_outputs(workflow, state)
```

---

## Validation Criteria

- [x] DSL specification document complete
- [x] YAML schema passes validation
- [x] All example workflows valid
- [x] Execution model is deterministic
- [x] Memory integration design clear
- [x] Error handling comprehensive
- [x] Language reference complete
- [x] Reviewed by orchestrator
- [x] No breaking changes to existing systems

---

## Acceptance Criteria

1. DSL specification covers all required features
2. YAML schema defined and self-validating
3. 7+ example workflows demonstrating all features
4. Execution model ensures determinism
5. Memory integration leverages L0-L3 layers
6. Error handling covers common failure modes
7. Language reference is comprehensive
8. Design approved by orchestrator (codex)
9. Git commit with conventional format
10. Ready for Slice 2.2 (Parser & Validator)

---

## Notes

- Keep DSL minimal - add features incrementally
- Prioritize readability over expressiveness
- Ensure backward compatibility in schema versioning
- Consider future features: workflows as code, IDE integration
- Reference MemPalace and Archon workflow systems for inspiration

---

**Next Slice:** Phase 2 Slice 2.2 - Parser & Validator
**Blocks:** All other Phase 2 slices
