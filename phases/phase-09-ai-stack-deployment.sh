#!/usr/bin/env bash
# Phase 9: AI Stack Deployment
# Part of: nixos-quick-deploy.sh
# Version: 2.0.0 (Podman-based llama.cpp stack)
# Purpose: Deploy containerized AI stack with llama.cpp

# ============================================================================
# Phase 9: AI Stack Deployment
# ============================================================================

phase_09_ai_stack_deployment() {
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
    local ram_gb=0
    if declare -F detect_total_ram_gb >/dev/null 2>&1; then
        ram_gb=$(detect_total_ram_gb)
    elif [[ -r /proc/meminfo ]]; then
        ram_gb=$(awk '/MemTotal:/ {printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0)
    fi

    # Default to CPU/iGPU-friendly models unless resources justify larger GGUFs.
    local default_coder="qwen2.5-coder"
    if [[ "$gpu_vram" -ge 24 ]]; then
        default_coder="qwen2.5-coder-14b"
    elif [[ "$gpu_vram" -ge 16 ]]; then
        default_coder="qwen2.5-coder"
    elif [[ "$ram_gb" -ge 32 ]]; then
        default_coder="qwen2.5-coder"
    else
        default_coder="qwen3-4b"
    fi

    local selected_coder="${CODER_MODEL:-$default_coder}"
    local selected_model_id="${LLAMA_CPP_DEFAULT_MODEL:-}"
    local model_file="${LLAMA_CPP_MODEL_FILE:-}"

    if [[ -z "$selected_model_id" ]]; then
        case "$selected_coder" in
            qwen3-4b|qwen3-4b-instruct)
                selected_model_id="unsloth/Qwen3-4B-Instruct-2507-GGUF"
                ;;
            qwen2.5-coder|qwen2.5-coder-7b|qwen2.5-coder-7b-instruct)
                selected_model_id="Qwen/Qwen2.5-Coder-7B-Instruct"
                ;;
            qwen2.5-coder-14b|qwen2.5-coder-14b-instruct)
                selected_model_id="Qwen/Qwen2.5-Coder-14B-Instruct"
                ;;
            deepseek-coder-v2-lite|deepseek-lite)
                selected_model_id="deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
                ;;
            deepseek-coder-v2|deepseek-v2)
                selected_model_id="deepseek-ai/DeepSeek-Coder-V2-Instruct"
                ;;
        esac
    fi

    map_model_id_to_file() {
        local model_id="$1"
        case "$model_id" in
            "Qwen/Qwen2.5-Coder-7B-Instruct"|"Qwen/Qwen2.5-Coder-7B-Instruct-GGUF")
                echo "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
                ;;
            "unsloth/Qwen3-4B-Instruct-2507-GGUF")
                echo "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
                ;;
            "TheBloke/deepseek-coder-6.7B-instruct-GGUF")
                echo "deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
                ;;
            "Qwen/Qwen2.5-Coder-14B-Instruct"|"Qwen/Qwen2.5-Coder-14B-Instruct-GGUF")
                echo "qwen2.5-coder-14b-instruct-q4_k_m.gguf"
                ;;
            *)
                echo ""
                ;;
        esac
    }

    local mapped_model_file=""
    mapped_model_file=$(map_model_id_to_file "$selected_model_id")

    if [[ -z "$mapped_model_file" ]]; then
        log_warning "Unknown llama.cpp model '${selected_model_id}'. Defaulting to qwen3-4b."
        selected_coder="qwen3-4b"
        selected_model_id="unsloth/Qwen3-4B-Instruct-2507-GGUF"
        mapped_model_file="Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
    fi

    if [[ -z "$model_file" ]]; then
        model_file="$mapped_model_file"
    elif [[ -n "$mapped_model_file" && "$model_file" != "$mapped_model_file" ]]; then
        log_warning "LLAMA_CPP_MODEL_FILE (${model_file}) does not match ${selected_model_id}; using ${mapped_model_file}."
        model_file="$mapped_model_file"
    fi

    log_info "System Resources:"
    log_info "  RAM: ${ram_gb}GB"
    log_info "  GPU: ${gpu_name:-None detected} ${gpu_vram:+(${gpu_vram}GB VRAM)}"
    log_info "  Coder Preset: ${selected_coder}"
    log_info "  llama.cpp Model: ${selected_model_id}"

    # Confirm deployment
    read -p "Deploy AI stack with ${selected_coder}? [Y/n]: " confirm
    if [[ "$confirm" =~ ^[Nn]$ ]]; then
        log_info "AI stack deployment cancelled"
        mark_phase_complete "phase-09-ai-stack"
        return 0
    fi

    # Create AI stack data directory
    log_info "Creating AI stack data directories..."
    mkdir -p "${AI_STACK_DATA}"/{qdrant,llama-cpp-models,open-webui,postgres,redis,aidb,hybrid-coordinator,mindsdb,telemetry,fine-tuning,ralph-wiggum,health-monitor,workspace,logs}

    # Ensure .env file for docker-compose
    log_info "Ensuring AI stack configuration..."

    local config_dir="${HOME}/.config/nixos-ai-stack"
    local ai_stack_env="${config_dir}/.env"
    mkdir -p "$config_dir"
    AI_STACK_ENV="${AI_STACK_ENV:-$ai_stack_env}"
    export AI_STACK_ENV_FILE="$AI_STACK_ENV"

    if declare -F ensure_ai_stack_env >/dev/null 2>&1; then
        if ! ensure_ai_stack_env; then
            return 1
        fi
    fi

    if [[ ! -f "$AI_STACK_ENV" ]]; then
        log_error "Missing AI stack env file: ${AI_STACK_ENV}"
        log_info "Re-run nixos-quick-deploy.sh to set AI stack credentials."
        return 1
    fi

    append_if_missing() {
        local key="$1"
        local value="$2"
        if ! rg -q "^${key}=" "$AI_STACK_ENV"; then
            printf '%s=%s\n' "$key" "$value" >> "$AI_STACK_ENV"
        fi
    }

    append_if_missing "AI_STACK_DATA" "${AI_STACK_DATA}"
    append_if_missing "LLAMA_CPP_MODEL_FILE" "${model_file}"
    append_if_missing "LLAMA_CPP_DEFAULT_MODEL" "${selected_model_id}"
    append_if_missing "LLAMA_CPP_LOG_LEVEL" "info"
    append_if_missing "LLAMA_CPP_WEB_CONCURRENCY" "4"
    append_if_missing "LLAMA_CTX_SIZE" "8192"
    append_if_missing "LLAMA_THREADS" "0"
    append_if_missing "LLAMA_BATCH_SIZE" "512"
    append_if_missing "LLAMA_UBATCH_SIZE" "128"
    append_if_missing "LLAMA_CACHE_TYPE_K" "q4_0"
    append_if_missing "LLAMA_CACHE_TYPE_V" "q4_0"
    append_if_missing "LLAMA_DEFRAG_THOLD" "0.1"
    append_if_missing "LLAMA_PARALLEL" "4"
    append_if_missing "POSTGRES_DB" "mcp"
    append_if_missing "POSTGRES_USER" "mcp"
    append_if_missing "HUGGING_FACE_HUB_TOKEN" "${HUGGINGFACEHUB_API_TOKEN:-}"
    append_if_missing "LOCAL_CONFIDENCE_THRESHOLD" "0.7"
    append_if_missing "HIGH_VALUE_THRESHOLD" "0.7"
    append_if_missing "PATTERN_EXTRACTION_ENABLED" "true"
    append_if_missing "AIDB_TOOL_DISCOVERY_ENABLED" "true"
    append_if_missing "AIDB_TOOL_DISCOVERY_INTERVAL" "300"
    append_if_missing "SELF_HEALING_ENABLED" "true"
    append_if_missing "SELF_HEALING_CHECK_INTERVAL" "30"
    append_if_missing "SELF_HEALING_COOLDOWN" "60"
    append_if_missing "CONTINUOUS_LEARNING_ENABLED" "true"
    append_if_missing "LEARNING_PROCESSING_INTERVAL" "3600"
    append_if_missing "LEARNING_DATASET_THRESHOLD" "1000"
    append_if_missing "RALPH_LOOP_ENABLED" "true"
    append_if_missing "RALPH_EXIT_CODE_BLOCK" "2"
    append_if_missing "RALPH_MAX_ITERATIONS" "0"
    append_if_missing "RALPH_CONTEXT_RECOVERY" "true"
    append_if_missing "RALPH_GIT_INTEGRATION" "true"
    append_if_missing "RALPH_REQUIRE_APPROVAL" "false"
    append_if_missing "RALPH_APPROVAL_THRESHOLD" "high"
    append_if_missing "RALPH_AUDIT_LOG" "true"
    append_if_missing "RALPH_DEFAULT_BACKEND" "aider"

    log_success "Configuration verified: ${AI_STACK_ENV}"

    set -a
    # shellcheck disable=SC1090
    source "$AI_STACK_ENV"
    set +a

    export POSTGRES_URL="postgresql://${POSTGRES_USER:-mcp}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-mcp}"

    # Start AI stack containers
    log_info "Starting AI stack containers..."
    log_info "This may take several minutes on first run..."

    pushd "${AI_STACK_COMPOSE}" >/dev/null 2>&1

    if podman-compose up -d 2>&1 | tee /tmp/podman-compose-up.log; then
        log_success "AI stack containers started successfully"
    else
        log_error "Failed to start AI stack containers"
        log_info "Check logs: podman-compose logs"
        log_info "Full output: /tmp/podman-compose-up.log"
        popd >/dev/null 2>&1
        return 1
    fi

    popd >/dev/null 2>&1

    # Download model if needed (optional)
    log_info "Checking for model file: ${model_file}"
    if [ ! -f "${AI_STACK_DATA}/llama-cpp-models/${model_file}" ]; then
        log_warning "Model not found. It will download on first API call."
        log_info "Optional: ${SCRIPT_DIR}/scripts/download-llama-cpp-models.sh --list"
    else
        log_success "Model file already exists: ${model_file}"
    fi

    # Wait for services to become healthy
    log_info "Waiting for services to start (max 120 seconds)..."
    local max_wait=120
    local waited=0
    local qdrant_healthy=false

    while [ $waited -lt $max_wait ]; do
        if curl -sf "${QDRANT_URL}/health" >/dev/null 2>&1; then
            log_success "Qdrant is healthy"
            qdrant_healthy=true
            break
        fi
        sleep 5
        waited=$((waited + 5))
        echo -n "."
    done
    echo ""

    if [ "$qdrant_healthy" = false ]; then
        log_warning "Qdrant health check timed out (may still be starting)"
    fi

    # Deploy VSCode AI extension configurations
    deploy_vscode_configs

    # Save deployment info
    cat > "${STATE_DIR}/ai-stack-deployment.json" <<EOF
{
  "deployed_at": "$(date -Iseconds)",
  "model": "${selected_model_id}",
  "model_file": "${model_file}",
  "ram_gb": ${ram_gb},
  "gpu_vram": ${gpu_vram:-0},
  "gpu_name": "${gpu_name:-none}",
  "services": {
    "qdrant": "${QDRANT_URL}",
    "llama_cpp": "${LLAMA_CPP_URL}",
    "open_webui": "${OPEN_WEBUI_URL}",
    "aidb": "${AIDB_MCP_URL}",
    "hybrid_coordinator": "${HYBRID_COORDINATOR_URL}",
    "mindsdb": "${MINDSDB_URL}"
  }
}
EOF

    # Display deployment summary
    cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI Stack Deployment Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Model: ${selected_coder} (${selected_model_id})
