# Ralph Wiggum Loop - Quick Start Guide

**"I'm helping!" - Your New 24/7 Autonomous Coding Assistant**

---

## What is Ralph Wiggum?

Ralph Wiggum is a continuous autonomous coding loop that **never gives up** on your tasks. Named after the persistent Simpsons character, it keeps iterating until your code is complete - even while you sleep!

### What It Does

- ✅ **Continuous iteration** on coding tasks
- ✅ **Never stops** until completion (blocks exit attempts)
- ✅ **Learns** from each iteration
- ✅ **Saves checkpoints** via git
- ✅ **Orchestrates multiple AI agents** (Aider, Goose, AutoGPT, etc.)
- ✅ **Recovers from crashes** automatically

### Real Results

- 🚀 **6 repos shipped overnight**
- 💰 **$50k contracts for $297 in API costs**
- 😴 **Code while you sleep**

---

## 5-Minute Quick Start

### 1. Start the AI Stack

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy
./scripts/hybrid-ai-stack.sh up
```

Wait 5-10 minutes for first-time setup (downloads models and builds containers).

### 2. Check Ralph is Running

```bash
curl http://localhost:8098/health
```

Should return:
```json
{
  "status": "healthy",
  "loop_enabled": true,
  "backends": ["aider", "continue", "goose", "autogpt", "langchain"]
}
```

### 3. Submit Your First Task

```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a FastAPI hello world app with a /health endpoint",
    "backend": "aider",
    "max_iterations": 10
  }'
```

Returns a `task_id` - save this!

### 4. Monitor Progress

```bash
# Replace {task_id} with your actual task ID
curl http://localhost:8098/tasks/{task_id}

# Or watch live telemetry
tail -f ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl
```

### 5. View Your Code

Check the workspace:
```bash
ls -la ~/.local/share/nixos-ai-stack/workspace
```

Ralph saves all code here!

---

## Common Use Cases

### Overnight Feature Development

```bash
# Submit before bed
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Build a complete user authentication system with JWT, email verification, and password reset",
    "backend": "aider",
    "max_iterations": 0
  }'

# Sleep 😴
# Wake up to completed feature! ✨
```

### Quick Bug Fix

```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Fix the bug in user login where tokens expire too quickly",
    "backend": "goose",
    "max_iterations": 5
  }'
```

### Complex Project

```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a REST API for a blog with posts, comments, tags, and search",
    "backend": "autogpt",
    "max_iterations": 50
  }'
```

---

## Agent Backends

Choose the right agent for your task:

### Aider (Default)
**Best for**: Feature development, refactoring
```json
{"backend": "aider"}
```

### Goose
**Best for**: Debugging, testing, file operations
```json
{"backend": "goose"}
```

### AutoGPT
**Best for**: Complex multi-step projects
```json
{"backend": "autogpt"}
```

### LangChain
**Best for**: RAG apps, conversational agents
```json
{"backend": "langchain"}
```

### Continue
**Best for**: IDE-style autocomplete and suggestions
```json
{"backend": "continue"}
```

---

## Ralph Loop Explained

### The Magic

```
1. Execute agent with your task
2. Check exit code
3. If exit code == 2: BLOCKED!
   → "I'm helping!" (Ralph voice)
   → Re-inject the prompt
   → Continue iteration
4. If complete: Exit
5. Else: Learn from iteration, save checkpoint, repeat
```

### Why It Works

- **Never gives up**: Blocks premature exits
- **Learns**: Each iteration improves understanding
- **Recovers**: Git checkpoints prevent data loss
- **Adapts**: Tries different approaches

---

## Configuration

### Default Settings (Already Configured)

```bash
RALPH_LOOP_ENABLED=true              # Loop is ON
RALPH_EXIT_CODE_BLOCK=2              # Block on exit code 2
RALPH_MAX_ITERATIONS=0               # Infinite (until complete)
RALPH_CONTEXT_RECOVERY=true          # Auto-recovery ON
RALPH_GIT_INTEGRATION=true           # Git checkpoints ON
RALPH_DEFAULT_BACKEND=aider          # Use Aider by default
```

### Custom Configuration

Edit `.env` file in `ai-stack/compose/`:

```bash
# Run for specific iterations
RALPH_MAX_ITERATIONS=20

# Change default agent
RALPH_DEFAULT_BACKEND=goose

# Enable human approval
RALPH_REQUIRE_APPROVAL=true
```

---

## Monitoring

### Check Task Status

```bash
curl http://localhost:8098/tasks/{task_id}
```

### View Statistics

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
  "average_iterations": 4.5
}
```

