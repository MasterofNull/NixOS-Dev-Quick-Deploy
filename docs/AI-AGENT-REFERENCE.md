# AI Agent Quick Reference - NixOS Hybrid Learning System

**Purpose**: Fast navigation to task-relevant information for remote AI agents
**Goal**: Reduce context overhead by loading only what's needed for current task
**Principle**: Continuous learning with local context augmentation

---

## 🎯 Quick Task Navigation

**Choose your task category below** - only load the documents you need:

### 🚀 Getting Started
- [System Overview](/docs/agent-guides/00-SYSTEM-OVERVIEW.md) - What this system is and does
- [Quick Start](/docs/agent-guides/01-QUICK-START.md) - Get up and running fast
- [Service Status](/docs/agent-guides/02-SERVICE-STATUS.md) - Check what's running

### 🔧 Development Tasks
- [NixOS Configuration](/docs/agent-guides/10-NIXOS-CONFIG.md) - Modify system/home configs
- [Container Management](/docs/agent-guides/11-CONTAINER-MGMT.md) - Podman/Docker operations
- [Debugging & Logs](/docs/agent-guides/12-DEBUGGING.md) - Find and fix issues

### 🤖 AI & LLM Operations
- [Local LLM Usage](/docs/agent-guides/20-LOCAL-LLM-USAGE.md) - Use llama.cpp/Ollama for inference
- [RAG & Context Augmentation](/docs/agent-guides/21-RAG-CONTEXT.md) - Reduce remote API costs
- [Continuous Learning](/docs/agent-guides/22-CONTINUOUS-LEARNING.md) - Store learnings & improve

### 💾 Data & Storage
- [Qdrant Vector DB](/docs/agent-guides/30-QDRANT-OPERATIONS.md) - Search/store embeddings
- [PostgreSQL Database](/docs/agent-guides/31-POSTGRES-OPS.md) - Structured data storage
- [Error Logging](/docs/agent-guides/32-ERROR-LOGGING.md) - Track and learn from failures

### 🔄 Workflows
- [Hybrid Workflow](/docs/agent-guides/40-HYBRID-WORKFLOW.md) - Local + Remote agent coordination
- [Value Scoring](/docs/agent-guides/41-VALUE-SCORING.md) - Identify high-value interactions
- [Pattern Extraction](/docs/agent-guides/42-PATTERN-EXTRACTION.md) - Reusable solutions

---

## 📊 System Architecture (High-Level)

```
Remote Agent (You)
    ↓ Query
    ↓
Local Context Layer (Qdrant + PostgreSQL)
    ↓ Augmented Query (with local context)
    ↓
Local LLM (llama.cpp/Ollama) OR Remote API
    ↓ Response
    ↓
Learning System (stores high-value data)
    ↓
Improved Local Context (for next query)
```

**Key Benefit**: Use local context to reduce your token usage by 30-50%

---

## 🎓 Continuous Learning Principles

**Always follow these principles** when working on tasks:

### 1. **Store Successes**
When a solution works:
```python
# Pseudo-code for what the system does
store_solution({
    "query": "What was the question?",
    "solution": "What worked?",
    "context": "What was relevant?",
    "outcome": "success",
    "value_score": calculate_value(complexity, reusability, novelty)
})
```

### 2. **Store Failures**
When something fails:
```python
store_error({
    "error": "What failed?",
    "attempted_solution": "What was tried?",
    "root_cause": "Why did it fail?",
    "correct_solution": "What actually worked?"
})
```

### 3. **Extract Patterns**
After successful interactions:
- Identify reusable patterns
- Store in `skills-patterns` collection
- Future agents can reference these

### 4. **Check Context First**
Before making remote API calls:
1. Search Qdrant for similar past queries
2. Check error-solutions for known issues
3. Review best-practices for the task type
4. Only use remote API if local context insufficient

---

## 🚀 Common Operations (Quick Reference)

### Check System Status
```bash
./scripts/hybrid-ai-stack.sh status
```

