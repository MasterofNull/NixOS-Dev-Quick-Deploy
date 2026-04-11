# Phase 2 Slice 2.4: Coordinator Integration - Delegation Plan

**Delegated To:** codex (integration specialist)
**Delegated By:** claude (orchestrator)
**Depends On:** Slice 2.3 (Workflow Executor) ⏳ PENDING
**Effort:** 5-6 days
**Priority:** P0
**Can Run Parallel With:** Slices 2.5 (Templates), 2.6 (CLI)
**Created:** 2026-04-11

---

## Delegation Context

**Prerequisites:**
- ✅ Slice 2.1: DSL Design complete
- ✅ Slice 2.2: Parser & Validator (in progress)
- ⏳ Slice 2.3: Workflow Executor (pending)

**Your task:** Integrate the workflow engine with the existing harness coordinator, agent routing, memory system, and dashboard.

---

## Objective

Create seamless integration between the workflow engine and existing infrastructure:

1. Bridge workflow executor to harness coordinator (harness-rpc.js)
2. Integrate with agent routing system
3. Connect to memory system (L0-L3 loading)
4. Add workflow execution tracking and persistence
5. Expose workflow APIs for dashboard monitoring
6. Enable execution history and state management

---

## Required Reading

1. **Workflow Engine Code** (from previous slices):
   - `ai-stack/workflows/executor.py`
   - `ai-stack/workflows/state.py`
   - `ai-stack/workflows/models.py`

2. **Existing Infrastructure:**
   - `scripts/ai/harness-rpc.js` - Coordinator RPC interface
   - `ai-stack/aidb/layered_loading.py` - Memory system
   - `scripts/ai/mcp-bridge-hybrid.py` - MCP bridge
   - Dashboard API code (if exists)

3. **Design Documents:**
   - `docs/architecture/workflow-dsl-design.md`
   - Phase 2 plan: `.agents/plans/phase-2-workflow-engine.md`

---

## Deliverables

### 1. Workflow Coordinator Bridge (`ai-stack/workflows/coordinator.py`)

```python
"""
Bridge between workflow engine and harness coordinator
"""

from typing import Dict, Any, Optional
import json
import subprocess
from pathlib import Path

from .parser import WorkflowParser
from .validator import WorkflowValidator
from .executor import WorkflowExecutor
from .state import WorkflowState, ExecutionStatus
from .persistence import WorkflowStateStore

class WorkflowCoordinator:
    """
    Main coordinator for workflow execution
    Integrates with harness-rpc.js
    """

    def __init__(
        self,
        parser: Optional[WorkflowParser] = None,
        validator: Optional[WorkflowValidator] = None,
        executor: Optional[WorkflowExecutor] = None,
        state_store: Optional[WorkflowStateStore] = None
    ):
        self.parser = parser or WorkflowParser()
        self.validator = validator or WorkflowValidator()
        self.executor = executor or WorkflowExecutor()
        self.state_store = state_store or WorkflowStateStore()

    def run_workflow(
        self,
        workflow_file: str,
        inputs: Dict[str, Any],
        async_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Run a workflow from file

        Args:
            workflow_file: Path to workflow YAML file
            inputs: Input parameters
            async_mode: Run in background if True

        Returns:
            Execution result or execution ID if async
        """
        # Parse workflow
        workflow = self.parser.parse_file(workflow_file)

        # Validate
        errors = self.validator.validate_all(workflow)
        if errors:
            return {
                "status": "validation_failed",
                "errors": [e.message for e in errors]
            }

        # Execute
        if async_mode:
            execution_id = self._execute_async(workflow, inputs)
            return {
                "status": "started",
                "execution_id": execution_id
            }
        else:
            state = self.executor.execute(workflow, inputs)
            self.state_store.save(state)
            return self._state_to_result(state)

    def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """Get status of running or completed execution"""
        state = self.state_store.load(execution_id)
        if not state:
            return {"status": "not_found"}
        return self._state_to_result(state)

    def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        """Cancel running execution"""
        # TODO: Implement cancellation
        pass

    def list_executions(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List workflow executions"""
        executions = self.state_store.list(
            workflow_name=workflow_name,
            status=status,
            limit=limit
        )
        return [self._state_to_summary(e) for e in executions]

    def _execute_async(self, workflow, inputs) -> str:
        """Execute workflow in background"""
        # TODO: Implement background execution
        # Options:
        # 1. Threading
        # 2. Subprocess
        # 3. Task queue (celery, rq)
        pass

    def _state_to_result(self, state: WorkflowState) -> Dict[str, Any]:
        """Convert WorkflowState to result dictionary"""
        return {
            "workflow_id": state.workflow_id,
            "workflow_name": state.workflow_name,
            "status": state.status.value,
            "inputs": state.inputs,
            "outputs": state.outputs,
            "nodes": {
                node_id: {
                    "status": node_state.status.value,
                    "outputs": node_state.outputs,
                    "error": node_state.error,
                    "execution_time_ms": node_state.execution_time_ms
                }
                for node_id, node_state in state.node_states.items()
            },
            "created_at": state.created_at.isoformat(),
            "completed_at": state.completed_at.isoformat() if state.completed_at else None,
            "total_execution_time_ms": state.total_execution_time_ms
        }

    def _state_to_summary(self, state: WorkflowState) -> Dict[str, Any]:
        """Convert WorkflowState to summary dictionary"""
        return {
            "workflow_id": state.workflow_id,
            "workflow_name": state.workflow_name,
            "status": state.status.value,
            "created_at": state.created_at.isoformat(),
            "total_execution_time_ms": state.total_execution_time_ms
        }
```

