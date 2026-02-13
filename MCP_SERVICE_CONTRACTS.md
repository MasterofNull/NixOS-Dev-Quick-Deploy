# MCP Service Contracts and Health Endpoints

## Standardized MCP Service Contracts for All Agents

This document defines the standardized Model Context Protocol (MCP) service contracts and health endpoints for all agents in the NixOS AI Stack.

### Standard MCP Service Contract Template

All MCP services in the AI stack should implement the following standard endpoints:

#### Core Endpoints
```
GET  /health          - Health check endpoint
GET  /health/ready    - Readiness probe
GET  /health/live     - Liveness probe  
GET  /health/startup  - Startup probe
GET  /metrics         - Prometheus metrics
GET  /discovery       - Service discovery
POST /query           - Main query endpoint
GET  /capabilities    - Available capabilities
```

### Individual Service Contracts

#### 1. AIDB MCP Server (Port 8091)
- **Base URL**: `http://aidb.ai-stack.svc.cluster.local:8091`

**Endpoints**:
```
GET  /health                          - Overall health status
GET  /health/live                     - Liveness probe
GET  /health/ready                    - Readiness probe  
GET  /metrics                         - Prometheus metrics
GET  /discovery                       - System capabilities
GET  /discovery/capabilities          - Available capabilities
GET  /discovery/quickstart            - Quick start guide
GET  /documents?search={query}        - Semantic search
GET  /documents                       - List documents
POST /documents                       - Import document
POST /vector/search                   - Vector similarity search
GET  /telemetry/summary               - Telemetry summary
POST /telemetry/probe                 - Telemetry probe
GET  /skills/list                     - Available skills
GET  /skills/{name}                   - Skill details
POST /skills/{name}/execute           - Execute skill
POST /tools/execute                   - Execute tool
GET  /ml/models                       - Available ML models
```

**Health Response Format**:
```json
{
  "status": "healthy",
  "version": "2.1.0",
  "database": "ok",
  "redis": "ok", 
  "qdrant": "ok",
  "circuit_breakers": "CLOSED",
  "dependencies": {
    "postgres": "connected",
    "redis": "connected", 
    "qdrant": "connected"
  }
}
```

#### 2. Hybrid Coordinator (Port 8092)
- **Base URL**: `http://hybrid-coordinator.ai-stack.svc.cluster.local:8092`

**Endpoints**:
```
GET  /health                          - Overall health status
GET  /health/live                     - Liveness probe
GET  /health/ready                    - Readiness probe
GET  /metrics                         - Prometheus metrics  
GET  /query                           - Hybrid query endpoint
POST /query                           - Execute hybrid query
GET  /collections                     - Available collections
GET  /collections/{name}/stats        - Collection statistics
POST /collections/{name}/search       - Search in collection
GET  /learning/stats                  - Learning statistics
GET  /patterns                        - Learned patterns
GET  /gc/stats                        - Garbage collection stats
POST /gc/run                          - Trigger garbage collection
GET  /telemetry                       - Telemetry events
POST /telemetry                       - Record telemetry event
```

**Health Response Format**:
```json
{
  "status": "healthy", 
  "version": "1.0.0",
  "learning_engine": "running",
  "garbage_collector": "running",
  "telemetry_processor": "running",
  "dependencies": {
    "postgres": "connected",
    "redis": "connected",
    "qdrant": "connected", 
    "aidb": "reachable",
    "embeddings": "reachable"
  }
}
```

#### 3. Ralph Wiggum (Port 8098)
- **Base URL**: `http://ralph-wiggum.ai-stack.svc.cluster.local:8098`

**Endpoints**:
```
GET  /health                          - Overall health status
GET  /health/live                     - Liveness probe
GET  /health/ready                    - Readiness probe
GET  /metrics                         - Prometheus metrics
POST /tasks                           - Create new task
GET  /tasks/{task_id}                 - Get task status
GET  /tasks/{task_id}/result          - Get task result
POST /tasks/{task_id}/stop            - Stop task
POST /tasks/{task_id}/approve         - Approve task
GET  /stats                           - Ralph statistics
GET  /config                          - Current configuration
PUT  /config                          - Update configuration
```

