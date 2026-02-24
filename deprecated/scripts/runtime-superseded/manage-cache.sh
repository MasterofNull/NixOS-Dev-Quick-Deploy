#!/usr/bin/env bash
# Cache Management Tool
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Show cache statistics and manage cache cleanup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/download-cache.sh"

BUILD_CACHE_ROOT="${BUILD_CACHE_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/buildah-cache}"

get_buildah_cache_dirs() {
    local dirs=()

    if compgen -G "${BUILD_CACHE_ROOT}*" > /dev/null 2>&1; then
        dirs+=( "${BUILD_CACHE_ROOT}"* )
    fi

    if [ -d "/var" ]; then
        while IFS= read -r dir; do
            dirs+=( "$dir" )
        done < <(find /var -maxdepth 2 -type d -name 'buildah-cache*' 2>/dev/null)
    fi

    if [ ${#dirs[@]} -eq 0 ]; then
        return 0
    fi

    printf '%s\n' "${dirs[@]}" | awk '!seen[$0]++'
}

# Show all cache statistics
show_all_stats() {
    echo "=== NixOS Quick Deploy - Cache Statistics ==="
    echo ""

    # Pip cache (BuildKit cache mount)
    echo "📦 Pip Cache (BuildKit):"
    mapfile -t buildah_cache_dirs < <(get_buildah_cache_dirs)
    if [ ${#buildah_cache_dirs[@]} -gt 0 ]; then
        for path in "${buildah_cache_dirs[@]}"; do
            local size
            size=$(du -sh "$path" 2>/dev/null | awk '{print $1}' || echo "0")
            echo "  $size - $(basename "$path")"
        done
        local total
        total=$(du -sh "${buildah_cache_dirs[@]}" 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "0")
        echo "  Total: ${total}"
    else
        echo "  (empty)"
    fi
    echo ""

    # HuggingFace cache
    echo "🤗 HuggingFace Cache:"
    if [ -d "${HOME}/.cache/huggingface" ]; then
        local size=$(du -sh "${HOME}/.cache/huggingface" 2>/dev/null | awk '{print $1}' || echo "0")
        local files=$(find "${HOME}/.cache/huggingface" -type f 2>/dev/null | wc -l)
        echo "  Size: $size"
        echo "  Files: $files"
        echo "  Location: ${HOME}/.cache/huggingface"
    else
        echo "  (empty)"
    fi
    echo ""

    # Podman build cache
    echo "🐳 Podman Build Cache:"
    if [ -d "${HOME}/.cache/podman-build-cache" ]; then
        local size=$(du -sh "${HOME}/.cache/podman-build-cache" 2>/dev/null | awk '{print $1}' || echo "0")
        echo "  Size: $size"
        echo "  Location: ${HOME}/.cache/podman-build-cache"
    else
        echo "  (empty)"
    fi
    echo ""

    # Download cache
    echo "⬇️  Download Cache:"
    show_cache_stats
    echo ""

    # Nix store (if accessible)
    echo "❄️  Nix Store:"
    if [ -d "/nix/store" ]; then
        if [ -r "/nix/store" ]; then
            local size=$(du -sh /nix/store 2>/dev/null | awk '{print $1}' || echo "unknown")
            echo "  Size: $size"
            echo "  Location: /nix/store"
        else
            echo "  (requires root to check)"
        fi
    else
        echo "  (not present)"
    fi
    echo ""

    # Total
    echo "=== Total Cache Usage ==="
    local total_mb=0

    if [ ${#buildah_cache_dirs[@]} -gt 0 ]; then
        local pip_mb
        pip_mb=$(du -sm "${buildah_cache_dirs[@]}" 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "0")
        total_mb=$((total_mb + pip_mb))
    fi

    if [ -d "${HOME}/.cache/huggingface" ]; then
        local hf_mb=$(du -sm "${HOME}/.cache/huggingface" 2>/dev/null | awk '{print $1}' || echo "0")
        total_mb=$((total_mb + hf_mb))
    fi

    if [ -d "${HOME}/.cache/podman-build-cache" ]; then
        local podman_mb=$(du -sm "${HOME}/.cache/podman-build-cache" 2>/dev/null | awk '{print $1}' || echo "0")
        total_mb=$((total_mb + podman_mb))
    fi

    if [ -d "${HOME}/.cache/nixos-quick-deploy/downloads" ]; then
        local dl_mb=$(du -sm "${HOME}/.cache/nixos-quick-deploy/downloads" 2>/dev/null | awk '{print $1}' || echo "0")
        total_mb=$((total_mb + dl_mb))
    fi

    local total_gb=$(echo "scale=2; $total_mb / 1024" | bc 2>/dev/null || echo "0")
    echo "  Total: ${total_gb} GB (${total_mb} MB)"
    echo ""
}

# Clear all caches
clear_all_caches() {
    echo "⚠️  WARNING: This will delete ALL caches!"
    echo "   You will need to re-download all packages and models."
    echo ""
    read -p "Are you sure you want to clear ALL caches? (y/N) " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "✓ Cancelled"
        return 0
    fi

    echo ""
    echo "🧹 Clearing all caches..."

    # Pip cache
    mapfile -t buildah_cache_dirs < <(get_buildah_cache_dirs)
    if [ ${#buildah_cache_dirs[@]} -gt 0 ]; then
        echo "  Clearing pip cache..."
        for path in "${buildah_cache_dirs[@]}"; do
            rm -rf "$path" 2>/dev/null || sudo rm -rf "$path" 2>/dev/null || echo "  ⚠ Could not remove (requires sudo): $path"
        done
    fi

    # HuggingFace cache
    if [ -d "${HOME}/.cache/huggingface" ]; then
        echo "  Clearing HuggingFace cache..."
        rm -rf "${HOME}/.cache/huggingface"
    fi

    # Podman build cache
    if [ -d "${HOME}/.cache/podman-build-cache" ]; then
        echo "  Clearing Podman build cache..."
        rm -rf "${HOME}/.cache/podman-build-cache"
    fi

    # Download cache
    if [ -d "${HOME}/.cache/nixos-quick-deploy/downloads" ]; then
        echo "  Clearing download cache..."
        rm -rf "${HOME}/.cache/nixos-quick-deploy/downloads"
    fi

    echo ""
    echo "✅ All caches cleared!"
    echo ""
    echo "Next steps:"
    echo "  - Run ./nixos-quick-deploy.sh to rebuild with fresh caches"
    echo "  - Caches will be repopulated automatically during next build"
}

# Clear only download cache
clear_download_cache() {
    echo "🧹 Clearing download cache..."
    if [ -d "${HOME}/.cache/nixos-quick-deploy/downloads" ]; then
        rm -rf "${HOME}/.cache/nixos-quick-deploy/downloads"
        echo "✓ Download cache cleared"
    else
        echo "✓ Download cache already empty"
    fi
}

# Clean old cache entries
clean_old_caches() {
    local days="${1:-30}"

    echo "🧹 Cleaning old cache entries (older than ${days} days)..."
    echo ""

    # Download cache
    echo "Cleaning download cache..."
    cleanup_download_cache "$days"
    echo ""

    # HuggingFace cache (be careful, only remove .lock files)
    if [ -d "${HOME}/.cache/huggingface" ]; then
        echo "Cleaning HuggingFace .lock files..."
        local lock_count=$(find "${HOME}/.cache/huggingface" -name "*.lock" -type f | wc -l)
        find "${HOME}/.cache/huggingface" -name "*.lock" -type f -delete 2>/dev/null || true
        echo "✓ Removed $lock_count lock files"
    fi

    echo ""
    echo "✅ Cleanup complete!"
}

# Usage information
usage() {
    cat <<EOF
Cache Management Tool

Usage: $0 COMMAND [OPTIONS]

Commands:
  stats              Show cache statistics for all components
  clear              Clear ALL caches (interactive confirmation)
  clear-downloads    Clear only download cache
  clean [DAYS]       Remove cache entries older than DAYS (default: 30)
  help               Show this help message

Examples:
  $0 stats                    # Show all cache statistics
  $0 clear                    # Clear all caches (with confirmation)
  $0 clear-downloads          # Clear only download cache
  $0 clean 60                 # Remove cache entries older than 60 days

Cache Locations:
  Pip:          ${BUILD_CACHE_ROOT}*
  HuggingFace:  ${HOME}/.cache/huggingface
  Podman Build: ${HOME}/.cache/podman-build-cache
  Downloads:    ${HOME}/.cache/nixos-quick-deploy/downloads
  Nix Store:    /nix/store (system-wide)

EOF
}

# Main
case "${1:-stats}" in
    stats)
        show_all_stats
        ;;
    clear)
        clear_all_caches
        ;;
    clear-downloads)
        clear_download_cache
        ;;
    clean)
        clean_old_caches "${2:-30}"
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo "Error: Unknown command: $1"
        echo ""
        usage
        exit 1
        ;;
esac
