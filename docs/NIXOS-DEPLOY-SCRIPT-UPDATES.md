# NixOS Quick Deploy Script Updates - Reflecting Working System
**Date**: 2025-12-22
**Purpose**: Update deployment script to match the successfully working AI stack configuration

---

## Overview

The NixOS quick deploy script needs updates to reflect the current working system:

1. **Podman-based AI Stack** - Using docker-compose with llama.cpp, not Ollama
2. **Filesystem Detection** - Support for ZFS/Btrfs for container storage
3. **Optional Conditions** - Streamlined AI stack enablement
4. **Model Selection** - Updated for December 2025 best coding models

---

## Current Working System (Target State)

### AI Stack Architecture
```
Podman Containers (docker-compose.yml):
├── qdrant:v1.16.2          - Vector database (port 6333)
├── llama-cpp (ghcr.io/ggml-org/llama.cpp:server) - LLM inference (port 8080)
├── open-webui:main         - Web interface (port 3001)
├── postgres:pgvector-0.8.1 - Database (port 5432)
├── redis:8.4.0-alpine      - Caching (port 6379)
├── aidb (custom build)     - MCP server (port 8091)
├── hybrid-coordinator (custom) - Learning system (port 8092)
└── mindsdb:latest          - Analytics (port 47334)
```

### Filesystem Support
- **ZFS** - Preferred for container storage (snapshots, compression)
- **Btrfs** - Alternative with CoW support
- **ext4/XFS** - Fallback with overlay2 driver

### Model Defaults (December 2025)
**Primary Coding Models**:
- `qwen2.5-coder:14b` - Best overall (14B params, ~10GB VRAM)
- `deepseek-coder-v2` - Complex reasoning
- `starcoder2:7b` - Fast autocomplete

### Data Locations
```
~/.local/share/nixos-ai-stack/
├── qdrant/          - Vector database
├── llama-cpp-models/ - GGUF model files
├── open-webui/      - UI data
├── postgres/        - SQL database
├── redis/           - Cache data
├── aidb/            - MCP server data
├── hybrid-coordinator/ - Learning data
├── mindsdb/         - Analytics data
└── telemetry/       - Event logs
```

---

## Required Updates

### 1. Update `config/variables.sh`

#### Current Issues:
- References "Ollama" and outdated models
- LLM_MODELS defaults need updating
- Missing Podman storage driver auto-detection
- Missing AI stack service URLs

#### Required Changes:

**Lines 542-600 - LLM Configuration**:
```bash
# BEFORE (OLD):
# LLM Backend Selection (llama.cpp via containerized server)
# llama.cpp is optimized for AMD GPUs with ROCm support
LLM_BACKEND="${LLM_BACKEND:-}"
if [[ -z "$LLM_BACKEND" && -f "$LLM_BACKEND_PREFERENCE_FILE" ]]; then
    _llm_backend_cached=$(awk -F'=' '/^LLM_BACKEND=/{print $2}' "$LLM_BACKEND_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    case "$_llm_backend_cached" in
        llama_cpp)
            LLM_BACKEND="$_llm_backend_cached"
            ;;
    esac
fi
if [[ -z "$LLM_BACKEND" ]]; then
    # Default to llama.cpp backend (served by the containerized server)
    LLM_BACKEND="llama_cpp"
fi
export LLM_BACKEND
unset _llm_backend_cached

# AFTER (NEW):
# LLM Backend Selection
# Primary: llama.cpp server (ghcr.io/ggml-org/llama.cpp:server)
# Serves GGUF models via OpenAI-compatible API on port 8080
readonly LLM_BACKEND="llama_cpp"  # Only supported backend
readonly LLAMA_CPP_URL="http://localhost:8080"
readonly LLAMA_CPP_HEALTH_URL="${LLAMA_CPP_URL}/health"
export LLM_BACKEND LLAMA_CPP_URL
```

