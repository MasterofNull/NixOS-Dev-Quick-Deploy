# Workflow Automation Operations Guide

**Status:** Active
**Owner:** AI Harness Team

**Version:** 1.0.0
**Audience:** Operators, SREs, DevOps Engineers
**Last Updated:** 2026-03-21

## Table of Contents

1. [Quick Start](#quick-start)
2. [Creating Effective Goals](#creating-effective-goals)
3. [Using Templates](#using-templates)
4. [Optimization Workflows](#optimization-workflows)
5. [Monitoring and Alerts](#monitoring-and-alerts)
6. [Troubleshooting](#troubleshooting)
7. [Performance Tuning](#performance-tuning)
8. [Security Considerations](#security-considerations)

## Quick Start

### 5-Minute Getting Started

1. **Generate your first workflow**:

```bash
curl -X POST http://localhost:8889/api/workflows/generate \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Deploy authentication service with health checks",
    "name": "Auth Service Deployment"
  }'
```

2. **Predict success probability**:

```bash
curl -X POST http://localhost:8889/api/workflows/predict \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "wf_abc123"}'
```

3. **Execute workflow**:

```bash
curl -X POST http://localhost:8889/api/workflows/execute \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "wf_abc123"}'
```

4. **Monitor execution**:

```bash
curl http://localhost:8889/api/workflows/executions/exec_xyz789
```

### Dashboard Quick Start

1. Open dashboard: `http://localhost:8888`
2. Navigate to "Workflow Automation" section
3. Enter goal in text box
4. Click "Generate Workflow"
5. Review generated workflow
6. Click "Predict Success" to assess risks
7. Click "Execute" to run workflow
8. Monitor progress in real-time

## Creating Effective Goals

### Goal Writing Principles

1. **Be Specific**: Include what, where, and how
2. **Use Action Verbs**: deploy, add, fix, optimize, investigate
3. **Include Context**: environment, service names, requirements
4. **Specify Validation**: health checks, tests, monitoring

### Goal Templates

#### Deployment Goals

```
# Good
"Deploy authentication service to staging with health checks and monitoring"

# Better
"Deploy authentication-service v2.1 to staging environment with:
- Health endpoint validation
- Prometheus metrics
- Error rate monitoring
- Rollback on failure"
```

#### Feature Development Goals

```
# Good
"Add rate limiting to API endpoints"

# Better
"Implement rate limiting on /api/v1/* endpoints using Redis with:
- 100 requests per minute per IP
- Custom rate limit headers
- Admin bypass capability
- Unit and integration tests"
```

#### Bug Fix Goals

```
# Good
"Fix memory leak in production"

# Better
"Investigate and fix memory leak in auth-service production:
- Analyze heap dumps
- Identify leak source
- Implement fix
- Deploy to staging
- Verify fix reduces memory growth
- Deploy to production"
```

#### Optimization Goals

```
# Good
"Optimize database performance"

# Better
"Optimize PostgreSQL query performance for /users endpoint:
- Profile slow queries
- Add missing indices
- Optimize JOIN operations
- Test with production-like load
- Validate <100ms P95 latency"
```

### Keywords That Work

| Category | Keywords |
|----------|----------|
| Deployment | deploy, rollout, launch, release |
| Development | add, implement, create, build |
| Operations | fix, resolve, repair, patch |
| Analysis | investigate, analyze, diagnose |
| Performance | optimize, improve, enhance, speed up |
| Testing | test, validate, verify, check |
| Monitoring | monitor, track, observe, alert |

### Anti-Patterns to Avoid

❌ **Vague Goals**:
- "Make it better"
- "Fix the thing"
- "Do deployment"

❌ **Too Generic**:
- "Update code"
- "Run tests"
- "Check logs"

❌ **Missing Context**:
- "Deploy service" (which service? where? how?)
- "Add feature" (which feature? to what?)
- "Fix bug" (which bug? where?)

## Using Templates

### Finding Templates

```bash
# List all templates
curl "http://localhost:8889/api/workflows/templates"

# Filter by category
curl "http://localhost:8889/api/workflows/templates?category=deployment"

# Filter by quality
curl "http://localhost:8889/api/workflows/templates?min_quality=80"
```

### Template Recommendations

```bash
# Get recommendations for a goal
curl -X POST http://localhost:8889/api/workflows/adapt \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Deploy authentication service v2",
    "template_id": null
  }'

# System will recommend best matching template
```

### Using a Template

```bash
# Adapt template with parameters
curl -X POST http://localhost:8889/api/workflows/adapt \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "template_abc",
    "goal": "Deploy new user service",
    "parameters": {
      "service_name": "user-service",
      "environment": "production"
    }
  }'
```

### Creating Custom Templates

Templates are automatically created from successful workflows:

```python
# After 3+ successful executions, create template
from workflows import TemplateManager, WorkflowStore

manager = TemplateManager()
store = WorkflowStore()

# Get successful workflow
workflow = store.get_workflow("wf_abc123")

# Get execution history
history = store.get_workflow_history("wf_abc123")

# Create template
template = manager.create_template(workflow, history)

print(f"Created template: {template.id}")
print(f"Quality score: {template.metadata.quality_score}")
```

### Template Best Practices

1. **Use High-Quality Templates**: Filter by `min_quality >= 80`
2. **Customize Parameters**: Always provide specific values
3. **Validate After Adaptation**: Check adapted workflow before execution
4. **Update Regularly**: Templates improve with more usage data
5. **Share Templates**: Export successful templates for team reuse

## Optimization Workflows

### When to Optimize

Optimize when:
- ✓ Workflow has >5 successful executions
- ✓ Average duration >15 minutes
- ✓ Success rate <90%
- ✓ High retry rates
- ✓ Frequent timeouts

### Optimization Process

```bash
# 1. Check workflow history
curl "http://localhost:8889/api/workflows/history?workflow_id=wf_abc123&limit=10"

# 2. Run optimization
curl -X POST http://localhost:8889/api/workflows/optimize \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "wf_abc123"}'

# 3. Review bottlenecks and suggestions
# 4. Apply suggested optimizations
# 5. Re-execute and measure improvement
```

### Common Optimizations

#### 1. Parallelization

**Before**:
```
task_1 → task_2 → task_3 → task_4
(All sequential, 80 minutes total)
```

**After**:
```
task_1 → task_3
       ↘       ↗
         task_2 → task_4
(Parallel, 50 minutes total)
```

**Improvement**: 37.5% faster

#### 2. Resource Allocation

```bash
# Increase resources for slow tasks
{
  "task_id": "build",
  "resources": {
    "cpu": "high",      # Was: medium
    "memory": "high"     # Was: medium
  }
}
```

**Improvement**: 25% faster task execution

#### 3. Timeout Adjustment

```bash
# Adjust timeouts based on history
{
  "task_id": "integration_test",
  "timeout_seconds": 1800  # Was: 900 (too short, causing failures)
}
```

**Improvement**: 15% fewer timeout failures

### Measuring Optimization Impact

```python
from workflows import WorkflowStore

store = WorkflowStore()

# Get metrics before optimization
before = store.get_workflow_history("wf_abc", days=7)
before_avg = sum(e['total_duration'] for e in before) / len(before)
before_success = sum(1 for e in before if e['success']) / len(before)

# ... apply optimizations ...

# Get metrics after optimization
after = store.get_workflow_history("wf_abc", days=7)
after_avg = sum(e['total_duration'] for e in after) / len(after)
after_success = sum(1 for e in after if e['success']) / len(after)

# Calculate improvement
duration_improvement = (before_avg - after_avg) / before_avg
success_improvement = after_success - before_success

print(f"Duration improved by: {duration_improvement*100:.1f}%")
print(f"Success rate improved by: {success_improvement*100:.1f}%")
```

## Monitoring and Alerts

### Key Metrics to Monitor

1. **Workflow Success Rate**: Should be >90%
2. **Average Duration**: Track trends over time
3. **Task Failure Rate**: Should be <5%
4. **Retry Rate**: Should be <10%
5. **Template Usage**: Track template reuse rate
6. **Execution Queue Depth**: Monitor backlog

### Setting Up Alerts

```python
# Example alerting logic
from workflows import WorkflowStore

store = WorkflowStore()
stats = store.get_statistics()

# Alert on low success rate
if stats['success_rate'] < 0.9:
    send_alert(
        severity="warning",
        message=f"Workflow success rate low: {stats['success_rate']:.1%}"
    )

# Alert on long average duration
if stats['avg_duration'] > 1800:  # 30 minutes
    send_alert(
        severity="info",
        message=f"Average workflow duration high: {stats['avg_duration']/60:.1f}m"
    )

# Alert on high execution volume
if stats['recent_executions_24h'] > 1000:
    send_alert(
        severity="info",
        message=f"High execution volume: {stats['recent_executions_24h']} in 24h"
    )
```

### Dashboard Monitoring

Access real-time monitoring at `http://localhost:8888/workflows`:

- Active executions
- Success/failure rates
- Average durations
- Bottleneck alerts
- Template usage stats

### Prometheus Metrics

Export metrics for Prometheus:

```bash
# Scrape workflow metrics
curl http://localhost:8889/metrics | grep workflow

# Example metrics:
# workflow_executions_total{status="success"} 1234
# workflow_executions_total{status="failure"} 56
# workflow_duration_seconds{workflow_id="wf_abc"} 180
# workflow_task_duration_seconds{task_type="deploy"} 45
```

## Troubleshooting

### Common Issues

#### Issue 1: Workflow Generation Fails

**Symptoms**: 500 error when generating workflow

**Diagnosis**:
```bash
# Check API logs
journalctl -u dashboard-api -n 100 | grep workflow

# Test goal parsing
curl -X POST http://localhost:8889/api/workflows/generate \
  -H "Content-Type: application/json" \
  -d '{"goal": "test simple workflow"}' -v
```

**Solutions**:
1. Simplify goal text
2. Check for special characters
3. Verify lib/workflows modules are importable
4. Restart API service

#### Issue 2: Execution Hangs

**Symptoms**: Workflow stuck in "running" state

**Diagnosis**:
```bash
# Check executor state
ls -la /tmp/workflow-state/

# Check for stuck tasks
curl http://localhost:8889/api/workflows/executions/exec_123
```

**Solutions**:
1. Cancel execution: `executor.cancel_execution(execution_id)`
2. Clear state: `rm /tmp/workflow-state/exec_123.json`
3. Adjust timeouts in configuration
4. Check agent availability

#### Issue 3: Low Success Rate

**Symptoms**: Success rate <70%

**Diagnosis**:
```bash
# Get failure analysis
curl "http://localhost:8889/api/workflows/history?status=failure&limit=50"

# Check common failure patterns
sqlite3 /tmp/workflow-store.db "
  SELECT task_id, error_message, COUNT(*) as failures
  FROM task_executions
  WHERE status = 'failure'
  GROUP BY task_id, error_message
  ORDER BY failures DESC
  LIMIT 10
"
```

**Solutions**:
1. Add retry policies to failing tasks
2. Increase task timeouts
3. Fix underlying task implementation
4. Add validation before task execution

#### Issue 4: Template Not Found

**Symptoms**: No template recommendations

**Diagnosis**:
```bash
# List all templates
curl http://localhost:8889/api/workflows/templates

# Check template storage
ls -la /tmp/workflow-templates/
cat /tmp/workflow-templates/templates.json
```

**Solutions**:
1. Create templates from successful workflows
2. Lower similarity threshold
3. Use broader search terms
4. Generate new workflow instead

#### Issue 5: High Memory Usage

**Symptoms**: System memory growing over time

**Diagnosis**:
```bash
# Check database size
du -h /tmp/workflow-store.db

# Check state directory
du -h /tmp/workflow-state/

# Count old executions
sqlite3 /tmp/workflow-store.db "
  SELECT COUNT(*) FROM workflow_executions
  WHERE start_time < datetime('now', '-90 days')
"
```

**Solutions**:
1. Run cleanup: `store.cleanup_old_data(days=30)`
2. Enable automatic cleanup in config
3. Archive old executions
4. Increase cleanup frequency

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Run workflow operations
# Detailed logs will show internal operations
```

## Performance Tuning

### Database Optimization

```bash
# Vacuum database
sqlite3 /tmp/workflow-store.db "VACUUM;"

# Analyze for better query plans
sqlite3 /tmp/workflow-store.db "ANALYZE;"

# Check index usage
sqlite3 /tmp/workflow-store.db ".indexes"
```

### Execution Performance

```yaml
# config/workflow-automation.yaml
executor:
  max_parallel_tasks: 10  # Increase for more parallelism
  default_timeout_seconds: 1800  # Adjust based on workload

  retry:
    max_retries: 3
    backoff_multiplier: 1.5  # Faster retries
```

### Template Performance

```yaml
# config/workflow-automation.yaml
templates:
  storage_path: "/var/lib/workflow-templates"  # Use persistent storage

performance:
  cache:
    enabled: true
    template_cache_ttl_seconds: 7200  # 2 hour cache
```

### API Performance

```yaml
# config/workflow-automation.yaml
performance:
  db_pool:
    min_connections: 5
    max_connections: 20

  limits:
    max_concurrent_executions: 20
```

## Security Considerations

### Input Validation

Always validate user input:

```python
# Goal length limits
MAX_GOAL_LENGTH = 500

# Sanitize inputs
import bleach
goal = bleach.clean(user_input, strip=True)
```

### Authentication

Configure authentication (when implemented):

```yaml
# config/workflow-automation.yaml
security:
  require_auth: true
  auth_provider: "oauth2"
```

### Authorization

Limit workflow operations by role:

```yaml
# config/workflow-automation.yaml
security:
  allowed_roles:
    - admin      # Can do everything
    - operator   # Can execute, optimize
    - developer  # Can generate, predict
```

### Rate Limiting

Prevent abuse:

```yaml
# config/workflow-automation.yaml
security:
  rate_limiting:
    enabled: true
    requests_per_minute: 60
    burst_size: 10
```

### Audit Logging

Track all operations:

```python
# All operations are logged
# Check logs:
tail -f /tmp/logs/workflow-*.log

# Search audit trail
grep "workflow_id=wf_abc123" /tmp/logs/*.log
```

---

**Need Help?**
- Check [Development Documentation](../development/agentic-workflow-automation.md)
- Review [Configuration](../../config/workflow-automation.yaml)
- Run tests: `python3 scripts/testing/test-workflow-automation.py`
- Run benchmarks: `bash scripts/testing/benchmark-workflow-automation.sh`