### 2. Agent Router Integration (`ai-stack/workflows/agent_router.py`)

```python
"""
Integration with existing agent routing system
"""

import subprocess
import json
from typing import Dict, Any, Optional

class HarnessAgentRouter:
    """
    Route workflow tasks to agents via harness-rpc.js
    """

    def __init__(self, harness_rpc_path: str = "scripts/ai/harness-rpc.js"):
        self.harness_rpc_path = harness_rpc_path

    def execute_task(
        self,
        agent: str,
        prompt: str,
        memory_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute task on agent via harness RPC

        Args:
            agent: Agent ID (qwen, codex, claude, gemini)
            prompt: Task prompt
            memory_context: Pre-loaded memory context

        Returns:
            Agent response
        """
        # Combine memory context with prompt if provided
        full_prompt = f"{memory_context}\n\n{prompt}" if memory_context else prompt

        # Call harness RPC
        try:
            result = self._call_harness_rpc(agent, full_prompt)
            return {
                "status": "completed",
                "outputs": self._parse_agent_response(result)
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__
            }

    def _call_harness_rpc(self, agent: str, prompt: str) -> str:
        """
        Call harness-rpc.js to execute agent task

        Args:
            agent: Agent ID
            prompt: Task prompt

        Returns:
            Agent response text
        """
        # Build RPC command
        cmd = [
            "node",
            self.harness_rpc_path,
            "run",
            "--agent", agent,
            "--prompt", prompt
        ]

        # Execute
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"Harness RPC failed: {result.stderr}")

        return result.stdout

    def _parse_agent_response(self, response: str) -> Dict[str, Any]:
        """
        Parse agent response into structured outputs

        Args:
            response: Raw agent response

        Returns:
            Parsed outputs dictionary
        """
        # Try to parse as JSON first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fall back to plain text
            return {"result": response.strip()}

class MCPAgentRouter:
    """
    Route workflow tasks to agents via MCP bridge
    """

    def __init__(self, mcp_bridge_path: str = "scripts/ai/mcp-bridge-hybrid.py"):
        self.mcp_bridge_path = mcp_bridge_path

    def execute_task(
        self,
        agent: str,
        prompt: str,
        memory_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute task via MCP bridge"""
        # Similar to HarnessAgentRouter but uses MCP protocol
        pass
```

### 3. Memory System Integration (`ai-stack/workflows/memory_integration.py`)

```python
"""
Integration with L0-L3 memory system
"""

from typing import List, Optional
from aidb.layered_loading import LayeredMemory

class WorkflowMemoryLoader:
    """
    Load memory context for workflow nodes
    """

    def __init__(self):
        self.memory = LayeredMemory()

    def load_memory(
        self,
        layers: List[str],
        topics: Optional[List[str]] = None,
        max_tokens: int = 500,
        query: Optional[str] = None
    ) -> str:
        """
        Load memory context based on configuration

        Args:
            layers: Memory layers to load (L0, L1, L2, L3)
            topics: Topic filters for L2
            max_tokens: Token budget
            query: Query for L3 semantic search

        Returns:
            Formatted memory context
        """
        context_parts = []

        # L0: Identity
        if "L0" in layers:
            l0 = self.memory.load_l0()
            context_parts.append(f"# Identity\n{l0}")

        # L1: Critical Facts
        if "L1" in layers:
            l1 = self.memory.load_l1()
            context_parts.append(f"# Critical Facts\n{l1}")

        # L2: Topic-Specific
        if "L2" in layers and topics:
            l2 = self.memory.load_l2(topics=topics)
            if l2:
                context_parts.append(f"# Topic Memory\n{l2}")

        # L3: Semantic Search
        if "L3" in layers and query:
            l3 = self.memory.load_l3(query=query)
            if l3:
                context_parts.append(f"# Search Results\n{l3}")

        # Combine and respect token budget
        full_context = "\n\n".join(context_parts)

        # Truncate if exceeds budget
        estimated_tokens = len(full_context) // 4
        if estimated_tokens > max_tokens:
            max_chars = max_tokens * 4
            full_context = full_context[:max_chars] + "\n\n[Context truncated to fit token budget]"

        return full_context
```

