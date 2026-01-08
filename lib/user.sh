#!/usr/bin/env bash
#
# User Information Gathering
# Purpose: Collect user preferences for configuration generation
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#   - lib/colors.sh → Color codes
#
# Exports:
#   - gather_user_info() → Collect user preferences
#
# ============================================================================

# ============================================================================
# Gather User Information
# ============================================================================
# Purpose: Collect user preferences for system configuration
# Sets Global Variables:
#   - SELECTED_TIMEZONE - User's timezone selection
#   - SELECTED_SHELL - User's preferred shell (bash/zsh/fish)
#   - SELECTED_EDITOR - User's preferred editor
#   - USER_DESCRIPTION - User's full name/description
# ============================================================================
gather_user_info() {
    local mode="${1:---interactive}"
    local interactive="true"
    local force_prompt="false"

    case "$mode" in
        --noninteractive|--hydrate)
            interactive="false"
            ;;
        --interactive)
            interactive="true"
            force_prompt="true"
            ;;
        *)
            interactive="true"
            ;;
    esac

    if [[ "$force_prompt" == "true" && -n "$SELECTED_EDITOR" && -z "${USER_PROFILE_DEFAULT_EDITOR:-}" ]]; then
        USER_PROFILE_DEFAULT_EDITOR="$SELECTED_EDITOR"
    fi

    if [[ "$force_prompt" == "true" ]]; then
        SELECTED_EDITOR=""
    fi

    print_section "User Configuration"

    # ========================================================================
    # Timezone Selection
    # ========================================================================
    if [ -z "$SELECTED_TIMEZONE" ]; then
        SELECTED_TIMEZONE=$(timedatectl show --property=Timezone --value 2>/dev/null || echo "America/New_York")
        print_info "Detected timezone: $SELECTED_TIMEZONE"
    fi

    # ========================================================================
    # User Description
    # ========================================================================
    if [ -z "$USER_DESCRIPTION" ]; then
        local current_user_info=$(getent passwd "$USER" | cut -d: -f5 | cut -d, -f1)
        if [ -n "$current_user_info" ] && [ "$current_user_info" != "$USER" ]; then
            USER_DESCRIPTION="$current_user_info"
            print_info "Using existing user description: $USER_DESCRIPTION"
        else
            USER_DESCRIPTION="$USER"
            print_info "User description: $USER_DESCRIPTION"
        fi
    fi

    # ========================================================================
    # Shell Selection
    # ========================================================================
    if [ -z "$SELECTED_SHELL" ]; then
        # Detect current shell
        local current_shell=$(getent passwd "$USER" | cut -d: -f7 | xargs basename)
        if [ -n "$current_shell" ]; then
            SELECTED_SHELL="$current_shell"
            print_info "Detected shell: $SELECTED_SHELL"
        else
            SELECTED_SHELL="bash"
            print_info "Default shell: $SELECTED_SHELL"
        fi
    fi

    # ========================================================================
    # Editor Selection
    # ========================================================================
    if [ -z "$SELECTED_EDITOR" ]; then
        local detected_editor="${EDITOR:-}"
        if [ -z "$detected_editor" ] && [ -n "${USER_PROFILE_DEFAULT_EDITOR:-}" ]; then
            detected_editor="${USER_PROFILE_DEFAULT_EDITOR}"
        fi

        if [[ "$interactive" == "true" ]]; then
            if [ -n "$detected_editor" ]; then
                print_info "Detected existing EDITOR: $detected_editor"
                if confirm "Keep $detected_editor as your default editor?" "y"; then
                    SELECTED_EDITOR="$detected_editor"
                fi
            fi

            if [ -z "$SELECTED_EDITOR" ]; then
                local -a editor_choices=(
                    "vim"
                    "nvim"
                    "codium"
                    "gitea-editor"
                )

                local -a editor_descriptions=(
                    "vim - Vi IMproved (terminal)"
                    "nvim - Neovim (modern terminal editor)"
                    "codium - VSCodium (graphical IDE)"
                    "gitea-editor - Lightweight browser editor"
                )

                print_info "Select your preferred default editor:"

                local idx
                for idx in "${!editor_choices[@]}"; do
                    local option_number=$((idx + 1))
                    local availability="available"
                    if ! command -v "${editor_choices[$idx]}" >/dev/null 2>&1; then
                        availability="will be installed"
                    fi
                    print_detail "$option_number) ${editor_descriptions[$idx]} (${availability})"
                done

                local default_choice="1"
                if [ -n "$detected_editor" ]; then
                    for idx in "${!editor_choices[@]}"; do
                        if [ "$detected_editor" = "${editor_choices[$idx]}" ]; then
                            default_choice=$((idx + 1))
                            break
                        fi
                    done
                fi

                local selection=""
                while true; do
                    selection=$(prompt_user "Choose editor (1-${#editor_choices[@]})" "$default_choice")
                    case "$selection" in
                        1) SELECTED_EDITOR="${editor_choices[0]}"; break ;;
                        2) SELECTED_EDITOR="${editor_choices[1]}"; break ;;
                        3) SELECTED_EDITOR="${editor_choices[2]}"; break ;;
                        4) SELECTED_EDITOR="${editor_choices[3]}"; break ;;
                        *)
                            print_warning "Invalid selection. Enter a number between 1 and ${#editor_choices[@]}."
                            ;;
                    esac
                done
            fi
        else
            if [ -n "$detected_editor" ]; then
                print_info "Retaining editor preference: $detected_editor"
                SELECTED_EDITOR="$detected_editor"
            fi

            if [ -z "$SELECTED_EDITOR" ]; then
                SELECTED_EDITOR="${DEFAULT_EDITOR:-vim}"
                print_info "Editor preference defaulted to $SELECTED_EDITOR (run Phase 1 to change)"
            fi
        fi
    fi

    if [ -z "$SELECTED_EDITOR" ]; then
        SELECTED_EDITOR="${DEFAULT_EDITOR:-vim}"
        print_info "Default editor: $SELECTED_EDITOR"
    fi

    DEFAULT_EDITOR="$SELECTED_EDITOR"
    export SELECTED_EDITOR DEFAULT_EDITOR

    print_success "Editor preference: $SELECTED_EDITOR"

    echo ""
    print_success "User configuration collected"
    echo ""

    return 0
}

