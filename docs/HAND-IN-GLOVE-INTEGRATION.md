# Hand-in-Glove Integration: NixOS ↔ AI-Optimizer
# Version: 6.0.0
# Date: 2025-11-22

## Overview

This document describes the seamless "hand-in-glove" integration between **NixOS-Dev-Quick-Deploy** (the hand) and **AI-Optimizer AIDB MCP** (the glove).

**Metaphor:**
- **Hand (NixOS)**: Fully functional, standalone system
- **Glove (AI-Optimizer)**: Optional enhancement that fits perfectly over the hand
- **Integration**: Zero conflicts, shared persistent data, seamless workflow

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        NixOS-Dev-Quick-Deploy                           │
│                        (The Hand - Fully Functional)                    │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ Phase 1-8: Complete NixOS Deployment                           │   │
│  │ • System initialization                                         │   │
│  │ • Configuration generation                                      │   │
│  │ • Package installation                                          │   │
│  │ • GPU detection & drivers                                       │   │
│  │ • Home Manager                                                  │   │
│  │ • Validation                                                    │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ Phase 9: AI-Optimizer Preparation (Optional)                   │   │
│  │ • Create shared data directories                               │   │
│  │ • Verify Docker/Podman prerequisites                           │   │
│  │ • Check port conflicts                                          │   │
│  │ • Configure networking                                          │   │
│  │ • Save integration status                                       │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │
                           │ Ready for AI-Optimizer
                           │
┌──────────────────────────▼───────────────────────────────────────────────┐
│                        AI-Optimizer AIDB MCP                             │
│                        (The Glove - Optional Enhancement)                │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ User Installs (Manual)                                          │   │
│  │ 1. git clone <your-repo> ~/Documents/AI-Optimizer             │   │
│  │ 2. cp .env.example .env                                         │   │
│  │ 3. docker compose -f docker-compose.new.yml up -d              │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ Services (Automatic)                                            │   │
│  │ • vLLM Inference (port 8000)                                   │   │
│  │ • AIDB MCP Server (ports 8091, 8791)                           │   │
│  │ • PostgreSQL + TimescaleDB (port 5432)                         │   │
│  │ • Redis + AOF (port 6379)                                      │   │
│  │ • Redis Insight (port 5540)                                     │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ Shared Persistent Data (survives reinstalls)                   │   │
│  │ • ~/.local/share/ai-optimizer/                                 │   │
│  │   ├── postgres/    (PostgreSQL database)                       │   │
│  │   ├── redis/       (Redis AOF + RDB)                          │   │
│  │   ├── qdrant/      (Vector database)                          │   │
│  │   ├── vllm-models/ (Downloaded LLM models)                    │   │
│  │   ├── imports/     (Imported documents)                        │   │
│  │   └── exports/     (Exported data)                            │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Key Principles

### 1. Zero Conflicts

✅ **NixOS services DO NOT conflict with AI-Optimizer**
- NixOS-Dev uses system Podman for local services (Ollama, Qdrant, etc.)
- AI-Optimizer uses Docker/Podman with isolated bridge network (`aidb-network`)
- No port conflicts (different ports)
- No container name conflicts (different naming)

### 2. Shared Persistent Data

✅ **Data persists across AI-Optimizer reinstalls**
- All AI-Optimizer data stored in: `~/.local/share/ai-optimizer/`
- All AI-Optimizer config stored in: `~/.config/ai-optimizer/`
- Symlinked from AI-Optimizer repository
- Safe to delete/update AI-Optimizer repo without losing data

### 3. Seamless Workflow

✅ **Step 1: Install NixOS-Dev-Quick-Deploy** (the hand)
```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh
# Complete all 9 phases
```

✅ **Step 2: Install AI-Optimizer** (the glove)
```bash
git clone <your-private-repo> ~/Documents/AI-Optimizer
cd ~/Documents/AI-Optimizer
cp .env.example .env
docker compose -f docker-compose.new.yml up -d
```

