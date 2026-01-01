#!/usr/bin/env bash
# AI-Optimizer Integration Library for NixOS-Dev-Quick-Deploy
# Version: 1.0.0
# Date: 2025-11-22
#
# Purpose: Optional integration with AI-Optimizer AIDB MCP for:
#   - llama.cpp-powered code generation
#   - NixOS configuration assistance
#   - ML-based system monitoring
#   - Intelligent deployment recommendations
#
# Falls back gracefully if AI-Optimizer is unavailable. This file is sourced
# as a library, so it does not modify shell options (set -e/-u/-o pipefail).

# ============================================================================
# Configuration
# ============================================================================

AIDB_BASE_URL="${AIDB_BASE_URL:-http://localhost:8091}"
LLAMA_CPP_BASE_URL="${LLAMA_CPP_BASE_URL:-http://localhost:8080}"
AI_ENABLED="${AI_ENABLED:-auto}"  # auto, true, false
AI_AVAILABLE=false

# Model catalog for interactive selection
declare -A AI_MODELS=(
    ["qwen-7b"]="Qwen/Qwen2.5-Coder-7B-Instruct"
    ["qwen-14b"]="Qwen/Qwen2.5-Coder-14B-Instruct"
    ["deepseek-lite"]="deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
    ["deepseek-v2"]="deepseek-ai/DeepSeek-Coder-V2-Instruct"
    ["phi-mini"]="microsoft/Phi-3-mini-4k-instruct"
    ["codellama-13b"]="codellama/CodeLlama-13b-Instruct-hf"
)

# Model metadata
declare -A MODEL_VRAM=(
    ["qwen-7b"]="16"
    ["qwen-14b"]="24"
    ["deepseek-lite"]="20"
    ["deepseek-v2"]="32"
    ["phi-mini"]="8"
    ["codellama-13b"]="24"
)

declare -A MODEL_SPEED=(
    ["qwen-7b"]="40-60"
    ["qwen-14b"]="30-45"
    ["deepseek-lite"]="20-30"
    ["deepseek-v2"]="15-25"
    ["phi-mini"]="60-80"
    ["codellama-13b"]="20-35"
)

declare -A MODEL_QUALITY=(
    ["qwen-7b"]="88.4%"
    ["qwen-14b"]="89.7%"
    ["deepseek-lite"]="81.1%"
    ["deepseek-v2"]="84.5%"
    ["phi-mini"]="68.3%"
    ["codellama-13b"]="78.2%"
)

# ============================================================================
# GPU Detection
# ============================================================================

detect_gpu_vram() {
    local vram_gb=0

    if command -v nvidia-smi &> /dev/null; then
        vram_gb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | awk '{print int($1/1024)}' || echo 0)
    fi

    echo "$vram_gb"
}

detect_gpu_model() {
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=gpu_name --format=csv,noheader 2>/dev/null | head -1
    else
        echo "No NVIDIA GPU detected"
    fi
}

# ============================================================================
# AI Availability Check
# ============================================================================

ai_check_availability() {
    if [ "$AI_ENABLED" = "false" ]; then
        AI_AVAILABLE=false
        return 1
    fi

    # Check AIDB MCP Server
    if curl -sf --max-time 2 "$AIDB_BASE_URL/health" > /dev/null 2>&1; then
        AI_AVAILABLE=true
        return 0
    else
        AI_AVAILABLE=false
        return 1
    fi
}

