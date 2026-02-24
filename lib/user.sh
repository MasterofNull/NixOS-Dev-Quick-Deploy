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
        local current_user_info
        current_user_info=$(getent passwd "$USER" | cut -d: -f5 | cut -d, -f1)
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
        local current_shell
        current_shell=$(getent passwd "$USER" | cut -d: -f7 | xargs basename)
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
            # Default to RUN_AI_MODEL if no preference/token set
            if [[ "${RUN_AI_MODEL:-true}" == "true" ]]; then
                LOCAL_AI_STACK_ENABLED="true"
            else
                LOCAL_AI_STACK_ENABLED="false"
            fi
        fi
        persist_local_ai_stack_preferences || true
        persist_huggingface_token_preferences || true
        return 0
    fi

    # Always show this section header in interactive mode
    print_section "Local AI Stack"
    print_info "AI stack configuration is handled declaratively by NixOS modules."
    print_info "Use --without-ai-model to skip AI stack deployment."
    if [[ -z "${LOCAL_AI_STACK_ENABLED:-}" ]]; then
        if [[ "${RUN_AI_MODEL:-true}" == "true" ]]; then
            LOCAL_AI_STACK_ENABLED="true"
        else
            LOCAL_AI_STACK_ENABLED="false"
        fi
    fi
    persist_local_ai_stack_preferences || true
    persist_huggingface_token_preferences || true
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