System: ${ram_gb}GB RAM${gpu_vram:+ / ${gpu_vram}GB VRAM}

🚀 Core Services Running:
  • Qdrant Vector DB:       ${QDRANT_URL}
  • llama.cpp API:          ${LLAMA_CPP_API_URL} (with Flash Attention + KV Q4 cache)
  • Open WebUI:             ${OPEN_WEBUI_URL}
  • PostgreSQL:             localhost:5432 (db: mcp, user: mcp)
  • Redis:                  localhost:6379
  • MindsDB:                ${MINDSDB_URL}

✨ Vibe Coding Stack (v3.0.0 - Agentic Era):
  • AIDB MCP Server:        ${AIDB_MCP_URL} (with tool discovery)
  • Hybrid Coordinator:     ${HYBRID_COORDINATOR_URL} (with continuous learning)
  • Ralph Wiggum Loop:      http://localhost:8098 (autonomous orchestrator)
  • Health Monitor:         Auto-healing enabled (monitors all containers)

📊 Management Commands:
  • View status:   cd ${AI_STACK_COMPOSE} && podman-compose ps
  • View logs:     cd ${AI_STACK_COMPOSE} && podman-compose logs -f [service]
  • Stop stack:    cd ${AI_STACK_COMPOSE} && podman-compose down
  • Start stack:   cd ${AI_STACK_COMPOSE} && podman-compose up -d
  • Restart:       cd ${AI_STACK_COMPOSE} && podman-compose restart

