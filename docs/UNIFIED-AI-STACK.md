# Unified AI Stack - Single Source of Truth

**Version**: 2.0.0 (Unified)
**Date**: 2025-12-20
**Status**: ✅ Production Ready

## 🎯 Overview

The NixOS Hybrid AI Learning Stack is now **fully unified** into a single, cohesive system. All parallel configurations, duplicate files, and fragmented setups have been consolidated into **ONE source of truth**.

## 📍 Single Source of Truth

**Configuration File**: [`ai-stack/compose/docker-compose.yml`](/ai-stack/compose/docker-compose.yml)

This is the **ONLY** docker-compose configuration. All other variants have been removed.

## 🏗️ Unified Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Single Unified AI Stack                       │
│                 (docker-compose.yml)                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
    ┌───▼────┐         ┌────▼───┐         ┌────▼────┐
    │Qdrant  │         │Ollama  │         │llama.cpp │
    │Vector  │         │Embed   │         │Inference│
    │Database│         │Models  │         │GGUF     │
    └───┬────┘         └────┬───┘         └────┬────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
    ┌───▼────┐         ┌────▼───┐         ┌────▼────┐
    │Open    │         │Postgres│         │Redis    │
    │WebUI   │         │MCP DB  │         │Cache    │
    └────────┘         └────────┘         └─────────┘
```

## 📦 Services

All services run with consistent naming (`local-ai-*`) and labels (`nixos.quick-deploy.ai-stack=true`):

| Service | Container Name | Port | Purpose |
|---------|---------------|------|---------|
| **Qdrant** | `local-ai-qdrant` | 6333 | Vector database for embeddings |
| **Ollama** | `local-ai-ollama` | 11434 | Local LLM and embeddings |
| **llama.cpp** | `local-ai-llama-cpp` | 8080 | GGUF model inference |
| **Open WebUI** | `local-ai-open-webui` | 3001 | Web interface |
| **PostgreSQL** | `local-ai-postgres` | 5432 | MCP server database |
| **Redis** | `local-ai-redis` | 6379 | Caching and sessions |
| **MindsDB** | `local-ai-mindsdb` | 47334 | Analytics (optional) |

## 🔧 Management Scripts

### Primary Script

**[`scripts/hybrid-ai-stack.sh`](/scripts/hybrid-ai-stack.sh)** - Unified stack manager

```bash
# Start all services
./scripts/hybrid-ai-stack.sh up

# Check status
./scripts/hybrid-ai-stack.sh status

# View logs
./scripts/hybrid-ai-stack.sh logs

# Restart everything
./scripts/hybrid-ai-stack.sh restart
```

### Automated Deployment

**[`scripts/setup-hybrid-learning-auto.sh`](/scripts/setup-hybrid-learning-auto.sh)** - Non-interactive setup

This runs automatically during `nixos-quick-deploy.sh --with-ai-stack`:
1. Installs Python dependencies in venv
2. Configures environment variables
3. Creates all required directories
4. Starts all containers
5. Initializes Qdrant collections
6. Verifies services

**No user prompts required** - fully automated!

## 🚀 Deployment

### Automatic (Recommended)

Run the full deployment:

```bash
./nixos-quick-deploy.sh --with-ai-stack
```

Phase 9 will automatically:
- Download GGUF models (~10.5GB)
- Setup hybrid learning system
- Initialize all services
- Configure Qdrant collections
- Display dashboard link

### Manual

If you need to manage services independently:

```bash
# Start stack
cd ai-stack/compose
podman-compose up -d

# Or use helper
./scripts/hybrid-ai-stack.sh up
```

## 📊 Data Storage

All data stored in: `~/.local/share/nixos-ai-stack/`

```
~/.local/share/nixos-ai-stack/
├── qdrant/              # Vector database data
├── ollama/              # Ollama models and config
├── llama-cpp-models/     # GGUF models (~10.5GB)
├── open-webui/          # WebUI data and chats
├── postgres/            # PostgreSQL database
├── redis/               # Redis persistence
├── fine-tuning/         # Generated training datasets
└── mindsdb/             # MindsDB storage (optional)
```

## 🎓 Features

All hybrid learning features are integrated into the single unified system:

### ✅ Core Capabilities

- **Context Augmentation**: Local Qdrant provides context to reduce remote API costs
- **Interaction Tracking**: All queries/responses logged for learning
- **Value Scoring**: Automatic identification of high-value interactions
- **Pattern Extraction**: Reusable patterns extracted from successful interactions
- **Fine-tuning Datasets**: Automatically generated from high-value data
- **Multi-node Federation**: Sync knowledge across multiple deployments

### ✅ Qdrant Collections

5 specialized collections for hybrid learning:

1. **codebase-context** - Code snippets and project context
2. **skills-patterns** - Reusable patterns from interactions
3. **error-solutions** - Solutions to common errors
4. **best-practices** - Curated best practices
5. **interaction-history** - Complete interaction log

## 🔍 Monitoring

### Dashboard

Open in browser: [`ai-stack/dashboard/index.html`](/ai-stack/dashboard/index.html)

Features:
- Real-time service health checks
- Learning metrics (interactions, patterns, solutions)
- Token savings calculator
- Federation status
- Links to all documentation

### Health Checks

```bash
# Check all services
./scripts/hybrid-ai-stack.sh status

