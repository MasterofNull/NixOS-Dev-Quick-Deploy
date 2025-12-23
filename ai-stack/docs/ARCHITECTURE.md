# AI Stack Architecture

**Version:** 1.0.0 (NixOS-Dev-Quick-Deploy v6.0.0)
**Date:** 2025-12-12
**Status:** ✅ Production Architecture

---

## Executive Summary

The AI Stack is a fully integrated, production-ready AI development environment built on:
- **PostgreSQL + TimescaleDB** - Time-series document storage
- **Redis** - High-performance caching
- **Qdrant** - Vector database for semantic search
- **llama.cpp vLLM** - Local OpenAI-compatible inference
- **FastAPI MCP Server** - Unified API gateway
- **29 Agent Skills** - Specialized AI capabilities

**Design Principles:**
1. **Declarative scaffolding** - NixOS provisions infrastructure
2. **Mutable configurations** - Editable configs for flexibility
3. **Data persistence** - Shared data survives reinstalls
4. **Zero coupling** - AI stack is optional, system works without it
5. **Public & documented** - No private dependencies

---

## System Layers

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: User Applications                                      │
│ VSCodium, Cursor, Aider, GPT CLI                                │
└─────────────────────────────────────────────────────────────────┘
                           ▲
                           │ HTTP/API
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: AI Stack (ai-stack/)                                   │
│ ┌─────────────┐  ┌──────────────┐  ┌────────────────┐          │
│ │ AIDB MCP    │  │ Agent Skills │  │ llama.cpp vLLM  │          │
│ │ Server      │  │ (29 skills)  │  │ Inference      │          │
│ │ (FastAPI)   │  └──────────────┘  └────────────────┘          │
│ └─────────────┘                                                 │
│       ▲                                                          │
│       │ Database/Cache/Vector Access                            │
│       ▼                                                          │
│ ┌──────────┐  ┌────────┐  ┌─────────┐                          │
│ │PostgreSQL│  │ Redis  │  │ Qdrant  │                          │
│ │TimescaleDB  │ Cache  │  │ Vectors │                          │
│ └──────────┘  └────────┘  └─────────┘                          │
└─────────────────────────────────────────────────────────────────┘
                           ▲
                           │ Podman Compose
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: Container Runtime                                      │
│ Podman (rootless), Podman Compose, Buildah                      │
└─────────────────────────────────────────────────────────────────┘
                           ▲
                           │ NixOS Services
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: NixOS Foundation                                       │
│ Declarative system, Home Manager, Flakes                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. AIDB MCP Server

**Purpose:** Unified API gateway for all AI operations

**Technology Stack:**
- FastAPI (Python) - Web framework
- SQLAlchemy - ORM
- Pydantic - Data validation
- Uvicorn - ASGI server

**Responsibilities:**
- Document CRUD operations
- Vector search orchestration
- Model inference routing
- Agent skill execution
- Caching strategy
- Health monitoring

**Port:** 8091

**API Endpoints:**
```
/health              - Health check
/docs                - OpenAPI documentation
/documents           - Document management
/search/semantic     - Vector search
/inference/generate  - Model inference
/skills              - Agent skill execution
```

**Database Connections:**
```python
# PostgreSQL
engine = create_engine(
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# Redis
redis_client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD
)

# Qdrant
qdrant_client = QdrantClient(
    host=QDRANT_HOST,
    port=QDRANT_PORT
)
```

### 2. llama.cpp vLLM

**Purpose:** Local OpenAI-compatible model inference

