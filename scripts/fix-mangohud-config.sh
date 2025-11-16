#!/usr/bin/env bash
# =============================================================================
# MangoHud Configuration Fix Script
# =============================================================================
# This script fixes incorrect MangoHud configurations on systems that were
# deployed with the bug where MangoHud overlays appeared on all COSMIC desktop
# applets and system windows instead of only on the desktop or in games.
#
# The fix adds "no_display=1" to the desktop profile configuration, which
# prevents MangoHud from overlaying applications when in desktop-only mode.
#
# Usage:
#   ./scripts/fix-mangohud-config.sh
#
# This script will:
# 1. Check if MangoHud is configured
# 2. Detect if the configuration has the bug (missing no_display=1)
# 3. Fix the configuration by adding no_display=1 if needed
# 4. Optionally re-apply home-manager configuration
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Repository paths
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../config/variables.sh
. "$SCRIPT_DIR/config/variables.sh"

# shellcheck source=../lib/colors.sh
. "$SCRIPT_DIR/lib/colors.sh"

# shellcheck source=../lib/user-interaction.sh
. "$SCRIPT_DIR/lib/user-interaction.sh"

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
MANGOHUD_CONFIG_FILE="${HOME}/.config/MangoHud/MangoHud.conf"
MANGOHUD_BACKUP_FILE="${HOME}/.config/MangoHud/MangoHud.conf.backup-$(date +%Y%m%d_%H%M%S)"

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

print_header() {
    echo ""
    echo "========================================================================="
    echo "  MangoHud Configuration Fix Utility"
    echo "========================================================================="
    echo ""
}

check_mangohud_config_exists() {
    if [[ ! -f "$MANGOHUD_CONFIG_FILE" ]]; then
        print_error "MangoHud configuration file not found at: $MANGOHUD_CONFIG_FILE"
        print_info "This system may not have MangoHud configured yet."
        return 1
    fi
    return 0
}

get_current_profile() {
    local profile="unknown"

    if [[ -n "${MANGOHUD_PROFILE_OVERRIDE:-}" ]]; then
        profile="$MANGOHUD_PROFILE_OVERRIDE"
    elif [[ -n "${MANGOHUD_PROFILE_PREFERENCE_FILE:-}" && -f "$MANGOHUD_PROFILE_PREFERENCE_FILE" ]]; then
        profile=$(awk -F'=' '/^MANGOHUD_PROFILE=/{print $2}' "$MANGOHUD_PROFILE_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    fi

    if [[ -z "$profile" || "$profile" == "unknown" ]]; then
        profile="desktop"  # Default profile
    fi

    printf '%s' "$profile"
}

config_has_no_display() {
    if grep -q "^no_display=1" "$MANGOHUD_CONFIG_FILE" 2>/dev/null; then
        return 0
    fi
    return 1
}

config_needs_fix() {
    local current_profile
    current_profile=$(get_current_profile)

    # Only desktop profile needs no_display=1
    if [[ "$current_profile" != "desktop" ]]; then
        return 1
    fi

    # Check if config already has no_display=1
    if config_has_no_display; then
        return 1
    fi

    # Needs fix
    return 0
}

backup_config() {
    if [[ -f "$MANGOHUD_CONFIG_FILE" ]]; then
        cp "$MANGOHUD_CONFIG_FILE" "$MANGOHUD_BACKUP_FILE"
        print_success "Backed up configuration to: $MANGOHUD_BACKUP_FILE"
        return 0
    fi
    return 1
}

fix_config() {
    local tmp_file
    tmp_file=$(mktemp "${MANGOHUD_CONFIG_FILE}.XXXXXX")

    # Read existing config and add no_display=1 after the control line
    local added=false
    while IFS= read -r line; do
        printf '%s\n' "$line" >> "$tmp_file"

        # Add no_display=1 right after hud_no_margin=1 line
        if [[ "$line" == "hud_no_margin=1" && "$added" == false ]]; then
            printf 'no_display=1\n' >> "$tmp_file"
            added=true
        fi
    done < "$MANGOHUD_CONFIG_FILE"

    # If we didn't find hud_no_margin=1, append no_display=1 at the end
    if [[ "$added" == false ]]; then
        printf 'no_display=1\n' >> "$tmp_file"
    fi

    mv "$tmp_file" "$MANGOHUD_CONFIG_FILE"
    print_success "Added no_display=1 to MangoHud configuration"
}

prompt_rebuild() {
    echo ""
    print_info "The MangoHud configuration has been fixed."
    echo ""
    echo "To apply the changes, you need to:"
    echo "  1. Re-run the deployment script to regenerate configs with the fix, OR"
    echo "  2. The fix has been applied to your current config file"
    echo ""
    echo "Would you like to restart any MangoHud services now? (y/n)"
    read -r response

    if [[ "$response" =~ ^[Yy]$ ]]; then
        systemctl --user restart mangohud-desktop 2>/dev/null || true
        print_success "Restarted mangohud-desktop service (if it was running)"
    fi
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

main() {
    print_header

    print_info "Checking MangoHud configuration..."

    if ! check_mangohud_config_exists; then
        exit 0
    fi

    local current_profile
    current_profile=$(get_current_profile)
    print_info "Current MangoHud profile: $current_profile"

    if ! config_needs_fix; then
        if [[ "$current_profile" == "desktop" ]]; then
            print_success "MangoHud configuration is already correct (has no_display=1)"
        else
            print_info "MangoHud profile '$current_profile' does not require no_display=1"
        fi
        exit 0
    fi

    print_warning "MangoHud configuration needs to be fixed!"
    echo ""
    echo "Issue: The 'desktop' profile is missing 'no_display=1', which causes"
    echo "       MangoHud to overlay on all applications and COSMIC applets."
    echo ""
    echo "Fix:   Add 'no_display=1' to prevent overlays except in mangoapp window."
    echo ""
    echo "Proceed with the fix? (y/n)"
    read -r response

    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_info "Fix cancelled by user"
        exit 0
    fi

    backup_config
    fix_config
    prompt_rebuild

    echo ""
    print_success "MangoHud configuration fix completed!"
    echo ""
    print_info "Next steps:"
    echo "  1. Re-run the deployment script to ensure all configs are updated:"
    echo "     ./nixos-quick-deploy.sh"
    echo "  2. Or manually apply the fix to your generated configs if you prefer"
    echo ""
}

main "$@"