ai_check_llama_cpp() {
    local base="${LLAMA_CPP_BASE_URL%/}"
    base="${base%/api/v1}"
    if curl -sf --max-time 2 "$base/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

aidb_post_with_fallback() {
    local primary_endpoint="$1"
    local fallback_endpoint="$2"
    local payload="$3"
    local timeout="$4"
    local response=""
    local last_response=""

    if [ -z "$timeout" ]; then
        timeout=60
    fi

    for endpoint in "$primary_endpoint" "$fallback_endpoint"; do
        if [ -z "$endpoint" ]; then
            continue
        fi

        response=$(curl -s -X POST "$AIDB_BASE_URL/$endpoint" \
            -H "Content-Type: application/json" \
            --max-time "$timeout" \
            -d "$payload")

        if echo "$response" | jq -e '.success == true' > /dev/null 2>&1; then
            echo "$response"
            return 0
        fi

        last_response="$response"
    done

    if [ -n "$last_response" ]; then
        echo "$last_response"
    else
        echo "$response"
    fi

    return 1
}

# ============================================================================
# Model Selection Interface
# ============================================================================

ai_recommend_model() {
    local vram_gb="$1"

    if [ "$vram_gb" -ge 24 ]; then
        echo "qwen-14b"  # Best quality for high-end GPUs
    elif [ "$vram_gb" -ge 16 ]; then
        echo "qwen-7b"   # Recommended for most users
    elif [ "$vram_gb" -ge 12 ]; then
        echo "deepseek-lite"
    else
        echo "phi-mini"  # Lightweight for budget GPUs
    fi
}

ai_display_model_menu() {
    local gpu_vram="$1"
    local gpu_name="$2"
    local recommended="$3"

    cat <<EOF

╭───────────────────────────────────────────────────────────────────────────╮
│ AI Model Selection (llama.cpp)                                             │
│                                                                            │
│ Detected GPU: $gpu_name
│ Available VRAM: ${gpu_vram}GB
│                                                                            │
│ Select the AI coding model for your workstation:                          │
│                                                                            │
│ [1] Qwen2.5-Coder-7B (Recommended for most users)                         │
│     - VRAM: 16GB  |  Speed: 40-60 tok/s  |  Quality: 88.4%               │
│     - Best for: NixOS, general coding, fast iteration                     │
│                                                                            │
│ [2] Qwen2.5-Coder-14B (Maximum quality)                                   │
│     - VRAM: 24GB  |  Speed: 30-45 tok/s  |  Quality: 89.7%               │
│     - Best for: Production workloads, complex code                         │
│                                                                            │
│ [3] DeepSeek-Coder-V2-Lite (Advanced reasoning)                           │
│     - VRAM: 20GB  |  Speed: 20-30 tok/s  |  Quality: 81.1%               │
│     - Best for: Algorithms, math, 300+ languages                           │
│                                                                            │
│ [4] DeepSeek-Coder-V2 (Enterprise)                                        │
│     - VRAM: 32GB  |  Speed: 15-25 tok/s  |  Quality: 84.5%               │
│     - Best for: Multi-GPU setups, highest reasoning                        │
│                                                                            │
│ [5] Phi-3-mini (Lightweight testing)                                      │
│     - VRAM: 8GB   |  Speed: 60-80 tok/s  |  Quality: 68.3%               │
│     - Best for: Testing, budget GPUs, CPU-only                             │
│                                                                            │
│ [6] CodeLlama-13B (Stable/Mature)                                         │
│     - VRAM: 24GB  |  Speed: 20-35 tok/s  |  Quality: 78.2%               │
│     - Best for: Legacy compatibility, well-tested                          │
│                                                                            │
│ [c] Custom (specify HuggingFace model ID)                                 │
│                                                                            │
│ [0] Skip AI model installation                                            │
│                                                                            │
╰───────────────────────────────────────────────────────────────────────────╯

EOF

    case "$recommended" in
        "qwen-14b")
            echo "💡 Recommended: [1] Qwen2.5-Coder-7B or [2] Qwen2.5-Coder-14B (you have 24GB+)"
            ;;
        "qwen-7b")
            echo "💡 Recommended: [1] Qwen2.5-Coder-7B (perfect for your 16GB GPU)"
            ;;
        "deepseek-lite")
            echo "💡 Recommended: [3] DeepSeek-Coder-V2-Lite (optimized for your VRAM)"
            ;;
        "phi-mini")
            echo "💡 Recommended: [5] Phi-3-mini (best fit for your GPU)"
            ;;
    esac
}

# Detect already downloaded models from cache
ai_detect_cached_models() {
    local hf_cache="${HOME}/.cache/huggingface"
    local ai_stack_models="${HOME}/.local/share/nixos-ai-stack/llama-cpp-models"
    local podman_models="${HOME}/.local/share/podman-ai-stack/llama-cpp-models"
    declare -A cached_models

    # Helper function to check if a model file exists in any location
    check_model_file() {
        local filename="$1"
        local model_key="$2"
        local model_id="$3"

        # Check in HuggingFace cache (downloaded via huggingface-cli)
        if find "${hf_cache}" -name "${filename}" 2>/dev/null | grep -q .; then
            cached_models[$model_key]="$model_id"
            return 0
        fi

        # Check in AI stack models directory (manually placed)
        if [ -f "${ai_stack_models}/${filename}" ]; then
            cached_models[$model_key]="$model_id"
            return 0
        fi

        # Check in podman AI stack directory (legacy location)
        if [ -f "${podman_models}/${filename}" ]; then
            cached_models[$model_key]="$model_id"
            return 0
        fi

        return 1
    }

    # Check for qwen-coder (Qwen2.5-Coder-7B)
    check_model_file "qwen2.5-coder-7b-instruct-q4_k_m.gguf" "qwen-coder" "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"

    # Check for qwen3-4b (Qwen3-4B-Instruct)
    check_model_file "Qwen3-4B-Instruct-2507-Q4_K_M.gguf" "qwen3-4b" "unsloth/Qwen3-4B-Instruct-2507-GGUF"

    # Check for deepseek (DeepSeek-Coder-6.7B)
    check_model_file "deepseek-coder-6.7b-instruct.Q4_K_M.gguf" "deepseek" "TheBloke/deepseek-coder-6.7B-instruct-GGUF"

    # Check for qwen-14b (Qwen2.5-Coder-14B)
    check_model_file "qwen2.5-coder-14b-instruct-q4_k_m.gguf" "qwen-14b" "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"

    # Return the keys of cached models
    echo "${!cached_models[@]}"
}