✅ **Step 3: Use AI Features**
```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
source lib/ai-optimizer.sh
ai_interactive_help
```

---

## Phase 9: AI-Optimizer Preparation

### Purpose

Phase 9 prepares the NixOS system to be "glove-ready" without installing AI-Optimizer:

1. **Create shared data directories** with proper permissions
2. **Verify Docker/Podman** is available and working
3. **Check for port conflicts** with AI-Optimizer services
4. **Configure container networking** for bridge networks
5. **Verify GPU acceleration** (NVIDIA container toolkit)
6. **Save integration status** for reference

### What Phase 9 Does NOT Do

❌ Clone AI-Optimizer repository
❌ Deploy AI-Optimizer services
❌ Download LLM models
❌ Start containers

**Why?** AI-Optimizer is YOUR private tool. You control when/how it's installed.

### Phase 9 Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NixOS System Prepared for AI-Optimizer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The "hand" (NixOS) is ready to receive the "glove" (AI-Optimizer).

Shared data directories created:
  • Data:   /home/user/.local/share/ai-optimizer
  • Config: /home/user/.config/ai-optimizer

Next Steps:
  1. Clone AI-Optimizer (your private repository)
  2. Configure .env file
  3. Deploy with docker-compose
  4. Use AI features in deployment scripts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Shared Persistent Data Layer

### Directory Structure

```
~/.local/share/ai-optimizer/
├── postgres/           # PostgreSQL database files
│   └── (TimescaleDB + pgvector data)
├── redis/              # Redis persistence
│   ├── appendonly.aof  # AOF log
│   └── dump.rdb        # RDB snapshot
├── qdrant/             # Qdrant vector database (optional)
│   └── storage/
├── vllm-models/        # Downloaded LLM models (HuggingFace cache)
│   ├── Qwen/
│   ├── deepseek-ai/
│   └── microsoft/
├── imports/            # Imported documents and catalogs
│   └── imported_docs.json
├── exports/            # Exported data and reports
└── backups/            # Database backups

~/.config/ai-optimizer/
├── config.yaml         # AIDB MCP Server config
├── .env                # Environment variables (symlinked from AI-Optimizer)
└── settings.json       # User preferences
```

### Why Shared Persistence?

**Problem:** If AI-Optimizer is reinstalled, all data is lost

**Solution:** Persistent data lives OUTSIDE the AI-Optimizer repository

**Benefits:**
- ✅ Reinstall AI-Optimizer without losing data
- ✅ Update AI-Optimizer with `git pull` safely
- ✅ Multiple NixOS installations share same AI-Optimizer data
- ✅ Easy backups (just backup `~/.local/share/ai-optimizer/`)

---

## Integration Hooks

### NixOS-Side Hooks (`lib/ai-optimizer-hooks.sh`)

**Purpose:** Prepare system, detect conflicts, create directories

**Functions:**
```bash
check_docker_podman_ready()          # Verify container runtime
check_nvidia_container_toolkit()     # Verify GPU toolkit
prepare_shared_data_directories()    # Create persistent dirs
detect_port_conflicts()              # Check for conflicts
ensure_docker_network_ready()        # Verify networking
save_integration_status()            # Save state
check_ai_optimizer_installed()       # Detect AI-Optimizer
get_ai_optimizer_status()            # running/stopped/not_installed
show_ai_optimizer_info()             # Display status
```

### AI-Optimizer-Side Hooks

**Your AI-Optimizer should:**
1. Use `POSTGRES_DATA_DIR`, `REDIS_DATA_DIR`, etc. from `.env`
2. Mount volumes from `~/.local/share/ai-optimizer/`
3. Create symlink from `deployment/data/` to shared directory
4. Respect existing services on ports 5432, 6379, etc.

