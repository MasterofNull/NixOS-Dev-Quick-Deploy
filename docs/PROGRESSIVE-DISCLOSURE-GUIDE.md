# Progressive Disclosure System for AI Agents
**Version**: 1.0.0
**Date**: 2025-12-22
**System**: NixOS Hybrid AI Learning Stack v2.1.0

---

## Table of Contents
1. [Overview](#overview)
2. [Disclosure Levels](#disclosure-levels)
3. [Agent Entry Points](#agent-entry-points)
4. [Capability Categories](#capability-categories)
5. [Workflow Examples](#workflow-examples)
6. [Continuous Improvement Integration](#continuous-improvement-integration)

---

## Overview

The progressive disclosure system allows AI agents (both local and remote) to **discover capabilities gradually**, minimizing token usage and cognitive load while providing pathways to advanced features.

### Design Principles

1. **Start Minimal** - Basic info without authentication
2. **Expand on Demand** - More detail as needed
3. **Learn Continuously** - Track what agents use and improve routing
4. **Save Tokens** - 90% reduction in discovery overhead

### Token Savings

| Disclosure Level | Tokens | Auth Required | Use Case |
|-----------------|--------|---------------|----------|
| **Basic** | ~50 | No | "What can this system do?" |
| **Standard** | ~200 | No | "Show me available tools" |
| **Detailed** | ~2000 | Yes | "Give me full schemas" |
| **Advanced** | ~3000 | Yes | "Show federation, ML models" |

**Savings**: Start with 50 tokens instead of 3000 tokens (98% reduction)

---

## Disclosure Levels

### Level 0: Basic (No Auth)

**Purpose**: Quick system identification and health check

**Endpoints**:
```bash
GET http://localhost:8091/discovery
GET http://localhost:8091/discovery/info
GET http://localhost:8091/health
```

**Response Example**:
```json
{
  "system": "NixOS Hybrid AI Learning Stack",
  "version": "2.1.0",
  "progressive_disclosure": true,
  "contact_points": {
    "aidb_mcp": "http://localhost:8091",
    "hybrid_coordinator": "http://localhost:8092",
    "vector_db": "http://localhost:6333",
    "local_llm": "http://localhost:8080"
  },
  "next_steps": {
    "list_capabilities": "GET /discovery/capabilities?level=standard",
    "get_started": "GET /discovery/quickstart"
  }
}
```

**Token Cost**: ~50 tokens

---

### Level 1: Standard (No Auth)

**Purpose**: Discover available capabilities without schemas

**Endpoints**:
```bash
GET http://localhost:8091/discovery/capabilities?level=standard
GET http://localhost:8091/discovery/capabilities?level=standard&category=knowledge
GET http://localhost:8091/discovery/quickstart
```

**Response Example**:
```json
{
  "level": "standard",
  "count": 18,
  "capabilities": [
    {
      "name": "search_documents",
      "category": "knowledge",
      "description": "Semantic search across knowledge base using vector embeddings",
      "cost_estimate": "low",
      "requires_auth": false
    },
    {
      "name": "local_llm_query",
      "category": "inference",
      "description": "Query local LLM (Qwen 2.5 Coder 7B) via llama.cpp",
      "cost_estimate": "free",
      "requires_auth": false
    }
  ],
  "next_steps": {
    "get_details": "GET /discovery/capabilities/{name}",
    "upgrade_level": "Use detailed level with API key"
  }
}
```

**Token Cost**: ~200 tokens
**Use When**: Agent needs to know what's available

---

### Level 2: Detailed (Requires Auth)

**Purpose**: Get full schemas, parameters, examples

**Endpoints**:
```bash
# Requires X-API-Key header
GET http://localhost:8091/discovery/capabilities?level=detailed
GET http://localhost:8091/discovery/capabilities/search_documents
```

**Authentication**:
```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8091/discovery/capabilities?level=detailed
```

**Response Example**:
```json
{
  "name": "search_documents",
  "category": "knowledge",
  "description": "Semantic search across knowledge base...",
  "endpoint": "GET /documents",
  "parameters": {
    "search": {"type": "string", "required": true},
    "project": {"type": "string", "required": false},
    "limit": {"type": "integer", "default": 5}
  },
  "response_schema": {
    "results": "array",
    "count": "integer"
  },
  "examples": [
    {
      "request": "GET /documents?search=NixOS+error&limit=3",
      "response": {"results": [...], "count": 3}
    }
  ],
  "cost_estimate": "low (~100 tokens)",
  "documentation_url": "/docs/agent-guides/21-RAG-CONTEXT.md"
}
```

**Token Cost**: ~2000 tokens
**Use When**: Agent ready to execute capabilities

---

### Level 3: Advanced (Requires Auth)

**Purpose**: Federation, custom skills, ML models

**Endpoints**:
```bash
GET http://localhost:8091/discovery/capabilities?level=advanced
GET http://localhost:8091/federated-servers
GET http://localhost:8091/ml-models
GET http://localhost:8091/skills/discover
```

**Response Example**:
```json
{
  "level": "advanced",
  "federation": {
    "available": true,
    "endpoint": "GET /federated-servers",
    "description": "Discover and connect to other MCP servers"
  },
  "ml_models": {
    "available": true,
    "models": [
      "all-MiniLM-L6-v2 (embeddings)",
      "qwen2.5-coder-7b-instruct (completion)"
    ]
  },
  "skill_discovery": {
    "available": true,
    "remote_repos": ["numman-ali/openskills"]
  }
}
```

**Token Cost**: ~3000 tokens
**Use When**: Agent needs advanced features, federation, custom skills

---

## Agent Entry Points

### For Remote Models (Claude, GPT-4, etc.)

**Start Here**:
```bash
# 1. Quick health check
curl http://localhost:8091/health

# 2. System info
curl http://localhost:8091/discovery/info

# 3. Discover capabilities
curl http://localhost:8091/discovery/capabilities?level=standard

# 4. Get quickstart guide
curl http://localhost:8091/discovery/quickstart
```

**Recommended Flow**:
```
1. GET /discovery/info          (50 tokens)
2. GET /discovery/quickstart    (150 tokens)
3. GET /discovery/capabilities  (200 tokens)
   ↓
   Agent decides what to use
   ↓
4. GET /discovery/capabilities/{name}  (500 tokens per capability)
5. Execute actual capability
```

**Total Token Cost**: ~400-900 tokens (vs 3000+ tokens without progressive disclosure)

---

### For Local Models (llama.cpp, Ollama, etc.)

**Route Through Hybrid Coordinator**:
```bash
# Smart routing - automatically chooses local vs remote
curl -X POST http://localhost:8092/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I configure NixOS?",
    "context": {"user_id": "agent_001"}
  }'
```

**Hybrid Coordinator Decision Tree**:
```
Query arrives
  ↓
Search Qdrant for context (vector similarity)
  ↓
Relevance score ≥ 0.85 + simple query
  → Local LLM (free, fast)
  ↓
Relevance score < 0.85 or complex query
  → Remote API (better quality)
  ↓
Store outcome for learning
```

**Benefits for Local Models**:
- Free inference (no API costs)
- Fast responses (~1-3s)
- Privacy (data stays local)
- Learning (improves over time)

---

## Capability Categories

### 1. Knowledge (RAG & Search)

**Capabilities**:
- `search_documents` - Semantic search across 5 collections
- `get_context` - Retrieve relevant context for query
- `import_documents` - Add documents to knowledge base

**Use When**: Agent needs to find information, learn from past solutions

**Example**:
```bash
curl 'http://localhost:8091/documents?search=GNOME+keyring+error&limit=3'
```

---

### 2. Inference (LLM & Embeddings)

**Capabilities**:
- `local_llm_query` - Query Qwen 2.5 Coder 7B (free)
- `generate_embeddings` - 384-dim vectors via SentenceTransformer (free)
- `hybrid_query` - Smart routing (local/remote)

**Use When**: Agent needs to generate text, get embeddings, make predictions

**Example**:
```bash
# Local LLM (free)
curl -X POST http://localhost:8080/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt": "def fibonacci(n):", "max_tokens": 100}'

# Embeddings (free)
curl -X POST http://localhost:8091/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "NixOS configuration example"}'
```

---

### 3. Storage (Databases)

**Capabilities**:
- `vector_store` - Store embeddings in Qdrant
- `sql_query` - Execute SQL on PostgreSQL + pgvector

**Use When**: Agent needs to persist data, store vectors

**Example**:
```python
from qdrant_client import QdrantClient
client = QdrantClient(url="http://localhost:6333")

# Store vector
client.upsert(
    collection_name="error-solutions",
    points=[{
        "id": "uuid-here",
        "vector": embedding,
        "payload": {"error": "...", "solution": "..."}
    }]
)
```

---

### 4. Learning (Continuous Improvement)

**Capabilities**:
- `record_interaction` - Store query-response pairs
- `extract_patterns` - Identify high-value interactions (score ≥ 0.7)
- `value_scoring` - 5-factor algorithm

**Use When**: Agent wants to improve over time, learn from experience

**Value Scoring Formula**:
```
score = (complexity × 0.2) +
        (reusability × 0.3) +
        (novelty × 0.2) +
        (confirmation × 0.15) +
        (impact × 0.15)

High-value (≥ 0.7) → Extracted as pattern
Low-value (< 0.5) → Not stored
```

**Example**:
```bash
curl -X POST http://localhost:8091/interactions/record \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to fix GNOME keyring?",
    "response": "Enable services.gnome.gcr-ssh-agent.enable = true and keep gnome-keyring for secrets",
    "metadata": {
      "complexity": 0.8,
      "reusability": 0.9,
      "confirmed": true
    }
  }'
```

---

### 5. Integration (Skills & MCP)

**Capabilities**:
- `list_skills` - 29 available skills
- `execute_skill` - Run specific skill
- `discover_remote_skills` - Import from GitHub

**Use When**: Agent needs pre-built workflows, specialized tools

**Example**:
```bash
# List skills
curl http://localhost:8091/skills

# Execute skill
curl -X POST http://localhost:8091/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "code_review",
    "parameters": {"file_path": "/path/to/code.py"}
  }'
```

---

### 6. Monitoring (Health & Metrics)

**Capabilities**:
- `health_check` - All services status
- `get_metrics` - Token savings, local query %
- `telemetry` - Query event history

**Use When**: Agent needs to monitor system, track performance

**Example**:
```bash
# System health
curl http://localhost:8091/health

# AI metrics
curl http://localhost:8091/metrics
# or run: bash scripts/collect-ai-metrics.sh
```

---

## Workflow Examples

### Example 1: New Agent Onboarding

**Scenario**: Remote AI agent (Claude) first connecting to the system

```bash
# Step 1: Discover system (50 tokens)
curl http://localhost:8091/discovery/info

# Response tells agent what's available and how to proceed

# Step 2: Get quickstart guide (150 tokens)
curl http://localhost:8091/discovery/quickstart

# Response provides 5-step workflow

# Step 3: List capabilities (200 tokens)
curl http://localhost:8091/discovery/capabilities?level=standard

# Response shows 18 capabilities across 6 categories

# Step 4: Agent picks "search_documents" to start
curl 'http://localhost:8091/documents?search=NixOS+quickstart&limit=3'

# Step 5: Agent records interaction for learning
curl -X POST http://localhost:8091/interactions/record \
  -d '{"query": "NixOS quickstart", "outcome": "success"}'
```

**Total Tokens**: ~400 tokens (vs 3000+ without progressive disclosure)

---

### Example 2: Local Model Integration

**Scenario**: Ollama or llama.cpp model wants to use the system

```bash
# Local models route through Hybrid Coordinator
curl -X POST http://localhost:8092/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I enable Docker in NixOS?",
    "context": {"model": "llama3.2:3b"}
  }'

# Hybrid Coordinator:
# 1. Searches Qdrant for similar past queries
# 2. Finds high relevance (0.92)
# 3. Routes to local llama.cpp (free)
# 4. Augments with retrieved context
# 5. Returns answer + routing decision
# 6. Stores interaction for future learning
```

**Benefits**:
- No API costs (free local inference)
- Fast (<2s response time)
- Learns from interactions
- Gets better over time

---

### Example 3: Skill Discovery & Execution

**Scenario**: Agent wants to use pre-built skills

```bash
# Step 1: List available skills
curl http://localhost:8091/skills

# Response: 29 skills (code-review, test-runner, docker-deploy, etc.)

# Step 2: Get skill details
curl http://localhost:8091/skills/code-review

# Response: Full skill manifest with parameters

# Step 3: Execute skill
curl -X POST http://localhost:8091/tools/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "tool_name": "code_review",
    "parameters": {
      "file_path": "/path/to/project/main.py",
      "checks": ["style", "security", "performance"]
    }
  }'

# Response: Code review results with suggestions
```

---

### Example 4: Continuous Learning Loop

**Scenario**: Agent learns from successful interactions

```python
# Agent workflow
query = "How to fix PostgreSQL connection error?"

# 1. Search knowledge base
results = requests.get(
    "http://localhost:8091/documents",
    params={"search": query, "limit": 5}
).json()

# 2. If high relevance found, use it
if results["results"][0]["score"] > 0.85:
    solution = results["results"][0]["content"]
else:
    # Query remote LLM
    solution = call_remote_llm(query)

# 3. Record interaction with value scoring
interaction = {
    "query": query,
    "response": solution,
    "metadata": {
        "complexity": 0.7,      # Medium complexity
        "reusability": 0.9,     # Highly reusable
        "novelty": 0.6,         # Somewhat novel
        "confirmed": True,      # User confirmed success
        "impact": 0.8           # High impact
    }
}

# Value score = 0.7*0.2 + 0.9*0.3 + 0.6*0.2 + 1.0*0.15 + 0.8*0.15
#              = 0.14 + 0.27 + 0.12 + 0.15 + 0.12 = 0.80 (HIGH VALUE!)

requests.post(
    "http://localhost:8091/interactions/record",
    json=interaction
)

# System automatically extracts this as a pattern (score ≥ 0.7)
# Future queries about "PostgreSQL connection error" will hit local knowledge base
```

---

## Continuous Improvement Integration

### How the System Learns

1. **Interaction Recording**
   - Every query-response pair stored
   - Metadata tracked (complexity, reusability, etc.)
   - Value score calculated automatically

2. **Pattern Extraction**
   - High-value interactions (score ≥ 0.7) extracted
   - Stored in `skills-patterns` collection
   - Used to improve local routing

3. **Query Routing Optimization**
   - Hybrid Coordinator learns which queries work locally
   - Increases local query percentage over time
   - Target: 70%+ local queries

4. **Token Savings Tracking**
   - Every local query saves ~500 tokens
   - Metrics tracked in telemetry
   - Dashboard shows effectiveness score

### Effectiveness Metrics

**Formula**:
```
Overall Score = (Usage × 0.4) + (Efficiency × 0.4) + (Knowledge × 0.2)

Where:
  Usage = min(total_events / 1000, 1.0) × 100
  Efficiency = local_query_percentage
  Knowledge = min(total_vectors / 10000, 1.0) × 100
```

**Target Metrics**:
- **1000+ events processed**
- **70%+ local queries**
- **10,000+ vectors** in knowledge base
- **Overall score: 80+**

### Monitoring Continuous Improvement

```bash
# Check current effectiveness
bash scripts/collect-ai-metrics.sh
cat ~/.local/share/nixos-system-dashboard/ai_metrics.json | jq .effectiveness

# Example output:
{
  "overall_score": 72,
  "total_events_processed": 1200,
  "local_query_percentage": 68,
  "estimated_tokens_saved": 408000,
  "knowledge_base_vectors": 2500
}
```

---

## Best Practices for Agents

### 1. Start Small, Expand Gradually

✅ **DO**:
```bash
# Start with basic info
curl http://localhost:8091/discovery/info

# Then expand to standard capabilities
curl http://localhost:8091/discovery/capabilities?level=standard
```

❌ **DON'T**:
```bash
# Don't immediately request full schemas
curl http://localhost:8091/discovery/capabilities?level=detailed
# (Wastes tokens if you don't need all details)
```

### 2. Use Categories to Filter

✅ **DO**:
```bash
# Only get knowledge capabilities
curl http://localhost:8091/discovery/capabilities?level=standard&category=knowledge
```

❌ **DON'T**:
```bash
# Don't fetch all capabilities and filter client-side
curl http://localhost:8091/discovery/capabilities?level=standard
# (Wastes tokens on categories you don't need)
```

### 3. Record All Interactions

✅ **DO**:
```python
# Always record outcomes
requests.post(
    "http://localhost:8091/interactions/record",
    json={"query": q, "response": r, "outcome": "success"}
)
```

❌ **DON'T**:
```python
# Don't skip recording - system can't learn
# (Misses opportunity to improve local routing)
```

### 4. Prefer Hybrid Coordinator for Queries

✅ **DO**:
```bash
# Let hybrid coordinator decide routing
curl -X POST http://localhost:8092/query -d '{"query": "..."}'
```

❌ **DON'T**:
```bash
# Don't always call remote API directly
curl -X POST https://api.anthropic.com/v1/messages ...
# (Wastes money when local LLM could handle it)
```

---

## Summary

The progressive disclosure system provides:

- **4 disclosure levels** (basic → advanced)
- **6 capability categories** (knowledge, inference, storage, learning, integration, monitoring)
- **90% token reduction** in discovery phase
- **Continuous learning** from all interactions
- **Clear entry points** for both remote and local models

**Next Steps**:
1. Try the quickstart: `curl http://localhost:8091/discovery/quickstart`
2. Explore capabilities: `curl http://localhost:8091/discovery/capabilities`
3. Read agent guides: Start with `/docs/agent-guides/00-SYSTEM-OVERVIEW.md`
4. Begin using the system and let it learn from your interactions!

---

**Document Version**: 1.0.0
**Last Updated**: 2025-12-22
**Related Docs**:
- [AI System Usage Guide](../AI-SYSTEM-USAGE-GUIDE.md)
- [Agent Guides](agent-guides/)
- [Agent Onboarding Package](../agent-onboarding-package-v2.0.0/)