### 4. State Persistence (`ai-stack/workflows/persistence.py`)

```python
"""
Persist workflow execution state
"""

import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from .state import WorkflowState, ExecutionStatus, NodeStatus

class WorkflowStateStore:
    """
    Store and retrieve workflow execution states
    """

    def __init__(self, storage_dir: str = "~/.aidb/workflow-executions"):
        self.storage_dir = Path(storage_dir).expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: WorkflowState):
        """Save workflow state to disk"""
        state_file = self.storage_dir / f"{state.workflow_id}.json"

        state_dict = {
            "workflow_id": state.workflow_id,
            "workflow_name": state.workflow_name,
            "status": state.status.value,
            "inputs": state.inputs,
            "outputs": state.outputs,
            "node_states": {
                node_id: {
                    "node_id": ns.node_id,
                    "status": ns.status.value,
                    "agent": ns.agent,
                    "outputs": ns.outputs,
                    "error": ns.error,
                    "error_type": ns.error_type,
                    "attempts": ns.attempts,
                    "started_at": ns.started_at.isoformat() if ns.started_at else None,
                    "completed_at": ns.completed_at.isoformat() if ns.completed_at else None,
                    "execution_time_ms": ns.execution_time_ms
                }
                for node_id, ns in state.node_states.items()
            },
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "completed_at": state.completed_at.isoformat() if state.completed_at else None,
            "total_execution_time_ms": state.total_execution_time_ms
        }

        with open(state_file, 'w') as f:
            json.dump(state_dict, f, indent=2)

    def load(self, workflow_id: str) -> Optional[WorkflowState]:
        """Load workflow state from disk"""
        state_file = self.storage_dir / f"{workflow_id}.json"

        if not state_file.exists():
            return None

        with open(state_file, 'r') as f:
            state_dict = json.load(f)

        # Reconstruct WorkflowState from dict
        # TODO: Implement full deserialization
        return state_dict

    def list(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[WorkflowState]:
        """List workflow executions"""
        executions = []

        for state_file in sorted(self.storage_dir.glob("*.json"), reverse=True):
            with open(state_file, 'r') as f:
                state_dict = json.load(f)

            # Filter by workflow name
            if workflow_name and state_dict.get("workflow_name") != workflow_name:
                continue

            # Filter by status
            if status and state_dict.get("status") != status:
                continue

            executions.append(state_dict)

            if len(executions) >= limit:
                break

        return executions

    def delete(self, workflow_id: str):
        """Delete workflow execution state"""
        state_file = self.storage_dir / f"{workflow_id}.json"
        if state_file.exists():
            state_file.unlink()
```

### 5. Dashboard API Integration (`ai-stack/workflows/dashboard_api.py`)

```python
"""
API endpoints for workflow monitoring in dashboard
"""

from flask import Flask, jsonify, request
from typing import Optional

from .coordinator import WorkflowCoordinator

# Assuming dashboard uses Flask or similar
# Integrate with existing dashboard API

def register_workflow_routes(app: Flask, coordinator: WorkflowCoordinator):
    """
    Register workflow API routes with dashboard

    Args:
        app: Flask app instance
        coordinator: WorkflowCoordinator instance
    """

    @app.route('/api/workflows/run', methods=['POST'])
    def run_workflow():
        """Start workflow execution"""
        data = request.json
        workflow_file = data.get('workflow_file')
        inputs = data.get('inputs', {})
        async_mode = data.get('async', False)

        result = coordinator.run_workflow(workflow_file, inputs, async_mode)
        return jsonify(result)

    @app.route('/api/workflows/<execution_id>', methods=['GET'])
    def get_execution(execution_id: str):
        """Get execution status"""
        result = coordinator.get_execution_status(execution_id)
        return jsonify(result)

    @app.route('/api/workflows/<execution_id>/cancel', methods=['POST'])
    def cancel_execution(execution_id: str):
        """Cancel running execution"""
        result = coordinator.cancel_execution(execution_id)
        return jsonify(result)

    @app.route('/api/workflows/executions', methods=['GET'])
    def list_executions():
        """List workflow executions"""
        workflow_name = request.args.get('workflow_name')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 10))

        executions = coordinator.list_executions(workflow_name, status, limit)
        return jsonify({"executions": executions})

    @app.route('/api/workflows/templates', methods=['GET'])
    def list_templates():
        """List available workflow templates"""
        # TODO: Scan ai-stack/workflows/templates/
        pass
```

