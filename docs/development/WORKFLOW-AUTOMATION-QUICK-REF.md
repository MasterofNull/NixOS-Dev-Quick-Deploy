# Workflow Automation Quick Reference

**Status:** Active
**Owner:** AI Harness Team
**Last Updated:** 2026-03-20

One-page reference for the Agentic Workflow Automation system.

## Quick Start

```python
from workflows import WorkflowGenerator, SuccessPredictor, WorkflowExecutor
import asyncio

# Generate workflow
generator = WorkflowGenerator()
workflow = generator.generate("Deploy authentication service")

# Predict success
predictor = SuccessPredictor()
prediction = predictor.predict(workflow)
print(f"Success probability: {prediction.success_probability:.1%}")

# Execute workflow
executor = WorkflowExecutor()
execution = asyncio.run(executor.execute(workflow))
print(f"Status: {execution.status.value}")
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/workflows/generate` | POST | Generate workflow from goal |
| `/api/workflows/optimize` | POST | Optimize based on telemetry |
| `/api/workflows/templates` | GET | List templates |
| `/api/workflows/adapt` | POST | Adapt workflow/template |
| `/api/workflows/predict` | POST | Predict success |
| `/api/workflows/execute` | POST | Execute workflow |
| `/api/workflows/executions/{id}` | GET | Get execution status |

## Goal Patterns

| Pattern | Example |
|---------|---------|
| Deployment | "Deploy <service> with <features>" |
| Feature | "Add <feature> to <target>" |
| Fix | "Fix <issue> in <location>" |
| Investigation | "Investigate <problem>" |
| Optimization | "Optimize <target> for <metric>" |

## Components

| Component | File | Purpose |
|-----------|------|---------|
| Generator | `workflow_generator.py` | Generate workflows from goals |
| Optimizer | `workflow_optimizer.py` | Optimize based on telemetry |
| Templates | `template_manager.py` | Manage workflow templates |
| Adapter | `workflow_adapter.py` | Adapt workflows to new goals |
| Predictor | `success_predictor.py` | Predict success probability |
| Executor | `workflow_executor.py` | Execute workflows (DAG) |
| Store | `workflow_store.py` | Persist workflows & telemetry |

## Common Operations

### Generate Workflow
```bash
curl -X POST http://localhost:8889/api/workflows/generate \
  -H "Content-Type: application/json" \
  -d '{"goal": "Deploy auth service", "name": "Auth Deployment"}'
```

### Optimize Workflow
```bash
curl -X POST http://localhost:8889/api/workflows/optimize \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "wf_abc123"}'
```

### Use Template
```bash
curl -X POST http://localhost:8889/api/workflows/adapt \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "template_xyz",
    "goal": "Deploy new service",
    "parameters": {"service_name": "auth-v2"}
  }'
```

### Execute Workflow
```bash
curl -X POST http://localhost:8889/api/workflows/execute \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "wf_abc123"}'
```

## Configuration

**File:** `config/workflow-automation.yaml`

Key settings:
- `executor.max_parallel_tasks`: Max concurrent tasks (default: 5)
- `executor.default_timeout_seconds`: Task timeout (default: 3600)
- `templates.storage_path`: Template storage location
- `store.db_path`: Database path
- `predictor.model_path`: ML model path

## Monitoring

### Get Statistics
```bash
curl http://localhost:8889/api/workflows/statistics
```

### View Execution History
```bash
curl "http://localhost:8889/api/workflows/history?workflow_id=wf_abc&limit=10"
```

### Check Execution Status
```bash
curl http://localhost:8889/api/workflows/executions/exec_xyz
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Generation fails | Simplify goal, check logs |
| Execution hangs | Check timeouts, cancel execution |
| Low success rate | Optimize workflow, add retries |
| Template not found | Create from successful workflows |
| High memory | Run cleanup: `store.cleanup_old_data()` |

## Testing

```bash
# Run all tests
python3 scripts/testing/test-workflow-automation.py

# Run benchmarks
bash scripts/testing/benchmark-workflow-automation.sh

# Quick test
python3 lib/workflows/workflow_generator.py
```

## Files & Directories

| Path | Purpose |
|------|---------|
| `lib/workflows/` | Core automation library |
| `dashboard/backend/api/routes/workflows.py` | API routes |
| `config/workflow-automation.yaml` | Configuration |
| `scripts/testing/test-workflow-automation.py` | Test suite |
| `docs/development/agentic-workflow-automation.md` | Full docs |
| `docs/operations/workflow-automation-guide.md` | Ops guide |

## Key Metrics

- **Generation Speed:** ~100ms per workflow
- **Success Rate Target:** >90%
- **Optimization Improvement:** 20-50%
- **Template Reuse:** >50% for common patterns
- **Prediction Accuracy:** >70%

## Support

- **Full Documentation:** `docs/development/agentic-workflow-automation.md`
- **Operations Guide:** `docs/operations/workflow-automation-guide.md`
- **Batch Summary:** `docs/development/BATCH-4.3-SUMMARY.md`
- **Configuration:** `config/workflow-automation.yaml`
