# AIDB MCP Server

**Version:** 1.0.0 (integrated with NixOS-Dev-Quick-Deploy v6.0.0)
**Status:** ✅ Production Ready

FastAPI-based Model Context Protocol (MCP) server for AI development workflows, integrated with PostgreSQL, Redis, and Qdrant vector database.

---

## Overview

The AIDB MCP Server provides a unified API for:
- **Document Storage & Retrieval** - PostgreSQL + TimescaleDB
- **Vector Search** - Qdrant embeddings and semantic search
- **Caching** - Redis for fast data access
- **Model Inference** - Integration with llama.cpp vLLM
- **Agent Skills** - Load and execute specialized AI agents
- **Parallel Processing** - Multi-model inference support

---

## Quick Start

```bash
# From repository root
./nixos-quick-deploy.sh --with-ai-stack

# Verify AIDB is running
curl http://localhost:8091/health | jq .

# Check API documentation
curl http://localhost:8091/docs
```

---

## Architecture

```
AIDB MCP Server (port 8091)
├── server.py              # FastAPI application
├── settings_loader.py     # Configuration management
├── skills_loader.py       # Agent skill loading
├── registry_api.py        # Model registry
├── parallel_inference.py  # Multi-model inference
├── ml_engine.py           # ML processing engine
├── codemachine_client.py  # CodeMachine integration
├── mindsdb_client.py      # MindsDB integration
├── llama_cpp_tool_agent.py   # llama.cpp agent
├── llm_parallel.py        # LLM parallelization
└── middleware/            # Request/response middleware
```

---

## Configuration

### Environment Variables

See [`../compose/.env.example`](../compose/.env.example) for complete configuration.

**Key Variables:**
```bash
# Database
AIDB_POSTGRES_HOST=postgres
AIDB_POSTGRES_PORT=5432
AIDB_POSTGRES_DB=mcp
AIDB_POSTGRES_USER=mcp
AIDB_POSTGRES_PASSWORD=change_me

# Redis
AIDB_REDIS_HOST=redis
AIDB_REDIS_PORT=6379
AIDB_REDIS_PASSWORD=

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# llama.cpp
LLAMA_CPP_BASE_URL=http://llama-cpp:8080
```

### Config File

The default config file used by the container image lives at:

```
ai-stack/mcp-servers/config/config.yaml
```

Override with `AIDB_CONFIG` if you want to mount a custom config.

---

## API Endpoints

### Health Check
```bash
GET /health
# Returns: {"status": "healthy", "services": {...}}
```

### Document Management
```bash
# Create document
POST /documents
{
  "content": "Document text",
  "metadata": {"key": "value"}
}

# Search documents
GET /documents?search=query

# Get document by ID
GET /documents/{id}
```

### Vector Search
```bash
# Semantic search
POST /search/semantic
{
  "query": "search query",
  "limit": 10
}
```

### Model Inference
```bash
# Generate completion
POST /inference/generate
{
  "prompt": "Your prompt",
  "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "max_tokens": 500
}

# Parallel inference (multiple models)
POST /inference/parallel
{
  "prompt": "Your prompt",
  "models": ["model1", "model2"]
}
```

### Agent Skills
```bash
# List available skills
GET /skills

# Execute skill
POST /skills/{skill_name}/execute
{
  "parameters": {...}
}
```

---

## Database Schema

### PostgreSQL Tables

**documents**
- `id` - UUID primary key
- `content` - TEXT
- `metadata` - JSONB
- `created_at` - TIMESTAMP
- `updated_at` - TIMESTAMP

**embeddings**
- `id` - UUID primary key
- `document_id` - UUID (foreign key)
- `vector` - VECTOR(1536)
- `model` - TEXT
- `created_at` - TIMESTAMP

**inference_logs**
- `id` - UUID primary key
- `prompt` - TEXT
- `completion` - TEXT
- `model` - TEXT
- `tokens` - INTEGER
- `latency_ms` - INTEGER
- `created_at` - TIMESTAMP

### Qdrant Collections

**documents**
- Vector size: 1536 (OpenAI ada-002 compatible)
- Distance: Cosine
- Indexed: Yes

---

## Development

### Running Locally

```bash
# Install dependencies
cd ai-stack/mcp-servers/aidb
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://mcp:password@localhost:5432/mcp
export REDIS_URL=redis://localhost:6379
export QDRANT_URL=http://localhost:6333

# Run server
uvicorn server:app --reload --port 8091
```