**Lines 585-600 - Model Defaults**:
```bash
# BEFORE (OLD):
LLM_MODELS="${LLM_MODELS:-}"
if [[ -z "$LLM_MODELS" && -f "$LLM_MODELS_PREFERENCE_FILE" ]]; then
    _llm_models_cached=$(awk -F'=' '/^LLM_MODELS=/{print $2}' "$LLM_MODELS_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    if [[ -n "$_llm_models_cached" ]]; then
        LLM_MODELS="$_llm_models_cached"
    fi
fi
if [[ -z "$LLM_MODELS" ]]; then
    # Default: Balanced set for 16GB VRAM mobile workstation
    # qwen2.5-coder:14b - Primary coding model (best code quality)
    # deepseek-coder-v2 - Secondary for complex debugging/reasoning
    # starcoder2:7b     - Fast autocomplete, 80+ languages
    LLM_MODELS="qwen2.5-coder:14b,deepseek-coder-v2,starcoder2:7b"
fi
export LLM_MODELS
unset _llm_models_cached

# AFTER (NEW):
# LLM Models Configuration (GGUF format for llama.cpp)
# Updated December 2025 - Best coding models
LLM_MODELS="${LLM_MODELS:-}"
if [[ -z "$LLM_MODELS" && -f "$LLM_MODELS_PREFERENCE_FILE" ]]; then
    _llm_models_cached=$(awk -F'=' '/^LLM_MODELS=/{print $2}' "$LLM_MODELS_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    if [[ -n "$_llm_models_cached" ]]; then
        LLM_MODELS="$_llm_models_cached"
    fi
fi
if [[ -z "$LLM_MODELS" ]]; then
    # Default model for deployment (single model to start)
    # qwen2.5-coder:7b - Best balance of quality vs resource usage
    # File: qwen2.5-coder-7b-instruct-q4_k_m.gguf (~4.4GB)
    LLM_MODELS="qwen2.5-coder:7b"
fi
export LLM_MODELS
unset _llm_models_cached

# Primary model file for docker-compose
# This is what gets loaded by llama-cpp container on startup
readonly LLAMA_CPP_MODEL_FILE="${LLAMA_CPP_MODEL_FILE:-qwen2.5-coder-7b-instruct-q4_k_m.gguf}"
export LLAMA_CPP_MODEL_FILE
```

**Lines 654-664 - Podman Storage**:
```bash
# BEFORE (OLD):
CONTAINER_STORAGE_FS_TYPE="${CONTAINER_STORAGE_FS_TYPE:-unknown}"
CONTAINER_STORAGE_SOURCE="${CONTAINER_STORAGE_SOURCE:-}"

DEFAULT_PODMAN_STORAGE_DRIVER="${DEFAULT_PODMAN_STORAGE_DRIVER:-zfs}"
PODMAN_AUTO_REPAIR_SYSTEM_STORAGE_CONF="${PODMAN_AUTO_REPAIR_SYSTEM_STORAGE_CONF:-true}"
PODMAN_SYSTEM_STORAGE_REPAIR_NOTE="${PODMAN_SYSTEM_STORAGE_REPAIR_NOTE:-}"
PODMAN_STORAGE_DRIVER="${PODMAN_STORAGE_DRIVER:-}"

if [[ -z "${PODMAN_STORAGE_COMMENT:-}" ]]; then
    PODMAN_STORAGE_COMMENT="Using ${PODMAN_STORAGE_DRIVER:-$DEFAULT_PODMAN_STORAGE_DRIVER} driver on detected filesystem."
fi

# AFTER (NEW):
CONTAINER_STORAGE_FS_TYPE="${CONTAINER_STORAGE_FS_TYPE:-unknown}"
CONTAINER_STORAGE_SOURCE="${CONTAINER_STORAGE_SOURCE:-}"

# Podman Storage Driver Selection (auto-detected based on filesystem)
# ZFS:    Use zfs driver (native snapshots, compression)
# Btrfs:  Use btrfs driver (CoW, subvolumes)
# ext4/XFS: Use overlay2 driver (standard overlay)
DEFAULT_PODMAN_STORAGE_DRIVER="${DEFAULT_PODMAN_STORAGE_DRIVER:-auto}"  # Changed from "zfs"
PODMAN_AUTO_REPAIR_SYSTEM_STORAGE_CONF="${PODMAN_AUTO_REPAIR_SYSTEM_STORAGE_CONF:-true}"
PODMAN_SYSTEM_STORAGE_REPAIR_NOTE="${PODMAN_SYSTEM_STORAGE_REPAIR_NOTE:-}"
PODMAN_STORAGE_DRIVER="${PODMAN_STORAGE_DRIVER:-}"

if [[ -z "${PODMAN_STORAGE_COMMENT:-}" ]]; then
    PODMAN_STORAGE_COMMENT="Storage driver will be auto-detected based on filesystem type."
fi
```

