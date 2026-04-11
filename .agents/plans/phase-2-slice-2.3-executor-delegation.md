# Phase 2 Slice 2.3: Workflow Executor - Delegation Plan

**Delegated To:** qwen (implementation agent)
**Delegated By:** claude (orchestrator)
**Depends On:** Slice 2.2 (Parser & Validator) ⏳ IN PROGRESS
**Effort:** 6-7 days
**Priority:** P0 (BLOCKS SLICES 2.4, 2.5, 2.6)
**Created:** 2026-04-11

---

## Delegation Context

**Prerequisites (from Slice 2.2):**
- ✅ Workflow parser and validator
- ✅ Data models (Workflow, WorkflowNode, etc.)
- ✅ Dependency graph analyzer
- ✅ Variable resolution

**Your task:** Implement the workflow execution engine that orchestrates multi-agent task execution based on the DSL.

---

## Objective

Implement a robust workflow executor that:
1. Executes workflows with deterministic behavior
2. Manages execution state across nodes
3. Handles loops with termination conditions
4. Evaluates conditional expressions
5. Coordinates parallel node execution
6. Implements retry logic and error handling
7. Integrates with memory system (L0-L3 loading)
8. Routes tasks to appropriate agents

---

## Required Reading

Read these files in order:

1. **DSL Specification:**
   - `docs/architecture/workflow-dsl-design.md` (focus on Execution Model section)
   - `docs/workflows/DSL-REFERENCE.md`

2. **Parser & Validator Code** (from Slice 2.2):
   - `ai-stack/workflows/models.py`
   - `ai-stack/workflows/parser.py`
   - `ai-stack/workflows/validator.py`
   - `ai-stack/workflows/graph.py`

3. **Memory System:**
   - `ai-stack/aidb/layered_loading.py` (L0-L3 loading)
   - `docs/memory-system/API-REFERENCE.md`

4. **Example Workflows:**
   - All files in `ai-stack/workflows/examples/`

---

## Deliverables

### 1. Execution State Models (`ai-stack/workflows/state.py`)

```python
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class NodeState:
    """State for a single workflow node execution"""
    node_id: str
    status: NodeStatus = NodeStatus.PENDING
    agent: Optional[str] = None
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    error_type: Optional[str] = None
    attempts: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None

@dataclass
class WorkflowState:
    """State for entire workflow execution"""
    workflow_id: str
    workflow_name: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    inputs: Dict[str, Any] = field(default_factory=dict)
    node_states: Dict[str, NodeState] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_execution_time_ms: Optional[int] = None

    def get_node_state(self, node_id: str) -> NodeState:
        """Get or create node state"""
        if node_id not in self.node_states:
            self.node_states[node_id] = NodeState(node_id=node_id)
        return self.node_states[node_id]

    def is_node_completed(self, node_id: str) -> bool:
        """Check if node has completed successfully"""
        return (node_id in self.node_states and
                self.node_states[node_id].status == NodeStatus.COMPLETED)

    def can_execute_node(self, node: 'WorkflowNode') -> bool:
        """Check if node's dependencies are satisfied"""
        if not node.depends_on:
            return True
        return all(self.is_node_completed(dep) for dep in node.depends_on)

@dataclass
class ExecutionContext:
    """Context available during node execution"""
    workflow_state: WorkflowState
    current_node: 'WorkflowNode'
    loop_iteration: int = 0
    loop_state: Dict[str, Any] = field(default_factory=dict)

    def resolve_variable(self, var_ref: str) -> Any:
        """
        Resolve variable reference like ${inputs.foo} or ${node.output}

        Args:
            var_ref: Variable reference string

        Returns:
            Resolved value
        """
        # Strip ${ and }
        var_path = var_ref.replace('${', '').replace('}', '')
        parts = var_path.split('.')

        if parts[0] == 'inputs':
            return self.workflow_state.inputs.get(parts[1])
        elif parts[0] == 'state':
            return self.loop_state.get(parts[1])
        else:
            # Node output reference
            node_id = parts[0]
            output_var = parts[1] if len(parts) > 1 else None
            node_state = self.workflow_state.node_states.get(node_id)
            if node_state and output_var:
                return node_state.outputs.get(output_var)
        return None

    def substitute_variables(self, template: str) -> str:
        """
        Substitute all ${...} variables in a string template

        Args:
            template: String with ${...} placeholders

        Returns:
            String with substitutions
        """
        import re
        def replace_var(match):
            var_ref = match.group(0)
            value = self.resolve_variable(var_ref)
            return str(value) if value is not None else var_ref

        pattern = r'\$\{[^}]+\}'
        return re.sub(pattern, replace_var, template)
```