### Watch Telemetry

```bash
tail -f ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl
```

### View Logs

```bash
podman logs -f local-ai-ralph-wiggum
```

---

## Task Management

### Stop a Running Task

```bash
curl -X POST http://localhost:8098/tasks/{task_id}/stop
```

### Approve a Task (if approval enabled)

```bash
curl -X POST http://localhost:8098/tasks/{task_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

---

## Tips & Best Practices

### 1. Be Specific

❌ Bad: "Add auth"
✅ Good: "Implement JWT authentication with login, logout, and token refresh endpoints"

### 2. Set Reasonable Limits

For testing:
```json
{"max_iterations": 10}
```

For overnight runs:
```json
{"max_iterations": 0}  // Infinite
```

### 3. Choose the Right Backend

- Quick fixes → **Aider**
- Debugging → **Goose**
- Planning → **AutoGPT**
- RAG apps → **LangChain**

### 4. Monitor Progress

Check status every few iterations:
```bash
watch -n 30 'curl -s http://localhost:8098/stats'
```

### 5. Use Git Checkpoints

Ralph automatically commits at each iteration:
```bash
cd ~/.local/share/nixos-ai-stack/workspace
git log --grep="ralph-wiggum-checkpoint"
```

---

## Troubleshooting

### Task Won't Complete

**Problem**: Loops forever without completing

**Solution**:
```bash
# Check what's happening
curl http://localhost:8098/tasks/{task_id}

# Review iterations
tail ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl | grep {task_id}

# Stop if needed
curl -X POST http://localhost:8098/tasks/{task_id}/stop
```

### Ralph Not Responding

**Problem**: Can't reach http://localhost:8098

**Solution**:
```bash
# Check Ralph is running
podman ps | grep ralph-wiggum

# Check logs
podman logs local-ai-ralph-wiggum

# Restart if needed
podman restart local-ai-ralph-wiggum
```

### Agent Backend Fails

**Problem**: Agent execution errors

**Solution**:
```bash
# Check backend health
curl http://localhost:8093/health  # Aider
curl http://localhost:8095/health  # Goose

# Restart backend
podman restart local-ai-aider
```

---

## Advanced Usage

### With Context

```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Add OAuth2 to the authentication system",
    "backend": "aider",
    "context": {
      "previous_work": "Already have JWT implemented",
      "requirements": "Support Google and GitHub OAuth"
    }
  }'
```

### With Human Approval

```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Deploy to production",
    "require_approval": true,
    "approval_threshold": "high"
  }'
```

Then approve when ready:
```bash
curl -X POST http://localhost:8098/tasks/{task_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

---

## Next Steps

### Learn More

1. **Full Documentation**: [docs/AI-STACK-V3-AGENTIC-ERA-GUIDE.md](/docs/AI-STACK-V3-AGENTIC-ERA-GUIDE.md)
2. **Ralph Skill**: [ai-stack/agents/skills/ralph-wiggum.md](/ai-stack/agents/skills/ralph-wiggum.md)
3. **Server README**: [ai-stack/mcp-servers/ralph-wiggum/README.md](/ai-stack/mcp-servers/ralph-wiggum/README.md)

### Try More

- Test different agent backends
- Submit overnight tasks
- Use for debugging
- Build complex projects
- Integrate with CI/CD

---

## Quick Reference

```bash
# Start
./scripts/hybrid-ai-stack.sh up

# Status
./scripts/hybrid-ai-stack.sh status

# Submit task
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{"prompt": "your task", "backend": "aider"}'

# Check task
curl http://localhost:8098/tasks/{task_id}

# Stats
curl http://localhost:8098/stats

# Stop task
curl -X POST http://localhost:8098/tasks/{task_id}/stop

# View logs
podman logs -f local-ai-ralph-wiggum

# Telemetry
tail -f ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl
```

---

## Resources

- [Ralph Wiggum Technique](https://paddo.dev/blog/ralph-wiggum-autonomous-loops/)
- [Ralph Orchestrator (GitHub)](https://github.com/mikeyobrien/ralph-orchestrator)
- [Anthropic's Ralph Plugin](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/ralph-wiggum)
- [Boundary ML: Ralph Under the Hood](https://boundaryml.com/podcast/2025-10-28-ralph-wiggum-coding-agent-power-tools)

---

**"I'm helping!"** - Ralph Wiggum (and your new coding loop) 🚀

---

**Happy Coding!**