# =========================================================================
# Cached User Profile Preferences
# =========================================================================
load_user_profile_preferences() {
    if [[ "${USER_PROFILE_PREFS_LOADED:-false}" == "true" ]]; then
        return 0
    fi

    if [[ -n "${USER_PROFILE_PREFERENCE_FILE:-}" && -f "$USER_PROFILE_PREFERENCE_FILE" ]]; then
        # shellcheck disable=SC1090
        . "$USER_PROFILE_PREFERENCE_FILE"
    fi

    USER_PROFILE_PREFS_LOADED="true"
    export USER_PROFILE_PREFS_LOADED SELECTED_TIMEZONE SELECTED_SHELL SELECTED_EDITOR USER_DESCRIPTION
    return 0
}

persist_user_profile_preferences() {
    if [[ -z "${USER_PROFILE_PREFERENCE_FILE:-}" ]]; then
        return 0
    fi

    local pref_dir
    pref_dir=$(dirname "$USER_PROFILE_PREFERENCE_FILE")
    if ! safe_mkdir "$pref_dir"; then
        print_warning "Unable to prepare user preference directory: $pref_dir"
        return 1
    fi

    local tz_q shell_q editor_q desc_q
    tz_q=$(printf '%q' "$SELECTED_TIMEZONE")
    shell_q=$(printf '%q' "$SELECTED_SHELL")
    editor_q=$(printf '%q' "$SELECTED_EDITOR")
    desc_q=$(printf '%q' "$USER_DESCRIPTION")

    if cat >"$USER_PROFILE_PREFERENCE_FILE" <<EOF
# Cached user profile preferences (auto-generated)
SELECTED_TIMEZONE=$tz_q
SELECTED_SHELL=$shell_q
SELECTED_EDITOR=$editor_q
USER_DESCRIPTION=$desc_q
EOF
    then
        chmod 600 "$USER_PROFILE_PREFERENCE_FILE" 2>/dev/null || true
        safe_chown_user_dir "$USER_PROFILE_PREFERENCE_FILE" || true
        return 0
    fi

    print_warning "Failed to persist user profile preferences to $USER_PROFILE_PREFERENCE_FILE"
    return 1
}

