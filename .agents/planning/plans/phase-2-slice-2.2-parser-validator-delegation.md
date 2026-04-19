# Phase 2 Slice 2.2: Parser & Validator - Delegation Plan

**Delegated To:** qwen (implementation agent)
**Delegated By:** claude (orchestrator)
**Depends On:** Slice 2.1 (Workflow DSL Design) ✅ COMPLETE
**Effort:** 5-6 days
**Priority:** P0 (BLOCKS SLICE 2.3+)
**Created:** 2026-04-11

---

## Delegation Context

Slice 2.1 (Workflow DSL Design) is complete with:
- ✅ DSL specification document
- ✅ JSON Schema for validation (workflow-v1.yaml)
- ✅ 7 example workflows demonstrating all features
- ✅ Execution model designed
- ✅ Memory integration architecture defined

**Your task:** Implement the workflow parser and validator based on the completed design.

---

## Objective

Implement a robust workflow parser and validator that:
1. Loads and parses YAML workflow files
2. Validates workflows against the JSON Schema
3. Analyzes dependency graphs for cycles
4. Validates variable references
5. Provides clear error messages with line numbers

---

## Required Reading

Before starting, read these files in order:

1. **DSL Specification** (PRIMARY REFERENCE):
   - `docs/architecture/workflow-dsl-design.md`

2. **JSON Schema**:
   - `ai-stack/workflows/schema/workflow-v1.yaml`

3. **Example Workflows** (for testing):
   - `ai-stack/workflows/examples/simple-sequential.yaml`
   - `ai-stack/workflows/examples/parallel-tasks.yaml`
   - `ai-stack/workflows/examples/conditional-flow.yaml`
   - `ai-stack/workflows/examples/loop-until-done.yaml`
   - `ai-stack/workflows/examples/error-handling.yaml`
   - `ai-stack/workflows/examples/feature-implementation.yaml`
   - `ai-stack/workflows/examples/sub-workflow.yaml`

---

## Deliverables

### 1. Data Models (`ai-stack/workflows/models.py`)

Define Python dataclasses for workflow representation:

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from enum import Enum

@dataclass
class MemoryConfig:
    layers: List[str]  # L0, L1, L2, L3
    topics: Optional[List[str]] = None
    max_tokens: int = 500
    isolation: Optional[str] = None
    diary_only: bool = False

@dataclass
class LoopConfig:
    until: str
    max_iterations: int
    prompt: Optional[str] = None
    fresh_context: bool = False

@dataclass
class RetryConfig:
    max_attempts: int = 3
    on_failure: Optional[List[str]] = None
    backoff: str = "exponential"
    backoff_base: float = 1.0

@dataclass
class ErrorHandler:
    handler: str
    continue_workflow: bool = False

@dataclass
class WorkflowNode:
    id: str
    agent: str
    prompt: str
    depends_on: List[str] = None
    condition: Optional[str] = None
    memory: Optional[MemoryConfig] = None
    loop: Optional[LoopConfig] = None
    retry: Optional[RetryConfig] = None
    parallel: bool = False
    outputs: Optional[List[str]] = None
    goto: Optional[str] = None
    on_error: Optional[ErrorHandler] = None

@dataclass
class Workflow:
    name: str
    version: str
    description: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    agents: Optional[Dict[str, str]] = None
    nodes: List[WorkflowNode] = None
    outputs: Optional[Dict[str, str]] = None
```

### 2. YAML Parser (`ai-stack/workflows/parser.py`)

```python
import yaml
from pathlib import Path
from typing import Dict, Any
from .models import Workflow, WorkflowNode, MemoryConfig, LoopConfig, RetryConfig

class WorkflowParser:
    """Parse YAML workflow files into Workflow objects"""

    def parse_file(self, yaml_file: str) -> Workflow:
        """
        Parse YAML file into Workflow object

        Args:
            yaml_file: Path to YAML workflow file

        Returns:
            Workflow object

        Raises:
            ParseError: If YAML is malformed
        """
        # Load YAML using safe_load
        # Convert to Workflow dataclass
        # Handle nested structures (memory, loop, retry configs)
        pass

    def parse_dict(self, workflow_dict: Dict[str, Any]) -> Workflow:
        """Parse workflow dictionary into Workflow object"""
        pass

    def _parse_node(self, node_dict: Dict[str, Any]) -> WorkflowNode:
        """Parse a single node definition"""
        pass

    def _parse_memory_config(self, memory_dict: Dict[str, Any]) -> MemoryConfig:
        """Parse memory configuration"""
        pass

    def _parse_loop_config(self, loop_dict: Dict[str, Any]) -> LoopConfig:
        """Parse loop configuration"""
        pass

    def _parse_retry_config(self, retry_dict: Dict[str, Any]) -> RetryConfig:
        """Parse retry configuration"""
        pass
