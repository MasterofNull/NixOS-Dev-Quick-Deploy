# Local Agent Recipes and Examples

**Status:** Production
**Owner:** AI Harness Team
**Last Updated:** 2026-03-21
**Audience:** Developers, Operators

---

## Quick Reference

Common automation tasks using local agents with tool calling.

## Table of Contents

1. [File Operations](#file-operations)
2. [System Monitoring](#system-monitoring)
3. [Code Execution](#code-execution)
4. [Alert Remediation](#alert-remediation)
5. [Workflow Automation](#workflow-automation)
6. [Multi-Step Tasks](#multi-step-tasks)

---

## File Operations

### Recipe 1: Backup Configuration Files

```python
from local_agents import get_registry, ToolCall
import asyncio
from datetime import datetime

async def backup_configs():
    registry = get_registry()
    
    # List config files
    list_call = ToolCall(
        id="list-configs",
        tool_name="list_files",
        arguments={"pattern": "*.conf", "path": "/etc"}
    )
    
    files = await registry.execute_tool_call(list_call)
    
    # Backup each file
    backup_dir = f"/tmp/backup-{datetime.now().strftime('%Y%m%d')}"
    
    for file_path in files.result:
        # Read original
        read_call = ToolCall(
            id=f"read-{file_path}",
            tool_name="read_file",
            arguments={"file_path": file_path}
        )
        content = await registry.execute_tool_call(read_call)
        
        # Write backup
        backup_path = f"{backup_dir}/{file_path.replace('/', '_')}"
        write_call = ToolCall(
            id=f"write-{backup_path}",
            tool_name="write_file",
            arguments={"file_path": backup_path, "content": content.result}
        )
        await registry.execute_tool_call(write_call)
    
    print(f"Backed up {len(files.result)} files to {backup_dir}")

asyncio.run(backup_configs())
```

### Recipe 2: Find and Replace in Files

```python
async def find_and_replace(directory, pattern, old_text, new_text):
    registry = get_registry()
    
    # Search for files containing pattern
    search_call = ToolCall(
        tool_name="search_files",
        arguments={"pattern": pattern, "path": directory}
    )
    
    matches = await registry.execute_tool_call(search_call)
    
    # Process each matching file
    for match in matches.result:
        file_path = match['file']
        
        # Read file
        read_call = ToolCall(
            tool_name="read_file",
            arguments={"file_path": file_path}
        )
        content = await registry.execute_tool_call(read_call)
        
        # Replace text
        new_content = content.result.replace(old_text, new_text)
        
        # Write back
        write_call = ToolCall(
            tool_name="write_file",
            arguments={"file_path": file_path, "content": new_content}
        )
        await registry.execute_tool_call(write_call)
        
        print(f"Updated: {file_path}")
```

---

## System Monitoring

### Recipe 3: System Health Dashboard

```python
async def system_health_dashboard():
    from local_agents import MonitoringAgent
    
    monitoring = MonitoringAgent()
    
    # Run all health checks
    checks = await monitoring.check_system_health()
    
    # Display dashboard
    print("\n=== System Health Dashboard ===\n")
    
    for check in checks:
        status_icon = {
            "healthy": "✓",
            "degraded": "⚠",
            "unhealthy": "✗",
            "critical": "🔴"
        }[check.status.value]
        
        print(f"{status_icon} {check.component:20s} {check.message}")
        
        if check.metrics:
            for key, value in check.metrics.items():
                print(f"    {key}: {value}")
        
        if check.remediation_suggested:
            print(f"    → Remediation: {check.remediation_suggested}")
    
    print("\n" + "="*40 + "\n")
```

### Recipe 4: Disk Space Monitor with Auto-Cleanup

```python
async def monitor_disk_space(threshold=85):
    registry = get_registry()
    
    # Get system info
    info_call = ToolCall(
        tool_name="get_system_info",
        arguments={}
    )
    
    info = await registry.execute_tool_call(info_call)
    disk_usage = float(info.result['disk']['use_percent'].rstrip('%'))
    
    print(f"Disk usage: {disk_usage}%")
    
    if disk_usage > threshold:
        print(f"⚠ Disk usage above threshold ({threshold}%)")
        
        # Clean up /tmp
        cleanup_code = """
#!/bin/bash
find /tmp -type f -mtime +7 -delete
find /tmp -type d -empty -delete
echo "Cleanup completed"
"""
        
        cleanup_call = ToolCall(
            tool_name="run_bash",
            arguments={"code": cleanup_code}
        )
        
        result = await registry.execute_tool_call(cleanup_call)
        print(result.result['stdout'])
        
        # Re-check
        info = await registry.execute_tool_call(info_call)
        new_usage = float(info.result['disk']['use_percent'].rstrip('%'))
        freed = disk_usage - new_usage
        
        print(f"✓ Freed {freed:.1f}% disk space")
```

---

## Code Execution

### Recipe 5: Run Python Analysis Script

```python
async def analyze_codebase(directory):
    from local_agents import get_code_executor, Language
    
    executor = get_code_executor()
    
    analysis_code = f"""
import os
import sys

directory = '{directory}'
stats = {{
    'total_files': 0,
    'total_lines': 0,
    'py_files': 0,
    'py_lines': 0
}}

for root, dirs, files in os.walk(directory):
    for file in files:
        stats['total_files'] += 1
        file_path = os.path.join(root, file)
        
        try:
            with open(file_path, 'r') as f:
                lines = len(f.readlines())
                stats['total_lines'] += lines
                
                if file.endswith('.py'):
                    stats['py_files'] += 1
                    stats['py_lines'] += lines
        except:
            pass

print(f"Total files: {{stats['total_files']}}")
print(f"Total lines: {{stats['total_lines']}}")
print(f"Python files: {{stats['py_files']}}")
print(f"Python lines: {{stats['py_lines']}}")
"""
    
    result = await executor.execute(analysis_code, Language.PYTHON)
    
    if result.success:
        print(result.stdout)
    else:
        print(f"Error: {result.error}")
```

### Recipe 6: Validate and Execute User Script

```python
async def safe_execute_script(code, language="python"):
    from local_agents import get_code_executor, Language
    
    executor = get_code_executor()
    lang = Language[language.upper()]
    
    # First validate
    scan = await executor.scanner.scan(code, lang)
    
    print(f"Security scan: {scan.level.value}")
    if scan.issues:
        print("Issues found:")
        for issue in scan.issues:
            print(f"  - {issue}")
    
    if not scan.safe_to_execute:
        print(f"❌ Execution blocked: {scan.reason}")
        return None
    
    # Execute if safe
    print("✓ Code is safe, executing...")
    result = await executor.execute(code, lang)
    
    if result.success:
        print(f"✓ Success ({result.execution_time_seconds:.2f}s)")
        print("\nOutput:")
        print(result.stdout)
        return result
    else:
        print(f"❌ Failed: {result.error}")
        print("\nStderr:")
        print(result.stderr)
        return None
```

---

## Alert Remediation

### Recipe 7: Auto-Remediate High Memory Usage

```python
async def remediate_high_memory():
    from local_agents import MonitoringAgent, get_executor, Task, AgentType
    
    monitoring = MonitoringAgent()
    executor = get_executor()
    
    # Check memory
    checks = await monitoring.check_system_health()
    memory_check = next(c for c in checks if c.component == "memory")
    
    if memory_check.status != "healthy":
        print(f"⚠ Memory issue: {memory_check.message}")
        
        # Create remediation task
        task = Task(
            id="remediation-memory",
            objective="Clear system caches to free memory",
            context={
                "component": "memory",
                "usage": memory_check.metrics.get("usage_percent"),
                "remediation": "clear_cache"
            },
            complexity=0.2,
            latency_critical=True
        )
        
        # Execute remediation
        result = await executor.execute_task(task, AgentType.AGENT)
        
        if result.status.value == "completed":
            print("✓ Memory remediation successful")
            
            # Verify improvement
            checks = await monitoring.check_system_health()
            memory_check = next(c for c in checks if c.component == "memory")
            print(f"New memory status: {memory_check.status.value}")
        else:
            print(f"❌ Remediation failed: {result.error}")
```

### Recipe 8: Service Health Monitor with Auto-Restart

```python
async def monitor_and_restart_service(service_name):
    registry = get_registry()
    
    # Check service status
    check_call = ToolCall(
        tool_name="check_service",
        arguments={"service_name": service_name}
    )
    
    status = await registry.execute_tool_call(check_call)
    
    if status.result['active'] != 'active':
        print(f"⚠ {service_name} is {status.result['active']}")
        
        # Restart service
        restart_call = ToolCall(
            tool_name="run_command",
            arguments={"command": f"systemctl restart {service_name}"}
        )
        
        result = await registry.execute_tool_call(restart_call)
        
        if result.status == "completed":
            print(f"✓ Restarted {service_name}")
            
            # Wait and verify
            import asyncio
            await asyncio.sleep(5)
            
            status = await registry.execute_tool_call(check_call)
            if status.result['active'] == 'active':
                print(f"✓ {service_name} is now active")
            else:
                print(f"❌ {service_name} failed to start")
        else:
            print(f"❌ Failed to restart: {result.error}")
    else:
        print(f"✓ {service_name} is healthy")
```

---

## Workflow Automation

### Recipe 9: Automated Deployment Workflow

```python
async def deploy_workflow(service_name, config_file):
    from local_agents import get_executor, Task, AgentType
    
    executor = get_executor()
    
    # Step 1: Validate configuration
    validate_task = Task(
        id="deploy-validate",
        objective=f"Validate configuration file {config_file}",
        complexity=0.3
    )
    
    result = await executor.execute_task(validate_task, AgentType.AGENT)
    if result.status.value != "completed":
        print("❌ Validation failed")
        return
    
    print("✓ Configuration valid")
    
    # Step 2: Backup current config
    backup_task = Task(
        id="deploy-backup",
        objective=f"Backup current {service_name} configuration",
        complexity=0.2
    )
    
    await executor.execute_task(backup_task, AgentType.AGENT)
    print("✓ Backup created")
    
    # Step 3: Deploy new config
    deploy_task = Task(
        id="deploy-apply",
        objective=f"Deploy new configuration for {service_name}",
        complexity=0.4
    )
    
    result = await executor.execute_task(deploy_task, AgentType.AGENT)
    print("✓ Configuration deployed")
    
    # Step 4: Restart service
    restart_task = Task(
        id="deploy-restart",
        objective=f"Restart {service_name} service",
        complexity=0.3
    )
    
    await executor.execute_task(restart_task, AgentType.AGENT)
    print("✓ Service restarted")
    
    # Step 5: Verify health
    verify_task = Task(
        id="deploy-verify",
        objective=f"Verify {service_name} is healthy after restart",
        complexity=0.3
    )
    
    result = await executor.execute_task(verify_task, AgentType.AGENT)
    
    if result.status.value == "completed":
        print("✓ Deployment successful")
    else:
        print("⚠ Deployment completed but verification failed")
```

### Recipe 10: Multi-Agent Data Processing

```python
async def process_data_pipeline(input_file, output_file):
    from local_agents import get_executor, get_router, Task, AgentType
    
    executor = get_executor()
    router = get_router()
    
    # Step 1: Extract data (simple, use local)
    extract_task = Task(
        id="pipeline-extract",
        objective=f"Extract data from {input_file}",
        complexity=0.2,
        latency_critical=True
    )
    
    extract_result = await executor.execute_task(extract_task, AgentType.AGENT)
    print(f"✓ Extracted data: {len(extract_result.result)} records")
    
    # Step 2: Transform data (complex, might need remote)
    transform_task = Task(
        id="pipeline-transform",
        objective="Apply complex transformations to extracted data",
        complexity=0.7,
        quality_critical=True,
        context={"data": extract_result.result}
    )
    
    # Router will decide local vs remote
    decision = router.route(
        objective=transform_task.objective,
        complexity=transform_task.complexity,
        quality_critical=True
    )
    
    print(f"Transform routed to: {decision.target.value} ({decision.reason})")
    
    transform_result = await executor.execute_task(transform_task, AgentType.AGENT)
    print(f"✓ Transformed data")
    
    # Step 3: Load data (simple, use local)
    load_task = Task(
        id="pipeline-load",
        objective=f"Load transformed data to {output_file}",
        complexity=0.2,
        latency_critical=True,
        context={"data": transform_result.result}
    )
    
    load_result = await executor.execute_task(load_task, AgentType.AGENT)
    print(f"✓ Loaded data to {output_file}")
    
    print("\n✓ Pipeline completed successfully")
```

---

## Multi-Step Tasks

### Recipe 11: Comprehensive System Audit

```python
async def system_audit():
    """Comprehensive system audit using multiple tools"""
    from local_agents import get_registry, get_executor, get_code_executor
    from local_agents import Task, AgentType, Language
    
    registry = get_registry()
    executor = get_executor()
    code_executor = get_code_executor()
    
    report = []
    
    # 1. System information
    info_call = ToolCall(tool_name="get_system_info", arguments={})
    info = await registry.execute_tool_call(info_call)
    
    report.append("=== System Information ===")
    report.append(f"CPU: {info.result['cpu']['percent']}%")
    report.append(f"Memory: {info.result['memory']['used_mb']}MB / {info.result['memory']['total_mb']}MB")
    report.append(f"Disk: {info.result['disk']['use_percent']}")
    report.append("")
    
    # 2. Service status
    services = ["llama-cpp-agent", "hybrid-coordinator", "aidb"]
    report.append("=== Service Status ===")
    
    for service in services:
        check_call = ToolCall(
            tool_name="check_service",
            arguments={"service_name": service}
        )
        status = await registry.execute_tool_call(check_call)
        report.append(f"{service}: {status.result['status']}")
    
    report.append("")
    
    # 3. Security audit
    security_check = """
import os
import pwd

# Check for users with UID 0
users_with_root = []
for user in pwd.getpwall():
    if user.pw_uid == 0:
        users_with_root.append(user.pw_name)

print(f"Users with UID 0: {', '.join(users_with_root)}")

# Check critical file permissions
critical_files = ['/etc/passwd', '/etc/shadow', '/etc/sudoers']
for file in critical_files:
    if os.path.exists(file):
        perms = oct(os.stat(file).st_mode)[-3:]
        print(f"{file}: {perms}")
"""
    
    security_result = await code_executor.execute(security_check, Language.PYTHON)
    report.append("=== Security Audit ===")
    report.append(security_result.stdout)
    report.append("")
    
    # 4. Tool usage statistics
    tool_stats = registry.get_statistics()
    report.append("=== Tool Usage ===")
    report.append(f"Total calls: {tool_stats['total_calls']}")
    report.append(f"Successful: {tool_stats['successful_calls']}")
    report.append(f"Failed: {tool_stats['failed_calls']}")
    report.append("")
    
    # 5. Write report
    report_text = "\n".join(report)
    report_file = f"/tmp/system-audit-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    
    write_call = ToolCall(
        tool_name="write_file",
        arguments={"file_path": report_file, "content": report_text}
    )
    await registry.execute_tool_call(write_call)
    
    print(report_text)
    print(f"\n✓ Audit report saved to: {report_file}")
```

---

## Common Patterns

### Pattern 1: Retry with Exponential Backoff

```python
async def retry_with_backoff(tool_call, max_retries=3):
    import asyncio
    
    registry = get_registry()
    
    for attempt in range(max_retries):
        result = await registry.execute_tool_call(tool_call)
        
        if result.status == "completed":
            return result
        
        if attempt < max_retries - 1:
            wait = 2 ** attempt  # 1s, 2s, 4s
            print(f"Attempt {attempt+1} failed, retrying in {wait}s...")
            await asyncio.sleep(wait)
    
    raise Exception(f"Failed after {max_retries} attempts")
```

### Pattern 2: Parallel Tool Execution

```python
async def parallel_execution(tool_calls):
    import asyncio
    from local_agents import get_registry
    
    registry = get_registry()
    
    # Execute all tool calls in parallel
    results = await asyncio.gather(*[
        registry.execute_tool_call(tc) for tc in tool_calls
    ])
    
    return results
```

### Pattern 3: Tool Call Pipeline

```python
async def tool_pipeline(*tool_calls):
    """Execute tools in sequence, passing results forward"""
    registry = get_registry()
    
    result = None
    for tool_call in tool_calls:
        # Previous result can be used in next call's arguments
        if result:
            tool_call.arguments['previous_result'] = result.result
        
        result = await registry.execute_tool_call(tool_call)
        
        if result.status != "completed":
            raise Exception(f"Pipeline failed at {tool_call.tool_name}")
    
    return result
```

---

**End of Recipes**

See also:
- **Operations Guide**: `/docs/operations/local-agent-operations-guide.md`
- **Tool Reference**: `/docs/reference/local-agent-tool-reference.md`
- **Developer Guide**: `/docs/development/local-agent-development-guide.md`