### Query Local LLM
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen-coder", "messages": [{"role": "user", "content": "..."}]}'
```

### Search Vector DB (Python)
```python
from qdrant_client import QdrantClient
client = QdrantClient(url="http://localhost:6333")
results = client.search(
    collection_name="codebase-context",
    query_vector=embedding,
    limit=5
)
```

### Store Learning (Python)
```python
client.upsert(
    collection_name="skills-patterns",
    points=[{
        "id": unique_id,
        "vector": embedding,
        "payload": {
            "pattern": "description",
            "example": "code or solution",
            "value_score": 0.85
        }
    }]
)
```

---

## 📍 Service Endpoints

| Service | Port | Health Check | Purpose |
|---------|------|--------------|---------|
| Qdrant | 6333 | `/healthz` | Vector database |
| Ollama | 11434 | `/api/tags` | Embeddings |
| llama.cpp | 8080 | `/health` | GGUF inference |
| Open WebUI | 3001 | `/` | Chat interface |
| PostgreSQL | 5432 | `pg_isready` | Structured data |
| Redis | 6379 | `PING` | Caching |

---

## 🗂️ Data Collections (Qdrant)

### Collections Available

1. **codebase-context** - Code snippets, function definitions, project structure
2. **skills-patterns** - Reusable solutions, patterns, best practices
3. **error-solutions** - Known errors and their fixes
4. **best-practices** - Curated guidelines for tasks
5. **interaction-history** - All past interactions with outcomes

### When to Use Each Collection

- **Debugging?** → Check `error-solutions` first
- **Implementing feature?** → Search `skills-patterns` and `best-practices`
- **Understanding code?** → Query `codebase-context`
- **Learning from history?** → Review `interaction-history`

---

## 💡 Task-Specific Workflows

### Workflow: Fix a Bug

1. **Search `error-solutions`** for similar error
2. If found → Apply known solution → Store success
3. If not found → Debug → Store new solution when fixed
4. Extract pattern if error type is common

**See**: [Debugging Guide](/docs/agent-guides/12-DEBUGGING.md)

### Workflow: Implement New Feature

1. **Search `skills-patterns`** for similar implementations
2. **Check `best-practices`** for this feature type
3. Implement using local LLM if possible (cheaper)
4. Store successful patterns for future use
5. Calculate value score for learning system

**See**: [Development Workflow](/docs/agent-guides/40-HYBRID-WORKFLOW.md)

### Workflow: NixOS Configuration Change

1. **Search `codebase-context`** for similar config patterns
2. Use local LLM to validate syntax
3. Test in isolation first
4. Store working configuration in Qdrant
5. Document any gotchas in `best-practices`

**See**: [NixOS Configuration Guide](/docs/agent-guides/10-NIXOS-CONFIG.md)

---

## 🎯 Context Reduction Strategies

### Strategy 1: Search Before Asking
```python
# Instead of loading full docs, search for specific info
results = search_qdrant("how to configure gnome-keyring")
if results.score > 0.8:
    use_local_answer(results)
else:
    ask_remote_api()  # Only if local context insufficient
```

### Strategy 2: Incremental Loading
```markdown
# Load only what you need:
1. Read AI-AGENT-REFERENCE.md (this file) - 500 tokens
2. Identify task category
3. Load ONLY that category's guide - 1000-2000 tokens
4. Total: ~2500 tokens vs 20000+ for full docs
```

### Strategy 3: Use Local LLM for Simple Tasks
```bash
# Use llama.cpp for:
- Code explanation
- Syntax checking
- Simple refactoring
- Pattern matching

# Use Remote API for:
- Complex architectural decisions
- Novel problem solving
- Multi-step planning
```

**See**: [RAG & Context Guide](/docs/agent-guides/21-RAG-CONTEXT.md)

---

## 📚 Complete Documentation Index

### Core System Docs
- [UNIFIED-AI-STACK.md](UNIFIED-AI-STACK.md) - Complete architecture
- [DEPLOYMENT-STATUS.md](/docs/archive/DEPLOYMENT-STATUS.md) - Current status
- [HYBRID-AI-SYSTEM-GUIDE.md](HYBRID-AI-SYSTEM-GUIDE.md) - Implementation guide

### Agent-Specific Guides (Focused)
- `docs/agent-guides/00-SYSTEM-OVERVIEW.md` - High-level overview
- `docs/agent-guides/01-QUICK-START.md` - Get started fast
- `docs/agent-guides/02-SERVICE-STATUS.md` - Check services
- `docs/agent-guides/10-NIXOS-CONFIG.md` - NixOS configuration
- `docs/agent-guides/11-CONTAINER-MGMT.md` - Container operations
- `docs/agent-guides/12-DEBUGGING.md` - Debug & logs
- `docs/agent-guides/20-LOCAL-LLM-USAGE.md` - Use local LLMs
- `docs/agent-guides/21-RAG-CONTEXT.md` - RAG & context augmentation
- `docs/agent-guides/22-CONTINUOUS-LEARNING.md` - Learning workflow
- `docs/agent-guides/30-QDRANT-OPERATIONS.md` - Vector DB ops
- `docs/agent-guides/31-POSTGRES-OPS.md` - Database ops
- `docs/agent-guides/32-ERROR-LOGGING.md` - Error tracking
- `docs/agent-guides/40-HYBRID-WORKFLOW.md` - Local+Remote coordination
- `docs/agent-guides/41-VALUE-SCORING.md` - Value calculation
- `docs/agent-guides/42-PATTERN-EXTRACTION.md` - Pattern mining

### MCP Server Catalogs
- [ai-knowledge-base/mcp-servers/](ai-knowledge-base/mcp-servers/) - Available MCP servers by category

---

## 🔑 Key File Locations

```
NixOS-Dev-Quick-Deploy/
├── templates/
│   ├── configuration.nix      # System config (source of truth)
│   └── home.nix               # User config (source of truth)
├── ai-stack/
│   ├── compose/
│   │   └── docker-compose.yml # AI stack definition (single source)
│   ├── dashboard/
│   │   └── index.html         # System monitoring dashboard
│   └── mcp-servers/
│       └── hybrid-coordinator/ # Learning system MCP server
├── scripts/
│   ├── hybrid-ai-stack.sh     # Main AI stack manager
│   └── setup-hybrid-learning-auto.sh  # Automated setup
└── docs/
    └── agent-guides/          # Focused agent documentation
