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

    # Respect global AI stack flag to avoid duplicate questions.
    if [[ "${RUN_AI_MODEL:-true}" != "true" || "${LOCAL_AI_STACK_ENABLED:-true}" != "true" ]]; then
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
    local gpu_vram
    local gpu_name
    gpu_vram=$(detect_gpu_vram)
    gpu_name=$(detect_gpu_model)

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
        if ! sed -i "s|^LLAMA_CPP_DEFAULT_MODEL=.*|LLAMA_CPP_DEFAULT_MODEL=$selected_model|" "$pref_file" 2>/dev/null; then
            log_warning "Failed to update LLAMA_CPP_DEFAULT_MODEL in $pref_file"
        fi
    else
        echo "LLAMA_CPP_DEFAULT_MODEL=$selected_model" >>"$pref_file"
    fi
    if grep -q "^GPU_VRAM=" "$pref_file" 2>/dev/null; then
        if ! sed -i "s|^GPU_VRAM=.*|GPU_VRAM=$gpu_vram|" "$pref_file" 2>/dev/null; then
            log_warning "Failed to update GPU_VRAM in $pref_file"
        fi
    else
        echo "GPU_VRAM=$gpu_vram" >>"$pref_file"
    fi
    # Runtime model/bootstrap scripts are deprecated in declarative mode.
    log_info "Skipping imperative model downloads and hybrid-learning bootstrap (declarative mode)."

    # Deploy AI stack with selected model
    log_info "Deploying AI stack with model: $selected_model"

    if ai_deploy_llama_cpp "$selected_model" "${SCRIPT_DIR}/ai-stack/kubernetes"; then
        log_success "AI stack deployment initiated"

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
  kubectl logs --request-timeout=30s -n ai-stack deploy/llama-cpp -f

Check Status:
  kubectl get pods --request-timeout=30s -n ai-stack -l app=llama-cpp
  kubectl get deploy --request-timeout=30s -n ai-stack llama-cpp

System Dashboard:
  • Open: ${SCRIPT_DIR}/ai-stack/dashboard/index.html in your browser
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
        if curl_safe -sf http://localhost:8080/health > /dev/null 2>&1; then
            log_success "llama.cpp is ready!"
            return 0
        fi

        # Show progress indicator
        local dots
        dots=$(printf '.%.0s' $(seq 1 $((elapsed / 10 % 4))))
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
