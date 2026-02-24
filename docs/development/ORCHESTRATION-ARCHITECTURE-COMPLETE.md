# AI Stack Orchestration Architecture - Complete Guide
**Date:** 2026-01-09
**Status:** 📐 DEFINITIVE REFERENCE

---

## Executive Summary

This document provides the **definitive guide** to how your AI stack orchestration works. It eliminates confusion by clearly defining what each component does, how they interact, and when to use what.

**Key Insight:** You have **THREE complementary orchestrators**, not competing ones. Each has a specific role in the workflow.

---

## Table of Contents

1. [The Three Orchestrators](#the-three-orchestrators)
2. [When to Use Which](#when-to-use-which)
3. [Complete Workflow Diagrams](#complete-workflow-diagrams)
4. [Database & Storage Architecture](#database--storage-architecture)
5. [Service Dependencies](#service-dependencies)
6. [Port Map & Routing](#port-map--routing)
7. [Configuration Hierarchy](#configuration-hierarchy)
8. [Common Workflows](#common-workflows)
9. [Troubleshooting Guide](#troubleshooting-guide)

---

## The Three Orchestrators

### 🔄 1. Ralph Wiggum - The Persistent Loop Engine

**Location:** `ai-stack/mcp-servers/ralph-wiggum/`
**Port:** 8090 (MCP) / 8098 (FastAPI)
**Purpose:** Autonomous task execution with continuous retry

**What It Does:**
```python
while not task_complete:
    result = execute_agent(task)

    if exit_code == 2:
        # Special: Block premature exit
        log("Exit blocked - Ralph keeps going!")
        continue

    if task_needs_retry:
        save_checkpoint()
        continue
    else:
        break

return final_result
```

**Key Features:**
- **Exit Code 2 Blocking** - Prevents agents from quitting too early
- **State Persistence** - Git commits + JSON checkpoints
- **Multi-Backend Support** - Aider, Continue, Goose, AutoGPT, LangChain
- **Human-in-the-Loop** - Approval gates for critical operations
- **Audit Logging** - Full telemetry of all actions

**Agent Backends:**

1. **Aider** (Default)
   - Git-aware pair programming
   - Best for: Multi-file changes, refactoring
   - Command: `aider --model qwen2.5-coder`

2. **Continue**
   - VSCode/IDE autopilot
   - Best for: In-editor coding, quick fixes
   - Command: `continue --task <task>`

3. **Goose**
   - Autonomous file system agent
   - Best for: File operations, search & replace
   - Command: `goose run <task>`

4. **AutoGPT**
   - Goal decomposition planner
   - Best for: Complex multi-step tasks
   - Command: `autogpt --task <task>`

5. **LangChain**
   - Tool chain orchestration
   - Best for: API integrations, workflows
   - Command: `langchain --task <task>`

**Configuration:**
```yaml
# ralph-wiggum/config/default.yaml
loop:
  max_iterations: 0  # 0 = infinite (Ralph never quits!)
  exit_code_block: 2  # Block exit code 2
  checkpoint_interval: 1  # Save after every iteration

backends:
  default: aider
  fallback: continue

approval:
  require_approval: false  # Set true for production
  approval_threshold: high  # low, medium, high

telemetry:
  path: /data/telemetry/ralph-events.jsonl
  enabled: true
```

**When Ralph Runs:**
- Large feature implementations
- Multi-file refactoring
- Code generation with iteration
- Tasks requiring multiple attempts
- Autonomous coding agents

**Example Usage:**
```bash
# Submit task to Ralph
curl -X POST http://localhost:8090/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Implement user authentication with JWT",
    "backend": "aider",
    "max_iterations": 10,
    "require_approval": false
  }'

# Returns: task_id

# Check status
curl http://localhost:8090/status/<task_id>

# Get result
curl http://localhost:8090/result/<task_id>
```

---

### 🔀 2. Hybrid Coordinator - The Smart Router

**Location:** `ai-stack/mcp-servers/hybrid-coordinator/`
**Port:** 8092
**Purpose:** Query routing between local LLM and cloud APIs with continuous learning

**What It Does:**
```python
async def route_query(query, context):
    # 1. Check cache
    cached = redis.get(query_hash)
    if cached and similarity > 0.95:
        return cached

    # 2. Augment with context
    context = qdrant.search(query, limit=5)

    # 3. Score with local LLM
    confidence = await local_llm.score(query, context)

    # 4. Route decision
    if confidence >= 0.85:
        result = await local_llm.execute(query, context)
        route = "local"
    elif confidence >= 0.70:
        result = await local_llm.execute(query, context)
        if result.quality < 0.8:
            result = await cloud_api.execute(query, context)
            route = "remote_fallback"
    else:
        result = await cloud_api.execute(query, context)
        route = "remote"

    # 5. Track & learn
    await track_interaction(query, result, route)
    value_score = compute_value_score(result)

    if value_score >= 0.7:
        await extract_pattern(query, result)
        await generate_finetuning_data(query, result)

    # 6. Cache result
    redis.set(query_hash, result, ttl=86400)

    return result
```

**Key Features:**
- **Smart Routing** - Local vs remote based on confidence
- **Context Augmentation** - Qdrant retrieval for better results
- **Continuous Learning** - Automatic pattern extraction
- **Cost Optimization** - Prefer local, use remote only when needed
- **Embedding Cache** - Redis-backed for fast repeated queries
- **Multi-Turn Context** - Session management via Redis
- **Federation Sync** - Multi-node pattern sharing

**Routing Decision Matrix:**

| Confidence | Action | Latency | Cost | Use Case |
|------------|--------|---------|------|----------|
| ≥ 0.85 | Local LLM | ~200ms | $0 | Simple queries, known patterns |
| 0.70-0.84 | Local + Fallback | ~300ms | ~$0.01 | Medium complexity, try local first |
| < 0.70 | Cloud API | ~2000ms | ~$0.05 | Complex queries, critical accuracy |

**Configuration:**
```yaml
# config/config.yaml - hybrid section
hybrid:
  local_confidence_threshold: 0.85
  fallback_threshold: 0.70
  high_value_threshold: 0.70

  routing:
    prefer_local: true
    fallback_enabled: true
    cache_ttl: 86400  # 24 hours

  learning:
    enabled: true
    interval: 3600  # Process telemetry every hour
    dataset_threshold: 1000  # Min examples before fine-tune
    value_score_threshold: 0.70

  cache:
    redis_enabled: true
    embedding_cache_size: 10000
    similarity_threshold: 0.95
```

**When Hybrid Coordinator Runs:**
- All user queries
- Any LLM interaction
- Context-aware responses
- Cost-sensitive operations
- Learning from interactions

**Example Usage:**
```bash
# Query with routing
curl -X POST http://localhost:8092/route \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I configure NixOS networking?",
    "context": {},
    "prefer_local": true
  }'

# Returns:
{
  "response": "To configure NixOS networking...",
  "route": "local",
  "confidence": 0.87,
  "latency_ms": 245,
  "cost": 0.0,
  "cached": false,
  "value_score": 0.78,
  "learned": true
}

# Get routing stats
curl http://localhost:8092/stats

# Returns:
{
  "total_queries": 1234,
  "local_route": 892,
  "remote_route": 342,
  "local_percentage": 72.3,
  "average_latency_ms": 356,
  "total_cost_saved": 45.67,
  "patterns_learned": 89
}
```

---

### 📚 3. AIDB - The Knowledge Base Server

**Location:** `ai-stack/mcp-servers/aidb/`
**Port:** 8091
**Purpose:** Central knowledge repository and MCP server

**What It Does:**
```python
async def handle_query(query):
    # 1. Validate & rate limit
    validate_query(query)
    check_rate_limit(user)

    # 2. Tool discovery
    relevant_tools = discover_tools(query)

    # 3. Search knowledge base
    documents = postgres.search(query)
    embeddings = qdrant.search(embed(query), limit=10)

    # 4. Augment context
    context = merge(documents, embeddings, relevant_tools)

    # 5. Route to hybrid coordinator
    result = await hybrid_coordinator.route(query, context)

    # 6. Track telemetry
    await log_event({
        "event_type": "query",
        "query": query,
        "context_size": len(context),
        "result": result,
        "timestamp": now()
    })

    return result
```

**Key Features:**
- **PostgreSQL Storage** - Structured data, tool registry, telemetry
- **Qdrant Vectors** - Semantic search, embeddings (384-dim)
- **Tool Discovery** - Dynamic MCP tool catalog
- **Health Checks** - Kubernetes-style probes (readiness, liveness, startup)
- **Issue Tracking** - Production error tracking with severity
- **Garbage Collection** - Automatic cleanup of old/duplicate data
- **Query Validation** - Input sanitization + Pydantic v2
- **Rate Limiting** - Token bucket algorithm (60/min, 1000/hr)

**PostgreSQL Tables:**

1. **`tool_registry`** - MCP tools and their manifests
2. **`imported_documents`** - User-added knowledge
3. **`open_skills`** - Available skills library
4. **`system_registry`** - System resources and versions
5. **`points_of_interest`** - Important URLs/resources
6. **`telemetry_events`** - All event tracking
7. **`document_embeddings`** - pgvector embeddings (384-dim)
8. **`issues`** - Production error tracking (P0/P1/P2)

**Qdrant Collections:**

1. **`codebase-context`** - Code snippets with metadata
2. **`skills-patterns`** - Reusable skill patterns
3. **`error-solutions`** - Known errors + fixes
4. **`interaction-history`** - Complete interaction log
5. **`best-practices`** - Curated guidelines
6. **`nixos-docs`** - NixOS documentation chunks

**Configuration:**
```yaml
# config/config.yaml - aidb section
database:
  postgres:
    host: postgres
    port: 5432
    database: mcp
    user: mcp
    password: change_me_in_production
    pool:
      size: 20
      max_overflow: 30

  redis:
    host: redis
    port: 6379
    pool:
      max_connections: 50

  qdrant:
    host: qdrant
    port: 6333
    collections:
      - codebase-context
      - skills-patterns
      - error-solutions

tools:
  discovery_enabled: true
  discovery_interval: 300  # 5 minutes
  progressive_disclosure: true

security:
  rate_limit:
    requests_per_minute: 60
    requests_per_hour: 1000
  query_validation: true
  max_query_length: 4096

garbage_collection:
  enabled: true
  schedule: "0 2 * * *"  # 2am daily
  max_age_days: 30
  dedup_threshold: 0.95
```

**When AIDB Runs:**
- All queries (entry point)
- Tool discovery
- Knowledge base search
- Health monitoring
- Issue tracking

**Example Usage:**
```bash
# Query knowledge base
curl -X POST http://localhost:8091/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to fix X?",
    "use_hybrid": true,
    "include_tools": true
  }'

# Discover tools
curl http://localhost:8091/tools/discover

# Check health
curl http://localhost:8091/health/live
curl http://localhost:8091/health/ready

# Track issue
curl -X POST http://localhost:8091/issues \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Production error X",
    "severity": "P1",
    "category": "bug",
    "description": "Error occurs when..."
  }'
```

---

## When to Use Which

### Decision Tree: Which Orchestrator?

```
Start: What do you need?

├─ "Execute a task with iteration"
│  └─ Use Ralph Wiggum
│     └─ Examples: "Implement feature X", "Refactor Y", "Fix bug Z"

├─ "Answer a query"
│  └─ Use Hybrid Coordinator (via AIDB)
│     └─ Examples: "How do I...?", "What is...?", "Explain..."

├─ "Search knowledge base"
│  └─ Use AIDB directly
│     └─ Examples: "Find docs about X", "List available tools"

├─ "Track system health"
│  └─ Use AIDB health endpoints
│     └─ Examples: Health checks, readiness probes

└─ "Report an issue"
   └─ Use AIDB issue tracker
      └─ Examples: Production errors, bugs, incidents
```

### Use Case Matrix

| Use Case | Primary | Secondary | Tertiary |
|----------|---------|-----------|----------|
| **Code Generation** | Ralph Wiggum | - | - |
| **Multi-file Refactoring** | Ralph Wiggum | - | - |
| **Bug Fixing (with iteration)** | Ralph Wiggum | - | - |
| **Simple Query** | AIDB → Hybrid | - | - |
| **Complex Query** | AIDB → Hybrid → Remote | - | - |
| **Repeated Query** | AIDB → Cache | - | - |
| **Knowledge Search** | AIDB → Qdrant | - | - |
| **Tool Discovery** | AIDB | - | - |
| **Health Monitoring** | AIDB | - | - |
| **Issue Tracking** | AIDB | - | - |
| **Pattern Learning** | Hybrid Coordinator | - | - |
| **Cost Optimization** | Hybrid Coordinator | - | - |

---

## Complete Workflow Diagrams

### Workflow 1: Simple Query (Cached)

```
User: "How to enable SSH in NixOS?"
  ↓
AIDB (port 8091)
  ├─ Validate query ✓
  ├─ Rate limit check ✓
  └─ Check Redis cache
     ↓
     🎯 CACHE HIT (95% similarity)
     ↓
  Return cached response (50ms)
  ↓
User receives answer

Telemetry:
- Event: cache_hit
- Latency: 50ms
- Cost: $0
```

### Workflow 2: Simple Query (Local LLM)

```
User: "How to configure firewall in NixOS?"
  ↓
AIDB (port 8091)
  ├─ Validate query ✓
  ├─ Rate limit check ✓
  ├─ Cache miss
  └─ Search Qdrant for context
     ├─ Found: nixos-docs/networking.md
     ├─ Found: best-practices/firewall.md
     └─ Found: error-solutions/firewall-config.md
  ↓
Hybrid Coordinator (port 8092)
  ├─ Score with local LLM
  │  └─ Confidence: 0.88 (HIGH)
  ├─ Decision: Route LOCAL
  └─ Execute on llama.cpp
     ↓
llama.cpp (port 8080)
  ├─ Model: Qwen2.5-Coder-7B
  ├─ Input: query + context (450 tokens)
  ├─ Output: detailed answer (280 tokens)
  └─ Latency: 245ms
  ↓
Hybrid Coordinator
  ├─ Track interaction
  ├─ Compute value_score: 0.76 (HIGH)
  ├─ Extract pattern ✓
  ├─ Generate fine-tuning data ✓
  ├─ Cache in Redis (TTL: 24h)
  └─ Return result
  ↓
AIDB
  └─ Log telemetry
  ↓
User receives answer (360ms total)

Telemetry:
- Event: query_completion
- Route: local
- Confidence: 0.88
- Latency: 360ms
- Cost: $0
- Learned: true
- Value score: 0.76
```

### Workflow 3: Complex Query (Remote API)

```
User: "Design a multi-tier NixOS deployment with HA and monitoring"
  ↓
AIDB (port 8091)
  ├─ Validate query ✓
  ├─ Rate limit check ✓
  ├─ Cache miss (novel query)
  └─ Search Qdrant for context
     ├─ Found: best-practices/deployment.md
     ├─ Found: skills-patterns/ha-setup.md
     └─ Context relevance: 0.65 (medium)
  ↓
Hybrid Coordinator (port 8092)
  ├─ Score with local LLM
  │  └─ Confidence: 0.58 (LOW)
  ├─ Decision: Route REMOTE (complex query)
  └─ Execute on Claude API
     ↓
Claude API (cloud)
  ├─ Model: Claude 3.5 Sonnet
  ├─ Input: query + context (850 tokens)
  ├─ Output: comprehensive design (1200 tokens)
  └─ Latency: 2450ms
  ↓
Hybrid Coordinator
  ├─ Track interaction
  ├─ Compute value_score: 0.85 (VERY HIGH)
  ├─ Extract multiple patterns ✓
  │  ├─ Pattern: "nixos_ha_deployment"
  │  ├─ Pattern: "multi_tier_architecture"
  │  └─ Pattern: "monitoring_integration"
  ├─ Generate fine-tuning data ✓ (3 examples)
  ├─ Cache in Redis (TTL: 24h)
  └─ Return result
  ↓
AIDB
  └─ Log telemetry
  ↓
User receives comprehensive answer (2800ms total)

Telemetry:
- Event: query_completion
- Route: remote
- Confidence: 0.58
- Latency: 2800ms
- Cost: $0.05
- Learned: true
- Value score: 0.85
- Patterns: 3
```

### Workflow 4: Ralph Wiggum Task Execution

```
User: "Implement user authentication with JWT"
  ↓
Ralph Wiggum (port 8090)
  ├─ Queue task (task_id: abc123)
  ├─ Select backend: Aider (default)
  └─ Start iteration loop
     ↓
Iteration 1:
  ├─ Execute: aider --model qwen2.5-coder
  ├─ Prompt: "Implement user authentication with JWT"
  ├─ Aider creates: auth.py, models.py
  ├─ Exit code: 0
  ├─ Completion check: ❌ Tests not written
  ├─ Save checkpoint (git commit)
  └─ Continue loop
     ↓
Iteration 2:
  ├─ Execute: aider --model qwen2.5-coder
  ├─ Prompt: "Add tests for authentication"
  ├─ Aider creates: test_auth.py
  ├─ Exit code: 2 (premature exit)
  ├─ StopHook BLOCKS exit code 2
  ├─ Log: "exit_blocked"
  ├─ Save checkpoint (git commit)
  └─ Continue loop
     ↓
Iteration 3:
  ├─ Execute: aider --model qwen2.5-coder
  ├─ Prompt: "Fix failing tests"
  ├─ Aider fixes: auth.py
  ├─ Exit code: 0
  ├─ Completion check: ✓ All tests pass
  ├─ Save final checkpoint (git commit)
  └─ Exit loop (COMPLETE)
  ↓
Ralph Wiggum
  ├─ Final state: COMPLETED
  ├─ Iterations: 3
  ├─ Files modified: 3
  ├─ Lines changed: 245
  └─ Log telemetry
  ↓
User receives result: "Task completed in 3 iterations"

Telemetry:
- Event: task_completed
- Task ID: abc123
- Backend: aider
- Iterations: 3
- Duration: 12 minutes
- Success: true
- Exit codes: [0, 2 (blocked), 0]
```

### Workflow 5: Continuous Learning Pipeline

```
Background Daemon (runs 24/7)
  ↓
Every 60 seconds:
  ↓
1. Check telemetry files
   ├─ ralph-events.jsonl (new: 5 events)
   ├─ aidb-events.jsonl (new: 23 events)
   ├─ hybrid-events.jsonl (new: 12 events)
   └─ vscode-events.jsonl (new: 8 events)
  ↓
2. Process new events (48 total)
   ├─ Parse JSONL lines
   ├─ Track file positions
   └─ Batch process
  ↓
3. Compute value scores
   ├─ Event 1: value=0.42 (low)
   ├─ Event 2: value=0.65 (medium)
   ├─ Event 3: value=0.78 (HIGH) ✓
   ├─ Event 4: value=0.53 (medium)
   ├─ Event 5: value=0.82 (HIGH) ✓
   ├─ ... (43 more)
   └─ High-value: 7 events (14.5%)
  ↓
4. Extract patterns (from 7 high-value events)
   ├─ Use local LLM (Qwen2.5-Coder-7B)
   ├─ Async processing (doesn't block)
   └─ Generate 7 patterns:
      ├─ Pattern 1: "nixos_firewall_config"
      ├─ Pattern 2: "jwt_auth_implementation"
      ├─ Pattern 3: "k8s_manifest_fix"
      ├─ Pattern 4: "python_async_error"
      ├─ Pattern 5: "git_merge_conflict"
      ├─ Pattern 6: "nixos_package_override"
      └─ Pattern 7: "postgres_connection_pooling"
  ↓
5. Store patterns
   ├─ Qdrant: skills-patterns collection (7 vectors)
   ├─ PostgreSQL: telemetry_events table (7 rows)
   └─ JSONL: fine-tuning/dataset.jsonl (7 examples)
  ↓
6. Update metrics
   ├─ Total patterns: 89 → 96
   ├─ Dataset size: 856 → 863 examples
   ├─ Learning rate: 14.5% (target: 20%)
   └─ Storage used: 5.6MB → 5.7MB
  ↓
Sleep 3540 seconds (until next hour)
  ↓
[Repeat forever]
```

---

## Database & Storage Architecture

### PostgreSQL (port 5432)

**Connection Pool:**
- Reserved: 20 connections
- Max: 50 connections (20 + 30 overflow)
- Timeout: 30 seconds
- Recycle: 1800 seconds (30 min)
- Pre-ping: true (validate before use)

**Tables & Usage:**

| Table | Rows (est.) | Size | Used By | Purpose |
|-------|-------------|------|---------|---------|
| `tool_registry` | 100 | 1MB | AIDB | MCP tool catalog |
| `imported_documents` | 1000 | 50MB | AIDB | User knowledge |
| `open_skills` | 500 | 10MB | AIDB | Skills library |
| `system_registry` | 50 | 100KB | AIDB | System resources |
| `points_of_interest` | 200 | 500KB | AIDB | Important URLs |
| `telemetry_events` | 100K | 500MB | All | Event tracking |
| `document_embeddings` | 10K | 150MB | AIDB | pgvector (384-dim) |
| `issues` | 500 | 5MB | AIDB | Error tracking |

**Indexes:**
```sql
-- Telemetry lookups
CREATE INDEX idx_telemetry_timestamp ON telemetry_events(timestamp);
CREATE INDEX idx_telemetry_event_type ON telemetry_events(event_type);

-- Vector search (pgvector)
CREATE INDEX idx_embeddings_vector ON document_embeddings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Tool discovery
CREATE INDEX idx_tools_category ON tool_registry(category);
```

**Backup Schedule:**
```bash
# Daily at 2:00 AM
0 2 * * * /path/to/backup-postgresql.sh
```

---

### Redis (port 6379)

**Connection Pool:**
- Max connections: 50
- Socket timeout: 5 seconds
- Connect timeout: 5 seconds

**Key Patterns & Usage:**

| Pattern | TTL | Size | Used By | Purpose |
|---------|-----|------|---------|---------|
| `embed:*` | 24h | ~2KB | Hybrid | Embedding cache |
| `query:*` | 24h | ~5KB | Hybrid | Query cache |
| `tool:*` | 1h | ~1KB | AIDB | Tool schema cache |
| `session:*` | 30m | ~10KB | Hybrid | Multi-turn context |
| `rate:*` | 1m | ~100B | AIDB | Rate limiter state |

**Memory Usage:**
```
embed:*   → 10,000 keys × 2KB  = 20MB
query:*   → 5,000 keys × 5KB   = 25MB
tool:*    → 100 keys × 1KB     = 100KB
session:* → 50 keys × 10KB     = 500KB
rate:*    → 1,000 keys × 100B  = 100KB
-------------------------------------------
Total: ~46MB (well within limits)
```

**Eviction Policy:**
```
maxmemory: 512MB
maxmemory-policy: allkeys-lru  # Least recently used
```

---

### Qdrant (port 6333)

**Collections & Vectors:**

| Collection | Vectors | Dims | Distance | Size | Used By |
|------------|---------|------|----------|------|---------|
| `codebase-context` | 10K | 384 | Cosine | 150MB | Hybrid, AIDB |
| `skills-patterns` | 500 | 384 | Cosine | 8MB | Hybrid |
| `error-solutions` | 200 | 384 | Cosine | 3MB | Hybrid |
| `interaction-history` | 50K | 384 | Cosine | 750MB | Hybrid |
| `best-practices` | 100 | 384 | Cosine | 2MB | Hybrid |
| `nixos-docs` | 5K | 384 | Cosine | 75MB | AIDB |

**HNSW Configuration:**
```yaml
hnsw_config:
  m: 16  # Max connections per node
  ef_construct: 64  # Construction search depth
  full_scan_threshold: 10000  # Switch to exact search

on_disk: false  # Keep in memory for speed
```

**Search Performance:**
```
Top-5 retrieval: ~20ms
Top-10 retrieval: ~35ms
Top-20 retrieval: ~50ms
```

**Disk Usage:**
```
Vectors: 1GB
Payload: 200MB
Index: 300MB
-------------------
Total: ~1.5GB
```

---

### File Storage

**Telemetry Files (JSONL):**
```
/data/telemetry/
├── ralph-events.jsonl       (~1MB/day)
├── aidb-events.jsonl        (~5MB/day)
├── hybrid-events.jsonl      (~2MB/day)
└── vscode-events.jsonl      (~3MB/day)

Growth: ~11MB/day × 30 days = 330MB/month
Rotation: Monthly (compress old files)
```

**Fine-Tuning Dataset:**
```
/data/fine-tuning/
└── dataset.jsonl            (~2KB per example)

Growth:
Week 1: 50 examples = 100KB
Month 1: 200 examples = 400KB
Quarter 1: 800 examples = 1.6MB
Year 1: 3000 examples = 6MB
```

**State Snapshots (Ralph):**
```
/data/ralph-wiggum/
├── state.json               (~10KB per task)
└── checkpoints/
    └── <task_id>/
        └── checkpoint_N.json

Growth: Variable (task-dependent)
Cleanup: After task completion
```

---

## Service Dependencies

### Startup Order

```
1. PostgreSQL
   └─ Health check: pg_isready
      ↓
2. Redis
   └─ Health check: redis-cli ping
      ↓
3. Qdrant
   └─ Health check: GET /health
      ↓
4. Embeddings
   ├─ Depends: PostgreSQL, Redis, Qdrant
   └─ Health check: GET /health
      ↓
5. AIDB
   ├─ Depends: PostgreSQL, Redis, Qdrant, Embeddings
   └─ Health check: GET /health/live
      ↓
6. Hybrid Coordinator
   ├─ Depends: PostgreSQL, Redis, Qdrant, Embeddings, AIDB
   └─ Health check: GET /health
      ↓
7. Ralph Wiggum
   ├─ Depends: AIDB, Hybrid Coordinator
   └─ Health check: GET /health
      ↓
8. Supporting Services
   ├─ Prometheus (metrics)
   ├─ Grafana (visualization)
   ├─ Jaeger (tracing)
   └─ nginx (reverse proxy)
```

### Dependency Matrix

```
                PG   Redis  Qdrant  Embed  AIDB  Hybrid  Ralph
PostgreSQL      -    -      -       -      -     -       -
Redis           -    -      -       -      -     -       -
Qdrant          -    -      -       -      -     -       -
Embeddings      ✓    ✓      ✓       -      -     -       -
AIDB            ✓    ✓      ✓       ✓      -     -       -
Hybrid-Coord    ✓    ✓      ✓       ✓      ✓     -       -
Ralph-Wiggum    -    -      -       -      ✓     ✓       -

✓ = Hard dependency (must be healthy before starting)
```

---

## Port Map & Routing

### Internal Ports (Container Network)

| Service | Port | Protocol | Access |
|---------|------|----------|--------|
| PostgreSQL | 5432 | TCP | Internal only |
| Redis | 6379 | TCP | Internal only |
| Qdrant | 6333 | HTTP | Internal only |
| Embeddings | 8081 | HTTP | Internal only |
| AIDB | 8091 | HTTP | Internal + nginx |
| Hybrid-Coordinator | 8092 | HTTP | Internal + nginx |
| Ralph Wiggum (MCP) | 8090 | HTTP | Internal + nginx |
| Ralph Wiggum (FastAPI) | 8098 | HTTP | Internal only |
| llama.cpp | 8080 | HTTP | Internal only |
| MindsDB | 47334 | HTTP | Localhost only |
| Prometheus | 9090 | HTTP | Localhost only |

### External Ports (Host Access)

| Service | Host Port | Container Port | Access |
|---------|-----------|----------------|--------|
| Dashboard | 8888 | - | http://localhost:8888/dashboard.html |
| nginx (HTTPS) | 8443 | 443 | https://localhost:8443/ |
| Open-WebUI | 3001 | 3001 | http://localhost:3001 |
| Grafana | 3002 | 3000 | http://localhost:3002 |
| Jaeger UI | 16686 | 16686 | http://localhost:16686 |
| MindsDB | 47334 | 47334 | http://localhost:47334 |
| Prometheus | 9090 | 9090 | http://localhost:9090 |

### nginx Reverse Proxy Routes

```nginx
# AIDB
location /aidb/ {
  proxy_pass http://aidb:8091/;
}

# Hybrid Coordinator
location /hybrid/ {
  proxy_pass http://hybrid-coordinator:8092/;
}

# Ralph Wiggum
location /ralph/ {
  proxy_pass http://ralph-wiggum:8090/;
}

# Embeddings
location /embeddings/ {
  proxy_pass http://embeddings:8081/;
}

# llama.cpp
location /llama/ {
  proxy_pass http://llama-cpp:8080/;
}
```

**Access via nginx:**
```bash
# Instead of internal ports
curl http://localhost:8091/health  # ❌ Won't work

# Use nginx proxy
curl https://localhost:8443/aidb/health  # ✓ Works
```

**Dashboard Proxy:**
```bash
# Dashboard server also proxies
curl http://localhost:8888/aidb/health/live
```

---

## Configuration Hierarchy

### Global Configuration
**File:** `ai-stack/mcp-servers/config/config.yaml`
**Used By:** All services

### Service-Specific Configuration
**Files:**
- `ralph-wiggum/config/default.yaml`
- Other services inherit from global

### Environment Variables & Secrets
**Files:**
- `ai-stack/kubernetes/kompose/env-configmap.yaml` (non-secret defaults)
- `ai-stack/kubernetes/secrets/secrets.sops.yaml` (encrypted secret bundle)
**Priority:** Highest (overrides config files once mounted into pods)

### Kubernetes Manifests
**Files:**
- `ai-stack/kubernetes/kompose/` (base manifests)
- `ai-stack/kustomize/overlays/` (environment overrides)
**Defines:** Service topology, volumes, env/secret mounts

### Override Order
```
1. Secret-mounted files + env vars in Deployments (highest priority)
2. ConfigMaps (env-configmap + service-specific configmaps)
3. Global config.yaml
4. Default values in code (lowest priority)
```

**Example:**
```yaml
# config.yaml
hybrid:
  local_confidence_threshold: 0.85

# .env
LOCAL_CONFIDENCE_THRESHOLD=0.90

# Result: Uses 0.90 (env var wins)
```

---

## Common Workflows

### Workflow: Full Stack Query

```mermaid
User → AIDB → Hybrid → llama.cpp → Hybrid → AIDB → User
         ↓        ↓         ↓           ↓       ↓
      Validate  Cache   Execute     Track   Return
                 ↓                    ↓
              Qdrant              PostgreSQL
                                    Qdrant
                                    JSONL
```

### Workflow: Code Generation Task

```mermaid
User → Ralph → Aider → Git → Ralph
         ↓       ↓       ↓      ↓
      Queue   Execute  Commit  Check
       ↓        ↓       ↓      ↓
     State   Iterate  Save  Complete
       ↓                      ↓
    JSONL                  Return
```

### Workflow: Continuous Learning

```mermaid
Telemetry Files → Daemon → Pattern Extraction → Storage
     ↓             ↓            ↓                  ↓
  3 sources    Batch        Local LLM         Qdrant
    ↓           ↓            ↓                PostgreSQL
  Append    Process     Generate JSON         JSONL
              ↓
         Value Score
              ↓
         Filter (≥0.7)
```

---

## Troubleshooting Guide

### Problem: Service Won't Start

**Check:**
```bash
# 1. Dependencies healthy?
podman ps --filter "health=unhealthy"

# 2. Logs
podman logs <service-name> --tail 100

# 3. Port conflicts
ss -ltn | grep <port>
```

### Problem: Query Returns "Offline"

**Check:**
```bash
# 1. AIDB healthy?
curl http://localhost:8091/health/live

# 2. Hybrid coordinator started?
podman ps | grep hybrid

# 3. Database accessible?
podman exec local-ai-postgres pg_isready
```

### Problem: Learning Not Working

**Check:**
```bash
# 1. Telemetry files exist?
ls -lh ~/.local/share/nixos-ai-stack/telemetry/

# 2. Daemon running?
podman top local-ai-hybrid-coordinator | grep daemon

# 3. Dataset growing?
wc -l ~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl
```

### Problem: High Latency

**Check:**
```bash
# 1. Cache hit rate
curl http://localhost:8092/stats | jq .cache_hit_rate

# 2. Local vs remote ratio
curl http://localhost:8092/stats | jq .local_percentage

# 3. Database connections
podman exec local-ai-postgres psql -U mcp -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## Summary

### The Three Orchestrators in One Sentence Each

1. **Ralph Wiggum**: Persistent loop for autonomous code generation with retry
2. **Hybrid Coordinator**: Smart router between local LLM and cloud API with learning
3. **AIDB**: Central knowledge base with tool discovery and health monitoring

### Key Takeaways

- Use **Ralph** for tasks requiring iteration
- Use **Hybrid** for queries requiring intelligence
- Use **AIDB** for everything (entry point)
- All three work together seamlessly
- Telemetry flows automatically
- Learning happens in background
- Everything is transparent and observable

---

**Status: Definitive Orchestration Reference**

*Clear roles, clear flows, clear decisions*
*No more confusion about what does what*
