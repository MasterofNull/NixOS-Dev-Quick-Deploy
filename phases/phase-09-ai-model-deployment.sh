#!/usr/bin/env bash
# Phase 9: AI Model Deployment (llama.cpp)
# Part of: nixos-quick-deploy.sh
# Version: Uses SCRIPT_VERSION from main script
# Purpose: Optional deployment of AI coding models via llama.cpp

# ============================================================================
# Phase 9: AI Model Deployment
# ============================================================================

phase_09_ai_model_deployment() {
    if declare -F log_phase_start >/dev/null 2>&1; then
        log_phase_start 9 "AI Model Deployment (Optional)"
    else
        log_info "Phase 9: AI Model Deployment (Optional)"
    fi

    # Respect global preference from the earlier prompt to avoid duplicate questions.
    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" != "true" ]]; then
        log_info "AI stack disabled earlier; skipping AI model deployment prompt"
        mark_phase_complete "phase-09-ai-model"
        return 0
    fi

    # Load AI-Optimizer integration library
    if [ -f "${SCRIPT_DIR}/lib/ai-optimizer.sh" ]; then
        if ! source "${SCRIPT_DIR}/lib/ai-optimizer.sh"; then
            log_error "Failed to load AI-Optimizer library"
            return 1
        fi
    else
        log_error "AI-Optimizer library not found"
        return 1
    fi

    # Detect GPU and recommend model
    local gpu_vram=$(detect_gpu_vram)
    local gpu_name=$(detect_gpu_model)

    if [ "$gpu_vram" -eq 0 ]; then
        log_warning "No NVIDIA GPU detected"
        read -p "Continue with CPU-only deployment? [y/N]: " cpu_confirm
        if [[ ! "$cpu_confirm" =~ ^[Yy]$ ]]; then
            log_info "Skipping AI model deployment"
            mark_phase_complete "phase-09-ai-model"
            return 0
        fi
    fi

    # Reuse the earlier model selection when available to avoid prompting twice.
    local selected_model=""
    selected_model=$(resolve_llama_cpp_model)

    if [[ -n "$selected_model" ]]; then
        log_info "Using previously selected model: $selected_model"
    else
        selected_model=$(ai_select_model)
    fi

    if [ "$selected_model" = "SKIP" ]; then
        log_info "AI model deployment skipped by user"
        mark_phase_complete "phase-09-ai-model"
        return 0
    fi

    # Save selection to preferences (consolidated with LLM models)
    local pref_file="${LLM_MODELS_PREFERENCE_FILE:-${CACHE_DIR}/preferences/llm-models.env}"
    mkdir -p "$(dirname "$pref_file")"
    if grep -q "^LLAMA_CPP_DEFAULT_MODEL=" "$pref_file" 2>/dev/null; then
        sed -i "s|^LLAMA_CPP_DEFAULT_MODEL=.*|LLAMA_CPP_DEFAULT_MODEL=$selected_model|" "$pref_file" 2>/dev/null || true
    else
        echo "LLAMA_CPP_DEFAULT_MODEL=$selected_model" >>"$pref_file"
    fi
    if grep -q "^GPU_VRAM=" "$pref_file" 2>/dev/null; then
        sed -i "s|^GPU_VRAM=.*|GPU_VRAM=$gpu_vram|" "$pref_file" 2>/dev/null || true
    else
        echo "GPU_VRAM=$gpu_vram" >>"$pref_file"
    fi

    # Pre-download selected GGUF models (optional)
    log_info "Preparing optional GGUF model downloads..."
    if [ -f "${SCRIPT_DIR}/scripts/download-llama-cpp-models.sh" ]; then
        local model_key
        local swap_keys
        local download_selected="yes"
        local download_swaps="no"
        local skip_selected_download="false"
        model_key=$(map_llama_model_to_download_key "$selected_model")
        swap_keys="qwen3-4b,qwen-coder,deepseek"

        # If the selected GGUF already exists (from Phase 6 or prior), skip all downloads.
        local model_file
        local model_dir="${HOME}/.local/share/nixos-ai-stack/llama-cpp-models"
        local cache_dir="${HUGGINGFACE_HOME:-$HOME/.cache/huggingface}"
        model_file=$(get_model_filename_from_id "$selected_model")
        if [[ -n "$model_file" ]]; then
            if find "$cache_dir" -name "$model_file" 2>/dev/null | grep -q . || [[ -f "${model_dir}/${model_file}" ]]; then
                log_info "Selected model already present (${model_file}); skipping selected model download."
                skip_selected_download="true"
            fi
        fi

        if [[ "$skip_selected_download" == "true" ]]; then
            :
        elif [[ -n "$model_key" ]]; then
            read -p "Download selected model now (${model_key})? [Y/n]: " download_confirm
            if [[ ! "$download_confirm" =~ ^[Nn]$ ]]; then
                bash "${SCRIPT_DIR}/scripts/download-llama-cpp-models.sh" --model "$model_key" || {
                    log_warning "Model download incomplete. It will download on first container startup."
                }
                download_selected="yes"
            else
                log_info "Selected model will download automatically on first container startup"
                download_selected="no"
            fi
        else
            log_warning "No GGUF download key matched for selected model; skipping pre-download."
            download_selected="no"
        fi

        read -p "Download additional swap models for quick testing? (qwen3-4b,qwen-coder,deepseek) [y/N]: " swap_confirm
        if [[ "$swap_confirm" =~ ^[Yy]$ ]]; then
            download_swaps="yes"
            if [[ -n "$model_key" ]]; then
                swap_keys=$(echo "$swap_keys" | awk -v key="$model_key" -F',' '{for (i=1;i<=NF;i++) if ($i!=key && $i!="") printf (out?"," :"")$i; out=1}')
            fi
            if [[ -n "$swap_keys" ]]; then
                bash "${SCRIPT_DIR}/scripts/download-llama-cpp-models.sh" --models "$swap_keys" || {
                    log_warning "Some swap models failed to download; check logs if needed."
                }
            fi
        fi
    else
        log_warning "Model download script not found; models will download on first container startup"
    fi

    # Ask whether to start the AI stack now (may pull images / auto-download models)
    read -p "Start AI stack now? (pulls images; llama.cpp may auto-download models) [Y/n]: " start_confirm
    if [[ "$start_confirm" =~ ^[Nn]$ ]]; then
        log_info "Skipping AI stack deployment and hybrid learning setup (can run later)."
        mark_phase_complete "phase-09-ai-model"
        return 0
    fi

    # Setup Hybrid Learning System (Automated)
    log_info "Setting up Hybrid Local-Remote AI Learning System..."
    export HYBRID_LEARNING_SETUP_TIMEOUT="${HYBRID_LEARNING_SETUP_TIMEOUT:-900}"
    export HYBRID_LEARNING_CLEAN_RESTART="${HYBRID_LEARNING_CLEAN_RESTART:-true}"
    if [[ "${SKIP_HYBRID_LEARNING_SETUP:-false}" == "true" ]]; then
        log_info "Skipping hybrid learning setup (SKIP_HYBRID_LEARNING_SETUP=true)"
    elif [ -f "${SCRIPT_DIR}/scripts/setup-hybrid-learning-auto.sh" ]; then
        local setup_timeout="${HYBRID_LEARNING_SETUP_TIMEOUT:-900}"
        local timeout_cmd=()
        if command -v timeout >/dev/null 2>&1; then
            timeout_cmd=(timeout "${setup_timeout}")
        fi

        if command -v stdbuf >/dev/null 2>&1; then
            "${timeout_cmd[@]}" stdbuf -oL -eL bash "${SCRIPT_DIR}/scripts/setup-hybrid-learning-auto.sh" 2>&1 | \
                while IFS= read -r line; do
                    log_info "[hybrid-setup] $line"
                done
        else
            "${timeout_cmd[@]}" bash "${SCRIPT_DIR}/scripts/setup-hybrid-learning-auto.sh" 2>&1 | \
                while IFS= read -r line; do
                    log_info "[hybrid-setup] $line"
                done
        fi

        local setup_status=${PIPESTATUS[0]:-0}
        if [[ $setup_status -eq 0 ]]; then
            log_success "Hybrid learning system initialized"
        else
            log_warning "Hybrid learning setup encountered issues (or timed out) but will continue"
        fi
    else
        log_warning "Automated setup script not found, skipping hybrid learning setup"
    fi

    # Deploy AI stack with selected model
    log_info "Deploying AI stack with model: $selected_model"

    if ai_deploy_llama_cpp "$selected_model" "${SCRIPT_DIR}/ai-stack/compose"; then
        log_success "AI stack deployment initiated"

        # Detect container runtime for user instructions
        local container_cmd="podman"
        if command -v docker >/dev/null 2>&1 && systemctl is-active docker >/dev/null 2>&1; then
            container_cmd="docker"
        fi

        # Add monitoring instructions
        cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI Model Deployment Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Selected Model: $selected_model
GPU: $gpu_name ($gpu_vram GB VRAM)

⏳ Model Download in Progress

The first-time model download may take 10-45 minutes depending on:
  • Model size (7GB to 32GB)
  • Internet connection speed
  • HuggingFace server load

Monitor Progress:
  $container_cmd logs -f local-ai-llama-cpp

Check Status:
  $container_cmd ps | grep llama-cpp
  curl http://localhost:8080/health

System Dashboard:
  • Open: ai-stack/dashboard/index.html in your browser
  • Monitor all services, learning metrics, and federation status
  • Access all documentation from one central hub
  • Real-time health checks every 30 seconds

Once Ready:
  • AIDB MCP Server: http://localhost:8091
  • llama.cpp General: http://localhost:8080
  • llama.cpp Coder: http://localhost:8001/api/v1
  • llama.cpp DeepSeek: http://localhost:8003/api/v1
  • Qdrant Vector DB: http://localhost:6333
  • Hybrid Coordinator MCP Server: Available via MCP protocol
  • AI Assistant available in deployment scripts

Hybrid Learning Features:
  ✓ Context augmentation from local knowledge base
  ✓ Automatic interaction tracking and value scoring
  ✓ Pattern extraction from successful interactions
  ✓ Multi-node federation for distributed learning
  ✓ Fine-tuning dataset generation
  ✓ Continuous improvement of local LLMs

Documentation:
  • Quick Start: AI-AGENT-SETUP.md
  • Complete Guide: HYBRID-AI-SYSTEM-GUIDE.md
  • Architecture: ai-knowledge-base/HYBRID-LEARNING-ARCHITECTURE.md
  • Multi-Node Setup: DISTRIBUTED-LEARNING-GUIDE.md
  • Dashboard Guide: SYSTEM-DASHBOARD-README.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

        # Offer to wait for completion
        read -p "Wait for model download to complete? [y/N]: " wait_confirm
        if [[ "$wait_confirm" =~ ^[Yy]$ ]]; then
            log_info "Waiting for llama.cpp model download..."
            wait_for_llama_cpp_ready
        fi

        mark_phase_complete "phase-09-ai-model"
        return 0
    else
        log_error "Failed to deploy AI stack"
        return 1
    fi
}

