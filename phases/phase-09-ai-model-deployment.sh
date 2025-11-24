#!/usr/bin/env bash
# Phase 9: AI Model Deployment (vLLM)
# Part of: nixos-quick-deploy.sh
# Version: 5.0.0
# Purpose: Optional deployment of AI coding models via vLLM

set -euo pipefail

# ============================================================================
# Phase 9: AI Model Deployment
# ============================================================================

phase_09_ai_model_deployment() {
    log_phase_start 9 "AI Model Deployment (Optional)"

    # Check if user wants AI capabilities
    if ! prompt_ai_deployment; then
        log_info "Skipping AI model deployment"
        mark_phase_complete 9
        return 0
    fi

    # Load AI-Optimizer integration library
    if [ -f "${SCRIPT_DIR}/lib/ai-optimizer.sh" ]; then
        source "${SCRIPT_DIR}/lib/ai-optimizer.sh"
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
            mark_phase_complete 9
            return 0
        fi
    fi

    # Interactive model selection
    local selected_model=$(ai_select_model)

    if [ "$selected_model" = "SKIP" ]; then
        log_info "AI model deployment skipped by user"
        mark_phase_complete 9
        return 0
    fi

    # Save selection to preferences
    mkdir -p "${CACHE_DIR}/preferences"
    echo "VLLM_MODEL=$selected_model" > "${CACHE_DIR}/preferences/ai-model.env"
    echo "GPU_VRAM=$gpu_vram" >> "${CACHE_DIR}/preferences/ai-model.env"

    # Deploy AI-Optimizer with selected model
    log_info "Deploying AI-Optimizer with model: $selected_model"

    if ai_deploy_vllm "$selected_model" "$HOME/Documents/AI-Optimizer"; then
        log_success "AI-Optimizer deployment initiated"

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
  docker logs -f vllm-inference

Check Status:
  docker ps | grep vllm
  curl http://localhost:8000/health

Once Ready:
  • AIDB MCP Server: http://localhost:8091
  • vLLM Inference: http://localhost:8000
  • AI Assistant available in deployment scripts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

        # Offer to wait for completion
        read -p "Wait for model download to complete? [y/N]: " wait_confirm
        if [[ "$wait_confirm" =~ ^[Yy]$ ]]; then
            log_info "Waiting for vLLM model download..."
            wait_for_vllm_ready "$selected_model"
        fi

        mark_phase_complete 9
        return 0
    else
        log_error "Failed to deploy AI-Optimizer"
        return 1
    fi
}

# ============================================================================
# Helper Functions
# ============================================================================

prompt_ai_deployment() {
    cat <<EOF

╭───────────────────────────────────────────────────────────────────────────╮
│ AI-Powered Development Environment                                        │
│                                                                            │
│ NixOS-Dev-Quick-Deploy can integrate with AI-Optimizer to provide:        │
│                                                                            │
│ ✨ AI-powered NixOS configuration generation                              │
│ ✨ Intelligent code review and suggestions                                │
│ ✨ Real-time coding assistance (10-60 tok/s)                              │
│ ✨ ML-based system monitoring                                             │
│ ✨ Automated deployment recommendations                                    │
│                                                                            │
│ Requirements:                                                              │
│   • NVIDIA GPU with 8GB+ VRAM (recommended 16GB+)                         │
│   • 20-50GB disk space for model storage                                  │
│   • Docker/Podman for containerized deployment                            │
│                                                                            │
│ Models Available (November 2025):                                         │
│   • Qwen2.5-Coder-7B: Best for most users (88.4% accuracy)               │
│   • Qwen2.5-Coder-14B: Maximum quality (89.7% accuracy)                   │
│   • DeepSeek-Coder-V2: Advanced reasoning (300+ languages)                │
│   • Phi-3-mini: Lightweight testing (8GB VRAM)                            │
│                                                                            │
╰───────────────────────────────────────────────────────────────────────────╯

EOF

    read -p "Deploy AI coding model? [Y/n]: " deploy_confirm

    if [[ "$deploy_confirm" =~ ^[Nn]$ ]]; then
        return 1
    else
        return 0
    fi
}

wait_for_vllm_ready() {
    local model_name="$1"
    local max_wait=3600  # 1 hour max
    local elapsed=0
    local interval=30

    log_info "Waiting for vLLM to download and load model..."
    log_info "This may take 10-45 minutes. Press Ctrl+C to skip and continue in background."

    while [ $elapsed -lt $max_wait ]; do
        if curl -sf --max-time 5 http://localhost:8000/health > /dev/null 2>&1; then
            log_success "vLLM is ready!"

            # Test model
            local test_response=$(curl -s -X POST http://localhost:8000/v1/completions \
                -H "Content-Type: application/json" \
                -d '{"model": "'"$model_name"'", "prompt": "def hello():", "max_tokens": 10}' 2>/dev/null || echo "")

            if [ -n "$test_response" ]; then
                log_success "Model loaded and responding!"
                return 0
            fi
        fi

        # Show progress indicator
        local dots=$(printf '.%.0s' $(seq 1 $((elapsed / 10 % 4))))
        echo -ne "\r⏳ Waiting for model download$dots (${elapsed}s elapsed)   "

        sleep $interval
        elapsed=$((elapsed + interval))
    done

    log_warning "Timed out waiting for vLLM. Model may still be downloading in background."
    log_info "Check progress: docker logs -f vllm-inference"
    return 1
}

# ============================================================================
# Phase Execution Check
# ============================================================================

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    # Running directly, not sourced
    echo "This script should be sourced by nixos-quick-deploy.sh"
    exit 1
fi