📚 Quick Start:
  • Open WebUI:    xdg-open ${OPEN_WEBUI_URL}
  • Dashboard:     xdg-open ${SCRIPT_DIR}/dashboard.html
  • Test API:      curl ${LLAMA_CPP_URL}/health

🔧 Helper Scripts:
  • Health check:  bash ${SCRIPT_DIR}/scripts/test-ai-stack-health.sh
  • Stack manage:  bash ${SCRIPT_DIR}/scripts/ai-stack-manage.sh [start|stop|restart|status]
  • Dashboard:     bash ${SCRIPT_DIR}/scripts/start-ai-stack-and-dashboard.sh

📖 Documentation:
  • Vibe Coding Guide:   ${SCRIPT_DIR}/QUICK-START-VIBE-CODING.md
  • Architecture:        ${SCRIPT_DIR}/docs/VIBE-CODING-SYSTEM-ARCHITECTURE.md
  • Implementation:      ${SCRIPT_DIR}/docs/VIBE-CODING-IMPLEMENTATION-SUMMARY.md
  • System Guide:        ${SCRIPT_DIR}/HYBRID-AI-SYSTEM-GUIDE.md
  • Dashboard Guide:     ${SCRIPT_DIR}/SYSTEM-DASHBOARD-GUIDE.md

