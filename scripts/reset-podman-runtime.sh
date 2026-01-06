#!/usr/bin/env bash
# Reset Podman runtime dirs when boot ID mismatch occurs.

set -euo pipefail

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }

uid="${PODMAN_RUNTIME_UID:-$(id -u)}"

user_dirs=(
    "/run/user/${uid}/libpod"
    "/run/user/${uid}/containers"
)

system_dirs=(
    "/run/libpod"
    "/run/containers/storage"
)

removed_any=false

info "Checking Podman runtime directories..."

for dir in "${user_dirs[@]}"; do
    if [[ -d "$dir" ]]; then
        if rm -rf "$dir" 2>/dev/null; then
            success "Removed $dir"
            removed_any=true
        elif command -v sudo >/dev/null 2>&1; then
            if sudo -n rm -rf "$dir" 2>/dev/null; then
                success "Removed $dir (via sudo)"
                removed_any=true
            else
                warn "Need sudo to remove: $dir"
                warn "Run: sudo rm -rf $dir"
                return 1
            fi
        else
            warn "Need sudo to remove: $dir"
            warn "Run: sudo rm -rf $dir"
            return 1
        fi
    fi
done

need_system_cleanup=false
for dir in "${system_dirs[@]}"; do
    if [[ -d "$dir" ]]; then
        need_system_cleanup=true
        break
    fi
done

if [[ "$need_system_cleanup" == "true" ]]; then
    if [[ "$EUID" -eq 0 ]]; then
        rm -rf "${system_dirs[@]}"
        success "Removed ${system_dirs[*]}"
        removed_any=true
    elif command -v sudo >/dev/null 2>&1; then
        if sudo -n rm -rf "${system_dirs[@]}" 2>/dev/null; then
            success "Removed ${system_dirs[*]} (via sudo)"
            removed_any=true
        else
            warn "Need sudo to remove: ${system_dirs[*]}"
            warn "Run: sudo rm -rf ${system_dirs[*]}"
            return 1
        fi
    else
        warn "Need sudo to remove: ${system_dirs[*]}"
        warn "Run: sudo rm -rf ${system_dirs[*]}"
        return 1
    fi
fi

if [[ "$removed_any" == "false" ]]; then
    info "No Podman runtime directories needed cleanup."
fi

success "Podman runtime cleanup complete."