# ============================================================================
# Helper Functions
# ============================================================================


wait_for_llama_cpp_ready() {
    local max_wait=3600  # 1 hour max
    local elapsed=0
    local interval=30

    log_info "Waiting for llama.cpp to download and load model..."
    log_info "This may take 10-45 minutes. Press Ctrl+C to skip and continue in background."

    while [ $elapsed -lt $max_wait ]; do
        if curl -sf --max-time 5 http://localhost:8080/health > /dev/null 2>&1; then
            log_success "llama.cpp is ready!"
            return 0
        fi

        # Show progress indicator
        local dots=$(printf '.%.0s' $(seq 1 $((elapsed / 10 % 4))))
        echo -ne "\r⏳ Waiting for model download$dots (${elapsed}s elapsed)   "

        sleep $interval
        elapsed=$((elapsed + interval))
    done

    log_warning "Timed out waiting for llama.cpp. Model may still be downloading in background."
    log_info "Check progress: docker logs -f llama-cpp"
    return 1
}

resolve_llama_cpp_model() {
    local model="${LLAMA_CPP_DEFAULT_MODEL:-}"
    local pref_file="${LLM_MODELS_PREFERENCE_FILE:-}"
    local legacy_pref="${CACHE_DIR:-$HOME/.cache/nixos-quick-deploy}/preferences/ai-model.env"

    if [[ -z "$model" && -n "$pref_file" && -f "$pref_file" ]]; then
        model=$(awk -F'=' '/^LLAMA_CPP_DEFAULT_MODEL=/{print $2}' "$pref_file" 2>/dev/null | tail -n1 | tr -d '\r')
    fi

    if [[ -z "$model" && -f "$legacy_pref" ]]; then
        model=$(awk -F'=' '/^LLAMA_CPP_DEFAULT_MODEL=/{print $2}' "$legacy_pref" 2>/dev/null | tail -n1 | tr -d '\r')
    fi

    if [[ -z "$model" && -n "${CODER_MODEL:-}" ]]; then
        model=$(map_coder_to_llama_model "$CODER_MODEL")
    fi

    if [[ -z "$model" && -n "${LLM_MODELS:-}" ]]; then
        local coder="${LLM_MODELS%%,*}"
        model=$(map_coder_to_llama_model "$coder")
    fi

    echo "$model"
}