**Example docker-compose.new.yml:**
```yaml
volumes:
  postgres:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${POSTGRES_DATA_DIR:-~/.local/share/ai-optimizer/postgres}

  redis:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${REDIS_DATA_DIR:-~/.local/share/ai-optimizer/redis}

  vllm-models:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${VLLM_MODELS_DIR:-~/.local/share/ai-optimizer/vllm-models}
```

---

## Integration with Deployment Scripts

### Using AI Features in NixOS-Dev

**After AI-Optimizer is installed:**

```bash
#!/usr/bin/env bash
cd ~/Documents/NixOS-Dev-Quick-Deploy

# Load AI integration library
source lib/ai-optimizer.sh

# Check if AI-Optimizer is available
if ai_check_availability; then
    echo "AI-Optimizer is available!"

    # Generate NixOS config
    ai_generate_nix_config "Enable PostgreSQL with TimescaleDB"

    # Review existing config
    ai_review_config ~/.dotfiles/home-manager/configuration.nix

    # Ask for help
    ai_chat "How do I configure GPU passthrough for VMs?"

    # Interactive assistant
    ai_interactive_help
else
    echo "AI-Optimizer not available (optional)"
    # Continue with normal deployment
fi
```

### Graceful Degradation

**If AI-Optimizer is NOT installed:**
- NixOS-Dev works perfectly fine (the hand is functional)
- AI features silently skip
- No errors, just informational messages
- User can install AI-Optimizer later

**If AI-Optimizer IS installed but stopped:**
- AI features return "unavailable" status
- User can start services manually
- Deployment continues normally

---

## Port Allocation

### NixOS-Dev Services

| Service | Port | Type |
|---------|------|------|
| Ollama (user) | 11434 | Podman user service |
| Qdrant (user) | 6333 | Podman user service |
| MindsDB (user) | 47334, 7735 | Podman user service |
| Open WebUI (user) | 8081 | Podman user service |

### AI-Optimizer Services

| Service | Port | Type |
|---------|------|------|
| vLLM | 8000 | Docker bridge network |
| AIDB MCP (HTTP) | 8091 | Docker bridge network |
| AIDB MCP (WebSocket) | 8791 | Docker bridge network |
| PostgreSQL | 5432 | Docker bridge network |
| Redis | 6379 | Docker bridge network |
| Redis Insight | 5540 | Docker bridge network |

**No conflicts:** Different services, different ports, different networks!

---

## Testing the Integration

### Test 1: NixOS-Dev Standalone

```bash
# Deploy NixOS without AI-Optimizer
cd ~/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh

# Choose "No" when Phase 9 asks about AI-Optimizer prep
# System should complete successfully (hand works alone)
```

**Expected:** ✅ All phases complete, NixOS fully functional

### Test 2: Prepare for AI-Optimizer

```bash
# Deploy NixOS with Phase 9 prep
cd ~/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh

# Choose "Yes" when Phase 9 asks about AI-Optimizer prep
# Shared directories created, prerequisites verified
```

**Expected:**
✅ Phase 9 completes
✅ Directories created: `~/.local/share/ai-optimizer/`
✅ Status saved: `~/.cache/nixos-quick-deploy/integration/ai-optimizer.json`

### Test 3: Install AI-Optimizer

```bash
# Clone AI-Optimizer
git clone <your-repo> ~/Documents/AI-Optimizer
cd ~/Documents/AI-Optimizer

# Configure
cp .env.example .env
nano .env  # Select model

# Deploy
docker compose -f docker-compose.new.yml up -d

# Wait for startup
docker compose -f docker-compose.new.yml logs -f
```

**Expected:**
✅ Containers start
✅ Data written to `~/.local/share/ai-optimizer/`
✅ Services accessible (ports 8091, 8000, etc.)

### Test 4: Use AI Features

```bash
# Test AI integration
cd ~/Documents/NixOS-Dev-Quick-Deploy
source lib/ai-optimizer.sh

# Check availability
ai_check_availability
# Should return 0 (success)

# Generate config
ai_generate_nix_config "Enable Docker with GPU support"
# Should return valid Nix code

# Interactive help
ai_interactive_help
# Should display menu
```