### 6. Integration Tests (`ai-stack/workflows/tests/test_integration.py`)

```python
import pytest
from ..coordinator import WorkflowCoordinator
from ..agent_router import HarnessAgentRouter
from ..persistence import WorkflowStateStore

class TestWorkflowIntegration:
    @pytest.fixture
    def coordinator(self):
        return WorkflowCoordinator()

    def test_end_to_end_execution(self, coordinator):
        """Test complete workflow execution via coordinator"""
        result = coordinator.run_workflow(
            workflow_file="ai-stack/workflows/examples/simple-sequential.yaml",
            inputs={"task_description": "Integration test"}
        )

        assert result["status"] in ["completed", "failed"]
        assert "workflow_id" in result

    def test_async_execution(self, coordinator):
        """Test asynchronous workflow execution"""
        result = coordinator.run_workflow(
            workflow_file="ai-stack/workflows/examples/simple-sequential.yaml",
            inputs={"task_description": "Async test"},
            async_mode=True
        )

        assert result["status"] == "started"
        assert "execution_id" in result

        # Check status
        execution_id = result["execution_id"]
        status = coordinator.get_execution_status(execution_id)
        assert status is not None

    def test_state_persistence(self):
        """Test workflow state persistence"""
        store = WorkflowStateStore()
        # Create and save state
        # Load and verify
        pass

    def test_memory_integration(self):
        """Test memory system integration"""
        # Verify L0-L3 loading in workflow execution
        pass

    def test_agent_routing(self):
        """Test agent routing via harness RPC"""
        router = HarnessAgentRouter()
        # Test routing to different agents
        pass
```

---

## Integration Points

### 1. Harness Coordinator (harness-rpc.js)

Update harness-rpc.js to expose workflow commands:

```javascript
// Add to harness-rpc.js
const workflowCommands = {
  'workflow:run': async (args) => {
    // Call Python workflow coordinator
    const result = await execPython('ai-stack/workflows/coordinator.py', ['run', args.workflow, args.inputs]);
    return result;
  },

  'workflow:status': async (args) => {
    const result = await execPython('ai-stack/workflows/coordinator.py', ['status', args.execution_id]);
    return result;
  },

  'workflow:list': async (args) => {
    const result = await execPython('ai-stack/workflows/coordinator.py', ['list', args.filters]);
    return result;
  }
};
```

### 2. Dashboard UI

Add workflow monitoring pages:
- Workflow execution list
- Execution detail view with node status
- Real-time execution progress
- Execution history

### 3. Memory System

Already integrated via `ai-stack/aidb/layered_loading.py` - no changes needed.

---

## Validation Criteria

- [ ] Workflow executor integrated with harness coordinator
- [ ] Agent routing works via harness-rpc.js
- [ ] Memory loading (L0-L3) integrated
- [ ] State persistence working
- [ ] Dashboard API endpoints functional
- [ ] Async execution supported
- [ ] All integration tests pass
- [ ] Code reviewed by orchestrator

---

## Acceptance Criteria

1. ✅ Workflows can be executed via coordinator
2. ✅ Agent tasks routed to harness RPC correctly
3. ✅ Memory context loaded for nodes
4. ✅ Execution state persisted and recoverable
5. ✅ Dashboard displays workflow executions
6. ✅ Async execution works
7. ✅ Integration tests pass
8. ✅ Code reviewed and approved

---

## Next Steps After Completion

- Integrate with Slice 2.5 (Templates)
- Connect to Slice 2.6 (CLI)
- Enable production workflow execution
- Monitor and optimize performance

---

**Expected Completion:** After Slice 2.3 completes + 5-6 days
**Delegated By:** Claude Sonnet 4.5 (orchestrator)
