# AI Stack - Integrated AI Development Environment

**Version:** 1.0.0 (integrated with NixOS-Dev-Quick-Deploy v6.0.0)
**Status:** ✅ Public, First-Class Component

This directory contains the complete AI development stack, fully integrated into NixOS-Dev-Quick-Deploy.

## Overview

The AI stack provides:
- **AIDB MCP Server** - PostgreSQL + TimescaleDB + Qdrant vector database + FastAPI MCP server
- **llama.cpp vLLM** - Local OpenAI-compatible model inference
- **Agentic Skills** - Specialized AI agents for deployment, testing, code review, and more
- **MCP Servers** - Model Context Protocol servers for NixOS, GitHub, and custom integrations
- **Model Management** - Model registry, download scripts, and version control

## Quick Start

```bash
# Deploy AI stack (from repo root)
./nixos-quick-deploy.sh --with-ai-stack

# Check AI stack status
kubectl get pods -n ai-stack

# View logs
kubectl logs -n ai-stack deployment/aidb --tail=100
```

## Directory Structure

```
ai-stack/
├── kubernetes/              # K3s manifests (generated + curated)
├── kustomize/               # Kustomize overlays (dev/prod/dev-agents)
├── mcp-servers/             # Model Context Protocol servers
│   ├── aidb/                # AIDB MCP server (PostgreSQL + Qdrant + FastAPI)
│   ├── nixos/               # NixOS-specific MCP server
│   └── github/              # GitHub integration MCP
├── agents/                  # Agentic AI skills
│   ├── orchestrator/        # Primary orchestrator agent
│   ├── skills/              # Specialized skills
│   └── shared/              # Shared agent utilities
├── models/                  # Model management
│   ├── registry.json        # Available models catalog
│   └── download.sh          # Model download script
├── database/                # Database schemas and migrations
│   ├── postgres/            # PostgreSQL schemas and migrations
│   ├── redis/               # Redis configuration
│   └── qdrant/              # Qdrant collection definitions
└── docs/                    # AI stack documentation
    ├── ARCHITECTURE.md
    ├── API.md
    ├── DEPLOYMENT.md
    └── TROUBLESHOOTING.md
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| AIDB MCP Server | 8091 | FastAPI MCP server |
| llama.cpp vLLM | 8080 | Model inference |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |
| Qdrant | 6333 | Vector database |
| Redis Insight | 5540 | Redis web UI |

## Service Dependencies

Startup dependencies are enforced with init containers in the K3s manifests to avoid race conditions.

```
Postgres ─┐
Redis    ├─> AIDB ─┐
Qdrant   ┘         ├─> Hybrid Coordinator ─┐
Embeddings ────────┘                       ├─> Ralph Wiggum
Postgres ──────────────────────────────────┘
Redis    ──────────────────────────────────┘
```

Dependency waits are defined in:
- `ai-stack/kubernetes/kompose/aidb-deployment.yaml`
- `ai-stack/kubernetes/kompose/hybrid-coordinator-deployment.yaml`
- `ai-stack/kubernetes/kompose/ralph-wiggum-deployment.yaml`

## Kustomize Overlays

- `dev`: development defaults
- `prod`: production-hardened defaults
- `dev-agents`: opt-in interactive agents (Aider)

Examples:

```bash
kubectl apply -k ai-stack/kustomize/overlays/dev
kubectl apply -k ai-stack/kustomize/overlays/dev-agents  # optional
```

## Data Persistence

K3s uses PersistentVolumeClaims for durable storage:

```bash
kubectl get pvc -n ai-stack
kubectl get pvc -n backups
```

## Configuration

Active configuration:
- `ai-stack/mcp-servers/config/config.yaml` - Base config for AIDB, embeddings, hybrid
- `ai-stack/mcp-servers/config/config.dev.yaml` - Dev overrides (set `STACK_ENV=dev`)
- `ai-stack/mcp-servers/config/config.staging.yaml` - Staging overrides (set `STACK_ENV=staging`)
- `ai-stack/mcp-servers/config/config.prod.yaml` - Prod overrides (set `STACK_ENV=prod`)
- `ai-stack/kubernetes/secrets/secrets.sops.yaml` - Encrypted secrets bundle (SOPS/age)
- `~/.config/nixos-ai-stack/ai-optimizer.json` - Integration metadata

Config overrides:
- `STACK_ENV` applies env-specific overlays for AIDB, embeddings, and hybrid
- `AIDB_CONFIG`, `EMBEDDINGS_CONFIG`, `HYBRID_CONFIG` override the config path

Required secrets are managed in the SOPS bundle:
```bash
sops ai-stack/kubernetes/secrets/secrets.sops.yaml
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - Technical architecture details
- [API Reference](docs/API.md) - MCP server API documentation
- [Deployment Guide](docs/DEPLOYMENT.md) - Deployment and configuration
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Database Migrations](migrations/README.md) - Alembic workflow and rollback testing
- [Main Integration Guide](../docs/AI-STACK-FULL-INTEGRATION.md) - Full integration documentation

## Migration

If you have an existing standalone AI-Optimizer installation:

```bash
# Automated migration (preserves all data)
./scripts/ai-stack-migrate.sh

# Dry run first
./scripts/ai-stack-migrate.sh --dry-run
```

See [Migration Guide](../docs/AI-STACK-FULL-INTEGRATION.md#4-migration-strategy) for details.

## Development

See [Implementation Checklist](../IMPLEMENTATION-CHECKLIST.md) for current development status.

---

**Part of:** NixOS-Dev-Quick-Deploy v6.0.0
**License:** MIT
