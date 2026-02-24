#!/usr/bin/env bash
#
# Service Conflict Resolution Library
# Purpose: Detect and resolve conflicts between system and user services
# Version: 1.0.0
#
# This library handles conflicts between:
# - System-level services (root, /etc/systemd/system/)
# - User-level services (home-manager, ~/.config/systemd/user/)
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
# Required Libraries:
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#
# ============================================================================
# CONFLICT DETECTION
# ============================================================================

# Provide lightweight fallbacks when user-interaction/logging helpers are not loaded
if ! declare -F print_info >/dev/null 2>&1; then
    print_info() { echo "INFO: $*"; }
fi
if ! declare -F print_success >/dev/null 2>&1; then
    print_success() { echo "OK: $*"; }
fi
if ! declare -F print_warning >/dev/null 2>&1; then
    print_warning() { echo "WARN: $*"; }
fi
if ! declare -F print_error >/dev/null 2>&1; then
    print_error() { echo "ERROR: $*" >&2; }
fi
if ! declare -F print_section >/dev/null 2>&1; then
    print_section() { echo "==== $* ===="; }
fi

# Mapping of service conflicts: system-service → user-services
declare -gA SERVICE_CONFLICT_MAP=(
    # AI Stack Services
    ["qdrant.service"]="podman-local-ai-qdrant.service"
)

# Port mapping for conflict detection
declare -gA SERVICE_PORT_MAP=(
    ["qdrant.service"]="6333,6334"
    ["podman-local-ai-qdrant.service"]="6333,6334"
)

# Check if a system service is active
is_system_service_active() {
    local service_name="$1"
    sudo systemctl is-active "$service_name" &>/dev/null
}

# Check if a user service is enabled in home-manager config
is_user_service_enabled_in_config() {
    local service_name="$1"
    local hm_config="${HM_CONFIG_DIR:-$HOME/.dotfiles/home-manager}/home.nix"

    # Check if localAiStackEnabled is true (for podman AI services)
    if [[ "$service_name" =~ ^podman-local-ai- ]]; then
        if [[ -f "$hm_config" ]]; then
            grep -q "localAiStackEnabled = true" "$hm_config" 2>/dev/null
            return $?
        fi
    fi

    return 1
}

# Detect service conflicts
detect_service_conflicts() {
    local -a conflicts=()

    print_info "Checking for service conflicts between system and user levels..."
    echo ""

    for system_service in "${!SERVICE_CONFLICT_MAP[@]}"; do
        local user_service="${SERVICE_CONFLICT_MAP[$system_service]}"

        # Check if system service is active
        if is_system_service_active "$system_service"; then
            # Check if user service would be enabled
            if is_user_service_enabled_in_config "$user_service"; then
                conflicts+=("$system_service:$user_service")
                print_warning "Conflict detected: $system_service (system) vs $user_service (user)"

                # Show port information
                local ports="${SERVICE_PORT_MAP[$system_service]:-unknown}"
                print_info "  Ports in use: $ports"
            fi
        fi
    done

    if (( ${#conflicts[@]} == 0 )); then
        print_success "✓ No service conflicts detected"
        return 0
    else
        echo ""
        print_warning "Found ${#conflicts[@]} service conflict(s)"
        return 1
    fi
}

# ============================================================================
# CONFLICT RESOLUTION
# ============================================================================

# Resolve a specific service conflict
resolve_service_conflict() {
    local system_service="$1"
    local user_service="$2"
    local strategy="${3:-disable-system}"  # Options: disable-system, disable-user, change-ports

    case "$strategy" in
        disable-system)
            print_info "Resolving conflict: Disabling system service $system_service"

            # Step 1: Stop the service if it's running
            if sudo systemctl is-active "$system_service" &>/dev/null; then
                if sudo systemctl stop "$system_service" 2>/dev/null; then
                    print_success "  ✓ Stopped $system_service"
                else
                    print_warning "  ⚠ Could not stop $system_service (may already be stopped)"
                fi
            else
                print_info "  • $system_service is not running"
            fi

            # Step 2: Mask the service (works on NixOS read-only filesystem)
            # Masking creates a symlink to /dev/null, preventing the service from starting
            if sudo systemctl is-enabled "$system_service" &>/dev/null 2>&1; then
                # Try mask instead of disable (works on read-only filesystems)
                if sudo systemctl mask "$system_service" 2>/dev/null; then
                    print_success "  ✓ Masked $system_service (prevents auto-start)"
                else
                    # If mask fails, try disable (for non-NixOS systems)
                    if sudo systemctl disable "$system_service" 2>/dev/null; then
                        print_success "  ✓ Disabled $system_service"
                    else
                        print_warning "  ⚠ Could not mask/disable $system_service"
                        print_info "  • Service is stopped, which is sufficient for now"
                        print_info "  • To permanently disable, remove from configuration.nix and rebuild"
                    fi
                fi
            else
                print_info "  • $system_service is not enabled"
            fi

            print_success "✓ System service $system_service stopped (user service can now start)"
            ;;

        disable-user)
            print_info "Resolving conflict: Keeping system service, disabling user service"
            print_info "  You need to set localAiStackEnabled = false in home.nix"
            print_warning "  This resolution strategy requires manual config changes"
            return 0
            ;;

        *)
            print_error "Unknown conflict resolution strategy: $strategy"
            return 1
            ;;
    esac
}

