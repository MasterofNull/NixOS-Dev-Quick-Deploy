# Local Agent Tool Reference

**Status:** Production
**Owner:** AI Harness Team
**Last Updated:** 2026-03-21
**Total Tools:** 24+

---

## Tool Categories

- [File Operations](#file-operations) (5 tools)
- [Shell Commands](#shell-commands) (3 tools)
- [Computer Use](#computer-use) (6 tools)
- [Code Execution](#code-execution) (4 tools)
- [AI Coordination](#ai-coordination) (5 tools)

---

## File Operations

### read_file

Read contents of a file.

**Parameters:**
- `file_path` (string, required): Absolute path to file

**Returns:** File contents as string

**Safety:** READ_ONLY

**Example:**
```python
tool_call = ToolCall(
    tool_name="read_file",
    arguments={"file_path": "/etc/hosts"}
)
result = await registry.execute_tool_call(tool_call)
print(result.result)
```

### write_file

Write contents to a file.

**Parameters:**
- `file_path` (string, required): Absolute path to file
- `content` (string, required): Content to write

**Returns:** Success message

**Safety:** WRITE_SAFE (for /tmp), WRITE_DATA (for other paths)

**Example:**
```python
tool_call = ToolCall(
    tool_name="write_file",
    arguments={
        "file_path": "/tmp/output.txt",
        "content": "Hello, World!"
    }
)
```

### list_files

List files matching glob pattern.

**Parameters:**
- `pattern` (string, required): Glob pattern (e.g., "*.py")
- `path` (string, optional): Directory path (default: current)

**Returns:** List of matching file paths

**Safety:** READ_ONLY

**Example:**
```python
tool_call = ToolCall(
    tool_name="list_files",
    arguments={"pattern": "*.py", "path": "/home/user"}
)
```

### search_files

Search file contents using grep.

**Parameters:**
- `pattern` (string, required): Search pattern (regex)
- `path` (string, required): Directory to search

**Returns:** List of matching lines with file paths

**Safety:** READ_ONLY

**Example:**
```python
tool_call = ToolCall(
    tool_name="search_files",
    arguments={"pattern": "TODO", "path": "/home/user/project"}
)
```

### file_exists

Check if file or directory exists.

**Parameters:**
- `path` (string, required): File or directory path

**Returns:** Boolean (true/false)

**Safety:** READ_ONLY

---

## Shell Commands

### run_command

Execute shell command in sandbox.

**Parameters:**
- `command` (string, required): Shell command to execute
- `timeout` (int, optional): Timeout in seconds (default: 30)

**Returns:** Object with stdout, stderr, exit_code

**Safety:** SYSTEM_MODIFY

**Example:**
```python
tool_call = ToolCall(
    tool_name="run_command",
    arguments={"command": "df -h"}
)
result = await registry.execute_tool_call(tool_call)
print(result.result["stdout"])
```

### get_system_info

Get system resource information.

**Parameters:** None

**Returns:** Object with CPU, memory, disk stats

**Safety:** READ_ONLY

**Example:**
```python
tool_call = ToolCall(tool_name="get_system_info", arguments={})
result = await registry.execute_tool_call(tool_call)
info = result.result
print(f"CPU: {info['cpu']['percent']}%")
print(f"Memory: {info['memory']['used_mb']} MB")
```

### check_service

Check systemd service status.

**Parameters:**
- `service_name` (string, required): Service name (e.g., "nginx")

**Returns:** Object with status, active, enabled

**Safety:** READ_ONLY

---

## Computer Use

### screenshot

Capture screen or region.

**Parameters:**
- `x` (int, optional): X coordinate of region
- `y` (int, optional): Y coordinate of region
- `width` (int, optional): Width of region
- `height` (int, optional): Height of region
- `output_path` (string, optional): Save path (default: /tmp)

**Returns:** Path to saved screenshot

**Safety:** READ_ONLY

**Example:**
```python
tool_call = ToolCall(
    tool_name="screenshot",
    arguments={
        "x": 0, "y": 0,
        "width": 1920, "height": 1080,
        "output_path": "/tmp/screen.png"
    }
)
```

### mouse_move

Move mouse to position.

**Parameters:**
- `x` (int, required): X coordinate
- `y` (int, required): Y coordinate

**Returns:** Success message

**Safety:** SYSTEM_MODIFY

### mouse_click

Click mouse at position.

**Parameters:**
- `x` (int, required): X coordinate
- `y` (int, required): Y coordinate
- `button` (string, optional): Button (left/right/middle, default: left)

**Returns:** Success message

**Safety:** SYSTEM_MODIFY

### keyboard_type

Type text at current focus.

**Parameters:**
- `text` (string, required): Text to type

**Returns:** Success message

**Safety:** SYSTEM_MODIFY

### keyboard_press

Press special keys.

**Parameters:**
- `keys` (string, required): Keys to press (e.g., "ctrl+c", "alt+tab")

**Returns:** Success message

**Safety:** SYSTEM_MODIFY

### get_screen_size

Get screen dimensions.

**Parameters:** None

**Returns:** Object with width and height

**Safety:** READ_ONLY

---

## Code Execution

### run_python

Execute Python code in sandbox.

**Parameters:**
- `code` (string, required): Python code to execute

**Returns:** Object with stdout, stderr, exit_code, security_scan

**Safety:** WRITE_SAFE (sandboxed)

**Resource Limits:**
- Timeout: 30s
- Memory: 256 MB
- CPU: 30s
- Network: Disabled

**Example:**
```python
tool_call = ToolCall(
    tool_name="run_python",
    arguments={
        "code": """
import math
print(f"Pi = {math.pi:.5f}")
"""
    }
)
result = await registry.execute_tool_call(tool_call)
print(result.result["stdout"])  # "Pi = 3.14159"
```

### run_bash

Execute Bash script in sandbox.

**Parameters:**
- `code` (string, required): Bash script to execute

**Returns:** Object with stdout, stderr, exit_code, security_scan

**Safety:** WRITE_SAFE (sandboxed)

**Resource Limits:** Same as run_python

**Example:**
```python
tool_call = ToolCall(
    tool_name="run_bash",
    arguments={
        "code": """
#!/bin/bash
echo "Current dir: $(pwd)"
ls -la
"""
    }
)
```

### run_javascript

Execute JavaScript code in sandbox.

**Parameters:**
- `code` (string, required): JavaScript code to execute

**Returns:** Object with stdout, stderr, exit_code, security_scan

**Safety:** WRITE_SAFE (sandboxed)

**Resource Limits:** Same as run_python

**Example:**
```python
tool_call = ToolCall(
    tool_name="run_javascript",
    arguments={
        "code": """
console.log('Hello from Node.js');
console.log('Sum:', [1,2,3,4,5].reduce((a,b) => a+b, 0));
"""
    }
)
```

### validate_code

Security scan code without execution.

**Parameters:**
- `code` (string, required): Code to validate
- `language` (string, required): Language (python/bash/javascript)

**Returns:** SecurityScanResult with level, issues, safe_to_execute

**Safety:** READ_ONLY

**Example:**
```python
tool_call = ToolCall(
    tool_name="validate_code",
    arguments={
        "code": "import os; os.system('rm -rf /')",
        "language": "python"
    }
)
result = await registry.execute_tool_call(tool_call)
scan = result.result
print(f"Safe: {scan['safe_to_execute']}")
print(f"Issues: {scan['issues']}")
```

---

## AI Coordination

### get_hint

Query hints engine for guidance.

**Parameters:**
- `query` (string, required): Query for hints

**Returns:** Hint response

**Safety:** READ_ONLY

**Example:**
```python
tool_call = ToolCall(
    tool_name="get_hint",
    arguments={"query": "How to deploy NixOS service?"}
)
```

### delegate_to_remote

Delegate task to remote agent.

**Parameters:**
- `task` (string, required): Task description
- `agent` (string, optional): Agent type (claude/codex/qwen)

**Returns:** Remote agent response

**Safety:** READ_ONLY

**Example:**
```python
tool_call = ToolCall(
    tool_name="delegate_to_remote",
    arguments={
        "task": "Design architecture",
        "agent": "claude"
    }
)
```

### query_context

Query AIDB context database.

**Parameters:**
- `query` (string, required): Semantic query

**Returns:** Relevant context

**Safety:** READ_ONLY

### store_memory

Store data in AIDB.

**Parameters:**
- `key` (string, required): Memory key
- `value` (string, required): Data to store

**Returns:** Success message

**Safety:** WRITE_DATA

### get_workflow_status

Get current workflow status.

**Parameters:**
- `workflow_id` (string, optional): Workflow ID

**Returns:** Workflow status object

**Safety:** READ_ONLY

---

## Safety Policies

| Policy | Allowed Operations | Confirmation Required |
|--------|-------------------|---------------------|
| READ_ONLY | Read files, fetch URLs | No |
| WRITE_SAFE | Write to /tmp, logs | No |
| WRITE_DATA | Write to data dirs | Yes (first time) |
| SYSTEM_MODIFY | Service restart, config | Yes (always) |
| DESTRUCTIVE | Delete, format, network | Yes (with delay) |

---

## Rate Limits

Default limits for all tools:
- **Per-minute:** 60 calls
- **Per-hour:** 1000 calls

Can be customized per-tool via ToolDefinition.

---

## Error Handling

All tool calls return result with:

```python
{
  "status": "completed" | "failed",
  "result": Any | None,
  "error": str | None,
  "execution_time_ms": float
}
```

Handle errors:

```python
result = await registry.execute_tool_call(tool_call)

if result.status == "completed":
    process_result(result.result)
else:
    logger.error(f"Tool failed: {result.error}")
```

---

## Common Patterns

### File Processing

```python
# Read, process, write
read_call = ToolCall(tool_name="read_file", arguments={"file_path": "/tmp/input.txt"})
content = await registry.execute_tool_call(read_call)

# Process content
processed = content.result.upper()

write_call = ToolCall(tool_name="write_file", arguments={"file_path": "/tmp/output.txt", "content": processed})
await registry.execute_tool_call(write_call)
```

### System Monitoring

```python
# Get system info
info_call = ToolCall(tool_name="get_system_info", arguments={})
info = await registry.execute_tool_call(info_call)

# Check thresholds
if info.result["memory"]["percent"] > 80:
    # Alert or remediate
    pass
```

### Code Execution

```python
# Validate first
validate_call = ToolCall(tool_name="validate_code", arguments={"code": code, "language": "python"})
scan = await registry.execute_tool_call(validate_call)

# Execute if safe
if scan.result["safe_to_execute"]:
    run_call = ToolCall(tool_name="run_python", arguments={"code": code})
    result = await registry.execute_tool_call(run_call)
```

---

**Reference Version:** 1.0
**Status:** Complete
**Total Tools:** 24+
