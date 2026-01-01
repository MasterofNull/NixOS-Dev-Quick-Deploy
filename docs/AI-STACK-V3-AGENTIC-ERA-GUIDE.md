# AI Stack v3.0 - Agentic Era Edition

**Complete Guide to December 2025 AI Coding Tools & Workflows**

Version: 3.0.0
Updated: December 30, 2025
Status: Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [What's New in v3.0](#whats-new-in-v30)
3. [Architecture](#architecture)
4. [Services Reference](#services-reference)
5. [Ralph Wiggum Loop](#ralph-wiggum-loop)
6. [Agent Backends](#agent-backends)
7. [Getting Started](#getting-started)
8. [Configuration](#configuration)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)
11. [API Reference](#api-reference)

---

## Overview

The NixOS AI Stack v3.0 represents the state-of-the-art in autonomous coding infrastructure as of December 2025. Built on the principles of the **Agentic Era**, this stack provides:

- **Continuous Autonomous Coding**: Ralph Wiggum loop for 24/7 development
- **Multi-Backend Agent Support**: Aider, Continue, Goose, AutoGPT, LangChain
- **Model Context Protocol (MCP)**: Industry-standard AI tool integration
- **Vibe Coding**: Optimized developer state with minimal context switching
- **Local-First AI**: Privacy-preserving local inference with selective cloud usage

### Key Statistics

- **15+ Docker Services**: Complete AI development environment
- **6 Agent Backends**: Choose the right tool for each task
- **100% Local Capable**: No cloud required (optional for enhanced features)
- **MCP Native**: Full Model Context Protocol support

---

## What's New in v3.0

### December 2025 Additions

#### 🎯 Ralph Wiggum Loop (Default for All Agents)

The Ralph Wiggum technique enables continuous autonomous coding:

- **While-true iteration** until task completion
- **Exit code blocking** to prevent premature stopping
- **Context recovery** from git and state files
- **Human-in-the-loop** approval gates

Real-world results:
- 6 repos shipped overnight
- $50k contracts for $297 in API costs
- Autonomous iteration while you sleep

#### 🤖 Agentic Coding Tools

Latest December 2025 video coding tools:

**Aider**
- AI pair programming with git integration
- Automatic commits with meaningful messages
- Multi-file refactoring awareness

**Continue**
- Open-source autopilot (20K+ GitHub stars)
- IDE integration for VS Code and JetBrains
- Context-aware code completion

**Goose**
- File system access and execution
- Autonomous debugging capabilities
- Open-source and enterprise-extensible

**AutoGPT**
- Goal decomposition and planning
- Multi-step task execution
- Memory and state persistence

**LangChain**
- Agent framework with RAG
- Memory management and tracing
- Tool integration ecosystem

#### 🎨 Video Coding & Content Generation

- **LangChain agents**: Memory and state management
- **AutoGPT workflows**: Autonomous goal planning
- **MCP integration**: Seamless tool access

#### 📊 Enhanced Telemetry

- Ralph loop performance metrics
- Agent backend statistics
- Token usage optimization tracking
- Iteration success rates

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Ralph Wiggum Loop                         │
│                  (Continuous Orchestration)                      │
└────────────────┬───────────────────────────────────┬────────────┘
                 │                                   │
         ┌───────▼──────┐                    ┌───────▼──────┐
         │    Agents     │                    │     MCP      │
         │              │                    │   Servers    │
         │ • Aider      │◄──────────────────►│ • AIDB       │
         │ • Continue   │                    │ • Hybrid     │
         │ • Goose      │                    │   Coord      │
         │ • AutoGPT    │                    │ • Ralph      │
         │ • LangChain  │                    └──────┬───────┘
         └──────┬───────┘                           │
                │                                   │
         ┌──────▼───────────────────────────────────▼──────┐
         │           Core Infrastructure                    │
         │                                                  │
         │  ┌─────────┐  ┌──────────┐  ┌────────┐         │
         │  │ Qdrant  │  │PostgreSQL│  │ Redis  │         │
         │  │ Vectors │  │ + pgvector│  │ Cache │         │
         │  └─────────┘  └──────────┘  └────────┘         │
         │                                                  │
         │  ┌─────────┐  ┌──────────┐  ┌────────┐         │
         │  │llama.cpp│  │ MindsDB  │  │OpenWebUI│        │
         │  │   LLM   │  │Analytics │  │   UI   │         │
         │  └─────────┘  └──────────┘  └────────┘         │
         └──────────────────────────────────────────────────┘
```

### Service Breakdown

| Service | Port | Purpose | Resources |
|---------|------|---------|-----------|
| **llama.cpp** | 8080 | Local LLM inference (Qwen2.5-Coder 7B) | 4-16GB RAM |
| **Qdrant** | 6333/6334 | Vector database for embeddings | 1-4GB RAM |
| **PostgreSQL 18** | 5432 | Database + pgvector | 512MB-4GB |
| **Redis** | 6379 | Caching and sessions | 256MB-1GB |
| **Open WebUI** | 3001 | ChatGPT-like interface | 512MB-2GB |
| **MindsDB** | 47334/47335 | Analytics and integration | 1-4GB |
| **AIDB** | 8091 | Context API + telemetry | 1-4GB |
| **Hybrid Coordinator** | 8092 | Query routing + learning | 512MB-2GB |
| **Ralph Wiggum** | 8098 | Loop orchestrator | 1-8GB |
| **Aider** | 8093 | AI pair programming | 512MB-2GB |
| **Continue** | 8094 | IDE autopilot | 512MB-2GB |
| **Goose** | 8095 | Autonomous agent | 512MB-2GB |
| **AutoGPT** | 8097 | Goal planning | 1-4GB |
| **LangChain** | 8096 | Agent framework | 1-4GB |

**Total Resource Requirements:**
- CPU: 8+ cores recommended
- RAM: 16GB minimum, 32GB recommended
- Disk: 50GB+ for models and data
- GPU: Optional (CPU inference supported)

---

## Services Reference

### Core AI Infrastructure

#### llama.cpp (Local LLM)

**Model**: Qwen2.5-Coder-7B-Instruct (Q4_K_M quantization)

Provides OpenAI-compatible API for local inference:

```bash
# Test the LLM
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "temperature": 0.7
  }'
```

**Features:**
- OpenAI API compatible
- 4096 token context window
- CPU inference (no GPU required)
- Model hot-swapping support

#### Qdrant (Vector Database)

Stores embeddings for RAG and context:

```bash
# Check collections
curl http://localhost:6333/collections
```

**Collections:**
- `codebase-context`: Code embeddings (384-dim)
- `skills-patterns`: Pattern recognition
- `error-solutions`: Error recovery knowledge
- `best-practices`: Domain expertise
- `interaction-history`: Conversation context

#### PostgreSQL 18 + pgvector

Primary database with vector support:

```sql
-- Connect
psql -h localhost -U mcp -d mcp

-- Check tables
\dt
```

**Schema:**
- `tool_registry`: MCP tool manifests
- `documents`: Imported documentation
- `embeddings`: Vector embeddings
- `workflows`: Codemachine workflows
- `skills`: Agent skills
- `ralph_tasks`: Ralph loop task history

---

## Ralph Wiggum Loop

### The Default Agent Behavior

All agents in the stack now operate under the Ralph Wiggum loop by default:

```python
while True:
    result = execute_agent(task)

    if result.exit_code == 2:  # Blocked!
        # I'm helping!
        re_inject_prompt()
        continue

    if is_complete(result):
        break

    learn_from_iteration(result)
    save_checkpoint()
```

### Philosophy

Named after Ralph Wiggum from The Simpsons, embodying:

- **Persistence**: Keep trying despite setbacks
- **Simplicity**: Just a bash while-true loop
- **Determinism**: Predictable failure and recovery
- **Context**: Git and state for persistence

### How to Use Ralph

#### Submit a Task

```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Implement user authentication with JWT",
    "backend": "aider",
    "max_iterations": 0
  }'
```

#### Monitor Progress

```bash
# Get task status
curl http://localhost:8098/tasks/{task_id}

# View live telemetry
tail -f ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl

# Statistics
curl http://localhost:8098/stats
```

#### Stop When Needed

```bash
curl -X POST http://localhost:8098/tasks/{task_id}/stop
```

### Ralph Configuration

Environment variables:

```bash
# Core settings
RALPH_LOOP_ENABLED=true
RALPH_EXIT_CODE_BLOCK=2
RALPH_MAX_ITERATIONS=0  # 0 = infinite

# Context recovery
RALPH_CONTEXT_RECOVERY=true
RALPH_GIT_INTEGRATION=true

# Human-in-the-loop
RALPH_REQUIRE_APPROVAL=false
RALPH_APPROVAL_THRESHOLD=high

# Backends
RALPH_AGENT_BACKENDS=aider,continue,goose,autogpt,langchain
RALPH_DEFAULT_BACKEND=aider
```

---

## Agent Backends

### When to Use Each Backend

#### Aider: Git-Aware Pair Programming

**Best for:**
- Multi-file refactoring
- Feature development with commits
- Code review and improvements

**Example:**
```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Refactor authentication module to use dependency injection",
    "backend": "aider"
  }'
```

#### Continue: IDE-Style Autocomplete

**Best for:**
- Context-aware completions
- Real-time coding assistance
- IDE integration workflows

#### Goose: Autonomous Debugging

**Best for:**
- File system operations
- Debugging and testing
- Command execution

**Example:**
```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Debug the failing tests in test_auth.py and fix the issues",
    "backend": "goose"
  }'
```

#### AutoGPT: Complex Planning

**Best for:**
- Multi-step projects
- Goal decomposition
- Long-running workflows

**Example:**
```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Build a complete REST API for a blog with authentication, posts, comments, and tags",
    "backend": "autogpt",
    "max_iterations": 50
  }'
```

#### LangChain: Memory-Intensive Tasks

**Best for:**
- RAG applications
- Conversational agents
- Tool integration

---

## Getting Started

### Quick Start

1. **Start the Stack**

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy
./scripts/hybrid-ai-stack.sh up
```

2. **Verify Services**

```bash
# Check all services
./scripts/test-ai-stack-health.sh

# Or manually
curl http://localhost:8098/health  # Ralph
curl http://localhost:8091/health  # AIDB
curl http://localhost:8092/health  # Hybrid Coordinator
curl http://localhost:8080/health  # llama.cpp
```

3. **Submit Your First Ralph Task**

```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a hello world FastAPI application with a health endpoint",
    "backend": "aider",
    "max_iterations": 10
  }'
```

4. **Access the Web UI**

Open http://localhost:3001 for the Open WebUI interface.

### First-Time Setup

The stack will automatically:
- Initialize databases
- Create vector collections
- Load the default LLM model
- Configure MCP servers
- Set up Ralph loop

**Initial startup takes 5-10 minutes** for model downloads.

---

## Configuration

### Environment Variables

Create `.env` file in `ai-stack/compose/`:

```bash
# Core settings
AI_STACK_DATA=~/.local/share/nixos-ai-stack
POSTGRES_PASSWORD=your_secure_password_here

# LLM settings
LLAMA_CPP_MODEL_FILE=qwen2.5-coder-7b-instruct-q4_k_m.gguf
LLAMA_CPP_DEFAULT_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct

# Ralph Wiggum
RALPH_LOOP_ENABLED=true
RALPH_DEFAULT_BACKEND=aider
RALPH_MAX_ITERATIONS=0

# Hybrid learning
LOCAL_CONFIDENCE_THRESHOLD=0.7
HIGH_VALUE_THRESHOLD=0.7
PATTERN_EXTRACTION_ENABLED=true

# Optional: External APIs
HUGGING_FACE_HUB_TOKEN=your_token
GOOGLE_SEARCH_API_KEY=your_key
GOOGLE_SEARCH_CX=your_cx
LANGCHAIN_API_KEY=your_key
```

### Model Configuration

Swap LLM models:

```bash
# Download new model
cd ~/.local/share/nixos-ai-stack/llama-cpp-models
wget https://huggingface.co/.../model.gguf

# Update environment
export LLAMA_CPP_MODEL_FILE=model.gguf

# Restart stack
./scripts/hybrid-ai-stack.sh restart
```

Supported models:
- Qwen2.5-Coder (7B, 14B, 32B)
- DeepSeek-Coder (6.7B, 33B)
- CodeLlama (7B, 13B, 34B)
- Phi-3 (3.8B)

---

## Best Practices

### 1. Use Ralph for Overnight Development

Submit complex tasks before bed:

```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Implement the entire user management system with CRUD operations, validation, and tests",
    "backend": "aider",
    "max_iterations": 0
  }'
```

Wake up to completed features!

### 2. Choose the Right Backend

- **Quick fixes**: Aider
- **Planning**: AutoGPT
- **Debugging**: Goose
- **RAG apps**: LangChain
- **IDE integration**: Continue

### 3. Monitor Resource Usage

```bash
# Check resource usage
docker stats

# View Ralph statistics
curl http://localhost:8098/stats
```

### 4. Use Human Approval for Production

```bash
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Deploy to production",
    "require_approval": true,
    "approval_threshold": "high"
  }'
```

### 5. Leverage Context Recovery

Ralph automatically saves checkpoints via git:

```bash
# View Ralph checkpoints
cd /workspace
git log --grep="ralph-wiggum-checkpoint"
```

---

## Troubleshooting

### Ralph Loop Stuck

**Symptom**: Task iterates without completing

**Solution**:
```bash
# Check status
curl http://localhost:8098/tasks/{task_id}

# Review recent iterations
tail ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl

# Stop if needed
curl -X POST http://localhost:8098/tasks/{task_id}/stop
```

### Agent Backend Unresponsive

**Symptom**: 503 errors from Ralph

**Solution**:
```bash
# Check backend health
curl http://localhost:8093/health  # Aider
curl http://localhost:8094/health  # Continue
curl http://localhost:8095/health  # Goose

# Restart specific service
podman restart local-ai-aider
```

### High Memory Usage

**Symptom**: System slowing down

**Solution**:
```bash
# Check resource limits
docker stats

# Reduce concurrent tasks
export RALPH_MAX_CONCURRENT_TASKS=5

# Use smaller model
export LLAMA_CPP_MODEL_FILE=qwen2.5-coder-1.5b-q4_k_m.gguf
```

### LLM Inference Slow

**Symptom**: Slow response times

**Solutions**:
- Use quantized models (Q4_K_M)
- Reduce context window
- Enable GPU if available
- Increase CPU allocation

---

## API Reference

See individual service documentation:

- [Ralph Wiggum API](../ai-stack/agents/skills/ralph-wiggum.md)
- [AIDB API](../ai-stack/mcp-servers/aidb/README.md)
- [Hybrid Coordinator API](../ai-stack/mcp-servers/hybrid-coordinator/README.md)

---

## Resources

### December 2025 AI Coding Tools

- [MIT Tech Review: Rise of AI Coding](https://www.technologyreview.com/2025/12/15/1128352/rise-of-ai-coding-developers-2026/)
- [Vibe Coding Guide 2025](https://plausiblefutures.substack.com/p/vibe-coding-in-2025-a-technical-guide)
- [AI Engineering Trends: MCP and Agents](https://thenewstack.io/ai-engineering-trends-in-2025-agents-mcp-and-vibe-coding/)

### Ralph Wiggum Technique

- [Ralph Wiggum: Autonomous Loops](https://paddo.dev/blog/ralph-wiggum-autonomous-loops/)
- [Ralph Orchestrator (GitHub)](https://github.com/mikeyobrien/ralph-orchestrator)
- [Anthropic's Ralph Plugin](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/ralph-wiggum)
- [Boundary ML: Ralph Under the Hood](https://boundaryml.com/podcast/2025-10-28-ralph-wiggum-coding-agent-power-tools)

### Agentic AI Tools

- [Top 5 Agentic AI Tools for Developers](https://www.qodo.ai/blog/agentic-ai-tools/)
- [Best AI Coding Assistants 2025](https://www.shakudo.io/blog/best-ai-coding-assistants)
- [10 Things Developers Want from Agentic IDEs](https://redmonk.com/kholterhoff/2025/12/22/10-things-developers-want-from-their-agentic-ides-in-2025/)

---

## License

MIT License - NixOS Quick Deploy AI Stack

## Support

- GitHub Issues: [NixOS-Dev-Quick-Deploy](https://github.com/hyperd/NixOS-Dev-Quick-Deploy)
- Documentation: `/docs/`
- Community: Join our Discord

---

**Welcome to the Agentic Era of Software Development!** 🚀
