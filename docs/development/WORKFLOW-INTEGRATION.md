# YAML Workflow System Integration

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-04-14

This document describes how the YAML workflow system integrates with the hybrid coordinator and other components of the AI stack.

## Architecture Overview

The YAML workflow system consists of several layers that work together:

```
┌─────────────────────────────────────────────────────────────┐
│                    HTTP API Layer                           │
│  /yaml-workflow/execute, /status, /executions, etc.        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Workflow Coordinator                           │
│  - Orchestrates workflow execution                          │
│  - Manages execution state                                  │
│  - Integrates with memory and agent routing                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           Core Workflow Engine                              │
│  Parser → Validator → Graph → Executor                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         Infrastructure Layer                                │
│  - Memory System (L0-L3)                                    │
│  - Agent Routing (local, qwen, codex, claude)               │
│  - Persistence (State Store)                                │
└─────────────────────────────────────────────────────────────┘
```

## Component Integration

### 1. HTTP API Integration

The workflow system exposes HTTP endpoints through the hybrid coordinator:

- **POST** `/yaml-workflow/execute` - Execute a workflow
- **GET** `/yaml-workflow/{execution_id}/status` - Get execution status
- **GET** `/yaml-workflow/executions` - List executions with filters
- **POST** `/yaml-workflow/{execution_id}/cancel` - Cancel execution
- **GET** `/yaml-workflow/stats` - Get execution statistics

These endpoints are registered in `ai-stack/mcp-servers/hybrid-coordinator/yaml_workflow_handlers.py`.

### 2. Workflow Coordinator

The `WorkflowCoordinator` class (`ai-stack/workflows/coordinator.py`) bridges the workflow engine with the harness infrastructure:

**Responsibilities:**
- Parse and validate YAML workflow definitions
- Coordinate multi-agent task execution
- Manage execution state and persistence
- Integrate with memory system (L0-L3 loading)
- Provide execution monitoring APIs

**Key Methods:**
```python
async def execute_workflow(
    workflow_file: str,
    inputs: Dict[str, Any],
    async_mode: bool = False,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]

async def get_execution_status(execution_id: str) -> Dict[str, Any]
async def list_executions(...) -> List[Dict[str, Any]]
async def cancel_execution(execution_id: str) -> Dict[str, Any]
```

### 3. Memory System Integration

Workflow nodes can specify memory configuration to load context from the hierarchical memory system:

```yaml
nodes:
  - id: analyze
    agent: qwen
    prompt: "Analyze the architecture"
    memory:
      layers: [L0, L1, L2, L3]  # Which memory layers to load
      topics: [architecture, patterns]  # Topic filters
      max_tokens: 1000  # Token budget for memory context
      isolation: agent  # Memory isolation level
      diary_only: false  # Load full memory or diary only
```

**Memory Layers:**
- **L0**: Session-level memory (ephemeral, current workflow)
- **L1**: Agent-level memory (ephemeral, current session)
- **L2**: Project-level memory (persistent, current repository)
- **L3**: Global memory (persistent, cross-project knowledge)

**Memory Loading Process:**
1. Workflow executor extracts memory config from node
2. Memory manager queries specified layers with topic filters
3. Retrieved context is prepended to node prompt
4. Token budget ensures context fits within limits

See `test-memory-integration.yaml` for examples of memory configuration.

### 4. Agent Routing Integration

Workflows can route tasks to different AI agents based on capability requirements:

```yaml
agents:
  implementer: qwen
  reviewer: codex

nodes:
  - id: task1
    agent: ${agents.implementer}  # Route via variable
    prompt: "Implement feature"

  - id: task2
    agent: codex  # Direct routing
    prompt: "Review code"

  - id: task3
    agent: local  # Always available
    prompt: "Validate"
```

**Available Agents:**
- **local**: Default agent (always available)
- **qwen**: Implementation and coding tasks
- **codex**: Code review and architecture
- **claude**: Complex reasoning and decision-making

