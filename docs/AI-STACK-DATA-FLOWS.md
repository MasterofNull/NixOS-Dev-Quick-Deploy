# AI Stack Data Flows

This document captures the current, implemented data flow for the deployed AI stack services.

## 1. RAG Pipeline Flow

```mermaid
flowchart LR
  U[User Query] --> HC[Hybrid Coordinator /query]
  HC --> AIDB[AIDB /query]
  AIDB --> PG[(PostgreSQL + pgvector)]
  AIDB --> QD[(Qdrant)]
  AIDB --> EMB[Embeddings Service /embed]
  EMB --> AIDB
  PG --> AIDB
  QD --> AIDB
  AIDB --> HC
  HC --> U
```

## 2. Task Execution Flow

```mermaid
sequenceDiagram
  participant C as Client
  participant R as Ralph Wiggum
  participant H as Hybrid Coordinator
  participant A as AIDB
  participant L as LLM Backend

  C->>R: Task request
  R->>H: Route/augment task context
  H->>A: Fetch relevant context
  A-->>H: Retrieved context
  H->>L: Inference request
  L-->>H: Model response
  H-->>R: Routed result
  R-->>C: Final task result
```

## 3. Health Monitoring Flow

```mermaid
flowchart TD
  HM[health-monitor] --> AIDB_H[AIDB /health]
  HM --> HYB_H[Hybrid /health]
  HM --> EMB_H[Embeddings /health]
  HM --> QD_H[Qdrant /healthz]
  HM --> LLAMA_H[llama.cpp /health]
  HM --> REDIS_H[Redis]
  HM --> PG_H[Postgres]
  HM --> OUT[Status + alerts + remediation hooks]
```

## 4. API Contracts (Primary)

| Service | Endpoint | Method | Contract Source |
|---|---|---|---|
| AIDB | `/health`, `/health/ready`, `/health/detailed` | `GET` | `ai-stack/mcp-servers/aidb/server.py` |
| AIDB | `/query` | `POST` | `ai-stack/mcp-servers/aidb/README.md` + service code |
| Hybrid Coordinator | `/health` | `GET` | `docs/api/hybrid-openapi.yaml`, `ai-stack/mcp-servers/hybrid-coordinator/server.py` |
| Hybrid Coordinator | `/query` | `POST` | `ai-stack/mcp-servers/hybrid-coordinator/server.py` |
| Hybrid Coordinator | `/augment_query` | `POST` | `docs/api/hybrid-openapi.yaml` |
| Embeddings Service | `/health`, `/embed` | `GET`, `POST` | `docs/api/embeddings-openapi.yaml` |
| Ralph Wiggum | `/health` | `GET` | `ai-stack/mcp-servers/ralph-wiggum/server.py` |

## 5. Data Transformation Notes

- Query text is normalized and context-augmented in Hybrid Coordinator before downstream retrieval/inference.
- AIDB retrieves from vector and relational stores, then assembles context for response generation.
- Embeddings service transforms raw text input into vector arrays used by retrieval workflows.

## 6. Validation Procedures

Run these to validate the documented flows:

```bash
# Service health
curl -sf http://localhost:8091/health
curl -sf http://localhost:8092/health
curl -sf http://localhost:8081/health

# Hybrid query path
curl -sf -X POST http://localhost:8092/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"health check","context":"minimal"}'
```

Kubernetes check path:

```bash
kubectl get pods -n ai-stack
kubectl get svc -n ai-stack
```

## 7. Troubleshooting

- `Hybrid /query` fails:
  - verify `ai-stack/mcp-servers/hybrid-coordinator/server.py` routes and service pod logs.
- Retrieval quality drops:
  - verify embeddings service health and embedding dimensions.
- Slow responses:
  - inspect dependency health (`Postgres`, `Qdrant`, `Redis`) and model backend latency.

## 8. Performance Considerations

- Keep embeddings model warm to reduce first-query latency.
- Avoid oversized context windows for frequent low-complexity queries.
- Monitor vector DB latency and memory pressure under concurrent load.
- Prefer local in-cluster service addressing to avoid unnecessary egress hops.