```

### 3. Schema Validator (`ai-stack/workflows/validator.py`)

```python
import jsonschema
from typing import List, Dict, Any
from .models import Workflow, WorkflowNode

class ValidationError:
    """Represents a validation error with context"""
    def __init__(self, message: str, path: str = None, line: int = None):
        self.message = message
        self.path = path
        self.line = line

class WorkflowValidator:
    """Validate workflows against schema and business rules"""

    def __init__(self, schema_file: str = None):
        """
        Initialize validator with JSON Schema

        Args:
            schema_file: Path to JSON Schema file
        """
        # Load JSON Schema from ai-stack/workflows/schema/workflow-v1.yaml
        pass

    def validate_schema(self, workflow: Workflow) -> List[ValidationError]:
        """
        Validate workflow against JSON Schema

        Args:
            workflow: Workflow object to validate

        Returns:
            List of validation errors (empty if valid)
        """
        # Use jsonschema library to validate
        # Convert validation errors to ValidationError objects
        pass

    def validate_dependencies(self, workflow: Workflow) -> List[ValidationError]:
        """
        Validate dependency graph:
        - No circular dependencies
        - Referenced nodes exist
        - Dependencies form a DAG

        Returns:
            List of validation errors
        """
        # Build dependency graph
        # Check for cycles using DFS
        # Validate node references
        pass

    def validate_variables(self, workflow: Workflow) -> List[ValidationError]:
        """
        Validate variable references:
        - All referenced variables are defined
        - Output variables are unique per node
        - Correct variable syntax

        Returns:
            List of validation errors
        """
        # Parse variable references (${...})
        # Check inputs, node outputs, agent references
        # Validate syntax
        pass

    def validate_agents(self, workflow: Workflow) -> List[ValidationError]:
        """
        Validate agent configuration:
        - Agent IDs are valid (qwen, codex, claude, gemini)
        - Agent references resolve correctly

        Returns:
            List of validation errors
        """
        pass

    def validate_memory(self, workflow: Workflow) -> List[ValidationError]:
        """
        Validate memory configuration:
        - Valid layer specifications (L0, L1, L2, L3)
        - Token budgets are reasonable

        Returns:
            List of validation errors
        """
        pass

    def validate_all(self, workflow: Workflow) -> List[ValidationError]:
        """
        Run all validations

        Returns:
            Combined list of all validation errors
        """
        errors = []
        errors.extend(self.validate_schema(workflow))
        errors.extend(self.validate_dependencies(workflow))
        errors.extend(self.validate_variables(workflow))
        errors.extend(self.validate_agents(workflow))
        errors.extend(self.validate_memory(workflow))
        return errors
```

### 4. Dependency Graph Analyzer (`ai-stack/workflows/graph.py`)

```python
from typing import List, Set, Dict
from .models import Workflow, WorkflowNode

class DependencyGraph:
    """Directed acyclic graph of workflow node dependencies"""

    def __init__(self, workflow: Workflow):
        """Build dependency graph from workflow"""
        self.workflow = workflow
        self.adjacency_list: Dict[str, Set[str]] = {}
        self._build_graph()

    def _build_graph(self):
        """Build adjacency list representation"""
        # Create adjacency list from node.depends_on
        pass

    def has_cycle(self) -> bool:
        """Check if graph contains cycles"""
        # Use DFS with visited/recursion stack
        pass

    def find_cycle(self) -> List[str]:
        """Find and return a cycle if one exists"""
        pass

    def topological_sort(self) -> List[str]:
        """
        Return nodes in topological order (dependencies first)

        Raises:
            ValueError: If graph has cycles
        """
        # Kahn's algorithm or DFS-based topological sort
        pass

    def get_dependencies(self, node_id: str) -> Set[str]:
        """Get all dependencies of a node (recursive)"""
        pass

    def get_dependents(self, node_id: str) -> Set[str]:
        """Get all nodes that depend on this node"""
        pass