# Individual service checks
curl http://localhost:6333/healthz      # Qdrant
curl http://localhost:8080/health       # llama.cpp
curl http://localhost:11434/api/tags    # Ollama
curl http://localhost:3001              # WebUI
```

## 📝 Configuration

### Environment Variables

Edit: [`ai-stack/compose/.env`](/ai-stack/compose/.env)

Key variables:
```bash
AI_STACK_DATA=~/.local/share/nixos-ai-stack
LLAMA_CPP_DEFAULT_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
POSTGRES_PASSWORD=change_me_in_production
HYBRID_MODE_ENABLED=true
HIGH_VALUE_THRESHOLD=0.7
PATTERN_EXTRACTION_ENABLED=true
```

### Customization

To modify services, edit the **single source of truth**:
```bash
vim ai-stack/compose/docker-compose.yml
```

Then reload:
```bash
./scripts/hybrid-ai-stack.sh restart
```

## 🗑️ What Was Removed

Eliminated duplicate/fragmented configurations:

- ❌ `docker-compose.hybrid.yml` (merged into main)
- ❌ `docker-compose.dev.yml` (redundant)
- ❌ `docker-compose.minimal.yml` (incomplete)
- ❌ Parallel profile systems
- ❌ Multiple competing setups

## ✨ Benefits of Unification

1. **Single Source of Truth** - One file to manage, no confusion
2. **Consistent Naming** - All containers use `local-ai-*` prefix
3. **Unified Labels** - Easy filtering with `nixos.quick-deploy.ai-stack=true`
4. **Automated Deployment** - No manual steps required
5. **Complete Feature Set** - All capabilities in one system
6. **Easier Maintenance** - Update once, applies everywhere
7. **Better Documentation** - Clear, unambiguous setup

## 📚 Documentation

Complete guide to the unified system:

- **This File**: Overview and reference
- **[DEPLOYMENT-STATUS.md](/docs/archive/DEPLOYMENT-STATUS.md)**: Current deployment status
- **[AI-AGENT-SETUP.md](AI-AGENT-SETUP.md)**: Quick start guide
- **[HYBRID-AI-SYSTEM-GUIDE.md](HYBRID-AI-SYSTEM-GUIDE.md)**: Complete implementation guide
- **[DISTRIBUTED-LEARNING-GUIDE.md](DISTRIBUTED-LEARNING-GUIDE.md)**: Multi-node federation
- **[SYSTEM-DASHBOARD-README.md](SYSTEM-DASHBOARD-README.md)**: Dashboard documentation

## 🔄 Migration from Old Setups

If you had previous parallel configurations:

1. Stop all old containers:
   ```bash
   podman stop $(podman ps -aq --filter "label=nixos.quick-deploy.ai-stack=true")
   ```

2. Pull latest code:
   ```bash
   git pull
   ```

3. Start unified stack:
   ```bash
   ./scripts/hybrid-ai-stack.sh up
   ```

4. Verify:
   ```bash
   ./scripts/hybrid-ai-stack.sh status
   ```

Data is preserved in `~/.local/share/nixos-ai-stack/`

## 🎯 Next Steps

1. **Test the unified system**:
   ```bash
   ./scripts/hybrid-ai-stack.sh status
   firefox ai-stack/dashboard/index.html
   ```

2. **Try Open WebUI**: Visit http://localhost:3001

3. **Run automated deployment**:
   ```bash
   ./nixos-quick-deploy.sh --with-ai-stack
   ```

4. **Explore hybrid learning**: See [HYBRID-AI-SYSTEM-GUIDE.md](HYBRID-AI-SYSTEM-GUIDE.md)

## ✅ Success Criteria

Unified system is successful when:

- ✅ ONE docker-compose.yml file (no variants)
- ✅ All services use consistent naming
- ✅ Automated deployment works without prompts
- ✅ All features integrated (no parallel systems)
- ✅ Scripts reference single source of truth
- ✅ Documentation is clear and unambiguous

**Current Status**: ✅ **ALL CRITERIA MET**

---

**The system is now fully unified and production-ready!** 🎉
