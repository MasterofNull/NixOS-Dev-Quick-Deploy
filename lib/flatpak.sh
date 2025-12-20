#!/usr/bin/env bash
#
# Flatpak Helpers
# Purpose: Architecture detection and profile pruning helpers for Flatpak
# profiles defined in config/variables.sh.
#
# Dependencies:
#   - None (pure bash, uses nix/uname if available)
# Required Variables (from config/variables.sh):
#   - FLATPAK_INSTALL_ARCH
#   - FLATPAK_PROFILE_CORE_APPS
#   - FLATPAK_PROFILE_AI_WORKSTATION_APPS
#   - FLATPAK_PROFILE_MINIMAL_APPS
#   - FLATPAK_ARCH_PRUNED_APPS
#
# Exports:
#   - detect_flatpak_install_arch()
#   - prune_arch_incompatible_flatpaks()
#

detect_flatpak_install_arch() {
    if [[ -n "${FLATPAK_INSTALL_ARCH:-}" ]]; then
        return 0
    fi

    local nix_system arch_guess
    if command -v nix >/dev/null 2>&1; then
        nix_system=$(nix eval --raw --expr 'builtins.currentSystem' 2>/dev/null || echo "")
        case "$nix_system" in
            x86_64-*) FLATPAK_INSTALL_ARCH="x86_64" ;;
            aarch64-*) FLATPAK_INSTALL_ARCH="aarch64" ;;
            armv7l-*|armv7-*) FLATPAK_INSTALL_ARCH="arm" ;;
        esac
    fi

    if [[ -z "${FLATPAK_INSTALL_ARCH:-}" ]]; then
        arch_guess=$(uname -m)
        case "$arch_guess" in
            x86_64|amd64) FLATPAK_INSTALL_ARCH="x86_64" ;;
            aarch64|arm64) FLATPAK_INSTALL_ARCH="aarch64" ;;
            armv7l|armv7hf|armv8l) FLATPAK_INSTALL_ARCH="arm" ;;
            *) FLATPAK_INSTALL_ARCH="$arch_guess" ;;
        esac
    fi
}

register_pruned_flatpak_app() {
    local candidate="$1"
    local existing
    for existing in "${FLATPAK_ARCH_PRUNED_APPS[@]}"; do
        if [[ "$existing" == "$candidate" ]]; then
            return 0
        fi
    done
    FLATPAK_ARCH_PRUNED_APPS+=("$candidate")
}

remove_flatpak_app() {
    local array_name="$1"
    local target="$2"
    local -n arr_ref="$array_name"
    local -a filtered=()
    local item
    for item in "${arr_ref[@]}"; do
        if [[ "$item" != "$target" ]]; then
            filtered+=("$item")
        fi
    done
    arr_ref=("${filtered[@]}")
}

prune_flatpak_app_everywhere() {
    local target="$1"
    local removed=0
    local before after array_name
    for array_name in \
        "FLATPAK_PROFILE_CORE_APPS" \
        "FLATPAK_PROFILE_AI_WORKSTATION_APPS" \
        "FLATPAK_PROFILE_GAMING_APPS" \
        "FLATPAK_PROFILE_MINIMAL_APPS"; do
        local -n prune_ref="$array_name"
        before=${#prune_ref[@]}
        remove_flatpak_app "$array_name" "$target"
        after=${#prune_ref[@]}
        if (( after < before )); then
            removed=1
        fi
    done

    if (( removed == 1 )); then
        register_pruned_flatpak_app "$target"
    fi
}

prune_arch_incompatible_flatpaks() {
    detect_flatpak_install_arch
    local arch="${FLATPAK_INSTALL_ARCH:-$(uname -m)}"
    case "$arch" in
        aarch64|arm64)
            prune_flatpak_app_everywhere "com.google.Chrome"
            prune_flatpak_app_everywhere "com.obsproject.Studio"
            # Gaming apps that don't support ARM
            prune_flatpak_app_everywhere "com.valvesoftware.Steam"
            prune_flatpak_app_everywhere "net.lutris.Lutris"
            prune_flatpak_app_everywhere "com.heroicgameslauncher.hgl"
            prune_flatpak_app_everywhere "net.pcsx2.PCSX2"
            prune_flatpak_app_everywhere "net.rpcs3.RPCS3"
            ;;
    esac
}

