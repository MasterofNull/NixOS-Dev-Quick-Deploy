#!/usr/bin/env bash
#
# Deploy CLI - Nix Binary Cache Management
# Incremental build optimization through binary cache configuration
#
# Usage:
#   source nix-caching.sh
#   setup_binary_cache
#   check_config_changed
#   export_build_to_cache

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

CACHE_DIR="${DEPLOY_CACHE_DIR:-/var/cache/nix-binary-cache}"
CONFIG_STATE_FILE="/var/cache/deploy-config.state"
FLAKE_REF="${FLAKE_REF:-.}"

# ============================================================================
# Cache Setup
# ============================================================================

setup_binary_cache() {
  log_info "Setting up local binary cache at $CACHE_DIR..."

  # Ensure cache directory exists
  if ! [[ -d "$CACHE_DIR" ]]; then
    sudo mkdir -p "$CACHE_DIR" 2>/dev/null || mkdir -p "$CACHE_DIR"
    sudo chmod 755 "$CACHE_DIR" 2>/dev/null || chmod 755 "$CACHE_DIR"
  fi

  # Check if nix.conf needs updating
  if ! grep -q "local binary cache" /etc/nix/nix.conf 2>/dev/null; then
    log_info "  Updating /etc/nix/nix.conf..."

    # Create nix.conf backup
    sudo cp /etc/nix/nix.conf /etc/nix/nix.conf.backup.$(date +%s) 2>/dev/null || true

    # Add cache configuration
    cat >> /tmp/nix-cache.conf <<EOF
# Local binary cache for faster incremental builds (auto-added)
substituters = file://${CACHE_DIR} https://cache.nixos.org https://nix-community.cachix.org
trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypG7a9Tf97NZ95/sZv7M7PwAgo= nix-community.cachix.org-1:mB9FSh9qf2QlDqL7m7OMu+8NvLEV+srxd7a5Bt2Ydz8=
EOF

    sudo tee -a /etc/nix/nix.conf < /tmp/nix-cache.conf >/dev/null 2>&1 || \
      cat /tmp/nix-cache.conf >> /etc/nix/nix.conf

    log_success "nix.conf updated with binary cache configuration"
  else
    log_debug "Binary cache already configured in nix.conf"
  fi
}

verify_cache_setup() {
  log_debug "Verifying cache setup..."

  if [[ ! -d "$CACHE_DIR" ]]; then
    log_warn "Cache directory does not exist: $CACHE_DIR"
    return 1
  fi

  if ! grep -q "file://${CACHE_DIR}" /etc/nix/nix.conf 2>/dev/null; then
    log_warn "Cache directory not in nix.conf"
    return 1
  fi

  log_success "Binary cache verified"
  return 0
}

# ============================================================================
# Configuration Change Detection
# ============================================================================

compute_config_hash() {
  # Compute hash of current flake metadata and configuration
  local hash

  hash="$(
    {
      git -C "$FLAKE_REF" rev-parse HEAD 2>/dev/null || echo "no-git"
      cat "$FLAKE_REF/flake.nix" 2>/dev/null | md5sum | awk '{print $1}' || echo "no-flake"
      cat "$FLAKE_REF/flake.lock" 2>/dev/null | md5sum | awk '{print $1}' || echo "no-lock"
    } | md5sum | awk '{print $1}'
  )"

  echo "$hash"
}

check_config_changed() {
  local current_hash
  current_hash="$(compute_config_hash)"

  if [[ ! -f "$CONFIG_STATE_FILE" ]]; then
    log_debug "No previous config state found"
    echo "$current_hash" > "$CONFIG_STATE_FILE" 2>/dev/null || true
    return 1  # Config "changed" (first time)
  fi

  local previous_hash
  previous_hash="$(cat "$CONFIG_STATE_FILE")"

  if [[ "$previous_hash" == "$current_hash" ]]; then
    log_info "Configuration unchanged since last deploy (may skip rebuild)"
    return 0  # No change
  else
    log_info "Configuration changed since last deploy"
    echo "$current_hash" > "$CONFIG_STATE_FILE"
    return 1  # Changed
  fi
}

# ============================================================================
# Cache Export and Import
# ============================================================================

export_build_to_cache() {
  local profile="${1:-/nix/var/nix/profiles/system}"

  log_info "Exporting built packages to binary cache..."

  verify_cache_setup || return 1

  # Export system packages to cache
  if nix copy --to "file://$CACHE_DIR" "$profile" 2>/dev/null; then
    log_success "System profile exported to cache"
  else
    log_warn "Could not export system profile (continuing anyway)"
  fi

  # Export current system closure
  if nix copy --to "file://$CACHE_DIR" /run/current-system 2>/dev/null; then
    log_success "Current system exported to cache"
  else
    log_debug "Could not export current system (continuing)"
  fi

  # Report cache size
  local cache_size
  cache_size="$(du -sh "$CACHE_DIR" 2>/dev/null | cut -f1)"
  log_info "  Cache size: $cache_size"
}

