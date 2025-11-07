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
}
