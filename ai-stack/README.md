# AI Stack - Integrated AI Development Environment

**Version:** 1.0.0 (integrated with NixOS-Dev-Quick-Deploy v6.0.0)
**Status:** ✅ Public, First-Class Component

This directory contains the complete AI development stack, fully integrated into NixOS-Dev-Quick-Deploy.

## Overview

The AI stack provides:
- **AIDB MCP Server** - PostgreSQL + TimescaleDB + Qdrant vector database + FastAPI MCP server
- **Lemonade vLLM** - Local OpenAI-compatible model inference
- **Agentic Skills** - Specialized AI agents for deployment, testing, code review, and more
- **MCP Servers** - Model Context Protocol servers for NixOS, GitHub, and custom integrations
- **Model Management** - Model registry, download scripts, and version control

## Quick Start

```bash
# Deploy AI stack (from repo root)
./nixos-quick-deploy.sh --with-ai-stack

# Manage AI stack
./scripts/ai-stack-manage.sh up      # Start services
./scripts/ai-stack-manage.sh status  # Check status
./scripts/ai-stack-manage.sh logs    # View logs
./scripts/ai-stack-manage.sh health  # Run health checks
```

## Directory Structure

```
ai-stack/
├── compose/                 # Docker Compose configurations
│   ├── docker-compose.yml   # Full production stack
│   ├── docker-compose.dev.yml  # Development overrides
│   ├── docker-compose.minimal.yml  # Minimal stack (Lemonade only)
│   └── .env.example         # Environment template
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
| Lemonade vLLM | 8080 | Model inference |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |
| Qdrant | 6333 | Vector database |
| Redis Insight | 5540 | Redis web UI |

## Data Persistence

All data is stored in shared directories that persist across reinstalls:

```
~/.local/share/nixos-ai-stack/
├── aidb/              # AIDB runtime data
├── telemetry/         # AIDB + coordinator telemetry events
├── postgres/          # PostgreSQL data
├── redis/             # Redis persistence
├── qdrant/            # Vector database
├── lemonade-models/   # Downloaded models
├── imports/           # Document imports
├── exports/           # Exported data
└── backups/           # Database backups
```

## Configuration

Active configuration:
- `~/.config/nixos-ai-stack/.env` - Environment variables
- `~/.config/nixos-ai-stack/ai-optimizer.json` - Integration metadata

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - Technical architecture details
- [API Reference](docs/API.md) - MCP server API documentation
- [Deployment Guide](docs/DEPLOYMENT.md) - Deployment and configuration
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
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