# Display menu showing ONLY cached models
ai_display_cached_model_menu() {
    local -a cached=($1)
    local count=${#cached[@]}

    if [ $count -eq 0 ]; then
        # No cached models - show message
        cat <<EOF

╭───────────────────────────────────────────────────────────────────────────╮
│ AI Model Selection (llama.cpp)                                             │
│                                                                            │
│ No models found in cache. Models will be downloaded on first startup.     │
│                                                                            │
│ [0] Skip AI model deployment                                              │
╰───────────────────────────────────────────────────────────────────────────╯
EOF
        return
    fi

    cat <<EOF

╭───────────────────────────────────────────────────────────────────────────╮
│ AI Model Selection (llama.cpp)                                             │
│                                                                            │
│ The following models are already downloaded and ready to use:             │
│                                                                            │
EOF

    local option=1
    for model in "${cached[@]}"; do
        case "$model" in
            qwen-coder)
                echo "│ [$option] Qwen2.5-Coder-7B (Recommended)                                      │"
                echo "│     - Size: 4.4GB  |  Speed: 40-60 tok/s  |  Quality: 88.4%               │"
                ;;
            qwen-14b)
                echo "│ [$option] Qwen2.5-Coder-14B (Maximum Quality)                                 │"
                echo "│     - Size: 8.9GB  |  Speed: 30-45 tok/s  |  Quality: 89.7%               │"
                ;;
            qwen3-4b)
                echo "│ [$option] Qwen3-4B-Instruct (Lightweight)                                     │"
                echo "│     - Size: 2.3GB  |  Speed: 60-80 tok/s  |  Quality: 85%                 │"
                ;;
            deepseek)
                echo "│ [$option] DeepSeek-Coder-6.7B (Advanced reasoning)                            │"
                echo "│     - Size: 3.8GB  |  Speed: 35-50 tok/s  |  Quality: 86%                 │"
                ;;
        esac
        option=$((option + 1))
    done

    cat <<EOF
│                                                                            │
│ [0] Skip AI model deployment                                              │
╰───────────────────────────────────────────────────────────────────────────╯
EOF
}

ai_select_model() {
    local gpu_vram=$(detect_gpu_vram)
    local gpu_name=$(detect_gpu_model)

    # Detect cached models
    local cached_models=$(ai_detect_cached_models)
    local -a cached_array=($cached_models)
    local count=${#cached_array[@]}

    # Display menu with only cached models (send to stderr so it shows when output captured)
    ai_display_cached_model_menu "$cached_models" >&2

    if [ $count -eq 0 ]; then
        # No cached models - skip
        read -p "Press Enter to skip or 'q' to quit: " choice >&2
        echo "SKIP"
        return
    fi

    echo "" >&2
    read -p "Select option [1-${count}, 0]: " choice >&2

    # Validate choice
    if [[ "$choice" == "0" ]]; then
        echo "SKIP"
        return
    elif [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "$count" ]; then
        # Valid selection - return the corresponding model
        local selected_index=$((choice - 1))
        local selected_model="${cached_array[$selected_index]}"

        case "$selected_model" in
            qwen-coder)
                echo "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
                ;;
            qwen-14b)
                echo "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"
                ;;
            qwen3-4b)
                echo "unsloth/Qwen3-4B-Instruct-2507-GGUF"
                ;;
            deepseek)
                echo "TheBloke/deepseek-coder-6.7B-instruct-GGUF"
                ;;
            *)
                echo "SKIP"
                ;;
        esac
    else
        echo "Invalid choice. Please try again." >&2
        ai_select_model  # Retry
    fi
}