**Technology:** vLLM (https://github.com/vllm-project/vllm)

**Supported Models:**
- Qwen2.5-Coder (7B, 14B)
- DeepSeek-Coder-V2 (Lite, Full)
- Phi-3-mini
- CodeLlama-13B

**Port:** 8080

**API Compatibility:**
- OpenAI completions API
- Chat completions
- Token counting
- Streaming responses

**Performance:**
- GPU acceleration (NVIDIA)
- Quantization support (GGUF)
- KV cache optimization
- Continuous batching

**Model Loading:**
```bash
# Automatic model download from HuggingFace
LLAMA_CPP_DEFAULT_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
HUGGING_FACE_HUB_TOKEN=<optional>

# Models cached in ~/.local/share/nixos-ai-stack/llama-cpp-models
```

### 3. PostgreSQL + TimescaleDB

**Purpose:** Time-series document storage and analytics

**Technology:**
- PostgreSQL 16
- TimescaleDB extension
- pgvector extension (for vector storage)

**Port:** 5432

**Schema Design:**
```sql
-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hypertable for time-series
SELECT create_hypertable('documents', 'created_at');

-- Indexes
CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata);
CREATE INDEX idx_documents_created_at ON documents (created_at DESC);

-- Embeddings table
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    vector VECTOR(1536),
    model TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Vector index
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (vector vector_cosine_ops);
```

**Data Persistence:**
- Volume: `~/.local/share/nixos-ai-stack/postgres`
- Automatic backups: `~/.local/share/nixos-ai-stack/backups`

### 4. Redis

**Purpose:** High-performance caching and session storage

**Technology:** Redis 7 (Alpine)

**Port:** 6379

**Usage Patterns:**
```python
# Cache model responses
cache_key = f"completion:{hash(prompt)}"
cached = redis.get(cache_key)
if cached:
    return cached

# Set with TTL (1 hour)
redis.setex(cache_key, 3600, response)

# Session storage
redis.hset(f"session:{user_id}", mapping=session_data)

# Rate limiting
redis.incr(f"ratelimit:{user_id}:{endpoint}")
redis.expire(f"ratelimit:{user_id}:{endpoint}", 60)
```

**Persistence:**
- AOF (Append-Only File) enabled
- RDB snapshots
- Volume: `~/.local/share/nixos-ai-stack/redis`

### 5. Qdrant Vector Database

**Purpose:** Semantic search and similarity matching

**Technology:** Qdrant (Rust-based vector DB)

**Port:** 6333 (HTTP), 6334 (gRPC)

**Collections:**
```python
# Document collection
qdrant.create_collection(
    collection_name="documents",
    vectors_config={
        "size": 1536,  # OpenAI ada-002 compatible
        "distance": "Cosine"
    }
)

# Insert vectors
qdrant.upsert(
    collection_name="documents",
    points=[
        PointStruct(
            id=doc_id,
            vector=embedding,
            payload={"text": text, "metadata": metadata}
        )
    ]
)

# Semantic search
results = qdrant.search(
    collection_name="documents",
    query_vector=query_embedding,
    limit=10
)
```

**Data Persistence:**
- Volume: `~/.local/share/nixos-ai-stack/qdrant`

### 6. Agent Skills

**Purpose:** Specialized AI capabilities for specific tasks

**Architecture:**
```
ai-stack/agents/
├── skills/                    # 29 specialized skills
│   ├── nixos-deployment/      # NixOS configuration generation
│   ├── code-review/           # Automated code review
│   ├── webapp-testing/        # Playwright-based testing
│   ├── canvas-design/         # Visual design generation
│   ├── mcp-builder/           # MCP server scaffolding
│   └── ... (24 more)
├── orchestrator/              # Primary orchestrator
└── shared/                    # Shared utilities
```

**Skill Interface:**
```python
class Skill:
    name: str
    description: str
    parameters: Dict[str, Any]

    async def execute(self, **kwargs) -> SkillResult:
        # Skill implementation
        pass
```

**Skill Loading:**
```python
# Automatic discovery
skills = discover_skills("ai-stack/agents/skills/")

# Dynamic execution
result = await skills["nixos-deployment"].execute(
    action="generate_config",
    packages=["vim", "git"]
)
```

---

## Data Flow

### Document Ingestion

```
User → AIDB MCP Server → PostgreSQL (store document)
                       → llama.cpp (generate embedding)
                       → Qdrant (store vector)
                       → Redis (cache)
```

### Semantic Search

```
User → AIDB MCP Server → llama.cpp (embed query)
                       → Qdrant (vector search)
                       → PostgreSQL (fetch documents)
                       → Redis (cache results)
                       → Response
```

### Model Inference

```
User → AIDB MCP Server → Redis (check cache)
                       → llama.cpp (generate completion)
                       → PostgreSQL (log inference)
                       → Redis (cache response)
                       → Response
```

### Agent Skill Execution

```
User → AIDB MCP Server → Skill Loader
                       → Skill.execute()
                       → llama.cpp (if LLM needed)
                       → PostgreSQL (store results)
                       → Response
```

---

## Networking

### Container Network

**Name:** `nixos-ai-stack-net`

**Services:**
- `aidb-mcp` (AIDB MCP Server)
- `llama-cpp` (vLLM inference)
- `postgres` (PostgreSQL)
- `redis` (Redis cache)
- `qdrant` (Vector DB)
- `redis-insight` (Web UI)

**DNS Resolution:**
```bash
# Services can reach each other by name
ping postgres
ping redis
ping qdrant
ping llama-cpp
```

### Port Mapping

| Service | Internal Port | External Port | Protocol |
|---------|---------------|---------------|----------|
| AIDB MCP | 8091 | 8091 | HTTP |
| llama.cpp | 8080 | 8080 | HTTP |
| PostgreSQL | 5432 | 5432 | TCP |
| Redis | 6379 | 6379 | TCP |
| Qdrant HTTP | 6333 | 6333 | HTTP |
| Qdrant gRPC | 6334 | 6334 | gRPC |
| Redis Insight | 5540 | 5540 | HTTP |

---

## Storage Architecture

### Shared Data Directory

**Location:** `~/.local/share/nixos-ai-stack/`

**Purpose:** Persistent data that survives container restarts and reinstalls

**Structure:**
```
~/.local/share/nixos-ai-stack/
├── postgres/          # PostgreSQL data files
│   └── data/
├── redis/             # Redis persistence
│   ├── appendonly.aof
│   └── dump.rdb
├── qdrant/            # Qdrant collections
│   ├── collections/
│   └── storage/
├── llama-cpp-models/   # HuggingFace model cache
│   └── hub/
├── imports/           # Document imports
├── exports/           # Exported data
├── backups/           # Database backups
│   └── YYYYMMDD/
└── logs/              # Service logs
    ├── aidb.log
    ├── llama-cpp.log
    └── postgres.log
```

### Configuration Directory

**Location:** `~/.config/nixos-ai-stack/`

**Structure:**
```
~/.config/nixos-ai-stack/
├── .env                    # Active configuration
└── ai-optimizer.json       # Integration metadata
```

---

## Security Architecture

### Network Isolation

- Container network isolated from host
- Only mapped ports accessible externally
- Internal service-to-service communication

### Authentication

**Development:**
- No authentication required
- Suitable for local development

**Production:**
- API key authentication
- JWT tokens
- Rate limiting

### Data Encryption

- TLS for external connections (when deployed)
- At-rest encryption for sensitive data
- Password hashing for credentials

---

## Scalability

### Horizontal Scaling

**Services that can scale:**
- AIDB MCP Server (multiple instances + load balancer)
- llama.cpp (multiple models on different GPUs)

**Services that require coordination:**
- PostgreSQL (read replicas supported)
- Redis (clustering supported)
- Qdrant (sharding supported)

### Vertical Scaling

**Memory:**
- PostgreSQL: Adjust `shared_buffers`
- Redis: Adjust `maxmemory`
- llama.cpp: Adjust GPU allocation

**CPU/GPU:**
- llama.cpp: Add more GPUs
- AIDB: Increase worker processes

---

## Monitoring & Observability

### Health Checks

```bash
# Overall health
curl http://localhost:8091/health

# Individual services
./scripts/ai-stack-manage.sh health
```

### Logs

```bash
# View all logs
./scripts/ai-stack-manage.sh logs

# View specific service
./scripts/ai-stack-manage.sh logs aidb-mcp
```

### Metrics

- Prometheus metrics at `/metrics`
- Grafana dashboards (optional)
- PostgreSQL query performance
- Redis hit rate
- Model inference latency

---

## Deployment Variants

### Development

```bash
# Enable auto-reload and debug logging
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Minimal (llama.cpp Only)

```bash
# Just model inference, no database
docker compose -f docker-compose.minimal.yml up
```

### Production

```bash
# Full stack with all services
docker compose up -d
```

---

## Disaster Recovery

### Backup Strategy

**Automated Backups:**
```bash
# PostgreSQL dump
pg_dump -U mcp mcp > backup.sql

# Redis snapshot
redis-cli BGSAVE

# Qdrant snapshot
curl -X POST http://localhost:6333/collections/documents/snapshots
```

**Backup Location:**
`~/.local/share/nixos-ai-stack/backups/`

### Recovery

```bash
# Restore PostgreSQL
psql -U mcp mcp < backup.sql

# Restore Redis
redis-cli --rdb dump.rdb

# Restore Qdrant
curl -X PUT http://localhost:6333/collections/documents/snapshots/upload \
  -H "Content-Type: application/octet-stream" \
  --data-binary @snapshot.dat
```

---

## Performance Tuning

### PostgreSQL

```ini
# postgresql.conf
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 41MB
min_wal_size = 2GB
max_wal_size = 8GB
```

### Redis

```bash
# redis.conf
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### llama.cpp

```bash
# Environment variables
LLAMA_CPP_WEB_CONCURRENCY=4
LLAMA_CPP_CTX_SIZE=4096
```

---

## Future Enhancements

1. **Multi-tenancy** - Support multiple users/projects
2. **OAuth2 authentication** - Enterprise SSO
3. **Distributed inference** - Multiple llama.cpp instances
4. **Real-time collaboration** - WebSocket support
5. **Advanced analytics** - ClickHouse integration
6. **Model fine-tuning** - LoRA training support

---

## References

- [Main Integration Guide](../../../docs/AI-STACK-FULL-INTEGRATION.md)
- [API Documentation](API.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [AIDB MCP Server README](../mcp-servers/aidb/README.md)

---

**Last Updated:** 2025-12-12
**Version:** 1.0.0
**Status:** Production Ready