# ============================================================================
# Git Identity Helpers
# ============================================================================
load_git_identity_preferences() {
    if [[ "${GIT_IDENTITY_PREFS_LOADED:-false}" == "true" ]]; then
        return 0
    fi

    if [[ -n "${GIT_IDENTITY_PREFERENCE_FILE:-}" && -f "$GIT_IDENTITY_PREFERENCE_FILE" ]]; then
        # shellcheck disable=SC1090
        . "$GIT_IDENTITY_PREFERENCE_FILE"
    fi

    GIT_IDENTITY_PREFS_LOADED="true"
    export GIT_USER_NAME GIT_USER_EMAIL GIT_IDENTITY_SKIP GIT_IDENTITY_PREFS_LOADED
    return 0
}

persist_git_identity_preferences() {
    if [[ -z "${GIT_IDENTITY_PREFERENCE_FILE:-}" ]]; then
        return 0
    fi

    local pref_dir
    pref_dir=$(dirname "$GIT_IDENTITY_PREFERENCE_FILE")
    if ! safe_mkdir "$pref_dir"; then
        print_warning "Unable to prepare git identity preference directory: $pref_dir"
        return 1
    fi

    local escaped_name
    local escaped_email
    escaped_name=$(printf '%q' "$GIT_USER_NAME")
    escaped_email=$(printf '%q' "$GIT_USER_EMAIL")

    if cat >"$GIT_IDENTITY_PREFERENCE_FILE" <<EOF
# Cached git identity preferences (auto-generated)
GIT_USER_NAME=$escaped_name
GIT_USER_EMAIL=$escaped_email
GIT_IDENTITY_SKIP=$GIT_IDENTITY_SKIP
EOF
    then
        chmod 600 "$GIT_IDENTITY_PREFERENCE_FILE" 2>/dev/null || true
        safe_chown_user_dir "$GIT_IDENTITY_PREFERENCE_FILE" || true
        return 0
    fi

    print_warning "Failed to persist git identity preferences to $GIT_IDENTITY_PREFERENCE_FILE"
    return 1
}

prompt_git_identity() {
    local mode="${1:---interactive}"
    local interactive="false"

    case "$mode" in
        --interactive)
            interactive="true"
            ;;
        --noninteractive|--hydrate)
            interactive="false"
            ;;
        *)
            interactive="true"
            ;;
    esac

    load_git_identity_preferences || true

    local existing_name existing_email
    existing_name=$(git config --global user.name 2>/dev/null || echo "")
    existing_email=$(git config --global user.email 2>/dev/null || echo "")

    if [[ -z "$GIT_USER_NAME" && -n "$existing_name" ]]; then
        GIT_USER_NAME="$existing_name"
    fi
    if [[ -z "$GIT_USER_EMAIL" && -n "$existing_email" ]]; then
        GIT_USER_EMAIL="$existing_email"
    fi

    if [[ "$interactive" == "true" && "${GIT_IDENTITY_SKIP:-false}" == "true" ]]; then
        print_info "Git identity prompts were previously skipped; re-running interactively."
        GIT_IDENTITY_SKIP="false"
    fi

    if [[ "$interactive" == "false" ]]; then
        if [[ "${GIT_IDENTITY_SKIP:-false}" == "true" ]]; then
            print_info "Git identity configuration skipped per cached preference."
            return 0
        fi

        if [[ -n "$GIT_USER_NAME" && -n "$GIT_USER_EMAIL" ]]; then
            configure_git_identity "$GIT_USER_NAME" "$GIT_USER_EMAIL"
            return 0
        fi

        print_info "Git identity not configured; rerun Phase 1 or edit $GIT_IDENTITY_PREFERENCE_FILE manually."
        return 0
    fi

    local configure_default="y"
    if [[ -n "$GIT_USER_NAME" || -n "$GIT_USER_EMAIL" ]]; then
        configure_default="n"
    fi

    if ! confirm "Configure git --global user.name and user.email now?" "$configure_default"; then
        GIT_IDENTITY_SKIP="true"
        persist_git_identity_preferences || true
        print_info "Skipping git identity configuration for this run."
        return 0
    fi

    local default_name="${GIT_USER_NAME:-$USER}"
    local default_email="${GIT_USER_EMAIL:-}"
    if [[ -z "$default_email" ]]; then
        local email_host
        email_host=$(hostname -f 2>/dev/null || hostname 2>/dev/null || echo "localhost")
        default_email="${USER}@${email_host}"
    fi

    local name_input
    name_input=$(prompt_user "Git user.name (commit author name)" "$default_name")
    name_input=${name_input:-$default_name}

    local email_input
    email_input=$(prompt_user "Git user.email (commit author email)" "$default_email")
    email_input=${email_input:-$default_email}

    if [[ -z "$name_input" || -z "$email_input" ]]; then
        print_warning "Git identity incomplete; global configuration unchanged."
        GIT_IDENTITY_SKIP="false"
        persist_git_identity_preferences || true
        return 0
    fi

    GIT_USER_NAME="$name_input"
    GIT_USER_EMAIL="$email_input"
    GIT_IDENTITY_SKIP="false"
    persist_git_identity_preferences || true

    configure_git_identity "$GIT_USER_NAME" "$GIT_USER_EMAIL"
    export GIT_USER_NAME GIT_USER_EMAIL
    return 0
}