```

### 5. Comprehensive Tests (`ai-stack/workflows/tests/`)

Create test files:
- `test_parser.py` - Parser tests
- `test_validator.py` - Validator tests
- `test_graph.py` - Dependency graph tests
- `test_integration.py` - End-to-end tests

**Test Coverage Requirements:**
- All example workflows parse correctly
- Schema validation catches invalid workflows
- Dependency graph detects cycles
- Variable validation catches undefined references
- Error messages include helpful context
- Edge cases handled (empty workflows, single node, etc.)

```python
# ai-stack/workflows/tests/test_parser.py
import pytest
from pathlib import Path
from ..parser import WorkflowParser
from ..models import Workflow

class TestWorkflowParser:
    @pytest.fixture
    def parser(self):
        return WorkflowParser()

    def test_parse_simple_sequential(self, parser):
        """Test parsing simple-sequential.yaml"""
        workflow = parser.parse_file("ai-stack/workflows/examples/simple-sequential.yaml")
        assert workflow.name == "simple-sequential"
        assert workflow.version == "1.0"
        assert len(workflow.nodes) == 3
        assert workflow.nodes[0].id == "analyze"

    def test_parse_parallel_tasks(self, parser):
        """Test parsing parallel-tasks.yaml"""
        workflow = parser.parse_file("ai-stack/workflows/examples/parallel-tasks.yaml")
        parallel_nodes = [n for n in workflow.nodes if n.parallel]
        assert len(parallel_nodes) == 3

    def test_parse_conditional_flow(self, parser):
        """Test parsing conditional-flow.yaml"""
        workflow = parser.parse_file("ai-stack/workflows/examples/conditional-flow.yaml")
        conditional_nodes = [n for n in workflow.nodes if n.condition]
        assert len(conditional_nodes) > 0

    def test_parse_loop(self, parser):
        """Test parsing loop-until-done.yaml"""
        workflow = parser.parse_file("ai-stack/workflows/examples/loop-until-done.yaml")
        loop_nodes = [n for n in workflow.nodes if n.loop]
        assert len(loop_nodes) == 1
        assert loop_nodes[0].loop.max_iterations == 10

    def test_parse_error_handling(self, parser):
        """Test parsing error-handling.yaml"""
        workflow = parser.parse_file("ai-stack/workflows/examples/error-handling.yaml")
        retry_nodes = [n for n in workflow.nodes if n.retry]
        assert len(retry_nodes) > 0

    def test_parse_invalid_yaml(self, parser):
        """Test that malformed YAML raises ParseError"""
        with pytest.raises(Exception):
            parser.parse_file("nonexistent.yaml")

# ai-stack/workflows/tests/test_validator.py
import pytest
from ..validator import WorkflowValidator, ValidationError
from ..parser import WorkflowParser

class TestWorkflowValidator:
    @pytest.fixture
    def validator(self):
        return WorkflowValidator()

    @pytest.fixture
    def parser(self):
        return WorkflowParser()

    def test_validate_all_examples(self, validator, parser):
        """Test that all example workflows are valid"""
        examples = [
            "simple-sequential.yaml",
            "parallel-tasks.yaml",
            "conditional-flow.yaml",
            "loop-until-done.yaml",
            "error-handling.yaml",
            "feature-implementation.yaml",
            "sub-workflow.yaml",
        ]
        for example in examples:
            workflow = parser.parse_file(f"ai-stack/workflows/examples/{example}")
            errors = validator.validate_all(workflow)
            assert len(errors) == 0, f"Validation errors in {example}: {errors}"

    def test_detect_circular_dependency(self, validator):
        """Test that circular dependencies are detected"""
        # Create workflow with circular dependency
        # Validate and check for cycle error
        pass

    def test_detect_undefined_node_reference(self, validator):
        """Test that undefined node references are caught"""
        pass

    def test_detect_invalid_variable_reference(self, validator):
        """Test that invalid variable syntax is caught"""
        pass

    def test_detect_invalid_agent(self, validator):
        """Test that invalid agent IDs are caught"""
        pass