**Expected:** ✅ All AI features work

### Test 5: Reinstall AI-Optimizer

```bash
# Stop and remove AI-Optimizer
cd ~/Documents/AI-Optimizer
docker compose -f docker-compose.new.yml down

# Delete repository
cd ~
rm -rf ~/Documents/AI-Optimizer

# Clone again
git clone <your-repo> ~/Documents/AI-Optimizer
cd ~/Documents/AI-Optimizer

# Deploy (using same shared data)
cp .env.example .env
docker compose -f docker-compose.new.yml up -d
```

**Expected:**
✅ PostgreSQL database still has old data
✅ Redis cache still has old data
✅ vLLM models don't re-download
✅ All history preserved

---

## Backup Strategy

### What to Backup

**NixOS-Dev (hand):**
- Configuration files: `~/.dotfiles/home-manager/`
- Deployment state: `~/.cache/nixos-quick-deploy/`
- User data: `~/Documents/`, `~/Downloads/`, etc.

**AI-Optimizer (glove):**
- Shared data: `~/.local/share/ai-optimizer/` ⭐ **MOST IMPORTANT**
- Configuration: `~/.config/ai-optimizer/`
- Repository: `~/Documents/AI-Optimizer/` (can re-clone)

### Backup Commands

```bash
# Backup AI-Optimizer data
tar -czf ai-optimizer-backup-$(date +%Y%m%d).tar.gz \
    ~/.local/share/ai-optimizer \
    ~/.config/ai-optimizer

# Restore AI-Optimizer data
tar -xzf ai-optimizer-backup-YYYYMMDD.tar.gz -C ~/

# Result: Full AI-Optimizer state restored
```

---

## Troubleshooting

### Issue: Phase 9 says "Docker/Podman not available"

**Cause:** Virtualization not enabled in NixOS configuration

**Solution:**
```nix
# In configuration.nix
virtualisation.podman = {
  enable = true;
  dockerCompat = true;  # Provides 'docker' command
  defaultNetwork.settings.dns_enabled = true;
};

# Or for Docker:
virtualisation.docker.enable = true;
```

**Then:**
```bash
sudo nixos-rebuild switch
./nixos-quick-deploy.sh --start-from-phase 9
```

### Issue: AI-Optimizer fails to start

**Symptom:** `docker compose up -d` fails

**Causes:**
1. Port conflicts
2. Missing GPU drivers
3. Incorrect .env configuration

**Debug:**
```bash
# Check ports
ss -tuln | grep -E "5432|6379|8000|8091"

# Check GPU
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi

# Check logs
docker compose -f docker-compose.new.yml logs
```

### Issue: vLLM out of memory

**Symptom:** vLLM container crashes with OOM

**Solution:**
```bash
# Edit .env
VLLM_GPU_MEM=0.75  # Down from 0.85
VLLM_MAX_LEN=4096  # Down from 8192

# Or switch to smaller model
VLLM_MODEL=microsoft/Phi-3-mini-4k-instruct

# Restart
docker compose -f docker-compose.new.yml restart vllm
```

### Issue: Lost data after reinstall

**Cause:** Shared persistence not configured

**Check:**
```bash
# Verify shared directories exist
ls -la ~/.local/share/ai-optimizer/

# Verify AI-Optimizer uses them
cd ~/Documents/AI-Optimizer
grep POSTGRES_DATA_DIR .env
# Should point to ~/.local/share/ai-optimizer/postgres
```

**Fix:**
```bash
# Update .env to use shared directories
cat >> .env <<EOF
POSTGRES_DATA_DIR=$HOME/.local/share/ai-optimizer/postgres
REDIS_DATA_DIR=$HOME/.local/share/ai-optimizer/redis
VLLM_MODELS_DIR=$HOME/.local/share/ai-optimizer/vllm-models
EOF
```

