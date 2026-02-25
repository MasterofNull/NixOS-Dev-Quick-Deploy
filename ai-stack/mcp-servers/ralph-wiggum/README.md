# Ralph Wiggum Loop MCP Server

**Continuous Autonomous Agent Orchestration**

Version: 1.0.0
Status: Production Ready
Created: December 30, 2025

---

## Overview

The Ralph Wiggum Loop MCP Server implements the Ralph Wiggum technique for continuous autonomous development. Named after Ralph Wiggum from The Simpsons, this server embodies the philosophy of persistent iteration despite setbacks.

## What is Ralph Wiggum?

> "I'm helping!" - Ralph Wiggum

The Ralph Wiggum technique is a simple yet powerful approach to autonomous AI development:

```bash
while true; do
    execute_agent task.txt
    exit_code=$?

    if [ $exit_code -eq 2 ]; then
        # Exit blocked - Ralph keeps going!
        continue
    elif [ $exit_code -eq 0 ]; then
        # Check if actually complete
        if task_complete; then
            break
        fi
    fi

    # Learn from iteration
    save_checkpoint
done
```

### Core Principles

1. **Simplicity Over Complexity**: Just a bash while-true loop
2. **Deterministic Failure**: Fail predictably in an unpredictable world
3. **Context Recovery**: Use git and state files for persistence
4. **Human-in-the-Loop**: Allow manual intervention when needed

### Real-World Results

- 6 repositories shipped overnight
- $50,000 contracts completed for $297 in API costs
- Projects completing while developers sleep

---

## Architecture

```
┌──────────────────────────────────────────────┐
│          Ralph Wiggum Loop Engine             │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │         Task Queue                      │ │
│  └────────────────────────────────────────┘ │
│               ↓                              │
│  ┌────────────────────────────────────────┐ │
│  │    While True Loop Processor           │ │
│  │                                        │ │
│  │  • Execute Agent                       │ │
│  │  • Check Exit Code                     │ │
│  │  • Block on Code 2                     │ │
│  │  • Check Completion                    │ │
│  │  • Save Checkpoints                    │ │
│  └────────────────────────────────────────┘ │
│               ↓                              │
│  ┌────────────────────────────────────────┐ │
│  │      Agent Orchestrator                │ │
│  │                                        │ │
│  │  • Aider                               │ │
│  │  • Continue                            │ │
│  │  • Goose                               │ │
│  │  • AutoGPT                             │ │
│  │  • LangChain                           │ │
│  └────────────────────────────────────────┘ │
│               ↓                              │
│  ┌────────────────────────────────────────┐ │
│  │         Hooks System                   │ │
│  │                                        │ │
│  │  • Stop Hook (exit blocking)           │ │
│  │  • Recovery Hook (git checkpoints)     │ │
│  │  • Approval Hook (human gates)         │ │
│  │  • Telemetry Hook (metrics)            │ │
│  └────────────────────────────────────────┘ │
│               ↓                              │
│  ┌────────────────────────────────────────┐ │
│  │       State Manager                    │ │
│  │                                        │ │
│  │  • Task state persistence              │ │
│  │  • Git integration                     │ │
│  │  • Context recovery                    │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

---

## Installation

The Ralph Wiggum server is automatically deployed as part of the AI stack:

```bash
cd /path/to/NixOS-Dev-Quick-Deploy
./scripts/hybrid-ai-stack.sh up
```

This will:
1. Build the Ralph Wiggum Docker container
2. Start the MCP server on port 8098
3. Connect to all agent backends
4. Initialize the loop engine

---

## Configuration

### Environment Variables

```bash
# Server
RALPH_MCP_SERVER_PORT=8098

# Loop engine
RALPH_LOOP_ENABLED=true
RALPH_EXIT_CODE_BLOCK=2
RALPH_MAX_ITERATIONS=0  # 0 = infinite

# Context recovery
RALPH_CONTEXT_RECOVERY=true
RALPH_GIT_INTEGRATION=true
RALPH_STATE_FILE=/data/ralph-state.json
RALPH_TELEMETRY_PATH=/data/telemetry/ralph-events.jsonl

# Database connections
RALPH_POSTGRES_HOST=postgres
RALPH_POSTGRES_PORT=5432
RALPH_POSTGRES_DB=mcp
RALPH_POSTGRES_USER=mcp
RALPH_POSTGRES_PASSWORD=change_me

RALPH_REDIS_HOST=redis
RALPH_REDIS_PORT=6379

# Agent backends
RALPH_AGENT_BACKENDS=aider,continue,goose,autogpt,langchain
RALPH_DEFAULT_BACKEND=aider

# MCP integration
RALPH_COORDINATOR_URL=http://hybrid-coordinator:8092
RALPH_AIDB_URL=http://aidb:8091

# Human-in-the-loop
RALPH_REQUIRE_APPROVAL=false
RALPH_APPROVAL_THRESHOLD=high  # low, medium, high
RALPH_AUDIT_LOG=true
```

### Configuration File

Edit `config/default.yaml` for advanced configuration:

```yaml
loop:
  enabled: true
  exit_code_block: 2
  max_iterations: 0
  context_recovery: true
  git_integration: true

agents:
  backends:
    - aider
    - continue
    - goose
    - autogpt
    - langchain
  default: aider

approval:
  enabled: false
  threshold: high
  timeout: 300

resources:
  max_iterations_per_task: 100
  max_concurrent_tasks: 10
```

---

## API Usage

### Health Check

```bash
curl http://localhost:8098/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "loop_enabled": true,
  "active_tasks": 2,
  "backends": ["aider", "continue", "goose", "autogpt", "langchain"]
}
```

### Submit a Task

```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Implement user authentication with JWT tokens",
    "backend": "aider",
    "max_iterations": 0,
    "require_approval": false,
    "context": {
      "repository": "/workspace/myapp",
      "branch": "feature/auth"
    }
  }'
