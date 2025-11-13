#!/usr/bin/env bash
# Interactive MangoHud profile selector.
# Helps switch between the shipped presets without editing Nix files manually.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../config/variables.sh
. "$SCRIPT_DIR/config/variables.sh"

current_profile() {
    local saved=""

    if [[ -n "${MANGOHUD_PROFILE_OVERRIDE:-}" ]]; then
        saved="$MANGOHUD_PROFILE_OVERRIDE"
    elif [[ -n "${MANGOHUD_PROFILE_PREFERENCE_FILE:-}" && -f "$MANGOHUD_PROFILE_PREFERENCE_FILE" ]]; then
        saved=$(awk -F'=' '/^MANGOHUD_PROFILE=/{print $2}' "$MANGOHUD_PROFILE_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    fi

    local default_profile="disabled"
    local enable_gaming_value
    enable_gaming_value=$(printf '%s' "${ENABLE_GAMING_STACK:-true}" | tr '[:upper:]' '[:lower:]')
    case "$enable_gaming_value" in
        true|1|yes|on)
            default_profile="desktop"
            ;;
    esac

    if [[ -z "$saved" ]]; then
        saved="$default_profile"
    fi

    printf '%s' "$saved"
}

persist_profile() {
    local profile="$1"

    if [[ -z "$profile" ]]; then
        return 1
    fi

    mkdir -p "$DEPLOYMENT_PREFERENCES_DIR"

    local tmp_file
    tmp_file=$(mktemp "${MANGOHUD_PROFILE_PREFERENCE_FILE}.XXXXXX" 2>/dev/null || printf '%s' "${MANGOHUD_PROFILE_PREFERENCE_FILE}.tmp")

    {
        printf 'MANGOHUD_PROFILE=%s\n' "$profile"
    } >"$tmp_file"

    mv "$tmp_file" "$MANGOHUD_PROFILE_PREFERENCE_FILE"
    chmod 600 "$MANGOHUD_PROFILE_PREFERENCE_FILE" 2>/dev/null || true
}

print_menu() {
    printf '\nMangoHud Overlay Profiles:\n'
    printf '  1) disabled – Do not inject MangoHud globally (recommended for terminals).\n'
    printf '  2) light    – Minimal horizontal stats bar (GPU/CPU temps, FPS, RAM).\n'
    printf '  3) full     – Verbose vertical overlay with frametimes and driver info.\n'
    printf '  4) desktop  – Keep MangoHud inside the movable mangoapp window only.\n'
    printf '  5) desktop-hybrid – Auto-start mangoapp while keeping in-app overlays.\n'
    printf '\nSelect [1-5] and press Enter: '
}

profile_from_choice() {
    case "$1" in
        1) printf 'disabled' ;;
        2) printf 'light' ;;
        3) printf 'full' ;;
        4) printf 'desktop' ;;
        5) printf 'desktop-hybrid' ;;
        *) return 1 ;;
    esac
}

main() {
    local current selected choice
    current=$(current_profile)

    printf 'Current MangoHud profile: %s\n' "$current"
    print_menu
    read -r choice

    if ! selected=$(profile_from_choice "$choice"); then
        printf 'No change made (invalid selection).\n' >&2
        exit 1
    fi

    if [[ "$selected" == "$current" ]]; then
        printf 'MangoHud profile already set to "%s". Nothing to do.\n' "$selected"
        exit 0
    fi

    persist_profile "$selected"

    cat <<EOF

Saved MangoHud profile: $selected
Preference file: $MANGOHUD_PROFILE_PREFERENCE_FILE

Next steps:
  1. Re-apply your Home Manager configuration so the new overlay setting takes effect:
       cd ~/.dotfiles/home-manager && home-manager switch -b backup --flake .
  2. Restart any applications you do not want MangoHud to wrap.

The deployer will reuse this preference automatically on future runs.
EOF
}

main "$@"