# Automatically resolve all detected conflicts
auto_resolve_service_conflicts() {
    local strategy="${1:-disable-system}"
    local -a conflicts=()
    local -a resolved_services=()

    # Collect conflicts
    for system_service in "${!SERVICE_CONFLICT_MAP[@]}"; do
        local user_service="${SERVICE_CONFLICT_MAP[$system_service]}"

        if is_system_service_active "$system_service"; then
            if is_user_service_enabled_in_config "$user_service"; then
                conflicts+=("$system_service:$user_service")
            fi
        fi
    done

    if (( ${#conflicts[@]} == 0 )); then
        return 0
    fi

    print_section "Resolving Service Conflicts"
    print_info "Strategy: $strategy"
    echo ""

    for conflict in "${conflicts[@]}"; do
        local system_service="${conflict%%:*}"
        local user_service="${conflict##*:}"

        if ! resolve_service_conflict "$system_service" "$user_service" "$strategy"; then
            print_error "Failed to resolve conflict: $system_service vs $user_service"
            return 1
        fi
        resolved_services+=("$system_service")
        echo ""
    done

    print_success "✓ All service conflicts resolved (temporarily)"
    echo ""

    # Provide instructions for permanent resolution
    if (( ${#resolved_services[@]} > 0 )); then
        print_info "For permanent resolution, disable these services in /etc/nixos/configuration.nix:"
        for service in "${resolved_services[@]}"; do
            local service_name="${service%.service}"
            print_info "  services.${service_name}.enable = false;"
        done
        echo ""
        print_info "Then run: sudo nixos-rebuild switch"
        echo ""
    fi

    return 0
}

# ============================================================================
# PRE-DEPLOYMENT CHECKS
# ============================================================================

# Run before home-manager switch
pre_home_manager_conflict_check() {
    local auto_resolve="${1:-false}"

    print_section "Pre-Deployment Service Conflict Check"
    echo ""

    if ! detect_service_conflicts; then
        echo ""

        if [[ "$auto_resolve" == "true" ]]; then
            print_info "Auto-resolution enabled: Will disable conflicting system services"
            echo ""
            auto_resolve_service_conflicts "disable-system"
            return $?
        else
            print_warning "Service conflicts detected but auto-resolution is disabled"
            echo ""
            print_info "Options:"
            print_info "  1. Run with --auto-resolve-conflicts to automatically disable system services"
            print_info "  2. Manually disable system services: sudo systemctl disable --now <service>"
            print_info "  3. Disable user services by setting localAiStackEnabled = false in home.nix"
            echo ""

            if declare -F confirm >/dev/null 2>&1; then
                if confirm "Automatically resolve conflicts by disabling system services?" "y"; then
                    auto_resolve_service_conflicts "disable-system"
                    return $?
                else
                    print_warning "Conflicts not resolved - deployment may fail"
                    return 1
                fi
            else
                return 1
            fi
        fi
    fi

    return 0
}

# ============================================================================
# PORT CONFLICT DETECTION
# ============================================================================

# Check if specific ports are in use
check_port_conflicts() {
    local ports="$1"
    local -a conflicting_ports=()

    IFS=',' read -ra port_array <<< "$ports"

    for port in "${port_array[@]}"; do
        if ss -tlnp 2>/dev/null | grep -q ":${port} " || ss -tlnp 2>/dev/null | grep -q ":${port}\$"; then
            conflicting_ports+=("$port")
        fi
    done

    if (( ${#conflicting_ports[@]} > 0 )); then
        print_warning "Ports in use: ${conflicting_ports[*]}"
        return 1
    fi

    return 0
}

# Show which processes are using conflicting ports
show_port_usage() {
    local ports="$1"

    IFS=',' read -ra port_array <<< "$ports"

    print_info "Port usage details:"
    for port in "${port_array[@]}"; do
        local processes
        processes=$(ss -tlnp 2>/dev/null | grep ":${port} " || ss -tlnp 2>/dev/null | grep ":${port}\$" || true)

        if [[ -n "$processes" ]]; then
            echo "  Port $port:"
            echo "$processes" | sed 's/^/    /'
        fi
    done
}

# ============================================================================
# SUMMARY AND REPORTING
# ============================================================================

# Generate conflict resolution report
generate_conflict_report() {
    local tmp_root="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
    local report_file="${1:-${tmp_root}/service-conflict-report.txt}"

    {
        echo "Service Conflict Report"
        echo "Generated: $(date)"
        echo "========================================"
        echo ""
        echo "System Services (Active):"
        for service in "${!SERVICE_CONFLICT_MAP[@]}"; do
            if is_system_service_active "$service"; then
                echo "  ✓ $service"
                local ports="${SERVICE_PORT_MAP[$service]:-unknown}"
                echo "    Ports: $ports"
            fi
        done
        echo ""
        echo "User Services (Configured in home.nix):"
        for service in "${SERVICE_CONFLICT_MAP[@]}"; do
            if is_user_service_enabled_in_config "$service"; then
                echo "  ✓ $service"
                local ports="${SERVICE_PORT_MAP[$service]:-unknown}"
                echo "    Ports: $ports"
            fi
        done
        echo ""
        echo "Port Usage:"
        ss -tlnp 2>/dev/null | grep -E ':(6333|6334|11434|8081)' || echo "  No AI stack ports in use"
    } > "$report_file"

    print_info "Conflict report saved to: $report_file"
}

# Export functions for use in other scripts
export -f is_system_service_active
export -f is_user_service_enabled_in_config
export -f detect_service_conflicts
export -f resolve_service_conflict
export -f auto_resolve_service_conflicts
export -f pre_home_manager_conflict_check
export -f check_port_conflicts
export -f show_port_usage
export -f generate_conflict_report
