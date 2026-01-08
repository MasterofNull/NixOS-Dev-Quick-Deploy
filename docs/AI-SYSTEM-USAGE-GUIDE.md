# AI Agent Helper System - Complete Usage Guide
**Date**: 2025-12-22
**System Version**: 2.1.0
**Status**: ✅ FULLY OPERATIONAL

---

## Table of Contents
1. [Quick Start](#quick-start)
2. [Progressive Disclosure & Token Minimization](#progressive-disclosure--token-minimization)
3. [MCP Server Usage](#mcp-server-usage)
4. [Monitoring & Effectiveness Metrics](#monitoring--effectiveness-metrics)
5. [RAG & Continuous Learning](#rag--continuous-learning)
6. [Dashboard Usage](#dashboard-usage)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Start All Services
```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose
podman-compose up -d
```

### Check Service Health
```bash
# All services
podman ps

# Specific health checks
curl http://localhost:6333/healthz        # Qdrant
curl http://localhost:8091/health         # AIDB MCP
curl http://localhost:8092/health         # Hybrid Coordinator
curl http://localhost:8080/health         # llama.cpp
```

### Stop All Services
```bash
podman-compose down
```

---

## Progressive Disclosure & Token Minimization

### Overview
The system implements **progressive disclosure** to minimize token usage and API costs:
- **Default Mode**: `minimal` - Returns only tool names and basic info
- **Full Mode**: `full` - Returns complete schemas and descriptions (requires API key)

### Token Savings Strategy
1. **Tool Discovery**: 90% reduction in tokens (minimal vs full)
2. **RAG Context**: Retrieves only relevant past solutions
3. **Local-First**: Routes simple queries to local LLM
4. **Caching**: Redis caches frequent responses

### Using Minimal Tool Discovery

**HTTP API**:
```bash
# Minimal mode (default) - ~200 tokens
curl http://localhost:8091/tools

# Response:
{
  "tools": [
    {"name": "search_codebase", "description": "Search code"},
    {"name": "generate_code", "description": "Generate code"}
  ],
  "count": 2,
  "mode": "minimal"
}
```

**Full Mode** (requires API key):
```bash
# Full mode - ~2000 tokens
curl -H "x-api-key: YOUR_KEY" \
  "http://localhost:8091/tools?mode=full"

# Response: Complete JSON schemas for all tools
```

### WebSocket API

Connect to `ws://localhost:8091/ws` for real-time communication:

```json
// Minimal discovery
{
  "action": "discover_tools",
  "mode": "minimal"
}

// Full discovery
{
  "action": "discover_tools",
  "mode": "full",
  "api_key": "YOUR_KEY"
}
```

### Configuration

Edit `/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/config/config.yaml`:

```yaml
server:
  default_tool_mode: "minimal"  # Default disclosure level
  full_tool_disclosure_requires_key: true  # Require API key for full mode
  tool_cache_ttl: 3600  # Cache tool schemas for 1 hour
```

---

## MCP Server Usage

### AIDB MCP Server (Port 8091)

**Capabilities**:
- Document storage and retrieval
- Vector search (Qdrant integration)
- Model inference orchestration
- Skill execution (29 agent skills)
- Parallel multi-model inference

**Key Endpoints**:

```bash
# 1. Health Check
curl http://localhost:8091/health
# Returns: database, redis, ml_engine, pgvector, llama_cpp status

# 2. Generate Embeddings
curl -X POST http://localhost:8091/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "example query"}'
# Returns: 384-dimensional vector

# 3. Search Similar Documents
curl -X POST http://localhost:8091/search \
  -H "Content-Type: application/json" \
  -d '{"query": "NixOS error", "limit": 5}'
# Returns: Top 5 similar documents from vector DB

# 4. Execute Skills
curl -X POST http://localhost:8091/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "code_review",
    "parameters": {"file_path": "/path/to/code.py"}
  }'

# 5. Import Documents
curl -X POST http://localhost:8091/documents/import \
  -H "Content-Type: application/json" \
  -d '{
    "project": "my-project",
    "relative_path": "README.md",
    "content": "..."
  }'
```

### Hybrid Coordinator (Port 8092)

**Capabilities**:
- Query routing (local vs remote)
- Context augmentation from Qdrant
- Continuous learning & pattern extraction
- Token usage optimization

**Key Endpoints**:

```bash
# 1. Health Check
curl http://localhost:8092/health
# Returns: service status + Qdrant collections

# 2. Process Query with Smart Routing
curl -X POST http://localhost:8092/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to fix GNOME keyring error?",
    "context": {"user_id": "dev1"}
  }'
# Returns: Answer + routing decision + token savings

# 3. Get Query Statistics
curl http://localhost:8092/stats
# Returns: local vs remote query counts, token savings
```

---

## Monitoring & Effectiveness Metrics

### Collect AI Metrics

**New Optimized Script** (runs in <0.2s):
```bash
# One-time collection
bash scripts/collect-ai-metrics.sh

# View results
cat ~/.local/share/nixos-system-dashboard/ai_metrics.json | jq .
```

**Output Structure**:
```json
{
  "timestamp": "2025-12-22T12:35:00-08:00",
  "services": {
    "aidb": {"status": "ok", "...": "..."},
    "hybrid_coordinator": {
      "status": "healthy",
      "telemetry": {
        "total_events": 1234,
        "local_queries": 800,
        "remote_queries": 434,
        "estimated_tokens_saved": 400000,
        "local_percentage": 65
      }
    },
    "qdrant": {
      "metrics": {
        "collection_count": 5,
        "total_vectors": 1523
      }
    }
  },
  "effectiveness": {
    "overall_score": 72,
    "total_events_processed": 1234,
    "local_query_percentage": 65,
    "estimated_tokens_saved": 400000,
    "knowledge_base_vectors": 1523
  }
}
```

### Effectiveness Scoring

The system calculates an **Overall Effectiveness Score** (0-100) based on:

1. **Usage Score** (40% weight)
   - Based on total events processed
   - 1000+ events = 100 points

2. **Efficiency Score** (40% weight)
   - Percentage of queries handled locally
   - Target: 70%+ local queries

3. **Knowledge Score** (20% weight)
   - Size of vector database
   - 10,000+ vectors = 100 points

**Example**:
- 1200 events → Usage: 100
- 65% local → Efficiency: 65
- 1500 vectors → Knowledge: 15
- **Overall**: (100×0.4) + (65×0.4) + (15×0.2) = **69/100**

### Continuous Monitoring

```bash
# Monitor in real-time (updates every 5s)
watch -n 5 'bash scripts/collect-ai-metrics.sh && cat ~/.local/share/nixos-system-dashboard/ai_metrics.json | jq .effectiveness'
```

---

## RAG & Continuous Learning

### How RAG Works

1. **Query Arrives** → Hybrid Coordinator
2. **Semantic Search** → Qdrant finds similar past queries
3. **Context Injection** → Top 3-5 relevant solutions added
4. **Decision**:
   - High relevance (>0.85) + simple → **Local LLM** (free, fast)
   - Low relevance or complex → **Remote API** (better quality)
5. **Learning** → Store query + outcome for future use

### Add Knowledge to System

**Import Documents**:
```bash
curl -X POST http://localhost:8091/documents/import \
  -H "Content-Type: application/json" \
  -d '{
    "project": "nixos-config",
    "relative_path": "errors/gnome-keyring.md",
    "title": "GNOME Keyring Fix",
    "content": "Error: GNOME keyring...\nSolution: Add libsecret to packages...",
    "content_type": "markdown"
  }'
```

**Store Error Solutions Manually**:
```python
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import uuid

client = QdrantClient(url="http://localhost:6333")

# Get embedding from AIDB
import requests
embedding = requests.post(
    "http://localhost:8091/embed",
    json={"text": "GNOME keyring error NixOS"}
).json()["embedding"]

# Store in error-solutions collection
client.upsert(
    collection_name="error-solutions",
    points=[PointStruct(
        id=str(uuid.uuid4()),
        vector=embedding,
        payload={
            "error": "GNOME keyring error in NixOS",
            "solution": "Add `services.gnome.gnome-keyring.enable = true;` and install `libsecret`",
            "severity": "medium",
            "timestamp": "2025-12-22T12:00:00Z"
        }
    )]
)
```

### Value Scoring

Every interaction is scored (0-1) based on 5 factors:

1. **Complexity** (20%): Lines of code / effort
2. **Reusability** (30%): How broadly applicable
3. **Novelty** (20%): Is it a new solution?
4. **Confirmation** (15%): Was it successful?
5. **Impact** (15%): Severity/importance

**High-value interactions (≥0.7)** are automatically extracted as patterns.

---

## Dashboard Usage

### Start Dashboard Server

```bash
# Start HTTP server on port 8000
bash scripts/serve-dashboard.sh

# Access at: http://localhost:8000
```

### Update Dashboard Data

```bash
# Full update (slow, ~10s) - run once/hour
bash scripts/generate-dashboard-data.sh

# Lite update (fast, ~0.2s) - run every 2-5s
bash scripts/generate-dashboard-data-lite.sh

# AI metrics only (fastest, ~0.2s)
bash scripts/collect-ai-metrics.sh
```

### Dashboard Collectors

**Managed Collectors**:
```bash
# Start lite collector (updates every 2s)
bash scripts/run-dashboard-collector-lite.sh &

# Start full collector (updates every 60s)
bash scripts/run-dashboard-collector-full.sh &

# Manage collectors
bash scripts/manage-dashboard-collectors.sh status
bash scripts/manage-dashboard-collectors.sh stop-all
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check for port conflicts
ss -tlnp | grep -E "6333|8080|8091|8092|5432|6379"

# Remove old containers
podman rm -f $(podman ps -aq)

# Restart cleanly
podman-compose down && podman-compose up -d
```

### AIDB Shows "no model loaded"

This is normal - AIDB uses SentenceTransformer for embeddings, not llama.cpp.

```bash
# Test embeddings work
podman exec local-ai-aidb python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
print('Model loaded:', model.encode('test').shape)
"
```

### Low Effectiveness Score

**Diagnosis**:
```bash
# Check what's causing low score
bash scripts/collect-ai-metrics.sh
cat ~/.local/share/nixos-system-dashboard/ai_metrics.json | jq .effectiveness
```

**Solutions**:
1. **Low Usage** → Start using the system more
2. **Low Efficiency** → Add more knowledge to Qdrant (improves local query routing)
3. **Low Knowledge** → Import documents, store error solutions

### Qdrant Connection Refused

```bash
# Check if Qdrant is running
podman ps | grep qdrant

# Check logs
podman logs local-ai-qdrant

# Restart if needed
podman restart local-ai-qdrant
```

---

## Performance Benchmarks

**Service Startup Times**:
- Qdrant: ~2s
- PostgreSQL: ~3s
- Redis: ~1s
- llama.cpp: ~5-10s (model loading)
- AIDB MCP: ~5s
- Hybrid Coordinator: ~2s

**Query Latency**:
- Local LLM (llama.cpp): 1-3s for simple queries
- Vector search (Qdrant): <50ms
- Embedding generation: ~100ms
- RAG workflow (search + augment): ~200ms

**Resource Usage** (idle):
- Total RAM: ~8GB
- Total CPU: <5%
- Disk: ~7GB (containers + models)

---

## API Reference Card

### Quick Reference

| Service | Port | Health | Purpose |
|---------|------|--------|---------|
| Qdrant | 6333 | `/healthz` | Vector DB |
| llama.cpp | 8080 | `/health` | Local LLM |
| AIDB | 8091 | `/health` | MCP Server |
| Hybrid | 8092 | `/health` | Coordinator |
| PostgreSQL | 5432 | `psql` | Database |
| Redis | 6379 | `redis-cli ping` | Cache |

### Environment Variables

```bash
# Set in ai-stack/compose/.env
POSTGRES_PASSWORD=your_secure_password
AIDB_API_KEY=your_api_key
QDRANT_API_KEY=optional_qdrant_key
LLAMA_CPP_MODEL_FILE=qwen2.5-coder-7b-instruct-q4_k_m.gguf
```

---

## Next Steps

1. **Import Your Codebase**
   ```bash
   curl -X POST http://localhost:8091/documents/import \
     -H "Content-Type: application/json" \
     -d @your_codebase.json
   ```

2. **Start Using for Development**
   - Ask questions via hybrid coordinator
   - Let it learn from your interactions
   - Monitor effectiveness score

3. **Optimize Based on Metrics**
   - Aim for 70%+ local queries
   - Build up knowledge base (10k+ vectors)
   - Track token savings

4. **Scale Up**
   - Add more skills
   - Fine-tune local model on collected data
   - Integrate with CI/CD

---

**System Status**: ✅ FULLY OPERATIONAL
**Documentation**: Complete
**Next Review**: Monitor effectiveness metrics after 1 week of usage