**Add New Section - AI Stack Service URLs** (after line 708):
```bash
# ============================================================================
# AI Stack Service Configuration
# ============================================================================
# Service URLs for the Podman-based AI stack
# All services are containerized via docker-compose.yml

readonly QDRANT_URL="http://localhost:6333"
readonly QDRANT_GRPC_URL="http://localhost:6334"
readonly LLAMA_CPP_API_URL="http://localhost:8080/v1"  # OpenAI-compatible
readonly OPEN_WEBUI_URL="http://localhost:3001"
readonly POSTGRES_URL="postgresql://mcp:change_me_in_production@localhost:5432/mcp"
readonly REDIS_URL="redis://localhost:6379"
readonly AIDB_MCP_URL="http://localhost:8091"
readonly HYBRID_COORDINATOR_URL="http://localhost:8092"
readonly MINDSDB_URL="http://localhost:47334"

# AI Stack data directory
readonly AI_STACK_DATA="${HOME}/.local/share/nixos-ai-stack"
readonly AI_STACK_COMPOSE="${SCRIPT_DIR}/ai-stack/compose"
readonly AI_STACK_ENV="${AI_STACK_COMPOSE}/.env"

export QDRANT_URL LLAMA_CPP_API_URL AIDB_MCP_URL HYBRID_COORDINATOR_URL
export AI_STACK_DATA AI_STACK_COMPOSE
```

---

### 2. Update `phases/phase-09-ai-model-deployment.sh`

#### Current Issues:
- References `AI-Optimizer` directory (outdated)
- GPU detection expects NVIDIA only
- Model selection UI mentions Ollama
- Hardcoded paths need updating

#### Required Changes:

**Function: `phase_09_ai_model_deployment()`** - Complete rewrite:

```bash
#!/usr/bin/env bash
# Phase 9: AI Stack Deployment
# Part of: nixos-quick-deploy.sh
# Version: 2.0.0 (Podman-based llama.cpp stack)
# Purpose: Deploy containerized AI stack with llama.cpp

phase_09_ai_model_deployment() {
    log_phase_start 9 "AI Stack Deployment (Optional)"

    # Check if user wants AI stack
    if ! prompt_ai_stack_deployment; then
        log_info "Skipping AI stack deployment"
        mark_phase_complete "phase-09-ai-stack"
        return 0
    fi

    # Ensure Podman is available
    if ! command -v podman >/dev/null 2>&1; then
        log_error "Podman not found. AI stack requires Podman."
        log_info "Install via: nix-env -iA nixos.podman"
        return 1
    fi

    if ! command -v podman-compose >/dev/null 2>&1; then
        log_error "podman-compose not found. AI stack requires podman-compose."
        log_info "Install via: nix-env -iA nixos.podman-compose"
        return 1
    fi

    # Detect hardware for model recommendations
    local gpu_vram=$(detect_gpu_vram)
    local gpu_name=$(detect_gpu_model)
    local ram_gb=$(detect_total_ram_gb)

    # Recommend model based on available resources
    local recommended_model
    if [ "$ram_gb" -ge 16 ]; then
        recommended_model="qwen2.5-coder:14b"
        local model_file="qwen2.5-coder-14b-instruct-q4_k_m.gguf"
    elif [ "$ram_gb" -ge 12 ]; then
        recommended_model="qwen2.5-coder:7b"
        local model_file="qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    else
        recommended_model="qwen2.5-coder:3b"
        local model_file="qwen2.5-coder-3b-instruct-q4_k_m.gguf"
    fi

    log_info "System Resources:"
    log_info "  RAM: ${ram_gb}GB"
    log_info "  GPU: ${gpu_name:-None detected} ${gpu_vram:+(${gpu_vram}GB VRAM)}"
    log_info "  Recommended Model: ${recommended_model}"

    # Confirm deployment
    read -p "Deploy AI stack with ${recommended_model}? [Y/n]: " confirm
    if [[ "$confirm" =~ ^[Nn]$ ]]; then
        log_info "AI stack deployment cancelled"
        mark_phase_complete "phase-09-ai-stack"
        return 0
    fi

    # Create AI stack data directory
    mkdir -p "${AI_STACK_DATA}"/{qdrant,llama-cpp-models,open-webui,postgres,redis,aidb,hybrid-coordinator,mindsdb,telemetry}

    # Generate .env file for docker-compose
    log_info "Generating AI stack configuration..."
    cat > "${AI_STACK_ENV}" <<EOF
# AI Stack Configuration
# Generated: $(date)

# Data directory
AI_STACK_DATA=${AI_STACK_DATA}

# llama.cpp configuration
LLAMA_CPP_MODEL_FILE=${model_file}
LLAMA_CPP_DEFAULT_MODEL=${recommended_model}
LLAMA_CPP_LOG_LEVEL=info
LLAMA_CPP_WEB_CONCURRENCY=4

# PostgreSQL configuration
POSTGRES_DB=mcp
POSTGRES_USER=mcp
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Hugging Face token (if available)
HUGGING_FACE_HUB_TOKEN=${HUGGINGFACEHUB_API_TOKEN:-}

# Hybrid Coordinator settings
LOCAL_CONFIDENCE_THRESHOLD=0.7
HIGH_VALUE_THRESHOLD=0.7
PATTERN_EXTRACTION_ENABLED=true
EOF

    log_success "Configuration created: ${AI_STACK_ENV}"

    # Start AI stack containers
    log_info "Starting AI stack containers..."
    log_info "This may take several minutes on first run..."

    pushd "${AI_STACK_COMPOSE}" >/dev/null

    if podman-compose up -d; then
        log_success "AI stack containers started successfully"
    else
        log_error "Failed to start AI stack containers"
        log_info "Check logs: podman-compose logs"
        popd >/dev/null
        return 1
    fi

    popd >/dev/null

    # Download model if needed
    log_info "Checking for model file: ${model_file}"
    if [ ! -f "${AI_STACK_DATA}/llama-cpp-models/${model_file}" ]; then
        log_info "Model not found. Downloading ${recommended_model}..."
        log_info "This may take 10-30 minutes depending on your connection"

        if [ -f "${SCRIPT_DIR}/scripts/download-llama-cpp-models.sh" ]; then
            bash "${SCRIPT_DIR}/scripts/download-llama-cpp-models.sh" "${recommended_model}" || {
                log_warning "Model download incomplete. llama-cpp will download on first API call."
            }
        else
            log_warning "Download script not found. Model will download on first API call."
        fi
    else
        log_success "Model file already exists: ${model_file}"
    fi

    # Wait for services to become healthy
    log_info "Waiting for services to start..."
    local max_wait=120
    local waited=0

    while [ $waited -lt $max_wait ]; do
        if curl -sf "${QDRANT_URL}/health" >/dev/null 2>&1; then
            log_success "Qdrant is healthy"
            break
        fi
        sleep 5
        waited=$((waited + 5))
    done

    # Display deployment summary
    cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI Stack Deployment Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Model: ${recommended_model}
System: ${ram_gb}GB RAM ${gpu_vram:+/ ${gpu_vram}GB VRAM}

🚀 Services Running:
  • Qdrant Vector DB:       ${QDRANT_URL}
  • llama.cpp API:          ${LLAMA_CPP_API_URL}
  • Open WebUI:             ${OPEN_WEBUI_URL}
  • PostgreSQL:             localhost:5432
  • Redis:                  localhost:6379
  • AIDB MCP Server:        ${AIDB_MCP_URL}
  • Hybrid Coordinator:     ${HYBRID_COORDINATOR_URL}
  • MindsDB:                ${MINDSDB_URL}

📊 Management Commands:
  • View status:   podman-compose ps
  • View logs:     podman-compose logs -f [service]
  • Stop stack:    podman-compose down
  • Start stack:   podman-compose up -d

📚 Quick Start:
  • Open WebUI:    xdg-open ${OPEN_WEBUI_URL}
  • Dashboard:     xdg-open ${SCRIPT_DIR}/dashboard.html
  • Test API:      curl ${LLAMA_CPP_API_URL}/models

📖 Documentation:
  • Setup Guide:      ${SCRIPT_DIR}/AI-AGENT-SETUP.md
  • System Guide:     ${SCRIPT_DIR}/HYBRID-AI-SYSTEM-GUIDE.md
  • Dashboard Guide:  ${SCRIPT_DIR}/SYSTEM-DASHBOARD-GUIDE.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

    mark_phase_complete "phase-09-ai-stack"
    return 0
}

# Prompt user for AI stack deployment
prompt_ai_stack_deployment() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Optional: Local AI Stack Deployment"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "The AI stack provides:"
    echo "  ✓ Local LLM inference (private, no API costs)"
    echo "  ✓ Vector database for RAG/embeddings"
    echo "  ✓ Web interface for chat"
    echo "  ✓ MCP servers for AI agent integration"
    echo "  ✓ Telemetry and continuous learning"
    echo ""
    echo "Requirements:"
    echo "  • 8GB+ RAM (16GB recommended)"
    echo "  • 20GB+ disk space"
    echo "  • Podman installed"
    echo ""
    read -p "Deploy local AI stack? [Y/n]: " response

    if [[ "$response" =~ ^[Nn]$ ]]; then
        return 1
    fi

    return 0
}

# Detect GPU VRAM (in GB)
detect_gpu_vram() {
    local vram=0

    # Try NVIDIA first
    if command -v nvidia-smi >/dev/null 2>&1; then
        vram=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | awk '{print int($1/1024)}')
    fi

    # Try AMD ROCm
    if [ "$vram" -eq 0 ] && command -v rocm-smi >/dev/null 2>&1; then
        vram=$(rocm-smi --showmeminfo vram --csv 2>/dev/null | tail -1 | awk -F',' '{print int($2/1024)}')
    fi

    echo "$vram"
}

# Detect GPU model name
detect_gpu_model() {
    local model=""

    if command -v nvidia-smi >/dev/null 2>&1; then
        model=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    elif command -v lspci >/dev/null 2>&1; then
        model=$(lspci | grep -i 'vga\|3d' | head -1 | cut -d':' -f3 | sed 's/^ *//')
    fi

    echo "$model"
}

# Detect total RAM in GB
detect_total_ram_gb() {
    local ram_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    echo $((ram_kb / 1024 / 1024))
}
```