**Routing Behavior:**
- Agent routing is handled by the coordinator
- Fallback to `local` if requested agent is unavailable
- Parallel execution supported for independent tasks
- Agent variables enable dynamic routing

See `test-agent-routing.yaml` for examples of agent routing.

### 5. State Persistence

Workflow execution state is persisted using `WorkflowStateStore`:

**Stored Data:**
- Execution ID and status
- Workflow definition and inputs
- Node execution results
- Start/completion timestamps
- Error information

**Storage Location:**
- Default: `.workflow-state/` directory
- Configurable via `WorkflowStateStore(storage_dir=...)`

**State Lifecycle:**
```
pending → running → completed/failed/cancelled
```

## API Endpoints and Usage

### Execute Workflow

Execute a YAML workflow file with inputs:

```bash
curl -X POST http://127.0.0.1:8003/yaml-workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": "ai-stack/workflows/examples/simple-sequential.yaml",
    "inputs": {
      "task_description": "Implement user authentication"
    },
    "async_mode": false
  }'
```

**Response:**
```json
{
  "status": "completed",
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow": "simple-sequential",
  "outputs": {
    "final_result": "...",
    "validation": "..."
  }
}
```

### Get Execution Status

Check the status of a running or completed workflow:

```bash
curl http://127.0.0.1:8003/yaml-workflow/{execution_id}/status
```

**Response:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow": "simple-sequential",
  "status": "completed",
  "started_at": "2026-04-14T10:30:00Z",
  "completed_at": "2026-04-14T10:31:45Z",
  "outputs": {...},
  "error": null
}
```

### List Executions

List workflow executions with optional filters:

```bash
# List all executions
curl http://127.0.0.1:8003/yaml-workflow/executions

# Filter by workflow name
curl http://127.0.0.1:8003/yaml-workflow/executions?workflow_name=simple-sequential

# Filter by status and limit results
curl http://127.0.0.1:8003/yaml-workflow/executions?status=completed&limit=10
```

**Response:**
```json
{
  "executions": [
    {
      "execution_id": "...",
      "workflow": "simple-sequential",
      "status": "completed",
      "started_at": "...",
      "completed_at": "..."
    }
  ],
  "count": 1
}
```

### Cancel Execution

Cancel a running workflow execution:

```bash
curl -X POST http://127.0.0.1:8003/yaml-workflow/{execution_id}/cancel
```

**Response:**
```json
{
  "status": "cancelled",
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Execution cancelled successfully"
}
```

### Get Statistics

Get workflow execution statistics:

```bash
# Global statistics
curl http://127.0.0.1:8003/yaml-workflow/stats

# Statistics for specific workflow
curl http://127.0.0.1:8003/yaml-workflow/stats?workflow_name=simple-sequential
```

**Response:**
```json
{
  "workflow": "simple-sequential",
  "total_executions": 42,
  "completed": 38,
  "failed": 3,
  "cancelled": 1,
  "avg_duration_seconds": 15.3
}
```

## Testing

### Unit Tests

Test individual components in isolation:

```bash
# Test parser
pytest ai-stack/workflows/tests/test_parser.py -v

# Test validator
pytest ai-stack/workflows/tests/test_validator.py -v

# Test coordinator
pytest ai-stack/workflows/tests/test_coordinator.py -v
```

### Integration Tests

Test workflow parsing and validation with example files:

```bash
pytest ai-stack/workflows/tests/test_integration.py -v
```

### End-to-End Tests

Test complete workflow execution via HTTP API:

```bash
# Start coordinator first
python ai-stack/mcp-servers/hybrid-coordinator/server.py --http --port 8003