### 2. Condition Evaluator (`ai-stack/workflows/conditions.py`)

```python
from typing import Any
from .state import ExecutionContext

class ConditionEvaluator:
    """Evaluate conditional expressions"""

    def evaluate(self, condition: str, context: ExecutionContext) -> bool:
        """
        Evaluate a condition expression

        Args:
            condition: Condition string like "${var == value}"
            context: Execution context

        Returns:
            True if condition is met, False otherwise
        """
        # Substitute variables
        expr = context.substitute_variables(condition)

        # Parse and evaluate safely
        # Use ast.literal_eval for safe evaluation
        # Support operators: ==, !=, >, <, >=, <=, &&, ||

        try:
            return self._safe_eval(expr)
        except Exception as e:
            print(f"Condition evaluation error: {e}")
            return False

    def _safe_eval(self, expr: str) -> bool:
        """
        Safely evaluate boolean expression

        Supports:
        - Comparisons: ==, !=, >, <, >=, <=
        - Boolean operators: &&, ||, !
        - Literals: true, false, numbers, strings

        Security: No arbitrary code execution
        """
        # Convert && and || to Python syntax
        expr = expr.replace('&&', ' and ').replace('||', ' or ')
        expr = expr.replace('true', 'True').replace('false', 'False')

        # Use ast for safe evaluation
        import ast
        try:
            node = ast.parse(expr, mode='eval')
            # Only allow safe operations
            return self._eval_node(node.body)
        except:
            return False

    def _eval_node(self, node):
        """Recursively evaluate AST node (safe subset only)"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Compare):
            # Handle comparisons
            left = self._eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator)
                if isinstance(op, ast.Eq):
                    result = left == right
                elif isinstance(op, ast.NotEq):
                    result = left != right
                elif isinstance(op, ast.Lt):
                    result = left < right
                elif isinstance(op, ast.LtE):
                    result = left <= right
                elif isinstance(op, ast.Gt):
                    result = left > right
                elif isinstance(op, ast.GtE):
                    result = left >= right
                else:
                    return False
                left = result
            return result
        elif isinstance(node, ast.BoolOp):
            # Handle and/or
            if isinstance(node.op, ast.And):
                return all(self._eval_node(v) for v in node.values)
            elif isinstance(node.op, ast.Or):
                return any(self._eval_node(v) for v in node.values)
        elif isinstance(node, ast.UnaryOp):
            # Handle not
            if isinstance(node.op, ast.Not):
                return not self._eval_node(node.operand)
        return False
```

### 3. Loop Handler (`ai-stack/workflows/loops.py`)

