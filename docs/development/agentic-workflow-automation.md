# Agentic Workflow Automation

**Version:** 1.0.0
**Owner:** AI Harness Team
**Last Updated:** 2026-03-21
**Status:** Production

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Workflow Generation](#workflow-generation)
5. [Workflow Optimization](#workflow-optimization)
6. [Template System](#template-system)
7. [Workflow Adaptation](#workflow-adaptation)
8. [Success Prediction](#success-prediction)
9. [Workflow Execution](#workflow-execution)
10. [Storage Layer](#storage-layer)
11. [API Reference](#api-reference)
12. [Best Practices](#best-practices)

## Overview

The Agentic Workflow Automation system provides intelligent, autonomous workflow management capabilities including:

- **Automatic Generation**: Create workflows from natural language goals
- **Intelligent Optimization**: Analyze telemetry to improve workflow performance
- **Template Reuse**: Extract and reuse successful workflow patterns
- **Smart Adaptation**: Adapt existing workflows to new goals
- **Risk Assessment**: Predict workflow success and identify risks
- **DAG Execution**: Execute workflows with parallel task orchestration

### Key Features

✅ Natural language goal parsing
✅ Task decomposition and dependency analysis
✅ Agent role assignment
✅ Telemetry-based optimization
✅ Bottleneck detection
✅ Template extraction and matching
✅ Workflow adaptation with parameter binding
✅ ML-based success prediction
✅ Parallel DAG execution
✅ Comprehensive telemetry collection

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Dashboard UI / API                        │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Generator   │    │  Optimizer   │    │  Predictor   │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        │                   ▼                   │
        │           ┌──────────────┐            │
        └──────────▶│   Template   │◀───────────┘
                    │   Manager    │
                    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │   Adapter    │
                    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐         ┌──────────────┐
                    │   Executor   │────────▶│  Telemetry   │
                    └──────────────┘         └──────────────┘
                            │                        │
                            ▼                        │
                    ┌──────────────┐                 │
                    │    Store     │◀────────────────┘
                    └──────────────┘
```

### Component Interactions

1. **Generation Flow**: Goal → Parser → Decomposer → Generator → Workflow
2. **Optimization Flow**: Workflow + Telemetry → Analyzer → Optimizer → Suggestions
3. **Template Flow**: Workflow → Extractor → Template → Store
4. **Adaptation Flow**: Template/Workflow + Goal → Adapter → New Workflow
5. **Prediction Flow**: Workflow → Feature Extractor → Model → Prediction
6. **Execution Flow**: Workflow → Executor → DAG Engine → Agents → Telemetry

## Components

### 1. Workflow Generator

**File**: `lib/workflows/workflow-generator.py`

Generates executable workflows from natural language goals.

#### Key Classes

- `WorkflowGenerator`: Main orchestrator
- `GoalParser`: Parses natural language goals
- `TaskDecomposer`: Breaks goals into tasks
- `DependencyAnalyzer`: Identifies task dependencies
- `AgentAssigner`: Assigns agents to tasks
- `ResourceEstimator`: Estimates resource requirements

#### Example Usage

```python
from workflows import WorkflowGenerator

generator = WorkflowGenerator()
workflow = generator.generate("Deploy authentication service with health checks")

print(f"Generated {len(workflow.tasks)} tasks")
for task in workflow.tasks:
    print(f"  - {task.name} ({task.task_type.value})")
```

### 2. Workflow Optimizer

**File**: `lib/workflows/workflow-optimizer.py`

Analyzes telemetry to identify bottlenecks and suggest optimizations.

#### Key Classes

- `WorkflowOptimizer`: Main orchestrator
- `TelemetryAnalyzer`: Analyzes performance metrics
- `BottleneckDetector`: Identifies workflow bottlenecks
- `ParallelizationAnalyzer`: Finds parallelization opportunities
- `ResourceOptimizer`: Optimizes resource allocation

#### Example Usage

```python
from workflows import WorkflowOptimizer

optimizer = WorkflowOptimizer()
result = optimizer.optimize(workflow, telemetry_history)

print(f"Found {len(result.bottlenecks)} bottlenecks")
print(f"Projected {result.projected_metrics['improvement_percentage']:.1f}% improvement")
```

### 3. Template Manager

**File**: `lib/workflows/template-manager.py`

Manages workflow templates for reuse.

#### Key Classes

- `TemplateManager`: Main orchestrator
- `TemplateExtractor`: Extracts templates from workflows
- `TemplateStore`: Persists templates
- `TemplateRecommender`: Recommends templates for goals

#### Example Usage

```python
from workflows import TemplateManager

manager = TemplateManager()

# Create template
template = manager.create_template(workflow, telemetry)

# Find templates
templates = manager.search_templates("deployment")

# Get recommendations
recommendations = manager.recommend_templates("Deploy new service")
```

### 4. Workflow Adapter

**File**: `lib/workflows/workflow-adapter.py`

Adapts existing workflows to new goals.

#### Key Classes

- `WorkflowAdapter`: Main orchestrator
- `SimilarityDetector`: Detects goal/workflow similarity
- `ParameterBinder`: Binds parameters to templates
- `WorkflowCustomizer`: Customizes workflows
- `WorkflowValidator`: Validates adapted workflows

#### Example Usage

```python
from workflows import WorkflowAdapter

adapter = WorkflowAdapter()

# Adapt from template
result = adapter.adapt_from_template(
    template,
    "Deploy new authentication service",
    parameters={"service_name": "auth-v2"}
)

print(f"Adapted with confidence: {result.confidence:.1%}")
```

### 5. Success Predictor

**File**: `lib/workflows/success-predictor.py`

Predicts workflow success probability and identifies risks.

#### Key Classes

- `SuccessPredictor`: Main orchestrator
- `FeatureExtractor`: Extracts workflow features
- `RiskIdentifier`: Identifies risk factors
- `SuccessModel`: ML model for prediction
- `AlternativeSuggester`: Suggests alternatives

#### Example Usage

```python
from workflows import SuccessPredictor

predictor = SuccessPredictor()
prediction = predictor.predict(workflow)

print(f"Success probability: {prediction.success_probability:.1%}")
print(f"Risk factors: {len(prediction.risk_factors)}")

for risk in prediction.risk_factors:
    print(f"  - {risk.description}")
```

### 6. Workflow Executor

**File**: `lib/workflows/workflow-executor.py`

Executes workflows with DAG orchestration.

#### Key Classes

- `WorkflowExecutor`: Main orchestrator
- `AgentDispatcher`: Dispatches tasks to agents
- `RetryPolicy`: Handles task retries
- `TelemetryCollector`: Collects execution metrics
- `StateManager`: Manages execution state

#### Example Usage

```python
from workflows import WorkflowExecutor
import asyncio

executor = WorkflowExecutor()

async def run():
    execution = await executor.execute(workflow)
    print(f"Execution status: {execution.status.value}")

asyncio.run(run())
```

### 7. Workflow Store

**File**: `lib/workflows/workflow-store.py`

Persists workflows, executions, and telemetry.

#### Key Features

- SQLite-based storage
- Workflow and execution persistence
- Telemetry storage
- Query and search APIs
- Statistics and analytics

#### Example Usage

```python
from workflows import WorkflowStore

store = WorkflowStore()

# Save workflow
store.save_workflow(workflow)

# Get execution history
history = store.get_workflow_history(workflow.id, days=30)

# Get statistics
stats = store.get_statistics()
```

## Workflow Generation

### Goal Parsing

The system parses natural language goals into structured components:

```python
# Example goals
goals = [
    "Deploy authentication service with health checks",
    "Add rate limiting to API endpoints",
    "Investigate and fix high memory usage",
    "Optimize database query performance",
]
```

### Supported Goal Patterns

1. **Deployment**: `deploy X`, `rollout X`, `launch X`
2. **Feature Development**: `add X`, `implement X`, `create X`
3. **Bug Fixes**: `fix X`, `resolve X`, `repair X`
4. **Investigation**: `investigate X`, `analyze X`, `diagnose X`
5. **Optimization**: `optimize X`, `improve X`, `enhance X`

### Task Decomposition

Goals are decomposed into standard task sequences:

**Deployment Workflow**:
1. Validate code
2. Build artifacts
3. Run tests
4. Deploy
5. Health checks
6. Monitor

**Feature Workflow**:
1. Design
2. Implement
3. Unit test
4. Integration test
5. Review
6. Document

**Fix Workflow**:
1. Investigate
2. Analyze root cause
3. Implement fix
4. Test fix
5. Verify
6. Document

### Dependency Analysis

The system automatically identifies dependencies:

- `test` depends on `code`
- `deploy` depends on `build` and `test`
- `monitor` depends on `deploy`
- `validate` depends on `code` or `fix`

### Agent Assignment

Tasks are assigned to appropriate agent roles:

| Task Type | Agent Role |
|-----------|-----------|
| code | developer |
| test | tester |
| deploy | deployer |
| monitor | monitor |
| analyze | analyst |
| review | reviewer |
| document | documenter |

## Workflow Optimization

### Telemetry Analysis

The optimizer analyzes execution telemetry to calculate:

- Average task duration
- Success rates
- Failure patterns
- Retry statistics
- Resource usage

### Bottleneck Detection

Bottlenecks are identified based on:

1. **Slow Execution**: Tasks >2x average duration
2. **High Failure Rate**: Success rate <80%
3. **High Retry Rate**: Average retries >1
4. **Timeouts**: Frequent timeout occurrences

### Optimization Strategies

1. **Parallelization**: Remove unnecessary dependencies
2. **Resource Allocation**: Increase resources for slow tasks
3. **Dependency Removal**: Eliminate transitive dependencies
4. **Task Reordering**: Optimize execution order
5. **Timeout Adjustment**: Adjust timeouts based on history
6. **Retry Policy**: Optimize retry strategies

### Critical Path Analysis

The optimizer identifies the critical path through the workflow:

```python
critical_path, duration = analyzer.identify_critical_path(workflow, metrics)
print(f"Critical path: {' → '.join(critical_path)}")
print(f"Critical path duration: {duration}s")
```

## Template System

### Template Creation

Templates are extracted from successful workflows:

```python
# Extract template
template = extractor.extract(workflow, telemetry)

# Template includes:
# - Parameterized task structure
# - Goal pattern for matching
# - Quality metrics
# - Usage statistics
```

### Template Parameters

Common template parameters:

- `service_name`: Name of service/component
- `environment`: Target environment (dev/staging/prod)
- `feature_name`: Name of feature being developed
- `target`: Generic target of workflow

### Template Matching

Templates are matched to goals using:

1. **Pattern Matching**: Regex patterns (40% weight)
2. **Keyword Overlap**: Shared keywords (30% weight)
3. **Quality Score**: Template success rate (30% weight)

### Template Versioning

Templates support versioning:

```yaml
version: "1.0.0"
created_at: "2024-01-01T00:00:00Z"
updated_at: "2024-01-15T10:30:00Z"
```

## Workflow Adaptation

### Similarity Detection

Goals are compared using:

- Sequence matching (60% weight)
- Keyword overlap (40% weight)

### Parameter Binding

Parameters are extracted from goals:

```python
# Template: "Deploy {{ service_name }}"
# Goal: "Deploy authentication service"
# Binding: service_name = "authentication"
```

### Workflow Customization

Workflows can be customized with:

```python
customizations = {
    "add_tasks": [
        {"name": "security_scan", "task_type": "validate"}
    ],
    "remove_tasks": ["task_3"],
    "modify_tasks": {
        "task_1": {"estimated_duration": 60}
    }
}
```

### Validation

Adapted workflows are validated for:

- No circular dependencies
- Valid task references
- Executable task graph

## Success Prediction

### Feature Extraction

Features extracted from workflows:

- Total tasks
- Maximum dependencies per task
- Average dependencies
- Critical path length
- Parallelism ratio
- Estimated duration
- Task type diversity
- Has retry policies
- Has validation criteria
- Resource intensity

### Risk Identification

Risk factors identified:

1. **High Complexity**: >20 tasks
2. **High Dependencies**: >5 dependencies per task
3. **Long Critical Path**: >10 tasks in critical path
4. **Low Parallelism**: <30% parallelism ratio
5. **Long Duration**: >2 hours estimated
6. **No Retry Policy**: Missing retry policies
7. **No Validation**: Missing validation criteria
8. **High Resource Intensity**: Heavy resource requirements

### Prediction Model

The system uses a heuristic-based model:

```python
# Base success rate
score = 0.85

# Apply weights for features
score += parallelism_ratio * 0.3
score -= total_tasks * 0.02
score -= max_dependencies * 0.05
# ... more weights

# Convert to probability (0-1)
probability = sigmoid(score)
```

### Confidence Scoring

Confidence decreases with workflow complexity:

```python
complexity = (tasks/50 + dependencies/20 + critical_path/30)
confidence = max(0.5, 1.0 - complexity)
```

## Workflow Execution

### DAG Execution

Workflows are executed as DAGs:

1. **Topological Sort**: Calculate execution order
2. **Batch Execution**: Execute independent tasks in parallel
3. **Dependency Resolution**: Wait for dependencies before execution
4. **Progress Tracking**: Update progress after each batch

### Parallel Execution

Tasks with no dependencies run in parallel:

```python
# Example execution order
batches = [
    ["task_1", "task_2"],      # Batch 1: 2 parallel tasks
    ["task_3"],                # Batch 2: 1 task (depends on batch 1)
    ["task_4", "task_5"],      # Batch 3: 2 parallel tasks
]
```

### Agent Dispatch

Tasks are dispatched to appropriate agents:

```python
# Agent pool by role
agents = {
    "developer": ["dev-1", "dev-2"],
    "tester": ["test-1"],
    "deployer": ["deploy-1"],
}

# Round-robin selection
agent_id = agents[task.agent_role.value][0]
```

### Retry Logic

Failed tasks are retried with exponential backoff:

```python
retry_policy = RetryPolicy(
    max_retries=3,
    backoff_multiplier=2.0
)

# Delay sequence: 2s, 4s, 8s
```

### State Persistence

Execution state is persisted after each batch:

```json
{
  "execution_id": "exec_123",
  "status": "running",
  "progress": 0.6,
  "completed_tasks": ["task_1", "task_2", "task_3"],
  "running_tasks": ["task_4"]
}
```

## Storage Layer

### Database Schema

**Workflows Table**:
```sql
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    goal TEXT,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
```

**Workflow Executions Table**:
```sql
CREATE TABLE workflow_executions (
    execution_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    total_duration INTEGER,
    success INTEGER,
    data TEXT NOT NULL
);
```

**Telemetry Table**:
```sql
CREATE TABLE telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    workflow_id TEXT,
    execution_id TEXT,
    timestamp TEXT NOT NULL,
    data TEXT
);
```

### Query Performance

Indices for performance:

- `idx_executions_workflow_id` on `workflow_executions(workflow_id)`
- `idx_executions_status` on `workflow_executions(status)`
- `idx_telemetry_workflow` on `telemetry(workflow_id)`
- `idx_telemetry_execution` on `telemetry(execution_id)`

### Data Retention

Automatic cleanup of old data:

```python
# Delete data older than 90 days
store.cleanup_old_data(days=90)
```

## API Reference

### POST /api/workflows/generate

Generate workflow from goal.

**Request**:
```json
{
  "goal": "Deploy authentication service",
  "name": "Auth Service Deployment"
}
```

**Response**:
```json
{
  "workflow": { /* workflow object */ },
  "message": "Generated workflow with 6 tasks"
}
```

### POST /api/workflows/optimize

Optimize workflow based on telemetry.

**Request**:
```json
{
  "workflow_id": "wf_abc123"
}
```

**Response**:
```json
{
  "optimization_result": {
    "bottlenecks": [ /* bottleneck objects */ ],
    "suggestions": [ /* suggestion objects */ ],
    "projected_metrics": { /* metrics */ }
  },
  "message": "Found 2 bottlenecks"
}
```

### GET /api/workflows/templates

List available templates.

**Query Parameters**:
- `category`: Filter by category
- `min_quality`: Minimum quality score
- `limit`: Maximum results

**Response**:
```json
{
  "templates": [ /* template objects */ ],
  "total": 15
}
```

### POST /api/workflows/adapt

Adapt workflow or template.

**Request**:
```json
{
  "template_id": "template_xyz",
  "goal": "Deploy new service",
  "parameters": {
    "service_name": "auth-v2"
  }
}
```

**Response**:
```json
{
  "adapted_workflow": { /* workflow object */ },
  "adaptation_result": {
    "similarity_score": 0.85,
    "confidence": 0.9
  },
  "message": "Adapted workflow"
}
```

### POST /api/workflows/predict

Predict workflow success.

**Request**:
```json
{
  "workflow_id": "wf_abc123"
}
```

**Response**:
```json
{
  "prediction": {
    "success_probability": 0.87,
    "confidence": 0.92,
    "risk_factors": [ /* risk objects */ ]
  },
  "message": "Predicted 87% success"
}
```

### POST /api/workflows/execute

Execute workflow.

**Request**:
```json
{
  "workflow_id": "wf_abc123"
}
```

**Response**:
```json
{
  "execution_id": "exec_xyz789",
  "status": "running",
  "message": "Started execution"
}
```

### GET /api/workflows/executions/{execution_id}

Get execution status.

**Response**:
```json
{
  "execution": {
    "execution_id": "exec_xyz789",
    "status": "success",
    "progress": 1.0,
    "total_duration": 180
  }
}
```

## Best Practices

### 1. Goal Writing

Write clear, specific goals:

✅ **Good**: "Deploy authentication service with health checks and monitoring"
❌ **Bad**: "Do deployment stuff"

✅ **Good**: "Add rate limiting to API endpoints with Redis backend"
❌ **Bad**: "Make API better"

### 2. Template Usage

Use templates for common patterns:

```python
# Check for templates first
recommendations = manager.recommend_templates(goal)

if recommendations and recommendations[0][1] > 0.7:
    # Use template if high similarity
    template, score = recommendations[0]
    workflow = adapter.adapt_from_template(template, goal)
else:
    # Generate new workflow
    workflow = generator.generate(goal)
```

### 3. Success Prediction

Always predict before execution:

```python
# Predict success
prediction = predictor.predict(workflow)

if prediction.success_probability < 0.7:
    print(f"Warning: Low success probability")
    for risk in prediction.risk_factors[:3]:
        print(f"  - {risk.description}")
        print(f"    Mitigation: {risk.mitigation}")

# Proceed or modify based on prediction
```

### 4. Optimization Workflow

Regular optimization cycle:

```python
# 1. Execute workflow multiple times
for i in range(10):
    await executor.execute(workflow)

# 2. Collect telemetry
history = store.get_workflow_history(workflow.id)

# 3. Optimize
result = optimizer.optimize(workflow, history)

# 4. Apply suggestions
for suggestion in result.suggestions:
    print(f"Consider: {suggestion.description}")
```

### 5. Error Handling

Handle execution errors gracefully:

```python
try:
    execution = await executor.execute(workflow)

    if execution.status != ExecutionStatus.SUCCESS:
        # Check which tasks failed
        failed_tasks = [
            t for t in execution.task_executions.values()
            if t.status == ExecutionStatus.FAILURE
        ]

        print(f"Failed tasks: {len(failed_tasks)}")
        for task_exec in failed_tasks:
            print(f"  {task_exec.task_id}: {task_exec.error_message}")

except Exception as e:
    print(f"Execution error: {e}")
```

### 6. Performance Optimization

Optimize for performance:

```python
# Use parallel execution
executor = WorkflowExecutor(max_parallel_tasks=10)

# Enable caching
template_manager = TemplateManager(cache_ttl=3600)

# Batch telemetry writes
telemetry_collector.set_batch_size(100)
```

### 7. Monitoring

Monitor workflow automation:

```python
# Get statistics
stats = store.get_statistics()

print(f"Total workflows: {stats['total_workflows']}")
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Avg duration: {stats['avg_duration']}s")

# Alert on low success rate
if stats['success_rate'] < 0.8:
    send_alert("Low workflow success rate")
```

---

**See Also**:
- [Operations Guide](../operations/workflow-automation-guide.md)
- [API Reference](../../dashboard/README.md)
- [Configuration Guide](../../config/workflow-automation.yaml)