map_coder_to_llama_model() {
    local coder="${1:-}"

    if [[ -z "$coder" ]]; then
        echo ""
        return 0
    fi

    if [[ "$coder" == */* ]]; then
        echo "$coder"
        return 0
    fi

    case "$coder" in
        qwen3-4b|qwen3-4b-instruct)
            echo "unsloth/Qwen3-4B-Instruct-2507-GGUF"
            ;;
        qwen2.5-coder|qwen2.5-coder-7b|qwen2.5-coder-7b-instruct)
            echo "Qwen/Qwen2.5-Coder-7B-Instruct"
            ;;
        qwen2.5-coder-14b|qwen2.5-coder-14b-instruct)
            echo "Qwen/Qwen2.5-Coder-14B-Instruct"
            ;;
        deepseek-coder-v2-lite|deepseek-lite)
            echo "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
            ;;
        deepseek-coder-v2|deepseek-v2)
            echo "deepseek-ai/DeepSeek-Coder-V2-Instruct"
            ;;
        phi-mini|phi-3-mini)
            echo "microsoft/Phi-3-mini-4k-instruct"
            ;;
        codellama-13b)
            echo "codellama/CodeLlama-13b-Instruct-hf"
            ;;
        *)
            echo ""
            ;;
    esac
}

map_llama_model_to_download_key() {
    local model="${1:-}"
    if [[ -z "$model" ]]; then
        echo ""
        return 0
    fi

    case "$model" in
        *Qwen2.5-Coder-7B*|*qwen2.5-coder-7b*)
            echo "qwen-coder"
            ;;
        *Qwen3-4B*|*qwen3-4b*)
            echo "qwen3-4b"
            ;;
        *deepseek*|*DeepSeek*)
            echo "deepseek"
            ;;
        *)
            echo ""
            ;;
    esac
}

# ============================================================================
# Phase Execution Check
# ============================================================================

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    # Running directly, not sourced
    echo "This script should be sourced by nixos-quick-deploy.sh"
    exit 1
fi