---

### 3. Update Filesystem Detection in `lib/common.sh`

#### Current State:
Functions `detect_container_storage_filesystem()` exist around lines 1150-1200

#### Required Enhancement:

Add auto-detection logic for Podman storage driver:

```bash
# After existing detect_container_storage_filesystem() function

# Auto-select Podman storage driver based on filesystem
select_podman_storage_driver() {
    local fs_type="${CONTAINER_STORAGE_FS_TYPE:-unknown}"
    local driver=""

    case "$fs_type" in
        zfs)
            driver="zfs"
            log_info "Detected ZFS filesystem → using zfs storage driver"
            ;;
        btrfs)
            driver="btrfs"
            log_info "Detected Btrfs filesystem → using btrfs storage driver"
            ;;
        ext4|xfs)
            driver="overlay2"
            log_info "Detected ${fs_type} filesystem → using overlay2 storage driver"
            ;;
        *)
            driver="overlay2"
            log_warning "Unknown filesystem type: ${fs_type} → defaulting to overlay2"
            ;;
    esac

    PODMAN_STORAGE_DRIVER="$driver"
    PODMAN_STORAGE_COMMENT="Auto-selected ${driver} driver for ${fs_type} filesystem"

    export PODMAN_STORAGE_DRIVER PODMAN_STORAGE_COMMENT
}
```

---

### 4. Update Optional Conditions Logic

#### File: `lib/user.sh` (or wherever AI stack prompting happens)

**Streamline AI Stack Enablement**:

```bash
# BEFORE (complex multi-step):
# 1. Prompt for Hugging Face token
# 2. Prompt for local AI stack
# 3. Prompt for LLM backend
# 4. Prompt for model selection

# AFTER (simplified):
prompt_local_ai_stack() {
    if [ "${LOCAL_AI_STACK_ENABLED}" = "true" ]; then
        log_info "Local AI stack already enabled (from cache)"
        return 0
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Local AI Stack (Optional)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Deploy containerized AI stack with:"
    echo "  • llama.cpp for local LLM inference"
    echo "  • Qdrant vector database"
    echo "  • MCP servers for agent integration"
    echo "  • Web UI for interaction"
    echo ""
    echo "Requirements: 8GB+ RAM, 20GB disk"
    echo ""
    read -p "Enable local AI stack? [y/N]: " response

    if [[ "$response" =~ ^[Yy]$ ]]; then
        LOCAL_AI_STACK_ENABLED="true"

        # Save preference
        mkdir -p "$(dirname "$LOCAL_AI_STACK_PREFERENCE_FILE")"
        echo "LOCAL_AI_STACK_ENABLED=true" > "$LOCAL_AI_STACK_PREFERENCE_FILE"

        log_success "Local AI stack enabled"
    else
        LOCAL_AI_STACK_ENABLED="false"
        echo "LOCAL_AI_STACK_ENABLED=false" > "$LOCAL_AI_STACK_PREFERENCE_FILE"
        log_info "Local AI stack disabled"
    fi

    export LOCAL_AI_STACK_ENABLED
}
```

---

## Testing Plan

After making changes, test the following:

### 1. Filesystem Detection Test
```bash
# Run hardware detection
bash lib/common.sh detect_container_storage_filesystem

# Verify output
echo "FS Type: $CONTAINER_STORAGE_FS_TYPE"
echo "Storage Driver: $PODMAN_STORAGE_DRIVER"

# Expected:
# - ZFS → zfs driver
# - Btrfs → btrfs driver
# - ext4/XFS → overlay2 driver
```

### 2. AI Stack Deployment Test
```bash
# Run Phase 9
bash phases/phase-09-ai-model-deployment.sh

# Expected:
# - Prompts for AI stack deployment
# - Detects RAM/GPU
# - Recommends appropriate model
# - Creates .env file
# - Starts containers
# - Services become healthy
```

### 3. Integration Test
```bash
# Full deployment (dry run)
bash nixos-quick-deploy.sh --dry-run

# Verify:
# - Variables loaded correctly
# - Filesystem detected
# - AI stack prompt appears
# - No errors in log
```

### 4. Container Verification
```bash
# After Phase 9 completes
podman-compose ps

# Expected services running:
# - local-ai-qdrant
# - local-ai-llama-cpp
# - local-ai-open-webui
# - local-ai-postgres
# - local-ai-redis
# - local-ai-aidb
# - local-ai-hybrid-coordinator
# - local-ai-mindsdb

# Test API endpoints
curl http://localhost:6333/health  # Qdrant
curl http://localhost:8080/health  # llama.cpp
curl http://localhost:8091/health  # AIDB
curl http://localhost:8092/health  # Hybrid Coordinator
```

---

## Migration Notes

### For Existing Deployments

If users already have the old AI-Optimizer setup:

1. **Backup existing data**:
   ```bash
   tar -czf ~/ai-optimizer-backup-$(date +%Y%m%d).tar.gz ~/.local/share/ai-optimizer
   ```

2. **Stop old services**:
   ```bash
   systemctl --user stop ollama
   systemctl --user disable ollama
   ```

3. **Run updated deployment**:
   ```bash
   bash nixos-quick-deploy.sh --phase 9
   ```

4. **Migrate data** (if needed):
   ```bash
   # Copy Qdrant data
   cp -r ~/.local/share/ai-optimizer/qdrant/* ~/.local/share/nixos-ai-stack/qdrant/

   # Copy telemetry
   cp -r ~/.local/share/ai-optimizer/telemetry/* ~/.local/share/nixos-ai-stack/telemetry/
   ```

---

## Summary of Changes

| Component | Change | Impact |
|-----------|--------|--------|
| `config/variables.sh` | Update LLM defaults, add service URLs | Models reflect December 2025 best practices |
| `phases/phase-09-ai-model-deployment.sh` | Complete rewrite for Podman stack | Uses docker-compose, llama.cpp, proper health checks |
| `lib/common.sh` | Add `select_podman_storage_driver()` | Auto-detects optimal driver for filesystem |
| `lib/user.sh` | Simplify AI stack prompt | Single yes/no instead of multi-step |
| `ai-stack/compose/docker-compose.yml` | Already correct | No changes needed (already updated) |

**Total Files Modified**: 4
**New Functions**: 4
**Removed Dependencies**: AI-Optimizer, Ollama references
**Added Services**: MindsDB, Hybrid Coordinator, AIDB

---

**Status**: Ready for implementation
**Last Updated**: 2025-12-22
**Next Step**: Apply changes to deployment script files