```python
from typing import Dict, Any
from .models import LoopConfig, WorkflowNode
from .state import ExecutionContext, NodeState, NodeStatus
from .conditions import ConditionEvaluator

class LoopHandler:
    """Handle loop execution with termination conditions"""

    def __init__(self, condition_evaluator: ConditionEvaluator):
        self.condition_evaluator = condition_evaluator

    def execute_loop(
        self,
        node: WorkflowNode,
        context: ExecutionContext,
        executor: 'NodeExecutor'
    ) -> NodeState:
        """
        Execute a loop until termination condition is met

        Args:
            node: Node with loop configuration
            context: Execution context
            executor: Node executor for running iterations

        Returns:
            Final node state after loop completion
        """
        loop_config = node.loop
        iteration = 0
        aggregated_outputs = {}

        while iteration < loop_config.max_iterations:
            iteration += 1
            context.loop_iteration = iteration

            # Check termination condition
            if self._should_terminate(loop_config, context):
                break

            # Execute iteration
            if loop_config.fresh_context:
                # Reset context for this iteration
                iteration_context = self._create_fresh_context(context)
            else:
                iteration_context = context

            # Use loop prompt or node prompt
            prompt = loop_config.prompt or node.prompt
            iteration_node = self._create_iteration_node(node, prompt, iteration)

            # Execute iteration
            iteration_result = executor.execute_node(iteration_node, iteration_context)

            # Update loop state
            self._update_loop_state(context, iteration_result, iteration)

            # Aggregate outputs
            self._aggregate_outputs(aggregated_outputs, iteration_result.outputs, iteration)

            # Check for errors
            if iteration_result.status == NodeStatus.FAILED:
                return iteration_result

        # Create final node state
        final_state = NodeState(
            node_id=node.id,
            status=NodeStatus.COMPLETED,
            outputs=aggregated_outputs
        )
        return final_state

    def _should_terminate(self, loop_config: LoopConfig, context: ExecutionContext) -> bool:
        """Check if loop should terminate"""
        if loop_config.until == "ALL_TASKS_COMPLETE":
            # Built-in condition
            return context.loop_state.get('remaining_tasks', 0) == 0
        else:
            # Evaluate custom condition
            return self.condition_evaluator.evaluate(loop_config.until, context)

    def _create_fresh_context(self, context: ExecutionContext) -> ExecutionContext:
        """Create fresh context for iteration"""
        # Implementation: create new context with minimal state
        pass

    def _create_iteration_node(self, node: WorkflowNode, prompt: str, iteration: int) -> WorkflowNode:
        """Create node for loop iteration"""
        # Implementation: clone node with updated prompt
        pass

    def _update_loop_state(self, context: ExecutionContext, result: NodeState, iteration: int):
        """Update loop state variables"""
        context.loop_state['iteration'] = iteration
        # Update other state based on result
        pass

    def _aggregate_outputs(self, aggregated: Dict, iteration_outputs: Dict, iteration: int):
        """Aggregate outputs from iteration"""
        # Collect outputs from all iterations
        for key, value in iteration_outputs.items():
            if key not in aggregated:
                aggregated[key] = []
            aggregated[key].append(value)
```

### 4. Node Executor (`ai-stack/workflows/executor.py`)