```

Response:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Task queued for Ralph loop processing"
}
```

### Get Task Status

```bash
curl http://localhost:8098/tasks/550e8400-e29b-41d4-a716-446655440000
```

Response:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "iteration": 5,
  "backend": "aider",
  "started_at": "2025-12-30T10:00:00Z",
  "last_update": "2025-12-30T10:05:00Z",
  "error": null
}
```

### Stop a Task

```bash
curl -X POST http://localhost:8098/tasks/550e8400-e29b-41d4-a716-446655440000/stop
```

### Approve a Task

```bash
curl -X POST http://localhost:8098/tasks/550e8400-e29b-41d4-a716-446655440000/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

### Get Statistics

```bash
curl http://localhost:8098/stats
```

Response:
```json
{
  "total_tasks": 10,
  "running": 2,
  "completed": 7,
  "failed": 1,
  "total_iterations": 45,
  "average_iterations": 4.5
}
```

---

## How It Works

### The Loop

1. **Task Submission**: User submits a task with a prompt and backend choice
2. **Queue Processing**: Task is added to the queue
3. **Iteration Loop**:
   - Execute the agent backend with the prompt
   - Capture exit code and output
   - **If exit_code == 2**: Block exit, re-inject prompt, continue (Ralph magic!)
   - **If exit_code == 0**: Check if task is actually complete
     - If complete: Exit loop
     - If incomplete: Continue iteration
   - **If other exit code**: Learn from error, continue
4. **Checkpoint**: Save state via git commit
5. **Repeat**: Go to step 3

### Exit Code Blocking

The core innovation of Ralph Wiggum:

```python
if exit_code == 2:
    # I'm helping!
    logger.info("ralph_exit_blocked", iteration=iteration)
    await run_hooks("stop", task, result)
    continue  # Back to the loop!
```

This prevents agents from giving up prematurely.

### Context Recovery

Ralph saves checkpoints at every iteration:

- **Git commits**: Full code state
- **State file**: Task metadata and history
- **Telemetry**: Performance metrics

If Ralph crashes, it can recover from the last checkpoint.

### Completion Detection

Ralph uses heuristics to detect actual completion:

- No errors in last 3 iterations
- Agent explicitly reports completion
- No TODOs or FIXMEs in output
- Tests passing (if applicable)

---

## Agent Backends

### Aider

Git-aware pair programming agent.

**Best for:**
- Multi-file refactoring
- Feature development with commits
- Code review

### Continue

IDE autopilot with context awareness.

**Best for:**
- Real-time coding assistance
- Autocomplete and suggestions
- IDE integration

### Goose

Autonomous agent with file system access.

**Best for:**
- Debugging and testing
- File operations
- Command execution

### AutoGPT

Goal decomposition and planning.

**Best for:**
- Complex multi-step projects
- Long-running workflows
- Autonomous planning

### LangChain

Agent framework with memory.

**Best for:**
- RAG applications
- Conversational agents
- Tool integration

---

## Telemetry

Ralph logs all events to JSONL:

```bash
tail -f ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl
```

Sample event:
```json
{
  "event": "iteration_completed",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "iteration": 5,
  "backend": "aider",
  "exit_code": 2,
  "timestamp": "2025-12-30T10:05:00Z"
}
```

---

## Troubleshooting

### Task Never Completes

**Cause**: Completion criteria too strict

**Solution**:
```bash
# Stop the task
curl -X POST http://localhost:8098/tasks/{task_id}/stop

# Review iterations
tail ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl | grep {task_id}
```

### High Resource Usage

**Cause**: Too many concurrent tasks

**Solution**:
```bash
# Set limit
export RALPH_MAX_CONCURRENT_TASKS=5

# Restart Ralph
sudo systemctl restart ai-ralph-wiggum.service
```

### Agent Backend Fails

**Cause**: Backend not responding

**Solution**:
```bash
# Check backend health
curl http://localhost:8093/health

# Restart backend
sudo systemctl restart ai-ralph-wiggum.service
```

---

## Development

### Project Structure

```
ralph-wiggum/
├── Dockerfile                 # Container definition
├── requirements.txt           # Python dependencies
├── server.py                  # FastAPI server
├── loop_engine.py            # Core loop implementation
├── orchestrator.py           # Agent backend orchestration
├── state_manager.py          # State persistence
├── hooks.py                  # Hook system
├── config/
│   └── default.yaml          # Default configuration
└── README.md                 # This file
```

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export RALPH_MCP_SERVER_PORT=8098
export RALPH_POSTGRES_HOST=localhost
# ... etc

# Run server
python server.py
```

### Testing

```bash
# Submit test task
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a hello world script",
    "backend": "aider",
    "max_iterations": 5
  }'

# Monitor logs
journalctl -u ai-ralph-wiggum.service -f
```

---

## Resources

- [Ralph Wiggum Technique](https://paddo.dev/blog/ralph-wiggum-autonomous-loops/)
- [Ralph Orchestrator (GitHub)](https://github.com/mikeyobrien/ralph-orchestrator)
- [Anthropic's Ralph Plugin](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/ralph-wiggum)
- [AI Stack v3.0 Guide](../../../docs/AI-STACK-V3-AGENTIC-ERA-GUIDE.md)

---

## License

MIT License - NixOS Quick Deploy AI Stack

## Contributing

Contributions welcome! Please open an issue or PR.

---

**"I'm helping!"** - Ralph Wiggum (and this MCP server)