💡 Next Steps:
  1. Open WebUI: xdg-open ${OPEN_WEBUI_URL}
  2. Test llama.cpp: curl ${LLAMA_CPP_URL}/health
  3. Submit autonomous task to Ralph: curl -X POST http://localhost:8098/tasks -d '{"prompt":"Create hello world","backend":"aider"}'
  4. Monitor self-healing: podman logs -f local-ai-health-monitor
  5. Check tool discovery: curl http://localhost:8091/api/v1/tools/discover
  6. Read vibe coding guide: cat ${SCRIPT_DIR}/QUICK-START-VIBE-CODING.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

    mark_phase_complete "phase-09-ai-stack"
    return 0
}

# ==========================================================================
# Helper Functions
# ==========================================================================

# Deploy VSCode AI extension configurations
deploy_vscode_configs() {
    log_info "Deploying VSCode AI extension configurations..."

    # Source service registry for dynamic URLs
    if [ -f "${SCRIPT_DIR}/lib/service-registry.sh" ]; then
        source "${SCRIPT_DIR}/lib/service-registry.sh"
    else
        log_warning "Service registry not found, using default URLs"
    fi

    # Deploy VSCode settings (merge with existing)
    if [[ -f "${SCRIPT_DIR}/templates/vscode/settings.json" ]]; then
        mkdir -p ~/.config/VSCodium/User

        if [[ -f ~/.config/VSCodium/User/settings.json ]]; then
            # Merge with existing settings
            if command -v jq >/dev/null 2>&1; then
                jq -s '.[0] * .[1]' \
                    ~/.config/VSCodium/User/settings.json \
                    "${SCRIPT_DIR}/templates/vscode/settings.json" \
                    > ~/.config/VSCodium/User/settings.json.tmp && \
                mv ~/.config/VSCodium/User/settings.json.tmp \
                   ~/.config/VSCodium/User/settings.json
                log_success "VSCode settings merged with existing configuration"
            else
                log_warning "jq not available, copying template (existing settings will be overwritten)"
                cp "${SCRIPT_DIR}/templates/vscode/settings.json" \
                   ~/.config/VSCodium/User/settings.json
            fi
        else
            cp "${SCRIPT_DIR}/templates/vscode/settings.json" \
               ~/.config/VSCodium/User/settings.json
            log_success "VSCode settings deployed"
        fi
    else
        log_warning "VSCode settings template not found"
    fi

    # Deploy Continue config
    if [[ -f "${SCRIPT_DIR}/templates/vscode/continue/config.json" ]]; then
        mkdir -p ~/.continue

        # Replace placeholders with actual service URLs
        if command -v get_service_url >/dev/null 2>&1; then
            cat "${SCRIPT_DIR}/templates/vscode/continue/config.json" | \
                sed "s|http://localhost:8080|$(get_service_url LLAMA_CPP 2>/dev/null || echo 'http://localhost:8080')|g" | \
                sed "s|http://localhost:8092|$(get_service_url HYBRID_COORDINATOR 2>/dev/null || echo 'http://localhost:8092')|g" \
                > ~/.continue/config.json
        else
            cp "${SCRIPT_DIR}/templates/vscode/continue/config.json" \
               ~/.continue/config.json
        fi

        log_success "Continue config deployed"
    else
        log_warning "Continue config template not found"
    fi

    # Deploy Claude Code MCP config
    if [[ -f "${SCRIPT_DIR}/templates/vscode/claude-code/mcp_servers.json" ]]; then
        mkdir -p ~/.claude-code

        # Replace placeholders with actual service URLs
        if command -v get_service_url >/dev/null 2>&1; then
            cat "${SCRIPT_DIR}/templates/vscode/claude-code/mcp_servers.json" | \
                sed "s|http://localhost:8091|$(get_service_url AIDB_MCP 2>/dev/null || echo 'http://localhost:8091')|g" | \
                sed "s|http://localhost:8092|$(get_service_url HYBRID_COORDINATOR 2>/dev/null || echo 'http://localhost:8092')|g" \
                > ~/.claude-code/mcp_servers.json
        else
            cp "${SCRIPT_DIR}/templates/vscode/claude-code/mcp_servers.json" \
               ~/.claude-code/mcp_servers.json
        fi

        log_success "Claude Code MCP config deployed"
    else
        log_warning "Claude Code MCP config template not found"
    fi

    log_success "All VSCode configurations deployed successfully"
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

# Main function (called by nixos-quick-deploy.sh)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being run directly (for testing)
    echo "Phase 9 AI Stack Deployment - Test Mode"
    echo "This phase should be called from nixos-quick-deploy.sh"
    exit 1
fi