### Running with Docker Compose

```bash
# Development mode (auto-reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Production mode
docker compose up -d aidb-mcp
```

### Testing

```bash
# Health check
curl http://localhost:8091/health

# API documentation
open http://localhost:8091/docs

# Interactive API
open http://localhost:8091/redoc
```

---

## Dependencies

See [`requirements.txt`](requirements.txt) for complete list.

**Key Dependencies:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM
- `psycopg2-binary` - PostgreSQL driver
- `redis` - Redis client
- `qdrant-client` - Qdrant vector DB client
- `pydantic` - Data validation
- `httpx` - HTTP client

---

## Integration with llama.cpp

AIDB automatically connects to llama.cpp for model inference:

```python
# Automatic llama.cpp integration
response = await client.post(
    f"{LLAMA_CPP_BASE_URL}/completions",
    json={
        "model": model_id,
        "prompt": prompt,
        "max_tokens": 500
    }
)
```

---

## Skills Loading

Agent skills are automatically loaded from `../../agents/skills/`:

```python
# Skills are discovered and loaded at startup
skills = load_skills_from_directory("../../agents/skills/")

# Execute skill
result = await execute_skill("nixos-deployment", parameters)
```

---

## Monitoring

### Logs

```bash
# Container logs
docker logs -f ai-stack-aidb

# Application logs
tail -f ~/.cache/nixos-ai-stack/logs/aidb.log
```

### Metrics

Access Prometheus metrics at:
```
http://localhost:8091/metrics
```

### Health Checks

```bash
# Overall health
curl http://localhost:8091/health

# Database connection
curl http://localhost:8091/health/database

# Redis connection
curl http://localhost:8091/health/redis

# Qdrant connection
curl http://localhost:8091/health/qdrant
```

---

## Troubleshooting

### Connection Refused

**Problem:** `Connection refused` when accessing http://localhost:8091

**Solution:**
```bash
# Check if service is running
docker ps | grep aidb

# Check logs
docker logs ai-stack-aidb

# Restart service
docker compose restart aidb-mcp
```

### Database Migration Errors

**Problem:** Database schema errors

**Solution:**
```bash
# Apply migrations
docker compose exec aidb-mcp alembic upgrade head

# Reset database (WARNING: data loss)
docker compose down -v
docker compose up -d
```

### Slow Performance

**Problem:** Slow API responses

**Solutions:**
1. Check database indexes
2. Verify Redis is caching
3. Monitor Qdrant performance
4. Check llama.cpp model load

```bash
# Check service health
./scripts/ai-stack-manage.sh health

# View metrics
curl http://localhost:8091/metrics
```

---

## API Documentation

Full API documentation available at:
- **OpenAPI/Swagger:** http://localhost:8091/docs
- **ReDoc:** http://localhost:8091/redoc
- **JSON Schema:** http://localhost:8091/openapi.json

---

## Security

### Authentication

AIDB supports multiple authentication methods:
- API Keys (recommended for production)
- JWT tokens
- OAuth2 (planned)

### Environment-Specific Security

```bash
# Development (no auth)
DEBUG=true

# Production (API key required)
AIDB_API_KEY=your-secure-key
AIDB_REQUIRE_AUTH=true
```

---

## Performance

### Benchmarks

| Operation | Latency | Throughput |
|-----------|---------|------------|
| Document insert | ~10ms | 100 req/s |
| Vector search | ~50ms | 20 req/s |
| Inference (7B model) | ~500ms | 2 req/s |
| Parallel inference (3 models) | ~600ms | 1.5 req/s |

### Optimization Tips

1. **Use Redis caching** - Cache frequent queries
2. **Batch operations** - Group document inserts
3. **Index optimization** - Add indexes for common queries
4. **Connection pooling** - Reuse database connections
5. **Parallel inference** - Use multiple models concurrently

---

## Contributing

See main [IMPLEMENTATION-CHECKLIST.md](../../../../IMPLEMENTATION-CHECKLIST.md) for development roadmap.

---

## License

MIT License - Part of NixOS-Dev-Quick-Deploy v6.0.0

---

## Links

- [Main Integration Docs](../../../../docs/AI-STACK-FULL-INTEGRATION.md)
- [AI Stack README](../../README.md)
- [Model Registry](../../models/registry.json)
- [Agent Skills](../../agents/skills/)
- [API Documentation](../../../docs/API.md) (coming soon)