import_from_cache() {
  log_debug "Importing from binary cache (if available)..."

  verify_cache_setup || return 1

  # Cache is automatically used by nix through substituters
  log_debug "Binary cache available for substitutions"
}

# ============================================================================
# Cache Management
# ============================================================================

cache_status() {
  log_info "Binary Cache Status:"

  if [[ ! -d "$CACHE_DIR" ]]; then
    log_warn "  Cache directory not found: $CACHE_DIR"
    return 1
  fi

  local size
  local file_count
  size="$(du -sh "$CACHE_DIR" 2>/dev/null | cut -f1)"
  file_count="$(find "$CACHE_DIR" -type f 2>/dev/null | wc -l)"

  log_info "  Location: $CACHE_DIR"
  log_info "  Size: $size"
  log_info "  Files: $file_count"

  # Check configuration
  if grep -q "file://${CACHE_DIR}" /etc/nix/nix.conf 2>/dev/null; then
    log_success "  Configuration: Active"
  else
    log_warn "  Configuration: Not configured"
  fi

  return 0
}

cache_clear() {
  log_warn "Clearing binary cache..."

  if [[ -d "$CACHE_DIR" ]]; then
    local count
    count="$(find "$CACHE_DIR" -type f | wc -l)"
    rm -rf "$CACHE_DIR"/*
    log_success "Cleared $count cache files"
  else
    log_info "Cache directory already empty"
  fi
}

cache_prewarm() {
  log_info "Pre-warming binary cache with common dependencies..."

  verify_cache_setup || return 1

  # List of commonly used packages to cache
  local common_packages=(
    "bash"
    "coreutils"
    "curl"
    "systemd"
    "nix"
  )

  for pkg in "${common_packages[@]}"; do
    if nix path-info "nixpkgs#$pkg" >/dev/null 2>&1; then
      nix copy --to "file://$CACHE_DIR" "nixpkgs#$pkg" 2>/dev/null || true
    fi
  done

  log_success "Cache pre-warming complete"
}

# ============================================================================
# Build Optimization
# ============================================================================

should_rebuild() {
  # Return 0 if rebuild needed, 1 if can skip
  if check_config_changed; then
    log_debug "Configuration unchanged - rebuild may be skipped"
    return 1
  else
    log_debug "Configuration changed - rebuild needed"
    return 0
  fi
}

# ============================================================================
# Home-Manager Optimization
# ============================================================================

check_home_manager_changed() {
  local prev_gen="/home/${USER:-root}/.local/state/home-manager/previous-generation"
  local prev_hash=""

  if [[ -L "$prev_gen" ]]; then
    prev_hash="$(readlink -f "$prev_gen" 2>/dev/null | md5sum | awk '{print $1}')"
  fi

  # Compute current home-manager config hash
  local curr_hash
  curr_hash="$(
    {
      cat "$FLAKE_REF/flake.nix" 2>/dev/null | md5sum | awk '{print $1}'
      find "$HOME" -name ".config" -type d 2>/dev/null | head -1 | xargs ls -la 2>/dev/null || echo ""
    } | md5sum | awk '{print $1}'
  )"

  if [[ -n "$prev_hash" ]] && [[ "$prev_hash" == "$curr_hash" ]]; then
    log_info "Home-manager configuration unchanged"
    return 0
  else
    log_info "Home-manager configuration changed"
    return 1
  fi
}

# ============================================================================
# Cache Optimization Toggles
# ============================================================================

enable_binary_cache() {
  export DEPLOY_USE_BINARY_CACHE=true
  log_debug "Binary cache optimization enabled"
}

disable_binary_cache() {
  export DEPLOY_USE_BINARY_CACHE=false
  log_debug "Binary cache optimization disabled"
}

is_binary_cache_enabled() {
  [[ "${DEPLOY_USE_BINARY_CACHE:-true}" == "true" ]]
}

# ============================================================================
# Export Functions
# ============================================================================

export -f setup_binary_cache
export -f verify_cache_setup
export -f compute_config_hash
export -f check_config_changed
export -f export_build_to_cache
export -f import_from_cache
export -f cache_status
export -f cache_clear
export -f cache_prewarm
export -f should_rebuild
export -f check_home_manager_changed
export -f enable_binary_cache
export -f disable_binary_cache
export -f is_binary_cache_enabled
