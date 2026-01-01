---
name: Ralph Wiggum Loop
description: Continuous autonomous agent orchestration using the Ralph Wiggum technique
version: 1.0.0
author: NixOS Quick Deploy AI Stack
created: 2025-12-30
tags:
  - autonomous
  - loop
  - agentic
  - orchestration
  - ralph-wiggum
capabilities:
  - continuous_iteration
  - exit_blocking
  - context_recovery
  - multi_backend_support
  - human_in_the_loop
dependencies:
  - aidb-knowledge
  - mcp-server
---

# Ralph Wiggum Loop Skill

## Overview

The Ralph Wiggum Loop skill enables continuous autonomous agent orchestration using the Ralph Wiggum technique. Named after Ralph Wiggum from The Simpsons, this approach embodies persistent iteration despite setbacks.

## What is the Ralph Wiggum Technique?

The Ralph Wiggum technique is a simple yet powerful method for autonomous AI development:

1. **While-True Loop**: Continuously iterate on a task
2. **Exit Code Blocking**: Use exit code 2 to block agent termination
3. **Re-injection**: Feed the same prompt back after blocking
4. **Context Recovery**: Use git and state files for persistence
5. **Human-in-the-Loop**: Allow manual intervention when needed

### Core Philosophy

> "I'm helping!" - Ralph Wiggum

Like Ralph, the loop keeps trying despite failures, learning from each iteration until the task is complete.

## How It Works

```
Task Submitted
    ↓
While True:
    ├─ Execute Agent
    ├─ Check Exit Code
    │   ├─ Exit Code 2: BLOCKED → Re-inject prompt → Continue
    │   ├─ Exit Code 0: Check completion criteria
    │   │   ├─ Complete: Exit loop
    │   │   └─ Incomplete: Continue
    │   └─ Other: Learn from error → Continue
    ├─ Save State (git checkpoint)
    └─ Repeat
```

## Features

### 1. Multi-Backend Support

Ralph Wiggum can orchestrate multiple AI agent backends:

- **Aider**: AI pair programming with git integration
- **Continue**: Open-source autopilot for IDEs
- **Goose**: Autonomous coding agent with file system access
- **AutoGPT**: Goal decomposition and planning
- **LangChain**: Agent framework with memory and state management

### 2. Exit Code Blocking

The stop hook intercepts exit attempts and forces continuation:

```python
if exit_code == 2:
    # I'm helping! (continues iteration)
    re_inject_prompt()
    continue
```

### 3. Context Recovery

Uses git checkpoints and state files to recover from crashes:

- Git commits at each iteration
- State snapshots in JSON
- Error history tracking
- Lessons learned extraction

### 4. Human-in-the-Loop Controls

Fine-grained control over autonomous behavior:

- **Approval Gates**: Require approval before destructive actions
- **Autonomy Levels**: Configure per task type
- **Audit Trails**: Complete log of all agent actions

### 5. Telemetry and Monitoring

Comprehensive tracking of loop performance:

- Iteration counts
- Exit code patterns
- Token usage
- Success rates
- Error patterns

## Usage

### Basic Usage

Submit a task to the Ralph loop:

```bash
# Using the MCP API
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Implement user authentication with JWT tokens",
    "backend": "aider",
    "max_iterations": 0
  }'
```

### Check Task Status

```bash
curl http://localhost:8098/tasks/{task_id}
```

### Stop a Running Task

```bash
curl -X POST http://localhost:8098/tasks/{task_id}/stop
```

### Approve a Task

```bash
curl -X POST http://localhost:8098/tasks/{task_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

## Configuration

Ralph Wiggum can be configured via environment variables:

```bash
# Enable/disable the loop
RALPH_LOOP_ENABLED=true

# Exit code that triggers blocking
RALPH_EXIT_CODE_BLOCK=2

# Max iterations (0 = infinite)
RALPH_MAX_ITERATIONS=0

# Context recovery
RALPH_CONTEXT_RECOVERY=true
RALPH_GIT_INTEGRATION=true

# Human-in-the-loop
RALPH_REQUIRE_APPROVAL=false
RALPH_APPROVAL_THRESHOLD=high  # low, medium, high