**Health Response Format**:
```json
{
  "status": "healthy",
  "version": "1.0.0", 
  "loop_enabled": true,
  "active_tasks": 2,
  "backends": ["aider", "continue-server", "goose", "autogpt", "langchain"],
  "dependencies": {
    "aidb": "reachable",
    "hybrid_coordinator": "reachable",
    "postgres": "reachable",
    "redis": "reachable"
  }
}
```

#### 4. Embeddings Service (Port 8081)
- **Base URL**: `http://embeddings.ai-stack.svc.cluster.local:8081`

**Endpoints**:
```
GET  /health                          - Overall health status
GET  /health/live                     - Liveness probe  
GET  /health/ready                    - Readiness probe
GET  /metrics                         - Prometheus metrics
POST /embeddings/generate             - Generate embeddings
POST /embeddings/similarity           - Calculate similarity
POST /embeddings/batch               - Batch embedding generation
GET  /models                          - Available models
GET  /models/{name}/info              - Model information
POST /text/chunk                      - Text chunking
GET  /config                          - Configuration
```

**Health Response Format**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "model_loaded": "BAAI/bge-small-en-v1.5",
  "dimensions": 384,
  "model_status": "ready",
  "batch_processor": "running"
}
```

#### 5. NixOS Docs Service (Port 8094)
- **Base URL**: `http://nixos-docs.ai-stack.svc.cluster.local:8094`

**Endpoints**:
```
GET  /health                          - Overall health status
GET  /health/live                     - Liveness probe
GET  /health/ready                    - Readiness probe  
GET  /metrics                         - Prometheus metrics
GET  /search?q={query}                - Search documentation
GET  /sources                         - Available sources
GET  /sources/{name}/docs             - Documents from source
GET  /cache/stats                     - Cache statistics
POST /sync                            - Sync documentation sources
GET  /config                          - Configuration
```

**Health Response Format**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "sources_synced": 8,
  "documents_indexed": 1247,
  "cache_status": "healthy",
  "dependencies": {
    "redis": "connected"
  }
}
```

### Standard Health Check Implementation

All services should implement the following health check patterns:

#### Liveness Probe
- Purpose: Determine if the container should be restarted
- Endpoint: `/health/live` or `/health`
- Timeout: 5 seconds
- Success: HTTP 200 with status "healthy"

#### Readiness Probe  
- Purpose: Determine if the container is ready to accept traffic
- Endpoint: `/health/ready`
- Timeout: 3 seconds  
- Success: HTTP 200 with status "ready" and all dependencies healthy

#### Startup Probe
- Purpose: Determine if the container has started successfully
- Endpoint: `/health/startup`
- Timeout: 10 seconds
- Higher failure threshold (30) to allow for slow startups

### Health Check Response Schema

Standard response format for all health endpoints:

```json
{
  "status": "healthy|ready|degraded|unhealthy",
  "timestamp": "2026-01-26T10:00:00Z",
  "version": "string",
  "service": "service-name",
  "dependencies": {
    "dependency-name": "status"
  },
  "details": {
    "memory_usage_mb": 123,
    "uptime_seconds": 3600,
    "active_connections": 5
  }
}
```

### Agent Integration Guidelines

#### Authentication
- All services support API key authentication via `X-API-Key` header
- API keys stored in Kubernetes secrets
- Services should implement rate limiting

#### Error Handling
- Standard error response format:
```json
{
  "error": "error_code",
  "message": "descriptive error message", 
  "details": {...}
}
```

#### Rate Limiting
- All services implement rate limiting to prevent abuse
- Standard headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`

This defines the standardized MCP service contracts for all agents in the system.