# ai-stack/workflows/tests/test_graph.py
import pytest
from ..graph import DependencyGraph
from ..parser import WorkflowParser

class TestDependencyGraph:
    def test_topological_sort_simple(self):
        """Test topological sort on simple sequential workflow"""
        pass

    def test_detect_cycle(self):
        """Test cycle detection"""
        pass

    def test_parallel_nodes(self):
        """Test that parallel nodes can be in any order"""
        pass
```

---

## Implementation Guidelines

### Python Libraries to Use

```python
# Install if needed
pip install pyyaml jsonschema pytest
```

### Code Structure

```
ai-stack/workflows/
├── __init__.py
├── models.py           # Data models
├── parser.py           # YAML parser
├── validator.py        # Schema and business logic validator
├── graph.py            # Dependency graph analyzer
├── schema/
│   └── workflow-v1.yaml
├── examples/           # (already created)
│   └── ...
└── tests/
    ├── __init__.py
    ├── test_parser.py
    ├── test_validator.py
    ├── test_graph.py
    └── test_integration.py
```

### Error Handling Best Practices

1. **Descriptive Error Messages:**
   ```python
   raise ValidationError(
       message="Circular dependency detected: analyze -> implement -> analyze",
       path="nodes[1].depends_on",
       line=42
   )
   ```

2. **Line Number Tracking:**
   - Use PyYAML's `LineLoader` to preserve line numbers
   - Include line numbers in all error messages

3. **Error Aggregation:**
   - Don't fail on first error
   - Collect all errors and return complete list
   - Categorize by severity (error, warning)

### Testing Strategy

1. **Unit Tests:**
   - Test each parser method independently
   - Test each validator rule independently
   - Test dependency graph operations

2. **Integration Tests:**
   - Parse all 7 example workflows
   - Validate all examples pass
   - Test invalid workflows fail correctly

3. **Edge Cases:**
   - Empty workflow
   - Single node workflow
   - Maximum complexity workflow
   - Malformed YAML
   - Missing required fields

---

## Validation Criteria

Before marking this slice complete, ensure:

- [ ] All 7 example workflows parse correctly
- [ ] All 7 example workflows validate successfully
- [ ] Circular dependency detection works
- [ ] Variable reference validation works
- [ ] Agent validation works
- [ ] Error messages include line numbers
- [ ] All tests pass (pytest)
- [ ] Code follows existing project conventions
- [ ] Documentation strings complete
- [ ] Type hints present
- [ ] Git commit with conventional format

---

## Acceptance Criteria

1. ✅ Parser loads all example workflows without errors
2. ✅ Validator passes all valid example workflows
3. ✅ Validator catches circular dependencies
4. ✅ Validator catches undefined variables
5. ✅ Validator catches invalid agents
6. ✅ Error messages are clear and include context
7. ✅ Dependency graph builds correctly
8. ✅ Topological sort works correctly
9. ✅ All tests pass (100% coverage goal)
10. ✅ Code reviewed by orchestrator (codex)

---

## Orchestrator Review Checklist

When complete, the orchestrator (codex) will review for:

- Code quality and readability
- Error handling robustness
- Test coverage completeness
- Adherence to design specification
- Performance (parsing < 100ms for typical workflow)
- Documentation quality

---

## Next Steps After Completion

Upon successful completion and review:
1. Orchestrator approves implementation
2. Git commit with conventional format
3. Proceed to **Slice 2.3: Workflow Executor**

---

## Questions or Blockers

If you encounter any of these, stop and ask the orchestrator:

- Ambiguity in DSL specification
- Missing information in JSON Schema
- Uncertainty about validation rules
- Technical blockers or library issues
- Example workflows that seem invalid

---

## Resources

**Design Documents:**
- Workflow DSL Design: `docs/architecture/workflow-dsl-design.md`
- Phase 2 Plan: `.agents/plans/phase-2-workflow-engine.md`

**Code Examples:**
- Existing parser patterns: `ai-stack/aidb/layered_loading.py`
- Existing validators: `ai-stack/aidb/temporal_query.py`

**Dependencies:**
- Python 3.13+
- PyYAML
- jsonschema
- pytest

---

**Delegation Date:** 2026-04-11
**Expected Completion:** 2026-04-16 (5-6 days)
**Delegated By:** Claude Sonnet 4.5 (orchestrator)