# Agent backends
RALPH_AGENT_BACKENDS=aider,continue,goose,autogpt,langchain
RALPH_DEFAULT_BACKEND=aider
```

## Real-World Results

From the Ralph Wiggum community:

- **6 repos shipped overnight** with continuous iteration
- **$50k contract completed for $297** in API costs
- **Projects completing while developers sleep**

## Best Practices

### 1. Start with Clear Prompts

Be specific about what you want accomplished:

```
✅ "Implement user authentication with JWT tokens, including login,
   logout, token refresh, and password reset endpoints"

❌ "Add auth"
```

### 2. Use Appropriate Backends

Choose the right tool for the job:

- **Aider**: Best for git-aware coding with commits
- **Continue**: Great for IDE-style autocomplete and suggestions
- **Goose**: Perfect for file system operations and debugging
- **AutoGPT**: Ideal for multi-step planning and execution
- **LangChain**: Best for memory-intensive workflows

### 3. Set Reasonable Iteration Limits

For testing, use finite iterations:

```json
{
  "max_iterations": 10
}
```

For production overnight runs:

```json
{
  "max_iterations": 0  // Infinite
}
```

### 4. Monitor Progress

Check task status regularly:

```bash
# Get statistics
curl http://localhost:8098/stats

# View telemetry
tail -f ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl
```

### 5. Use Human Approval for Critical Tasks

Enable approval for destructive operations:

```json
{
  "require_approval": true,
  "approval_threshold": "medium"
}
```

## Integration with Existing Stack

Ralph Wiggum integrates with the existing AI stack:

- **AIDB**: Context and knowledge base
- **Hybrid Coordinator**: Query routing and learning
- **PostgreSQL**: Task state persistence
- **Redis**: Caching and session management
- **Qdrant**: Vector embeddings for context

## Troubleshooting

### Task Stuck in Loop

Check if completion criteria are too strict:

```bash
# View task details
curl http://localhost:8098/tasks/{task_id}

# Stop if needed
curl -X POST http://localhost:8098/tasks/{task_id}/stop
```

### Agent Backend Not Responding

Check backend health:

```bash
# Ralph health includes backend status
curl http://localhost:8098/health
```

### Resource Limits Exceeded

Adjust resource limits in configuration:

```yaml
resources:
  max_iterations_per_task: 100
  max_concurrent_tasks: 10
```

## API Reference

### POST /tasks

Submit a new task.

**Request:**
```json
{
  "prompt": "string",
  "backend": "string (optional)",
  "max_iterations": "number (optional)",
  "require_approval": "boolean (optional)",
  "context": "object (optional)"
}
```

**Response:**
```json
{
  "task_id": "string",
  "status": "queued",
  "message": "string"
}
```

### GET /tasks/{task_id}

Get task status.

**Response:**
```json
{
  "task_id": "string",
  "status": "string",
  "iteration": "number",
  "backend": "string",
  "started_at": "string",
  "last_update": "string",
  "error": "string (optional)"
}
```

### POST /tasks/{task_id}/stop

Stop a running task.

### POST /tasks/{task_id}/approve

Approve or reject a task.

**Request:**
```json
{
  "approved": true
}
```

### GET /stats

Get Ralph loop statistics.

**Response:**
```json
{
  "total_tasks": "number",
  "running": "number",
  "completed": "number",
  "failed": "number",
  "total_iterations": "number",
  "average_iterations": "number"
}
```

### GET /health

Health check.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "loop_enabled": true,
  "active_tasks": "number",
  "backends": ["string"]
}
```

## Resources

- [Ralph Wiggum Original Technique](https://paddo.dev/blog/ralph-wiggum-autonomous-loops/)
- [Ralph Orchestrator on GitHub](https://github.com/mikeyobrien/ralph-orchestrator)
- [Anthropic's Ralph Plugin](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/ralph-wiggum)
- [Boundary ML Podcast: Ralph Under the Hood](https://boundaryml.com/podcast/2025-10-28-ralph-wiggum-coding-agent-power-tools)

## License

MIT License - Part of NixOS Quick Deploy AI Stack