configure_git_identity() {
    local name="$1"
    local email="$2"

    if [[ -z "$name" || -z "$email" ]]; then
        return 0
    fi

    if command -v git >/dev/null 2>&1; then
        if run_as_primary_user git config --global user.name "$name" >/dev/null 2>&1; then
            print_success "Configured git user.name as '$name'"
        else
            print_warning "Failed to set git user.name automatically. Run: git config --global user.name \"$name\""
        fi

        if run_as_primary_user git config --global user.email "$email" >/dev/null 2>&1; then
            print_success "Configured git user.email as '$email'"
        else
            print_warning "Failed to set git user.email automatically. Run: git config --global user.email \"$email\""
        fi
    else
        print_warning "git not available; configure manually with git config --global user.name \"$name\""
    fi
}

# ============================================================================
# Hugging Face token + local AI stack preferences
# ============================================================================
persist_local_ai_stack_preferences() {
    safe_mkdir "$DEPLOYMENT_PREFERENCES_DIR" || return 1
    printf 'LOCAL_AI_STACK_ENABLED=%s\n' "${LOCAL_AI_STACK_ENABLED:-false}" >"$LOCAL_AI_STACK_PREFERENCE_FILE"
}

persist_llm_backend_preferences() {
    safe_mkdir "$DEPLOYMENT_PREFERENCES_DIR" || return 1
    printf 'LLM_BACKEND=%s\n' "${LLM_BACKEND:-llama_cpp}" >"$LLM_BACKEND_PREFERENCE_FILE"
}

