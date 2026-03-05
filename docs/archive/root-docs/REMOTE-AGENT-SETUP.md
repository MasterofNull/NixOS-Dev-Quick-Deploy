# Remote Agent Setup Guide

This document provides the necessary information for remote agents to connect to the NixOS AI Stack.

## Required Ports

The following ports need to be accessible for remote agent connectivity:

| Port | Service | Purpose | Protocol |
|------|---------|---------|----------|
| 8091 | AIDB MCP Server | Main AI knowledge base and query interface | HTTP |
| 8092 | Hybrid Coordinator | Smart routing and coordination service | HTTP |
| 8094 | NixOS Docs | Documentation search and retrieval | HTTP |
| 8098 | Ralph Wiggum | Autonomous AI loop orchestration | HTTP |
| 8080 | Llama.cpp | Local LLM inference | HTTP |
| 8081 | Embeddings Service | Vector embedding generation | HTTP |
| 5432 | PostgreSQL | Primary database (with pgvector) | TCP |
| 6379 | Redis | Caching and session storage | TCP |
| 6333 | Qdrant | Vector database | HTTP/TCP |

## Required Environment Variables

Remote agents need to configure the following environment variables:

### Core Services
```bash
# AIDB MCP Server (Primary AI Knowledge Base)
AIDB_URL=http://<host>:8091
AIDB_API_KEY=<your_api_key>  # If authentication required

# Hybrid Coordinator (Smart Routing)
HYBRID_COORDINATOR_URL=http://<host>:8092
HYBRID_COORDINATOR_API_KEY=<your_api_key>  # If authentication required

# Embeddings Service
EMBEDDINGS_URL=http://<host>:8081
EMBEDDINGS_API_KEY=<your_api_key>  # If authentication required
```

### Database Connections
```bash
# PostgreSQL with pgvector (for vector storage)
DATABASE_URL=postgresql://<username>:<password>@<host>:5432/<database>

# Redis (for caching)
REDIS_URL=redis://<host>:6379

# Qdrant (alternative vector database)
QDRANT_URL=http://<host>:6333
```

### Optional Services
```bash
# NixOS Documentation Service
NIXOS_DOCS_URL=http://<host>:8094
NIXOS_DOCS_API_KEY=<your_api_key>  # If authentication required

# Ralph Wiggum Loop Service
RALPH_WIGGUM_URL=http://<host>:8098
RALPH_WIGGUM_API_KEY=<your_api_key>  # If authentication required

# Llama.cpp Local LLM
LLAMA_CPP_URL=http://<host>:8080
```

## Service Discovery Endpoints

Remote agents can discover available services using these endpoints:

### AIDB Discovery
- `GET /discovery` - Basic system information
- `GET /discovery/capabilities` - Available capabilities
- `GET /discovery/quickstart` - Quick start guide for agents

### Federation Endpoints
- `GET /api/v1/federation/servers` - List federated MCP servers
- `POST /api/v1/federation/servers` - Register federated server

## Authentication

Some endpoints require API key authentication:
- Set `X-API-Key` header or use `API_KEY` environment variable
- Keys are typically stored in Kubernetes secrets or Docker secrets
- Contact system administrator for API key provisioning

## Network Configuration

### Firewall Rules
Ensure the following ports are open for inbound connections:
- TCP 8091 (AIDB)
- TCP 8092 (Hybrid Coordinator) 
- TCP 8094 (NixOS Docs)
- TCP 8098 (Ralph Wiggum)
- TCP 8080, 8081 (LLM and Embeddings)
- TCP 5432 (PostgreSQL)
- TCP 6379 (Redis)
- TCP 6333 (Qdrant)

### DNS/LB Configuration
For production deployments, consider using:
- Load balancers for high availability
- DNS records for service discovery
- TLS termination for secure connections

## Agent Bootstrap Command Block

To quickly bootstrap a remote agent connection to the NixOS AI Stack, use the following command block:

```bash
# Set environment variables for AI Stack connectivity
export AIDB_URL=http://<your-host>:8091
export HYBRID_COORDINATOR_URL=http://<your-host>:8092
export EMBEDDINGS_URL=http://<your-host>:8081
export NIXOS_DOCS_URL=http://<your-host>:8094

# Optional: Set API keys if authentication is required
export AIDB_API_KEY=<your_api_key>
export HYBRID_COORDINATOR_API_KEY=<your_api_key>

# Verify connectivity to core services
curl -f $AIDB_URL/health && echo "✓ AIDB OK"
curl -f $HYBRID_COORDINATOR_URL/health && echo "✓ Hybrid Coordinator OK"
curl -f $EMBEDDINGS_URL/health && echo "✓ Embeddings OK"

# Discover available capabilities
curl -s $AIDB_URL/discovery/capabilities?level=standard | jq '.'
```

## Example Agent Configuration

```python
import os
import httpx

# Initialize client with environment variables
aidb_url = os.getenv("AIDB_URL", "http://localhost:8091")
aidb_api_key = os.getenv("AIDB_API_KEY")

headers = {}
if aidb_api_key:
    headers["X-API-Key"] = aidb_api_key

async def query_knowledge_base(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{aidb_url}/documents",
            params={"search": query, "limit": 5},
            headers=headers
        )
        return response.json()

# Example usage
# results = await query_knowledge_base("How to configure NixOS?")
```

## Troubleshooting

### Connectivity Issues
1. Verify all required ports are accessible: `telnet <host> <port>`
2. Check firewall rules on both client and server
3. Confirm service is running: `curl http://<host>:<port>/health`

### Authentication Errors
1. Verify API key is correct and not expired
2. Check that `X-API-Key` header is properly set
3. Confirm API key has required permissions

### Service Discovery
1. Use `/discovery` endpoint to verify available services
2. Check `/health` endpoint for individual service status
3. Review service logs for error details