# ============================================================================
# AI-Optimizer Integration Functions
# ============================================================================

ai_generate_nix_config() {
    local description="$1"
    local context="${2:-}"

    if ! ai_check_availability; then
        log_warning "AI-Optimizer not available - manual configuration needed"
        return 1
    fi

    log_info "Generating NixOS configuration with AI..."

    local payload=$(jq -n \
        --arg desc "$description" \
        --arg ctx "$context" \
        '{description: $desc, context: $ctx}')

    local response
    if response=$(aidb_post_with_fallback "llama_cpp/nix" "vllm/nix" "$payload" 60); then
        echo "$response" | jq -r '.nix_code'
        return 0
    else
        local error=$(echo "$response" | jq -r '.error // "Unknown error"')
        log_error "Failed to generate configuration: $error"
        return 1
    fi
}

ai_review_config() {
    local config_file="$1"

    if ! ai_check_availability; then
        log_warning "AI review not available - please review manually"
        return 1
    fi

    if [ ! -f "$config_file" ]; then
        log_error "Configuration file not found: $config_file"
        return 1
    fi

    log_info "Reviewing configuration with AI..."

    local code=$(cat "$config_file")
    local payload=$(jq -n \
        --arg code "$code" \
        '{code: $code, language: "nix"}')

    local response
    if response=$(aidb_post_with_fallback "llama_cpp/review" "vllm/review" "$payload" 60); then
        echo "$response" | jq -r '.review'
        return 0
    else
        log_error "Failed to review configuration"
        return 1
    fi
}

ai_explain_code() {
    local code="$1"
    local language="${2:-nix}"

    if ! ai_check_availability; then
        return 1
    fi

    local payload=$(jq -n \
        --arg code "$code" \
        --arg lang "$language" \
        '{code: $code, language: $lang}')

    local response
    if response=$(aidb_post_with_fallback "llama_cpp/explain" "vllm/explain" "$payload" 30); then
        echo "$response" | jq -r '.explanation'
        return 0
    else
        return 1
    fi
}

ai_chat() {
    local question="$1"
    local system_prompt="${2:-You are a NixOS deployment expert. Provide concise, actionable answers.}"

    if ! ai_check_availability; then
        return 1
    fi

    local payload=$(jq -n \
        --arg sys "$system_prompt" \
        --arg user "$question" \
        '{
            messages: [
                {role: "system", content: $sys},
                {role: "user", content: $user}
            ],
            max_tokens: 500,
            temperature: 0.7
        }')

    local response
    if response=$(aidb_post_with_fallback "llama_cpp/chat" "vllm/chat" "$payload" 60); then
        echo "$response" | jq -r '.message'
        return 0
    else
        return 1
    fi
}

# ============================================================================
# Interactive AI Features
# ============================================================================

ai_interactive_help() {
    if ! ai_check_availability; then
        log_warning "AI assistance not available"
        return 1
    fi

    cat <<EOF

╭───────────────────────────────────────────────────────────────╮
│ AI-Powered Deployment Assistant                               │
│                                                                │
│ What would you like help with?                                 │
│                                                                │
│ [g] Generate NixOS configuration from description              │
│ [r] Review existing configuration                             │
│ [e] Explain code snippet                                      │
│ [q] Ask a question                                            │
│ [0] Return to deployment                                      │
│                                                                │
╰───────────────────────────────────────────────────────────────╯

EOF

    read -p "Select option [g/r/e/q/0]: " choice

    case "$choice" in
        g|G)
            echo ""
            read -p "Describe what you want to configure: " description
            echo ""
            log_info "Generating configuration..."
            local generated=$(ai_generate_nix_config "$description")
            if [ $? -eq 0 ]; then
                echo ""
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "Generated Configuration:"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "$generated"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
                read -p "Save to file? [Y/n]: " save
                if [[ ! "$save" =~ ^[Nn]$ ]]; then
                    read -p "Filename: " filename
                    echo "$generated" > "$filename"
                    log_success "Saved to: $filename"
                fi
            fi
            ;;
        r|R)
            echo ""
            read -p "Path to configuration file: " config_path
            echo ""
            log_info "Reviewing configuration..."
            local review=$(ai_review_config "$config_path")
            if [ $? -eq 0 ]; then
                echo ""
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "AI Review:"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "$review"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            fi
            ;;
        e|E)
            echo ""
            echo "Paste code to explain (Ctrl+D when done):"
            local code=$(cat)
            echo ""
            read -p "Language [nix]: " language
            language="${language:-nix}"
            log_info "Generating explanation..."
            local explanation=$(ai_explain_code "$code" "$language")
            if [ $? -eq 0 ]; then
                echo ""
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "Explanation:"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "$explanation"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            fi
            ;;
        q|Q)
            echo ""
            read -p "Your question: " question
            echo ""
            log_info "Thinking..."
            local answer=$(ai_chat "$question")
            if [ $? -eq 0 ]; then
                echo ""
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "AI Assistant:"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "$answer"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            fi
            ;;
        0)
            return 0
            ;;
        *)
            log_warning "Invalid choice"
            ai_interactive_help
            ;;
    esac

    echo ""
    read -p "Press Enter to continue..."
    ai_interactive_help  # Loop back to menu
}