persist_llm_models_preferences() {
    safe_mkdir "$DEPLOYMENT_PREFERENCES_DIR" || return 1
    local resolved_model="${LLAMA_CPP_DEFAULT_MODEL:-}"
    if [[ -z "$resolved_model" && -f "$LLM_MODELS_PREFERENCE_FILE" ]]; then
        resolved_model=$(awk -F'=' '/^LLAMA_CPP_DEFAULT_MODEL=/{print $2}' "$LLM_MODELS_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    fi
    {
        printf 'LLM_MODELS=%s\n' "${LLM_MODELS:-}"
        if [[ -n "$resolved_model" ]]; then
            printf 'LLAMA_CPP_DEFAULT_MODEL=%s\n' "$resolved_model"
        fi
    } >"$LLM_MODELS_PREFERENCE_FILE"
}

persist_llama_cpp_model_preferences() {
    if [[ -z "${LLM_MODELS_PREFERENCE_FILE:-}" ]]; then
        return 0
    fi
    safe_mkdir "$(dirname "$LLM_MODELS_PREFERENCE_FILE")" || return 1
    if [[ -f "$LLM_MODELS_PREFERENCE_FILE" ]] && \
        grep -q "^LLAMA_CPP_DEFAULT_MODEL=" "$LLM_MODELS_PREFERENCE_FILE" 2>/dev/null; then
        sed -i "s|^LLAMA_CPP_DEFAULT_MODEL=.*|LLAMA_CPP_DEFAULT_MODEL=${LLAMA_CPP_DEFAULT_MODEL:-}|" \
            "$LLM_MODELS_PREFERENCE_FILE" 2>/dev/null || true
        return 0
    fi
    if [[ -n "${LLAMA_CPP_DEFAULT_MODEL:-}" ]]; then
        printf 'LLAMA_CPP_DEFAULT_MODEL=%s\n' "${LLAMA_CPP_DEFAULT_MODEL}" >>"$LLM_MODELS_PREFERENCE_FILE"
    fi
}

persist_huggingface_token_preferences() {
    safe_mkdir "$DEPLOYMENT_PREFERENCES_DIR" || return 1
    if [[ -n "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
        cat >"$HUGGINGFACE_TOKEN_PREFERENCE_FILE" <<EOF
HUGGINGFACEHUB_API_TOKEN=${HUGGINGFACEHUB_API_TOKEN}
EOF
    else
        rm -f "$HUGGINGFACE_TOKEN_PREFERENCE_FILE" 2>/dev/null || true
    fi
}

load_existing_huggingface_token() {
    # Prefer in-memory/env or cached preference first
    if [[ -n "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
        return 0
    fi

    local home_token_file="$PRIMARY_HOME/.config/huggingface/token"
    local token=""

    if [[ -r "$home_token_file" ]]; then
        token=$(head -n1 "$home_token_file" 2>/dev/null | tr -d '\r')
    fi

    if [[ -n "$token" ]]; then
        HUGGINGFACEHUB_API_TOKEN="$token"
        export HUGGINGFACEHUB_API_TOKEN
        return 0
    fi

    return 1
}

ensure_huggingface_token_file() {
    local token="$1"
    local home_token_file="$PRIMARY_HOME/.config/huggingface/token"

    if [[ -z "$token" ]]; then
        return 0
    fi

    if safe_mkdir "$(dirname "$home_token_file")"; then
        printf '%s\n' "$token" >"$home_token_file"
        chmod 600 "$home_token_file" 2>/dev/null || true
        safe_chown_user_dir "$home_token_file" || true
        return 0
    fi

    print_warning "Unable to store Hugging Face token at $home_token_file automatically."
    return 1
}

prompt_huggingface_token() {
    local mode="${1:---interactive}"
    local interactive="true"

    case "$mode" in
        --noninteractive|--hydrate)
            interactive="false"
            ;;
        --interactive)
            interactive="true"
            ;;
        *)
            interactive="true"
            ;;
    esac

    # Hydrate from existing system files if available
    load_existing_huggingface_token || true

    # Respect previously stored selection when running non-interactively
    if [[ "$interactive" == "false" ]]; then
        # In non-interactive mode, respect existing preference file first
        if [[ -f "$LOCAL_AI_STACK_PREFERENCE_FILE" ]]; then
            _local_ai_cached=$(awk -F'=' '/^LOCAL_AI_STACK_ENABLED=/{print $2}' "$LOCAL_AI_STACK_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
            case "$_local_ai_cached" in
                true)
                    LOCAL_AI_STACK_ENABLED="true"
                    ;;
                false|*)
                    LOCAL_AI_STACK_ENABLED="false"
                    ;;
            esac
        elif [[ -n "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
            # If no preference but token exists, enable AI stack
            LOCAL_AI_STACK_ENABLED="true"
        else
            LOCAL_AI_STACK_ENABLED="false"
        fi
        persist_local_ai_stack_preferences || true
        persist_huggingface_token_preferences || true
        return 0
    fi

    # Always show this section header in interactive mode
    print_section "Local AI Stack (Podman Containers)"
    print_info "The local AI stack includes Podman containers for:"
    print_info "  • llama.cpp - Local LLM inference server (containerized)"
    print_info "  • Open WebUI - Web interface for AI models"
    print_info "  • Qdrant - Vector database for embeddings"
    print_info "  • MindsDB - AI workflow orchestration"
    echo ""

    # First, ask if user wants to enable the AI stack
    # In interactive mode, always show the prompt (even if previously set to false)
    # This allows users to change their mind during deployment
    local enable_ai_stack=false
    
    # Check if confirm function is available
    if ! declare -F confirm >/dev/null 2>&1; then
        print_error "confirm function not available - cannot prompt for AI stack"
        enable_ai_stack=false
        LOCAL_AI_STACK_ENABLED="false"
    else
        # Always prompt in interactive mode, but use previous selection as default
        local default_choice="n"
        if [[ "${LOCAL_AI_STACK_ENABLED:-}" == "true" ]]; then
            default_choice="y"
        fi
        
        if confirm "Enable local AI stack (Podman containers)?" "$default_choice"; then
            enable_ai_stack=true
            LOCAL_AI_STACK_ENABLED="true"
        else
            enable_ai_stack=false
            LOCAL_AI_STACK_ENABLED="false"
        fi
    fi

    # If AI stack is enabled, ask for LLM backend and optional Hugging Face token
    if [[ "$enable_ai_stack" == "true" ]]; then
        echo ""
        print_section "LLM Backend Selection"
        print_info "Using llama.cpp backend (served by the containerized server)."
        if declare -p LLM_BACKEND 2>/dev/null | grep -q 'declare -r'; then
            print_warning "LLM_BACKEND is readonly; keeping current value: ${LLM_BACKEND:-unknown}"
        else
            LLM_BACKEND="llama_cpp"
        fi
        print_success "Selected: ${LLM_BACKEND:-llama_cpp} (containerized server)"
        export LLM_BACKEND
        
        # Model configuration (choose embedding + coder)
        echo ""
        print_section "RAG Embedding Model Selection"
        local default_embedding="${EMBEDDING_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"
        print_info "Default embedding model: ${default_embedding}"
        print_info "Options:"
        print_info "  1) sentence-transformers/all-MiniLM-L6-v2 (default)"
        print_info "  2) BAAI/bge-small-en-v1.5"
        print_info "  3) BAAI/bge-base-en-v1.5"
        print_info "  4) nomic-ai/nomic-embed-text-v1"

        local embedding_choice="1"
        if declare -F prompt_user >/dev/null 2>&1; then
            embedding_choice=$(prompt_user "Select embedding model [1-4]" "1")
        fi

        case "${embedding_choice}" in
            2) EMBEDDING_MODEL="BAAI/bge-small-en-v1.5" ;;
            3) EMBEDDING_MODEL="BAAI/bge-base-en-v1.5" ;;
            4) EMBEDDING_MODEL="nomic-ai/nomic-embed-text-v1" ;;
            *) EMBEDDING_MODEL="${default_embedding}" ;;
        esac
        export EMBEDDING_MODEL
        print_success "Embedding model: ${EMBEDDING_MODEL}"

        echo ""
        print_section "Coder LLM Selection"
        local gpu_vram_gb=0
        local ram_gb=0

        if declare -F detect_gpu_vram >/dev/null 2>&1; then
            gpu_vram_gb=$(detect_gpu_vram)
        fi

        if [[ -r /proc/meminfo ]]; then
            ram_gb=$(awk '/MemTotal:/ {printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0)
        fi

        local default_coder="${CODER_MODEL:-qwen2.5-coder}"
        if [[ "$gpu_vram_gb" -ge 24 ]]; then
            default_coder="qwen2.5-coder-14b"
        elif [[ "$gpu_vram_gb" -ge 16 ]]; then
            default_coder="qwen2.5-coder"
        elif [[ "$ram_gb" -ge 32 ]]; then
            default_coder="qwen2.5-coder"
        else
            default_coder="qwen3-4b"
        fi

        print_info "Default coder model: ${default_coder}"
        print_info "Options:"
        print_info "  1) qwen3-4b (CPU/iGPU friendly)"
        print_info "  2) qwen2.5-coder"
        print_info "  3) qwen2.5-coder-14b"
        print_info "  4) deepseek-coder-v2-lite"
        print_info "  5) deepseek-coder-v2"

        local coder_choice="2"
        if declare -F prompt_user >/dev/null 2>&1; then
            case "$default_coder" in
                qwen3-4b)
                    coder_choice=$(prompt_user "Select coder model [1-5]" "1")
                    ;;
                qwen2.5-coder)
                    coder_choice=$(prompt_user "Select coder model [1-5]" "2")
                    ;;
                qwen2.5-coder-14b)
                    coder_choice=$(prompt_user "Select coder model [1-5]" "3")
                    ;;
                deepseek-coder-v2-lite)
                    coder_choice=$(prompt_user "Select coder model [1-5]" "4")
                    ;;
                deepseek-coder-v2)
                    coder_choice=$(prompt_user "Select coder model [1-5]" "5")
                    ;;
                *)
                    coder_choice=$(prompt_user "Select coder model [1-5]" "2")
                    ;;
            esac
        fi

        case "${coder_choice}" in
            1) CODER_MODEL="qwen3-4b" ;;
            2) CODER_MODEL="qwen2.5-coder" ;;
            3) CODER_MODEL="qwen2.5-coder-14b" ;;
            4) CODER_MODEL="deepseek-coder-v2-lite" ;;
            5) CODER_MODEL="deepseek-coder-v2" ;;
            *) CODER_MODEL="${default_coder}" ;;
        esac
        export CODER_MODEL
        print_success "Coder model: ${CODER_MODEL}"

        local coder_model_id=""
        case "${CODER_MODEL}" in
            qwen3-4b|qwen3-4b-instruct)
                coder_model_id="unsloth/Qwen3-4B-Instruct-2507-GGUF"
                ;;
            qwen2.5-coder|qwen2.5-coder-7b|qwen2.5-coder-7b-instruct)
                coder_model_id="Qwen/Qwen2.5-Coder-7B-Instruct"
                ;;
            qwen2.5-coder-14b|qwen2.5-coder-14b-instruct)
                coder_model_id="Qwen/Qwen2.5-Coder-14B-Instruct"
                ;;
            deepseek-coder-v2-lite|deepseek-lite)
                coder_model_id="deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
                ;;
            deepseek-coder-v2|deepseek-v2)
                coder_model_id="deepseek-ai/DeepSeek-Coder-V2-Instruct"
                ;;
        esac

        if [[ -n "$coder_model_id" ]]; then
            LLAMA_CPP_DEFAULT_MODEL="$coder_model_id"
            export LLAMA_CPP_DEFAULT_MODEL
            persist_llama_cpp_model_preferences || true
            print_success "llama.cpp model: ${LLAMA_CPP_DEFAULT_MODEL}"
        fi

        LLM_MODELS="${CODER_MODEL},${EMBEDDING_MODEL}"
        export LLM_MODELS
        print_success "Models configured: ${LLM_MODELS}"
        
        # Optionally ask for Hugging Face token
        echo ""
        print_section "Hugging Face Token (Optional)"
        print_info "A Hugging Face token enables additional AI features:"
        print_info "  • Access to Hugging Face model repositories"
        print_info "  • TGI (Text Generation Inference) integration"
        print_info "  • Enhanced Continue.dev presets"
        print_info "You can skip this and add a token later if needed."

        if [[ -n "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
            print_info "Detected an existing Hugging Face token; press Enter to keep it or enter a new one."
        fi

        local token_input
        token_input=$(prompt_secret "Hugging Face token (blank to skip)")

        if [[ -z "$token_input" ]]; then
            if [[ -n "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
                token_input="$HUGGINGFACEHUB_API_TOKEN"
            fi
        fi

        if [[ -n "$token_input" ]]; then
            HUGGINGFACEHUB_API_TOKEN="$token_input"
            export HUGGINGFACEHUB_API_TOKEN
            ensure_huggingface_token_file "$token_input" || true
            print_success "Hugging Face token saved."
        else
            print_info "Skipping Hugging Face token (can be added later)."
        fi

        persist_local_ai_stack_preferences || true
        persist_llm_backend_preferences || true
        persist_llm_models_preferences || true
        persist_huggingface_token_preferences || true
        export LOCAL_AI_STACK_ENABLED

        print_success "Local AI stack enabled with $LLM_BACKEND backend."
    else
        LOCAL_AI_STACK_ENABLED="false"
        unset HUGGINGFACEHUB_API_TOKEN
        persist_local_ai_stack_preferences || true
        persist_huggingface_token_preferences || true
        print_info "Local AI stack disabled."
    fi

    return 0
}

# ============================================================================
# Session-Wide User Settings Initialization
# ============================================================================
ensure_user_settings_ready() {
    local mode="${1:---interactive}"
    local interactive="true"

    case "$mode" in
        --noninteractive|--hydrate)
            interactive="false"
            ;;
        --interactive)
            interactive="true"
            ;;
        *)
            interactive="true"
            ;;
    esac

    if [[ "$interactive" == "false" && "${USER_SETTINGS_INITIALIZED:-false}" == "true" ]]; then
        return 0
    fi

    load_user_profile_preferences || true

    if [[ "$interactive" == "true" ]]; then
        export USER_PROFILE_DEFAULT_TIMEZONE="${SELECTED_TIMEZONE:-}"
        export USER_PROFILE_DEFAULT_DESCRIPTION="${USER_DESCRIPTION:-}"
        export USER_PROFILE_DEFAULT_SHELL="${SELECTED_SHELL:-}"
        export USER_PROFILE_DEFAULT_EDITOR="${SELECTED_EDITOR:-}"
        SELECTED_TIMEZONE=""
        USER_DESCRIPTION=""
        SELECTED_SHELL=""
        SELECTED_EDITOR=""
    fi

    local gather_flag="--noninteractive"
    if [[ "$interactive" == "true" ]]; then
        gather_flag="--interactive"
    fi

    # Gather basic user info (timezone, shell, editor, etc.)
    # Don't fail completely if this has issues - use defaults and continue
    if ! gather_user_info "$gather_flag"; then
        print_warning "User info gathering had issues, using defaults and continuing..."
        # Set safe defaults if gather_user_info failed
        SELECTED_TIMEZONE="${SELECTED_TIMEZONE:-$(timedatectl show --property=Timezone --value 2>/dev/null || echo "America/New_York")}"
        SELECTED_SHELL="${SELECTED_SHELL:-$(getent passwd "$USER" | cut -d: -f7 | xargs basename 2>/dev/null || echo "bash")}"
        SELECTED_EDITOR="${SELECTED_EDITOR:-${EDITOR:-vim}}"
        USER_DESCRIPTION="${USER_DESCRIPTION:-$USER}"
    fi

    if [[ "$interactive" == "true" ]]; then
        persist_user_profile_preferences || true
    fi

    unset USER_PROFILE_DEFAULT_TIMEZONE USER_PROFILE_DEFAULT_DESCRIPTION \
        USER_PROFILE_DEFAULT_SHELL USER_PROFILE_DEFAULT_EDITOR

    local prompt_flag="--noninteractive"
    if [[ "$interactive" == "true" ]]; then
        prompt_flag="--interactive"
    fi

    # Prompt for git identity - continue even if it fails
    if declare -F prompt_git_identity >/dev/null 2>&1; then
        if ! prompt_git_identity "$prompt_flag"; then
            print_warning "Git identity prompt had issues, but continuing..."
        fi
    else
        print_warning "prompt_git_identity function not found - git identity prompt will be skipped"
    fi

    # Prompt for Flatpak profile - continue even if it fails
    if declare -F select_flatpak_profile >/dev/null 2>&1; then
        if ! select_flatpak_profile "$prompt_flag"; then
            print_warning "Flatpak profile selection had issues, but continuing..."
        fi
    else
        print_warning "select_flatpak_profile function not found - Flatpak profile prompt will be skipped"
    fi

    if declare -F ensure_gitea_secrets_ready >/dev/null 2>&1; then
        if ! ensure_gitea_secrets_ready "$prompt_flag"; then
            print_warning "Gitea secrets preparation had issues, but continuing with other prompts..."
            # Don't return early - continue to other prompts
        fi
    fi

    # Always prompt for AI stack (even if Gitea setup had issues)
    if declare -F prompt_huggingface_token >/dev/null 2>&1; then
        prompt_huggingface_token "$prompt_flag" || true
    else
        print_warning "prompt_huggingface_token function not found - AI stack prompt will be skipped"
    fi

    USER_SETTINGS_INITIALIZED="true"
    export USER_SETTINGS_INITIALIZED
    return 0
}
