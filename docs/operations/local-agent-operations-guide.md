# Local Agent Operations Guide

**Status:** Production
**Owner:** Operations Team
**Last Updated:** 2026-03-21
**Audience:** System Operators, DevOps Engineers

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration](#configuration)
3. [Tool Usage](#tool-usage)
4. [Monitoring](#monitoring)
5. [Troubleshooting](#troubleshooting)
6. [Safety & Security](#safety--security)
7. [Performance Tuning](#performance-tuning)
8. [Workflow Integration](#workflow-integration)
9. [Alert Remediation](#alert-remediation)
10. [Best Practices](#best-practices)

---

## Quick Start

### Prerequisites

```bash
# Ensure services are running
systemctl status llama-cpp-agent
systemctl status hybrid-coordinator
systemctl status aidb

# Check network connectivity
curl http://127.0.0.1:8080/health  # llama.cpp
curl http://127.0.0.1:8003/health  # hybrid coordinator
curl http://127.0.0.1:8002/health  # aidb
```

### Initialize Tool Registry

```python
#!/usr/bin/env python3
from local_agents import get_registry, initialize_builtin_tools

# Initialize registry with all built-in tools
registry = get_registry()
initialize_builtin_tools(registry)

# Verify tools loaded
stats = registry.get_statistics()
print(f"Loaded {stats['total_tools']} tools")
print(f"Enabled: {stats['enabled_tools']}")
```

### Execute First Task

```python
from local_agents import get_executor, Task, AgentType

# Create executor
executor = get_executor()

# Simple task
task = Task(
    id="test-001",
    objective="Get system information and list Python files",
    complexity=0.3,
    latency_critical=True
)

# Execute
result = await executor.execute_task(task, AgentType.AGENT)

print(f"Status: {result.status.value}")
print(f"Result: {result.result}")
print(f"Time: {result.execution_time_ms}ms")
print(f"Tool calls: {len(result.tool_calls_made)}")
```

### Start Monitoring Agent

```python
from local_agents import MonitoringAgent, get_registry

# Create monitoring agent
monitoring = MonitoringAgent(
    tool_registry=get_registry(),
    check_interval_seconds=60  # Check every minute
)

# Run health checks
checks = await monitoring.check_system_health()
for check in checks:
    print(f"{check.component}: {check.status.value}")

# Start monitoring loop (background)
asyncio.create_task(monitoring.monitoring_loop())
```

---

## Configuration

### Environment Variables

```bash
# llama.cpp endpoint
export LLAMA_ENDPOINT="http://127.0.0.1:8080"

# Hybrid coordinator endpoint
export COORDINATOR_ENDPOINT="http://127.0.0.1:8003"

# AIDB endpoint
export AIDB_ENDPOINT="http://127.0.0.1:8002"

# Offline resilience controls
export LOCAL_AGENT_OFFLINE_MODE="false"
export LOCAL_AGENT_ALLOW_DEGRADED_LOCAL="true"
export LOCAL_AGENT_REMOTE_PROBE_TIMEOUT_SECONDS="2"
export LOCAL_AGENT_REMOTE_TIMEOUT_SECONDS="60"

# Tool registry database
export TOOL_AUDIT_DB="$HOME/.local/share/nixos-ai-stack/local-agents/tool_audit.db"

# Resource limits
export CODE_EXEC_TIMEOUT=30
export CODE_EXEC_MEMORY_MB=256
export CODE_EXEC_CPU_SECONDS=30
```

### Tool Registry Configuration

```python
from local_agents import ToolRegistry, ResourceLimits
from pathlib import Path

# Custom database path
registry = ToolRegistry(
    db_path=Path("/var/lib/local-agents/audit.db")
)

# Customize resource limits
limits = ResourceLimits(
    timeout_seconds=60,           # 1 minute timeout
    cpu_time_seconds=60,
    memory_bytes=512 * 1024 * 1024,  # 512 MB
    max_processes=20,
    max_file_size_bytes=50 * 1024 * 1024,  # 50 MB
    max_output_bytes=5 * 1024 * 1024,  # 5 MB
)
```

### Agent Executor Configuration

```python
from local_agents import LocalAgentExecutor

executor = LocalAgentExecutor(
    llama_endpoint="http://127.0.0.1:8080",
    enable_fallback=True,  # Enable remote fallback
    fallback_endpoint="http://127.0.0.1:8003",
    offline_mode=False,
    allow_degraded_local_execution=True,
)
```

### Task Router Configuration

```python
from local_agents import TaskRouter

router = TaskRouter(
    local_success_threshold=0.75,  # Fallback if <75% success
    complexity_threshold=0.6,      # Route complex tasks remote
    default_to_local=True,         # Prefer local by default
    offline_mode=False,
    allow_degraded_local=True,
)
```

### Offline Operation

When internet or remote delegation is unavailable, keep the local stack running and let the executor degrade to local-only routing instead of hard failing:

```bash
export LOCAL_AGENT_OFFLINE_MODE="true"
export LOCAL_AGENT_ALLOW_DEGRADED_LOCAL="true"
```

In this mode:
- Flagship-required and quality-critical tasks run locally with a degraded-routing note instead of blocking.
- Remote fallback probes are skipped.
- Loopback AI services (`llama.cpp`, `hybrid-coordinator`, `aidb`) continue to be treated as the primary execution path.

If captive portal sign-in is blocking HTTP/DNS egress, use the command center firewall controls to enable a short-lived bypass, sign in, then let the auto-revert restore normal rules.

### Monitoring Configuration

```python
from local_agents import MonitoringAgent

monitoring = MonitoringAgent(
    executor=executor,
    tool_registry=registry,
    check_interval_seconds=60,  # Check every minute
)
```

---

## Tool Usage

### File Operations

#### Read File

```python
from local_agents import get_registry, ToolCall

registry = get_registry()

tool_call = ToolCall(
    id="read-001",
    tool_name="read_file",
    arguments={"file_path": "/etc/hosts"}
)

result = await registry.execute_tool_call(tool_call)
print(result.result)  # File contents
```

#### Write File

```python
tool_call = ToolCall(
    id="write-001",
    tool_name="write_file",
    arguments={
        "file_path": "/tmp/output.txt",
        "content": "Hello, World!"
    }
)

result = await registry.execute_tool_call(tool_call)
```

#### List Files

```python
tool_call = ToolCall(
    id="list-001",
    tool_name="list_files",
    arguments={"pattern": "*.py", "path": "/home/user"}
)

result = await registry.execute_tool_call(tool_call)
print(result.result)  # List of Python files
```

#### Search Files

```python
tool_call = ToolCall(
    id="search-001",
    tool_name="search_files",
    arguments={
        "pattern": "TODO",
        "path": "/home/user/project"
    }
)

result = await registry.execute_tool_call(tool_call)
```

### Shell Commands

#### Run Command

```python
tool_call = ToolCall(
    id="cmd-001",
    tool_name="run_command",
    arguments={"command": "df -h"}
)

result = await registry.execute_tool_call(tool_call)
print(result.result["stdout"])
```

#### Get System Info

```python
tool_call = ToolCall(
    id="sysinfo-001",
    tool_name="get_system_info",
    arguments={}
)

result = await registry.execute_tool_call(tool_call)
info = result.result

print(f"CPU: {info['cpu']['percent']}%")
print(f"Memory: {info['memory']['used_mb']} / {info['memory']['total_mb']} MB")
print(f"Disk: {info['disk']['use_percent']}")
```

#### Check Service

```python
tool_call = ToolCall(
    id="service-001",
    tool_name="check_service",
    arguments={"service_name": "llama-cpp-agent"}
)

result = await registry.execute_tool_call(tool_call)
print(f"Status: {result.result['status']}")
```

### Computer Use

#### Screenshot

```python
tool_call = ToolCall(
    id="screenshot-001",
    tool_name="screenshot",
    arguments={
        "x": 0,
        "y": 0,
        "width": 1920,
        "height": 1080,
        "output_path": "/tmp/screen.png"
    }
)

result = await registry.execute_tool_call(tool_call)
print(f"Screenshot saved: {result.result}")
```

#### Mouse Click

```python
tool_call = ToolCall(
    id="click-001",
    tool_name="mouse_click",
    arguments={"x": 100, "y": 200, "button": "left"}
)

result = await registry.execute_tool_call(tool_call)
```

#### Keyboard Type

```python
tool_call = ToolCall(
    id="type-001",
    tool_name="keyboard_type",
    arguments={"text": "Hello, World!"}
)

result = await registry.execute_tool_call(tool_call)
```

### Code Execution

#### Run Python

```python
tool_call = ToolCall(
    id="python-001",
    tool_name="run_python",
    arguments={
        "code": """
import math
print(f"Pi = {math.pi:.5f}")
result = sum(range(10))
print(f"Sum = {result}")
"""
    }
)

result = await registry.execute_tool_call(tool_call)
print(result.result["stdout"])
# Output:
# Pi = 3.14159
# Sum = 45
```

#### Run Bash

```python
tool_call = ToolCall(
    id="bash-001",
    tool_name="run_bash",
    arguments={
        "code": """
#!/bin/bash
echo "Current directory: $(pwd)"
ls -la
"""
    }
)

result = await registry.execute_tool_call(tool_call)
```

#### Validate Code

```python
tool_call = ToolCall(
    id="validate-001",
    tool_name="validate_code",
    arguments={
        "code": "import os; os.system('rm -rf /')",
        "language": "python"
    }
)

result = await registry.execute_tool_call(tool_call)
scan = result.result

print(f"Safety: {scan['level']}")
print(f"Safe to execute: {scan['safe_to_execute']}")
print(f"Issues: {scan['issues']}")
```

### AI Coordination

#### Get Hint

```python
tool_call = ToolCall(
    id="hint-001",
    tool_name="get_hint",
    arguments={"query": "How to deploy NixOS service?"}
)

result = await registry.execute_tool_call(tool_call)
print(result.result)  # Hint from hints engine
```

#### Delegate to Remote

```python
tool_call = ToolCall(
    id="delegate-001",
    tool_name="delegate_to_remote",
    arguments={
        "task": "Design scalable microservices architecture",
        "agent": "claude"
    }
)

result = await registry.execute_tool_call(tool_call)
```

---

## Monitoring

### Health Checks

```python
from local_agents import MonitoringAgent

monitoring = MonitoringAgent()

# Run all health checks
checks = await monitoring.check_system_health()

# Process results
for check in checks:
    status_icon = {
        "healthy": "✓",
        "degraded": "⚠",
        "unhealthy": "✗",
        "critical": "🔴"
    }[check.status.value]

    print(f"{status_icon} {check.component}: {check.message}")

    if check.remediation_suggested:
        print(f"  → Suggested: {check.remediation_suggested}")
```

### Performance Metrics

```python
from local_agents import get_executor

executor = get_executor()

# Get performance stats
stats = executor.get_performance_stats()

for agent_type, perf in stats.items():
    print(f"\n{agent_type}:")
    print(f"  Total tasks: {perf['total_tasks']}")
    print(f"  Success rate: {perf['success_rate']:.1%}")
    print(f"  Avg time: {perf['avg_execution_time_ms']:.0f}ms")
    print(f"  Tool success: {perf['tool_success_rate']:.1%}")
```

### Tool Registry Stats

```python
from local_agents import get_registry

registry = get_registry()
stats = registry.get_statistics()

print(f"Total tools: {stats['total_tools']}")
print(f"Enabled: {stats['enabled_tools']}")
print(f"Total calls: {stats['total_calls']}")
print(f"Success: {stats['successful_calls']}")
print(f"Failed: {stats['failed_calls']}")

print("\nBy category:")
for category, count in stats['tools_by_category'].items():
    print(f"  {category}: {count}")

print("\nBy safety policy:")
for policy, count in stats['tools_by_policy'].items():
    print(f"  {policy}: {count}")
```

### Quality Tracking

```python
from local_agents import SelfImprovementEngine, AgentType

engine = SelfImprovementEngine()

# Analyze performance
analysis = engine.analyze_performance(
    agent_type=AgentType.AGENT,
    time_window_days=7
)

print(f"Sample count: {analysis['sample_count']}")
print(f"Correctness: {analysis['avg_correctness']:.1%}")
print(f"Completeness: {analysis['avg_completeness']:.1%}")
print(f"Efficiency: {analysis['avg_efficiency']:.1%}")
print(f"Overall: {analysis['avg_overall']:.1%}")

# Get recommendations
recommendations = engine.generate_improvement_recommendations(AgentType.AGENT)

for rec in recommendations:
    print(f"\n[{rec.priority.upper()}] {rec.category}")
    print(f"  {rec.description}")
    for action in rec.suggested_actions:
        print(f"  - {action}")
```

---

## Troubleshooting

### Common Issues

#### Issue: Tool calls failing with "Tool not found"

**Symptoms:**
```
Tool call failed: Tool read_file not found
```

**Solution:**
```python
# Re-initialize tool registry
from local_agents import get_registry, initialize_builtin_tools

registry = get_registry()
initialize_builtin_tools(registry)

# Verify tools loaded
print(f"Loaded {len(registry.tools)} tools")
```

#### Issue: Rate limit exceeded

**Symptoms:**
```
Tool call failed: Rate limit exceeded: 60/60 calls/min
```

**Solution:**
```python
# Wait for rate limit window to pass
import time
time.sleep(60)

# Or increase limits
tool = registry.get_tool("tool_name")
tool.max_calls_per_minute = 120
tool.max_calls_per_hour = 2000
```

#### Issue: Code execution timeout

**Symptoms:**
```
Execution timeout (30s)
```

**Solution:**
```python
from local_agents import get_code_executor, ResourceLimits

# Increase timeout
limits = ResourceLimits(timeout_seconds=60)
executor = get_code_executor(limits=limits)
```

#### Issue: Memory limit exceeded during code execution

**Symptoms:**
```
MemoryError or process killed
```

**Solution:**
```python
# Increase memory limit
limits = ResourceLimits(memory_bytes=512 * 1024 * 1024)  # 512 MB
executor = get_code_executor(limits=limits)
```

#### Issue: Local agent fallback loop

**Symptoms:**
- All tasks falling back to remote
- High remote API costs

**Solution:**
```python
# Check local agent performance
executor = get_executor()
stats = executor.get_performance_stats()

agent_stats = stats['agent']
print(f"Success rate: {agent_stats['success_rate']:.1%}")

# If low, investigate failed tasks
# Check llama.cpp service
curl http://127.0.0.1:8080/health

# Restart if needed
systemctl restart llama-cpp-agent
```

### Diagnostic Commands

```bash
# Check service status
systemctl status llama-cpp-agent
systemctl status hybrid-coordinator
systemctl status aidb

# View logs
journalctl -u llama-cpp-agent -f
journalctl -u hybrid-coordinator -f

# Check database
sqlite3 ~/.local/share/nixos-ai-stack/local-agents/tool_audit.db \
  "SELECT COUNT(*) FROM tool_calls;"

# Check recent failures
sqlite3 ~/.local/share/nixos-ai-stack/local-agents/tool_audit.db \
  "SELECT timestamp, tool_name, error FROM tool_calls WHERE status='failed' ORDER BY timestamp DESC LIMIT 10;"
```

### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# See detailed tool execution
logger = logging.getLogger("local_agents")
logger.setLevel(logging.DEBUG)
```

---

## Safety & Security

### Safety Policy Levels

Understand the 5 safety policy levels:

| Level | Description | Examples | Confirmation |
|-------|-------------|----------|--------------|
| READ_ONLY | Read-only operations | read_file, get_system_info | No |
| WRITE_SAFE | Write to safe locations | write to /tmp, logs | No |
| WRITE_DATA | Write to data directories | write to /home, /var | First time |
| SYSTEM_MODIFY | System changes | restart service, edit config | Always |
| DESTRUCTIVE | Destructive operations | delete, format, network | Always + delay |

### User Confirmation

Implement confirmation callbacks:

```python
def request_confirmation(tool_call: ToolCall) -> bool:
    """Request user confirmation for sensitive operations"""
    print(f"\n⚠️  Confirmation required:")
    print(f"Tool: {tool_call.tool_name}")
    print(f"Arguments: {tool_call.arguments}")

    response = input("Proceed? (yes/no): ")
    return response.lower() in ["yes", "y"]

# Use with executor
result = await registry.execute_tool_call(
    tool_call,
    request_confirmation=request_confirmation
)
```

### Security Best Practices

1. **Review audit logs regularly**
   ```bash
   # Check for suspicious activity
   sqlite3 ~/.local/share/nixos-ai-stack/local-agents/tool_audit.db \
     "SELECT * FROM tool_calls WHERE user_confirmed=0 AND status='failed';"
   ```

2. **Enable security scanning**
   ```python
   # Never skip security scans
   result = await executor.execute(code, language, skip_security_scan=False)
   ```

3. **Limit network access**
   ```python
   # Disable network for code execution
   executor = get_code_executor(allow_network=False)
   ```

4. **Use least privilege**
   - Run agents as non-root user
   - Limit filesystem access
   - Restrict network access

5. **Monitor resource usage**
   ```python
   # Check executor stats
   stats = executor.get_statistics()
   if stats['blocked_executions'] > 0:
       print(f"⚠️  {stats['blocked_executions']} executions blocked")
   ```

### Audit Trail

Query audit database:

```sql
-- Recent tool calls
SELECT timestamp, tool_name, status, execution_time_ms
FROM tool_calls
ORDER BY timestamp DESC
LIMIT 20;

-- Failed tool calls
SELECT tool_name, COUNT(*) as failures
FROM tool_calls
WHERE status = 'failed'
GROUP BY tool_name
ORDER BY failures DESC;

-- Tool usage by model
SELECT model_id, COUNT(*) as calls
FROM tool_calls
GROUP BY model_id;

-- Slow tool calls
SELECT tool_name, AVG(execution_time_ms) as avg_time
FROM tool_calls
WHERE status = 'completed'
GROUP BY tool_name
ORDER BY avg_time DESC;
```

---

## Performance Tuning

### Optimize Task Routing

```python
from local_agents import TaskRouter

# Tune routing thresholds
router = TaskRouter(
    local_success_threshold=0.75,  # Lower to use local more
    complexity_threshold=0.6,      # Raise to keep more local
    default_to_local=True
)

# Update performance metrics
router.update_local_performance(success_rate=0.85)
```

### Optimize Resource Limits

```python
from local_agents import ResourceLimits

# Balance safety and performance
limits = ResourceLimits(
    timeout_seconds=45,              # Longer for complex tasks
    memory_bytes=384 * 1024 * 1024,  # More memory
    cpu_time_seconds=45,
    max_processes=15,                # More parallelism
)
```

### Reduce Tool Call Overhead

```python
# Batch operations when possible
tool_calls = [
    ToolCall(id=f"read-{i}", tool_name="read_file",
             arguments={"file_path": f"/tmp/file{i}.txt"})
    for i in range(10)
]

# Execute in parallel
results = await asyncio.gather(*[
    registry.execute_tool_call(tc) for tc in tool_calls
])
```

### Monitor Performance

```python
import time

# Track execution time
start = time.time()
result = await executor.execute_task(task)
elapsed = time.time() - start

print(f"Task: {result.execution_time_ms}ms")
print(f"Total: {elapsed * 1000}ms")
print(f"Overhead: {(elapsed * 1000) - result.execution_time_ms}ms")
```

---

## Workflow Integration

### Task Creation

```python
from local_agents import Task

# Simple task
task = Task(
    id="task-001",
    objective="List all Python files and count lines",
    complexity=0.3,  # Simple
    latency_critical=True,
    context={"directory": "/home/user/project"}
)

# Complex task
task = Task(
    id="task-002",
    objective="Analyze codebase and generate architecture diagram",
    complexity=0.8,  # Complex
    quality_critical=True,
    requires_flagship=False,  # Try local first
)
```

### Multi-Agent Workflow

```python
from local_agents import get_executor, get_router, AgentType

router = get_router()
executor = get_executor()

# Step 1: Plan (use planner)
plan_task = Task(
    id="plan-001",
    objective="Break down: Build HTTP service",
    complexity=0.6
)

# Route to planner
decision = router.route(
    objective=plan_task.objective,
    complexity=plan_task.complexity
)

plan_result = await executor.execute_task(plan_task, AgentType.PLANNER)

# Step 2: Execute steps (use agent)
for step in parse_plan(plan_result.result):
    step_task = Task(
        id=f"step-{step.id}",
        objective=step.description,
        complexity=step.complexity
    )

    step_result = await executor.execute_task(step_task, AgentType.AGENT)
    print(f"Step {step.id}: {step_result.status.value}")
```

### Fallback Handling

```python
from local_agents import TaskStatus

# Execute with automatic fallback
result = await executor.execute_task(task)

if result.status == TaskStatus.FALLBACK:
    print("⚠️  Task fell back to remote agent")
    print(f"Reason: Check router logs")

elif result.status == TaskStatus.COMPLETED:
    if result.assigned_agent.startswith("local"):
        print("✓ Completed locally (cost savings!)")
    else:
        print("✓ Completed remotely")
```

---

## Alert Remediation

### Automatic Remediation

```python
from local_agents import MonitoringAgent

monitoring = MonitoringAgent(
    executor=executor,
    check_interval_seconds=60
)

# Health check detects issue
checks = await monitoring.check_system_health()

for check in checks:
    if check.status != HealthStatus.HEALTHY:
        # Triage and create remediation task
        task = await monitoring.triage_issue(check)

        if task:
            # Execute remediation
            success = await monitoring.execute_remediation(task)

            if success:
                print(f"✓ Remediated {check.component}")
            else:
                print(f"✗ Failed to remediate {check.component}")
```

### Manual Remediation

```python
# Manually create remediation task
from local_agents import Task, AgentType

remediation_task = Task(
    id="remediation-001",
    objective="Clear system cache to free memory",
    context={
        "component": "memory",
        "issue": "Memory usage >80%",
        "remediation": "clear_cache"
    },
    complexity=0.2,
    latency_critical=True
)

result = await executor.execute_task(remediation_task, AgentType.AGENT)
```

### Remediation Workflows

Common remediation workflows:

```python
REMEDIATION_WORKFLOWS = {
    "restart_service": """
    1. Check service status
    2. Stop service gracefully
    3. Wait 5 seconds
    4. Start service
    5. Verify health
    """,

    "clear_cache": """
    1. Get current memory usage
    2. Clear /tmp cache
    3. Clear application caches
    4. Verify memory reduced
    """,

    "rotate_logs": """
    1. Check disk usage
    2. Compress old logs
    3. Archive to backup
    4. Delete old archives
    5. Verify disk freed
    """,

    "switch_to_remote": """
    1. Update router config
    2. Set local_success_threshold = 1.0
    3. Force remote routing
    4. Monitor remote success
    """,
}
```

---

## Best Practices

### 1. Task Design

**DO:**
- Use clear, specific objectives
- Set appropriate complexity (0.0-1.0)
- Provide relevant context
- Set latency/quality flags correctly

**DON'T:**
- Use vague objectives
- Over-estimate complexity (wastes remote)
- Under-estimate complexity (fails local)
- Omit important context

### 2. Tool Usage

**DO:**
- Use appropriate tools for task
- Check tool availability first
- Handle tool call failures gracefully
- Log tool usage for auditing

**DON'T:**
- Skip security scans
- Ignore rate limits
- Execute untrusted code
- Bypass safety policies

### 3. Error Handling

**DO:**
```python
try:
    result = await executor.execute_task(task)

    if result.status == TaskStatus.COMPLETED:
        process_success(result)
    elif result.status == TaskStatus.FALLBACK:
        log_fallback(result)
        process_success(result)  # Still got result
    else:
        handle_error(result)

except Exception as e:
    logger.exception(f"Task execution failed: {e}")
    alert_operator(e)
```

**DON'T:**
```python
# Ignore errors
result = await executor.execute_task(task)
# Hope it worked
```

### 4. Monitoring

**DO:**
- Monitor health checks regularly
- Track performance metrics
- Review audit logs
- Set up alerts for issues

**DON'T:**
- Ignore degraded status
- Let critical issues persist
- Run without monitoring
- Skip performance tracking

### 5. Security

**DO:**
- Enable all security features
- Review audit logs
- Use least privilege
- Implement confirmation callbacks

**DON'T:**
- Skip security scans
- Grant excessive permissions
- Ignore security warnings
- Disable safety policies

### 6. Performance

**DO:**
- Tune routing thresholds based on metrics
- Optimize resource limits
- Monitor overhead
- Use local agents when appropriate

**DON'T:**
- Over-use remote agents (expensive)
- Under-provision resources (failures)
- Ignore performance degradation
- Skip quality tracking

---

## Quick Reference

### Essential Commands

```python
# Initialize
from local_agents import (
    get_registry, initialize_builtin_tools,
    get_executor, get_router, MonitoringAgent
)

registry = get_registry()
initialize_builtin_tools(registry)
executor = get_executor()
router = get_router()
monitoring = MonitoringAgent()

# Execute task
task = Task(id="1", objective="Do something", complexity=0.5)
result = await executor.execute_task(task)

# Health check
checks = await monitoring.check_system_health()

# Stats
tool_stats = registry.get_statistics()
perf_stats = executor.get_performance_stats()
```

### Configuration Files

```
~/.local/share/nixos-ai-stack/local-agents/
├── tool_audit.db          # Tool call audit trail
├── improvement.db         # Quality scores and benchmarks
└── config.yaml           # Configuration (optional)
```

### Service Endpoints

```
http://127.0.0.1:8080     # llama.cpp (local models)
http://127.0.0.1:8003     # Hybrid coordinator
http://127.0.0.1:8002     # AIDB (context database)
```

---

## Next Steps

1. **Set up monitoring dashboard** - Grafana dashboards for metrics
2. **Configure alerts** - Integrate with alert engine
3. **Tune routing** - Optimize for your workload
4. **Review security** - Audit logs and policies
5. **Performance baseline** - Establish benchmarks

---

## Support

- **Documentation**: `/docs/architecture/local-agent-agentic-capabilities.md`
- **Developer Guide**: `/docs/development/local-agent-development-guide.md`
- **Tool Reference**: `/docs/reference/local-agent-tool-reference.md`
- **Examples**: `/docs/examples/local-agent-recipes.md`

---

**Guide Version:** 1.0
**Status:** Production Ready
**Last Review:** 2026-03-21