```python
import time
from typing import Dict, Any, Optional
from datetime import datetime

from .models import Workflow, WorkflowNode, RetryConfig
from .state import WorkflowState, NodeState, NodeStatus, ExecutionStatus, ExecutionContext
from .conditions import ConditionEvaluator
from .loops import LoopHandler
from .graph import DependencyGraph

class AgentRouter:
    """Route tasks to agents"""

    def execute_task(self, agent: str, prompt: str, memory_config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute task on specified agent

        Args:
            agent: Agent ID (qwen, codex, claude, gemini)
            prompt: Task prompt
            memory_config: Memory configuration (layers, topics, max_tokens)

        Returns:
            Agent response with outputs
        """
        # TODO: Integrate with actual agent routing system
        # For now, simulate execution
        print(f"[{agent}] Executing: {prompt[:100]}...")

        # Load memory if configured
        if memory_config:
            context_memory = self._load_memory(memory_config)
            full_prompt = f"{context_memory}\n\n{prompt}"
        else:
            full_prompt = prompt

        # Simulate agent execution
        # In real implementation, call harness-rpc or agent API
        result = {
            "status": "completed",
            "outputs": {
                "result": f"Completed task by {agent}"
            }
        }

        return result

    def _load_memory(self, memory_config: Dict) -> str:
        """Load memory context using L0-L3 system"""
        from aidb.layered_loading import LayeredMemory

        memory = LayeredMemory()

        layers = memory_config.get('layers', ['L0', 'L1'])
        topics = memory_config.get('topics', [])
        max_tokens = memory_config.get('max_tokens', 500)

        # Load appropriate layers
        context_parts = []

        if 'L0' in layers:
            context_parts.append(memory.load_l0())
        if 'L1' in layers:
            context_parts.append(memory.load_l1())
        if 'L2' in layers and topics:
            context_parts.append(memory.load_l2(topics=topics))
        if 'L3' in layers:
            # L3 requires query - use first topic or generic
            query = topics[0] if topics else "general"
            context_parts.append(memory.load_l3(query=query))

        return "\n\n".join(context_parts)

class NodeExecutor:
    """Execute individual workflow nodes"""

    def __init__(self, agent_router: AgentRouter):
        self.agent_router = agent_router
        self.condition_evaluator = ConditionEvaluator()

    def execute_node(
        self,
        node: WorkflowNode,
        context: ExecutionContext
    ) -> NodeState:
        """
        Execute a single workflow node

        Args:
            node: Node to execute
            context: Execution context

        Returns:
            Node execution state
        """
        node_state = context.workflow_state.get_node_state(node.id)
        node_state.status = NodeStatus.RUNNING
        node_state.agent = node.agent
        node_state.started_at = datetime.utcnow()

        try:
            # Check condition
            if node.condition and not self.condition_evaluator.evaluate(node.condition, context):
                node_state.status = NodeStatus.SKIPPED
                return node_state

            # Substitute variables in prompt
            prompt = context.substitute_variables(node.prompt)

            # Execute with retry logic
            if node.retry:
                result = self._execute_with_retry(node, prompt, context)
            else:
                result = self.agent_router.execute_task(
                    agent=node.agent,
                    prompt=prompt,
                    memory_config=node.memory.__dict__ if node.memory else None
                )

            # Update state
            node_state.outputs = result.get('outputs', {})
            node_state.status = NodeStatus.COMPLETED

        except Exception as e:
            node_state.status = NodeStatus.FAILED
            node_state.error = str(e)
            node_state.error_type = type(e).__name__

            # Handle error if configured
            if node.on_error:
                self._handle_error(node, node_state, context)

        finally:
            node_state.completed_at = datetime.utcnow()
            if node_state.started_at:
                delta = node_state.completed_at - node_state.started_at
                node_state.execution_time_ms = int(delta.total_seconds() * 1000)

        return node_state

    def _execute_with_retry(
        self,
        node: WorkflowNode,
        prompt: str,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Execute with retry logic"""
        retry_config = node.retry
        attempt = 0
        last_error = None

        while attempt < retry_config.max_attempts:
            attempt += 1

            try:
                result = self.agent_router.execute_task(
                    agent=node.agent,
                    prompt=prompt,
                    memory_config=node.memory.__dict__ if node.memory else None
                )
                return result

            except Exception as e:
                last_error = e
                error_type = type(e).__name__

                # Check if this error type should trigger retry
                if retry_config.on_failure and error_type not in retry_config.on_failure:
                    raise

                # Calculate backoff delay
                if attempt < retry_config.max_attempts:
                    delay = self._calculate_backoff(
                        attempt,
                        retry_config.backoff,
                        retry_config.backoff_base
                    )
                    print(f"Retry {attempt}/{retry_config.max_attempts} after {delay}s...")
                    time.sleep(delay)

        # All retries exhausted
        raise last_error

    def _calculate_backoff(self, attempt: int, strategy: str, base: float) -> float:
        """Calculate backoff delay"""
        if strategy == "constant":
            return base
        elif strategy == "linear":
            return base * attempt
        elif strategy == "exponential":
            return base * (2 ** (attempt - 1))
        return base

    def _handle_error(self, node: WorkflowNode, node_state: NodeState, context: ExecutionContext):
        """Handle node error"""
        # TODO: Execute error handler node
        print(f"Error handler: {node.on_error.handler}")

class WorkflowExecutor:
    """Main workflow execution engine"""

    def __init__(self, agent_router: Optional[AgentRouter] = None):
        self.agent_router = agent_router or AgentRouter()
        self.node_executor = NodeExecutor(self.agent_router)
        self.loop_handler = LoopHandler(ConditionEvaluator())

    def execute(
        self,
        workflow: Workflow,
        inputs: Dict[str, Any]
    ) -> WorkflowState:
        """
        Execute a workflow with given inputs

        Args:
            workflow: Workflow to execute
            inputs: Input parameters

        Returns:
            Final workflow state
        """
        # Initialize state
        state = WorkflowState(
            workflow_id=f"{workflow.name}-{int(time.time())}",
            workflow_name=workflow.name,
            inputs=inputs,
            status=ExecutionStatus.RUNNING
        )

        try:
            # Build dependency graph
            dep_graph = DependencyGraph(workflow)

            # Check for cycles
            if dep_graph.has_cycle():
                raise ValueError(f"Circular dependency detected: {dep_graph.find_cycle()}")

            # Get execution order
            execution_order = dep_graph.topological_sort()

            # Execute nodes in order
            for node_id in execution_order:
                node = next(n for n in workflow.nodes if n.id == node_id)

                # Wait for dependencies
                if not state.can_execute_node(node):
                    continue

                # Create execution context
                context = ExecutionContext(
                    workflow_state=state,
                    current_node=node
                )

                # Execute node (or loop)
                if node.loop:
                    node_state = self.loop_handler.execute_loop(node, context, self.node_executor)
                else:
                    node_state = self.node_executor.execute_node(node, context)

                # Update workflow state
                state.node_states[node_id] = node_state

                # Handle goto (loop back)
                if node.goto and node_state.status == NodeStatus.COMPLETED:
                    # Re-execute target node
                    # TODO: Implement goto logic
                    pass

                # Check for failures
                if node_state.status == NodeStatus.FAILED and not node.on_error:
                    state.status = ExecutionStatus.FAILED
                    break

            # Aggregate outputs
            if state.status == ExecutionStatus.RUNNING:
                state.outputs = self._aggregate_outputs(workflow, state)
                state.status = ExecutionStatus.COMPLETED

        except Exception as e:
            state.status = ExecutionStatus.FAILED
            print(f"Workflow execution failed: {e}")

        finally:
            state.completed_at = datetime.utcnow()
            delta = state.completed_at - state.created_at
            state.total_execution_time_ms = int(delta.total_seconds() * 1000)

        return state

    def _aggregate_outputs(self, workflow: Workflow, state: WorkflowState) -> Dict[str, Any]:
        """Aggregate workflow outputs from node results"""
        outputs = {}

        if workflow.outputs:
            context = ExecutionContext(workflow_state=state, current_node=None)
            for output_name, var_ref in workflow.outputs.items():
                outputs[output_name] = context.resolve_variable(var_ref)

        return outputs
```