```

---

## ⚡ Emergency Commands

```bash
# System completely broken?
./nixos-quick-deploy.sh --rollback

# AI stack not responding?
./scripts/hybrid-ai-stack.sh restart

# Need to check logs?
./scripts/hybrid-ai-stack.sh logs

# Qdrant down?
podman restart local-ai-qdrant

# Full system status?
./scripts/hybrid-ai-stack.sh status
```

---

## 📊 Dashboard & Monitoring

**Open Dashboard**: `firefox ai-stack/dashboard/index.html`

The dashboard shows:
- ✅ Service health (real-time)
- 📊 Learning metrics (interactions, patterns, value)
- 🔄 Federation status (if multi-node)
- 📚 Quick links to all documentation

**See**: [SYSTEM-DASHBOARD-README.md](SYSTEM-DASHBOARD-README.md)

---

## 🎓 Learning System Flow

```
1. Receive Task
    ↓
2. Search Local Context (Qdrant)
    ↓
3. Augment Query with Relevant Context
    ↓
4. Execute with Local LLM (if simple) OR Remote API (if complex)
    ↓
5. Store Outcome + Context
    ↓
6. Calculate Value Score
    ↓
7. If High Value → Extract Pattern → Store for Reuse
    ↓
8. Next Task Benefits from This Learning
```

---

## 💬 Usage Examples

### Example 1: Fix GNOME Keyring Error
```python
# 1. Search for similar errors
results = search_qdrant("gnome keyring error OS keyring")

# 2. If found (score > 0.8), use that solution
if results[0].score > 0.8:
    apply_solution(results[0].payload["solution"])
else:
    # 3. Debug and find solution
    solution = debug_and_fix()
    # 4. Store for future
    store_solution("gnome-keyring-fix", solution, value_score=0.9)
```

### Example 2: NixOS Config Change
```python
# 1. Check best practices
practices = search_qdrant("nixos configuration best practices")

# 2. Search for similar configs
examples = search_qdrant("enable systemd service nixos")

# 3. Use local LLM to generate config
config = local_llm_generate(prompt=f"Based on {examples}, generate...")

# 4. Test and store
test_config(config)
store_pattern("systemd-service-pattern", config)
```

---

## 🚦 Decision Tree: When to Use What

```
Task Received
    │
    ├─ Simple/Repetitive? → Use Local LLM (llama.cpp)
    │
    ├─ Seen Before? → Search Qdrant → Apply Stored Solution
    │
    ├─ Error/Bug? → Check error-solutions → Apply Known Fix
    │
    ├─ New Implementation? → Search patterns → Use Best Practices
    │
    └─ Complex/Novel? → Use Remote API → Store Result for Learning
```

---

## 📖 Next Steps

1. **New to the system?** → Read [System Overview](/docs/agent-guides/00-SYSTEM-OVERVIEW.md)
2. **Ready to code?** → Read [Quick Start](/docs/agent-guides/01-QUICK-START.md)
3. **Specific task?** → Jump to relevant guide above
4. **Want full details?** → See [UNIFIED-AI-STACK.md](UNIFIED-AI-STACK.md)

---

**Remember**: The goal is to load **only what you need** for your current task, not everything at once. Use this reference to navigate to the specific information required.

**Last Updated**: 2025-12-20