# Run E2E tests
pytest ai-stack/workflows/tests/test_e2e_integration.py -v
```

## Example Workflows

The system includes several example workflows in `ai-stack/workflows/examples/`:

### Basic Workflows

- **simple-sequential.yaml**: Basic sequential workflow with 3 nodes
- **parallel-tasks.yaml**: Parallel task execution
- **conditional-flow.yaml**: Conditional branching

### Advanced Workflows

- **loop-until-done.yaml**: Iterative task execution
- **error-handling.yaml**: Retry logic and error handlers
- **feature-implementation.yaml**: Multi-agent feature development
- **sub-workflow.yaml**: Nested workflow composition

### Test Workflows

- **test-memory-integration.yaml**: Memory system integration testing
- **test-agent-routing.yaml**: Agent routing validation

## Troubleshooting

### Common Issues

#### 1. Workflow Not Found

**Error:** `parse_failed: File not found`

**Solution:** Ensure the workflow file path is correct and accessible from the coordinator's working directory. Use absolute paths or paths relative to the repository root.

#### 2. Validation Failed

**Error:** `validation_failed: errors: [....]`

**Solution:** Check the error messages for specific validation issues:
- Invalid workflow name format (use kebab-case)
- Invalid version format (use semver: `1.0`, `1.0.0`)
- Undefined dependencies in `depends_on`
- Invalid agent names
- Circular dependencies

#### 3. Execution Stuck

**Status:** Workflow shows `running` but never completes

**Solution:**
- Check coordinator logs for errors
- Verify agent endpoints are accessible
- Check for deadlocks in dependency graph
- Use `/cancel` endpoint to stop stuck execution

#### 4. Memory Integration Not Working

**Issue:** Memory context not loading in prompts

**Solution:**
- Verify memory layers exist and have content
- Check topic filters match memory entries
- Ensure `max_tokens` budget is sufficient
- Review memory manager logs for errors

#### 5. Agent Routing Failures

**Issue:** Tasks fail with agent routing errors

**Solution:**
- Verify agent is registered and available
- Check agent endpoint health
- Review routing configuration
- Use `local` agent as fallback for testing

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
export LOG_LEVEL=DEBUG
python ai-stack/mcp-servers/hybrid-coordinator/server.py --http --port 8003
```

### Checking Coordinator Status

Verify the coordinator is running and workflow system is initialized:

```bash
# Check if coordinator is accessible
curl http://127.0.0.1:8003/health

# Check workflow system status
curl http://127.0.0.1:8003/yaml-workflow/stats
```

## Performance Considerations

### Execution Performance

- **Async Mode**: Use `async_mode: true` for long-running workflows
- **Parallel Execution**: Mark independent nodes with `parallel: true`
- **Memory Budget**: Limit `max_tokens` to avoid excessive context loading
- **State Persistence**: State is written to disk on each status change

### Scalability

- **Concurrent Executions**: Default max 10 concurrent workflows
- **State Storage**: JSON files in `.workflow-state/` directory
- **Memory Usage**: Each execution loads workflow definition into memory
- **API Rate Limits**: No built-in rate limiting (rely on coordinator limits)

## Security

### Input Validation

- All workflow inputs are validated against defined schemas
- Variable interpolation uses safe string substitution
- No arbitrary code execution in workflow definitions

### File Access

- Workflow files must be readable by coordinator process
- State files written to configured `storage_dir`
- No automatic file cleanup (implement separately if needed)

### Authentication

- HTTP endpoints inherit coordinator authentication
- No workflow-specific authentication layer
- Agent API calls use coordinator credentials

## Future Enhancements

Planned improvements for the workflow system:

1. **Real Execution Engine**: Currently returns placeholder results
2. **Streaming Results**: Stream node outputs as they complete
3. **Workflow Templates**: Reusable workflow components
4. **Visual Editor**: Web-based workflow designer
5. **Metrics Dashboard**: Real-time execution monitoring
6. **Webhook Notifications**: Event-driven workflow triggers
7. **Cost Tracking**: Per-workflow token and cost tracking
8. **Workflow Versioning**: Version control for workflow definitions

## References

- **Workflow Schema**: `ai-stack/workflows/schema/workflow-v1.yaml`
- **API Handlers**: `ai-stack/mcp-servers/hybrid-coordinator/yaml_workflow_handlers.py`
- **Coordinator**: `ai-stack/workflows/coordinator.py`
- **Examples**: `ai-stack/workflows/examples/`
- **Tests**: `ai-stack/workflows/tests/`