---

## Best Practices

### 1. Always Run Phase 9

Even if you don't install AI-Optimizer immediately, run Phase 9:
- Creates shared directories
- Verifies prerequisites
- Documents system state
- Makes future AI-Optimizer installation easier

### 2. Use Shared Persistence

Never store AI-Optimizer data in the repository:
- ✅ Data in: `~/.local/share/ai-optimizer/`
- ❌ Data in: `~/Documents/AI-Optimizer/data/`

### 3. Backup Regularly

Backup `~/.local/share/ai-optimizer/` regularly:
- PostgreSQL database has all tool registrations
- Redis has all cached data
- vLLM models are 10-30GB (re-download takes time)

### 4. Test Before Reinstall

Before reinstalling AI-Optimizer:
```bash
# Backup data
tar -czf backup.tar.gz ~/.local/share/ai-optimizer

# Stop services
docker compose -f docker-compose.new.yml down

# Reinstall
rm -rf ~/Documents/AI-Optimizer
git clone <repo> ~/Documents/AI-Optimizer

# Deploy with same data
cd ~/Documents/AI-Optimizer
cp .env.example .env
docker compose -f docker-compose.new.yml up -d

# Verify data survived
docker exec -it mcp-postgres psql -U mcp -d mcp -c "SELECT COUNT(*) FROM tools;"
```

---

## Migration Guide

### From Old AI Stack to AI-Optimizer

If you have existing Ollama/Qdrant/MindsDB services:

**Step 1: Stop old services**
```bash
systemctl --user stop podman-local-ai-*.service
```

**Step 2: Export data (if needed)**
```bash
# Export Qdrant collections
curl http://localhost:6333/collections > qdrant-backup.json

# Export Ollama models list
ollama list > ollama-models.txt
```

**Step 3: Deploy AI-Optimizer**
```bash
cd ~/Documents/AI-Optimizer
docker compose -f docker-compose.new.yml up -d
```

**Step 4: Import data (if needed)**
```bash
# Re-pull Ollama models in vLLM format
# (vLLM uses HuggingFace models, different from Ollama)

# Qdrant collections (if using AI-Optimizer's Qdrant)
# Not needed - AI-Optimizer uses pgvector instead
```

---

## Version History

### v6.0.0 (2025-11-22) - Hand-in-Glove Integration

**Added:**
- ✅ Phase 9: AI-Optimizer System Preparation
- ✅ Integration hooks library (`lib/ai-optimizer-hooks.sh`)
- ✅ Shared persistent data layer
- ✅ Port conflict detection
- ✅ GPU acceleration verification
- ✅ Seamless workflow documentation

**Philosophy:**
- Hand (NixOS): Fully functional standalone
- Glove (AI-Optimizer): Optional perfect-fit enhancement
- Zero conflicts, shared persistence, clean separation

---

## Summary

**The Integration in One Image:**

```
┌─────────────────────────────────────┐
│         1. Install Hand             │
│   (NixOS-Dev-Quick-Deploy)          │
│   ./nixos-quick-deploy.sh           │
│   ✓ Phases 1-9 complete             │
└──────────┬──────────────────────────┘
           │
           │ Hand is functional
           │ (can stop here)
           │
┌──────────▼──────────────────────────┐
│         2. Add Glove                │
│   (AI-Optimizer AIDB MCP)           │
│   git clone + docker compose        │
│   ✓ Services running                │
└──────────┬──────────────────────────┘
           │
           │ Perfect fit!
           │
┌──────────▼──────────────────────────┐
│         3. Use Together             │
│   Hand + Glove = Enhanced System    │
│   AI features + NixOS deployment    │
│   ✓ Seamless integration            │
└─────────────────────────────────────┘
```

---

**Status:** ✅ Ready for Production
**Version:** 6.0.0
**Date:** November 22, 2025
**Co-authored by:** Human & Claude

🎯 **Hand-in-glove integration complete!**
