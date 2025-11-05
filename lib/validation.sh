#!/usr/bin/env bash
#
# Validation Functions
# Purpose: Input validation and disk space checks
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/user-interaction.sh → print_* functions
#   - lib/logging.sh → log() function
#
# Required Variables:
#   - REQUIRED_DISK_SPACE_GB → Minimum required disk space
#
# Exports:
#   - validate_hostname() → Validate hostname format
#   - validate_github_username() → Validate GitHub username format
#   - assert_unique_paths() → Check for path conflicts
#   - check_disk_space() → Verify sufficient disk space
#
# ============================================================================

# Validate input (prevent injection)
validate_hostname() {
    local hostname="$1"
    if [[ ! "$hostname" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$ ]]; then
        print_error "Invalid hostname: $hostname"
        print_info "Hostname must be alphanumeric with optional hyphens"
        return 1
    fi
    return 0
}

validate_github_username() {
    local username="$1"
    if [[ ! "$username" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,38}[a-zA-Z0-9])?$ ]]; then
        print_error "Invalid GitHub username: $username"
        return 1
    fi
    return 0
}

# Assert unique paths
assert_unique_paths() {
    local -a paths=()
    local -a vars=("$@")

    # Collect all path values
    for var_name in "${vars[@]}"; do
        local path="${!var_name}"
        if [[ -n "$path" ]]; then
            paths+=("$path")
        fi
    done

    # Check for duplicates
    local -A seen=()
    for path in "${paths[@]}"; do
        if [[ -n "${seen[$path]:-}" ]]; then
            print_error "Path conflict detected: $path is used multiple times"
            return 1
        fi
        seen[$path]=1
    done

    return 0
}

# Disk space check
check_disk_space() {
    local required_gb=$REQUIRED_DISK_SPACE_GB
    local available_gb=$(df -BG /nix 2>/dev/null | awk 'NR==2 {print $4}' | tr -d 'G' || echo "0")

    log INFO "Disk space check: ${available_gb}GB available, ${required_gb}GB required"

    if (( available_gb < required_gb )); then
        print_error "Insufficient disk space: ${available_gb}GB available, ${required_gb}GB required"
        print_info "Free up space or add more storage before continuing"
        echo ""
        print_info "This deployment installs:"
        echo "  • 100+ CLI tools and development utilities"
        echo "  • Python ML/AI environment (PyTorch, TensorFlow, LangChain, etc.)"
        echo "  • AI development tools (Ollama, GPT4All, Aider, etc.)"
        echo "  • Container stack (Podman, buildah, skopeo)"
        echo "  • Desktop applications via Flatpak"
        echo ""
        print_info "To free up space:"
        echo "  sudo nix-collect-garbage -d      # Remove old generations"
        echo "  sudo nix-store --optimize        # Deduplicate store files"
        echo "  sudo nix-store --gc              # Garbage collect unused paths"
        log ERROR "Disk space check failed"
        return 1
    fi

    print_success "Disk space check passed: ${available_gb}GB available"
    return 0
}