### 5. Tests (`ai-stack/workflows/tests/test_executor.py`)

```python
import pytest
from ..parser import WorkflowParser
from ..executor import WorkflowExecutor, AgentRouter
from ..state import ExecutionStatus, NodeStatus

class TestWorkflowExecutor:
    @pytest.fixture
    def parser(self):
        return WorkflowParser()

    @pytest.fixture
    def executor(self):
        return WorkflowExecutor()

    def test_execute_simple_sequential(self, parser, executor):
        """Test simple sequential workflow execution"""
        workflow = parser.parse_file("ai-stack/workflows/examples/simple-sequential.yaml")

        result = executor.execute(workflow, {
            "task_description": "Test task"
        })

        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.node_states) == 3
        assert result.node_states['analyze'].status == NodeStatus.COMPLETED
        assert result.node_states['execute'].status == NodeStatus.COMPLETED
        assert result.node_states['validate'].status == NodeStatus.COMPLETED

    def test_execute_parallel_tasks(self, parser, executor):
        """Test parallel task execution"""
        workflow = parser.parse_file("ai-stack/workflows/examples/parallel-tasks.yaml")

        result = executor.execute(workflow, {
            "codebase_path": "/test/path"
        })

        assert result.status == ExecutionStatus.COMPLETED
        # Verify all parallel nodes executed
        assert result.node_states['security-scan'].status == NodeStatus.COMPLETED
        assert result.node_states['performance-scan'].status == NodeStatus.COMPLETED
        assert result.node_states['code-quality-scan'].status == NodeStatus.COMPLETED
        assert result.node_states['aggregate'].status == NodeStatus.COMPLETED

    def test_execute_conditional(self, parser, executor):
        """Test conditional node execution"""
        workflow = parser.parse_file("ai-stack/workflows/examples/conditional-flow.yaml")

        # Test with run_tests = true
        result = executor.execute(workflow, {
            "environment": "dev",
            "run_tests": True,
            "require_approval": False
        })

        assert result.node_states['test'].status == NodeStatus.COMPLETED

        # Test with run_tests = false
        result = executor.execute(workflow, {
            "environment": "dev",
            "run_tests": False,
            "require_approval": False
        })

        assert result.node_states['test'].status == NodeStatus.SKIPPED

    def test_execute_loop(self, parser, executor):
        """Test loop execution"""
        workflow = parser.parse_file("ai-stack/workflows/examples/loop-until-done.yaml")

        result = executor.execute(workflow, {
            "file_path": "/test/file.py",
            "quality_threshold": 8.0
        })

        assert result.status == ExecutionStatus.COMPLETED
        loop_node = result.node_states['refactor']
        assert loop_node.status == NodeStatus.COMPLETED

    def test_error_handling(self, parser, executor):
        """Test error handling and retry"""
        workflow = parser.parse_file("ai-stack/workflows/examples/error-handling.yaml")

        result = executor.execute(workflow, {
            "service_name": "test-service",
            "environment": "staging"
        })

        # Should complete or handle errors gracefully
        assert result.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]

    def test_variable_substitution(self, executor):
        """Test variable substitution in prompts"""
        # Create simple workflow with variables
        # Test that ${inputs.foo} and ${node.output} are substituted
        pass

    def test_memory_integration(self, executor):
        """Test memory system integration"""
        # Verify L0-L3 loading works
        pass
```