# ============================================================================
# llama.cpp Container Management
# ============================================================================

# Helper function to get GGUF filename from model ID
get_model_filename_from_id() {
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
            # Try to extract filename from model ID
            local base=$(basename "$model_id")
            if [[ "$base" == *.gguf ]]; then
                echo "$base"
            else
                echo "qwen2.5-coder-7b-instruct-q4_k_m.gguf"  # Default fallback
            fi
            ;;
    esac
}

ai_deploy_llama_cpp() {
    local model_id="$1"
    local ai_stack_dir="${2:-${SCRIPT_DIR}/ai-stack/compose}"

    if [ "$model_id" = "SKIP" ]; then
        log_info "Skipping AI model installation"
        return 0
    fi

    log_info "Deploying llama.cpp with model: $model_id"

    # Check if AI stack directory exists
    if [ ! -d "$ai_stack_dir" ]; then
        log_error "AI stack directory not found at: $ai_stack_dir"
        return 1
    fi

    cd "$ai_stack_dir"

    # Detect container runtime
    local compose_cmd=""
    if command -v podman-compose >/dev/null 2>&1; then
        compose_cmd="podman-compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        compose_cmd="docker-compose"
    elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        compose_cmd="docker compose"
    else
        log_error "No container runtime found (podman-compose, docker-compose, or docker compose)"
        return 1
    fi

    log_info "Using container runtime: $compose_cmd"

    # Update .env with selected model
    if [ -f ".env" ]; then
        # Update existing .env
        if grep -q "^LLAMA_CPP_DEFAULT_MODEL=" .env; then
            sed -i "s|^LLAMA_CPP_DEFAULT_MODEL=.*|LLAMA_CPP_DEFAULT_MODEL=$model_id|" .env
        else
            echo "LLAMA_CPP_DEFAULT_MODEL=$model_id" >> .env
        fi

        # Add LLAMA_CPP_MODEL_FILE if not present
        local model_file=$(get_model_filename_from_id "$model_id")
        if [ -n "$model_file" ]; then
            if grep -q "^LLAMA_CPP_MODEL_FILE=" .env; then
                sed -i "s|^LLAMA_CPP_MODEL_FILE=.*|LLAMA_CPP_MODEL_FILE=$model_file|" .env
            else
                echo "LLAMA_CPP_MODEL_FILE=$model_file" >> .env
            fi
        fi
    else
        log_error ".env file not found at: $ai_stack_dir/.env"
        return 1
    fi

    log_info "Updated .env with model: $model_id"

    # Deploy stack
    log_info "Deploying AI stack with $compose_cmd..."
    if $compose_cmd up -d 2>&1 | tee /tmp/ai-stack-deploy.log; then
        log_success "AI stack deployment initiated"
        log_info "Model download may take 10-45 minutes depending on model size"

        # Provide correct monitoring commands based on runtime
        local container_cmd="podman"
        if [[ "$compose_cmd" == *"docker"* ]]; then
            container_cmd="docker"
        fi
        log_info "Monitor progress: $container_cmd logs -f local-ai-llama-cpp"
        log_info "Check status: $container_cmd ps"
    else
        log_error "Failed to deploy AI stack. Check logs at: /tmp/ai-stack-deploy.log"
        return 1
    fi

    return 0
}

# ============================================================================
# Export Functions
# ============================================================================

# Only export functions if AI is available or in auto mode
if [ "$AI_ENABLED" != "false" ]; then
    export -f ai_check_availability
    export -f ai_check_llama_cpp
    export -f ai_select_model
    export -f ai_generate_nix_config
    export -f ai_review_config
    export -f ai_explain_code
    export -f ai_chat
    export -f ai_interactive_help
    export -f ai_deploy_llama_cpp
    export -f get_model_filename_from_id
    export -f detect_gpu_vram
    export -f detect_gpu_model
fi
