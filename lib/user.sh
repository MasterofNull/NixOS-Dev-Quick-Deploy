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
        # Check if user has EDITOR set
        if [ -n "$EDITOR" ]; then
            SELECTED_EDITOR="$EDITOR"
            print_info "Using existing EDITOR: $SELECTED_EDITOR"
        else
            SELECTED_EDITOR="nano"
            print_info "Default editor: $SELECTED_EDITOR"
        fi
    fi

    echo ""
    print_success "User configuration collected"
    echo ""
}