---

## Implementation Guidelines

### Execution Flow

1. **Parse & Validate** (already done by Slice 2.2)
2. **Initialize State** - Create WorkflowState with inputs
3. **Build Dependency Graph** - Get topological order
4. **Execute Nodes** - In dependency order:
   - Check dependencies satisfied
   - Evaluate condition (skip if false)
   - Handle loops if configured
   - Execute agent task with retry if configured
   - Store outputs
   - Handle errors if they occur
5. **Aggregate Outputs** - Resolve output variables
6. **Return Final State**

### Determinism Requirements

- Same workflow + inputs → same execution path
- No hidden state or randomness
- Clear, traceable execution order
- Reproducible across runs

### Performance Targets

- Workflow overhead < 5% of total execution time
- Fast variable substitution (< 1ms per substitution)
- Efficient state management (no unnecessary copying)

### Error Handling

- Clear error messages with context
- Proper cleanup on failure
- Error propagation with stack traces
- Graceful degradation where possible

---

## Validation Criteria

Before marking complete:

- [ ] All 7 example workflows execute successfully
- [ ] Sequential execution works correctly
- [ ] Parallel execution works (may serialize for now)
- [ ] Conditional nodes skip/execute correctly
- [ ] Loops terminate correctly with max_iterations safety
- [ ] Variable substitution works in all contexts
- [ ] Retry logic works with backoff strategies
- [ ] Error handling executes error handler nodes
- [ ] Memory integration loads L0-L3 correctly
- [ ] All tests pass (pytest)
- [ ] Code follows project conventions
- [ ] Type hints and docstrings complete

---

## Acceptance Criteria

1. ✅ Execute all 7 example workflows without errors
2. ✅ Deterministic execution (same inputs → same path)
3. ✅ Proper dependency resolution
4. ✅ Conditional branching works
5. ✅ Loop execution with termination
6. ✅ Retry logic with exponential backoff
7. ✅ Error handlers execute correctly
8. ✅ Memory system integration (L0-L3)
9. ✅ Variable substitution in prompts/conditions
10. ✅ All tests pass with good coverage
11. ✅ Code reviewed by orchestrator

---

## Integration Points

### Agent Router

Initially stub out agent execution:
```python
def execute_task(agent, prompt, memory_config):
    print(f"[{agent}] {prompt}")
    return {"outputs": {"result": "simulated"}}
```

Later integrate with:
- `harness-rpc.js` for actual agent calls
- Agent routing infrastructure
- Real memory loading

### Memory System

Use existing `LayeredMemory` from `ai-stack/aidb/layered_loading.py`:
```python
from aidb.layered_loading import LayeredMemory

memory = LayeredMemory()
context = memory.progressive_load(query="...", max_tokens=500)
```

---

## Testing Strategy

1. **Unit Tests:**
   - Test each component independently
   - Mock agent execution
   - Test state management

2. **Integration Tests:**
   - Execute all example workflows
   - Verify end-to-end behavior
   - Test error scenarios

3. **Edge Cases:**
   - Empty workflows
   - Single node workflows
   - Maximum complexity
   - Circular dependencies (should be caught by validator)
   - Infinite loops (should hit max_iterations)

---

## Next Steps After Completion

Upon successful completion:
1. Orchestrator review and approval
2. Git commit with conventional format
3. Integration with coordinator (Slice 2.4)
4. Template creation (Slice 2.5)
5. CLI development (Slice 2.6)

---

## Questions or Blockers

If you encounter these, ask the orchestrator:

- Agent routing integration unclear
- Memory loading integration issues
- Parallel execution strategy questions
- Error handling edge cases

---

## Resources

**Design:**
- `docs/architecture/workflow-dsl-design.md`
- `docs/workflows/DSL-REFERENCE.md`

**Dependencies:**
- Slice 2.2 code (models, parser, validator, graph)
- Memory system (`ai-stack/aidb/layered_loading.py`)

---

**Expected Completion:** After Slice 2.2 completes + 6-7 days
**Delegated By:** Claude Sonnet 4.5 (orchestrator)
