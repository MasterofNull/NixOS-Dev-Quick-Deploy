#!/usr/bin/env bash
#
# Input Validation - Sanitize and validate all user inputs
# Purpose: Prevent command injection, path traversal, and invalid data
# Version: 6.1.0
#
# ============================================================================

: "${MIN_PASSWORD_LENGTH:=12}"

# ============================================================================
# Validate hostname (RFC 1123)
# ============================================================================
# Accepts: lowercase alphanumeric, hyphens, 1-63 chars per label
# Rejects: uppercase, special chars, leading/trailing hyphens
# ============================================================================
validate_hostname() {
    local hostname="${1:-}"

    if [[ -z "$hostname" ]]; then
        echo "Hostname cannot be empty" >&2
        return 1
    fi

    if [[ ${#hostname} -gt 253 ]]; then
        echo "Hostname exceeds 253 character limit" >&2
        return 1
    fi

    # Check each label
    IFS='.' read -ra labels <<< "$hostname"
    for label in "${labels[@]}"; do
        if [[ ${#label} -gt 63 ]] || [[ ${#label} -eq 0 ]]; then
            echo "Label '$label' must be 1-63 characters" >&2
            return 1
        fi
        if [[ ! "$label" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]]; then
            echo "Label '$label' contains invalid characters (use lowercase, digits, hyphens)" >&2
            return 1
        fi
    done

    return 0
}

# ============================================================================
# Validate username (POSIX)
# ============================================================================
# Accepts: starts with lowercase letter or underscore, then alphanumeric/underscore/hyphen
# Rejects: special chars, spaces, command injection attempts
# ============================================================================
validate_username() {
    local username="${1:-}"

    if [[ -z "$username" ]]; then
        echo "Username cannot be empty" >&2
        return 1
    fi

    if [[ ${#username} -gt 32 ]]; then
        echo "Username exceeds 32 character limit" >&2
        return 1
    fi

    if [[ ! "$username" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]; then
        echo "Username must start with a letter or underscore, followed by lowercase letters, digits, underscores, or hyphens" >&2
        return 1
    fi

    return 0
}

# ============================================================================
# Validate and sanitize a file path
# ============================================================================
# Rejects: path traversal (..), null bytes, command substitution
# Returns: Canonicalized path on stdout
# ============================================================================
validate_path() {
    local path="${1:-}"

    if [[ -z "$path" ]]; then
        echo "Path cannot be empty" >&2
        return 1
    fi

    # Note: Bash variables cannot hold null bytes, so null byte injection
    # is not possible through bash string parameters.

    # Reject path traversal
    if [[ "$path" == *".."* ]]; then
        echo "Path traversal (..) not allowed" >&2
        return 1
    fi

    # Reject command substitution attempts
    if [[ "$path" == *'$('* ]] || [[ "$path" == *'`'* ]]; then
        echo "Command substitution not allowed in paths" >&2
        return 1
    fi

    # Reject semicolons, pipes, and other shell metacharacters
    local _meta_re='[;|&><]'
    if [[ "$path" =~ $_meta_re ]]; then
        echo "Shell metacharacters not allowed in paths" >&2
        return 1
    fi

    # Canonicalize (resolve symlinks and simplify)
    local canonical
    canonical=$(realpath -m "$path" 2>/dev/null) || {
        echo "Cannot resolve path: $path" >&2
        return 1
    }

    echo "$canonical"
    return 0
}

# ============================================================================
# Validate an integer within a range
# ============================================================================
# Usage: validate_integer <value> [min] [max]
# ============================================================================
validate_integer() {
    local value="${1:-}"
    local min="${2:-0}"
    local max="${3:-999999}"

    if [[ -z "$value" ]]; then
        echo "Value cannot be empty" >&2
        return 1
    fi

    if [[ ! "$value" =~ ^-?[0-9]+$ ]]; then
        echo "'$value' is not a valid integer" >&2
        return 1
    fi

    if [[ "$value" -lt "$min" ]]; then
        echo "$value is below minimum ($min)" >&2
        return 1
    fi

    if [[ "$value" -gt "$max" ]]; then
        echo "$value exceeds maximum ($max)" >&2
        return 1
    fi

    return 0
}

# ============================================================================
# Validate password strength
# ============================================================================
# Requires: minimum length + 3 of 4 character classes
# ============================================================================
validate_password_strength() {
    local password="${1:-}"
    local min_length="${2:-$MIN_PASSWORD_LENGTH}"

    if [[ -z "$password" ]]; then
        echo "Password cannot be empty" >&2
        return 1
    fi

    if [[ ${#password} -lt $min_length ]]; then
        echo "Password must be at least $min_length characters (got ${#password})" >&2
        return 1
    fi

    local score=0
    [[ "$password" =~ [A-Z] ]] && score=$((score + 1))
    [[ "$password" =~ [a-z] ]] && score=$((score + 1))
    [[ "$password" =~ [0-9] ]] && score=$((score + 1))
    [[ "$password" =~ [^a-zA-Z0-9] ]] && score=$((score + 1))

    if [[ $score -lt 3 ]]; then
        echo "Password must contain at least 3 of: uppercase, lowercase, digit, special character (score: $score/4)" >&2
        return 1
    fi

    return 0
}

# ============================================================================
# Validate a Nix attribute path
# ============================================================================
# Accepts: dot-separated alphanumeric identifiers (e.g., nixpkgs.python3)
# Rejects: shell metacharacters, command injection
# ============================================================================
validate_nix_attr() {
    local attr="${1:-}"

    if [[ -z "$attr" ]]; then
        echo "Attribute path cannot be empty" >&2
        return 1
    fi

    if [[ ! "$attr" =~ ^[a-zA-Z_][a-zA-Z0-9_.-]*$ ]]; then
        echo "Invalid Nix attribute path: $attr" >&2
        return 1
    fi

    return 0
}

# ============================================================================
# Validate a K8s namespace name
# ============================================================================
# RFC 1123 DNS label: lowercase, alphanumeric, hyphens, 1-63 chars
# ============================================================================
validate_k8s_namespace() {
    local ns="${1:-}"

    if [[ -z "$ns" ]]; then
        echo "Namespace cannot be empty" >&2
        return 1
    fi

    if [[ ${#ns} -gt 63 ]]; then
        echo "Namespace exceeds 63 character limit" >&2
        return 1
    fi

    if [[ ! "$ns" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]]; then
        echo "Namespace must be lowercase alphanumeric with hyphens" >&2
        return 1
    fi

    return 0
}

# ============================================================================
# Sanitize a string for safe use in shell commands
# ============================================================================
# Removes or escapes dangerous characters
# ============================================================================
sanitize_string() {
    local input="${1:-}"

    # Remove null bytes, control characters (except newline/tab)
    local sanitized
    sanitized=$(printf '%s' "$input" | tr -d '\0' | tr -d '\001-\010\013\014\016-\037')

    # Escape single quotes for safe shell use
    sanitized="${sanitized//\'/\'\\\'\'}"

    echo "$sanitized"
}

# ============================================================================
# Validate core configuration settings
# ============================================================================
# Ensures central config values are valid before proceeding.
# Returns ERR_CONFIG_INVALID on failure.
# ============================================================================
validate_config_settings() {
    local failures=0
    local err_code="${ERR_CONFIG_INVALID:-30}"

    local ai_ns="${AI_STACK_NAMESPACE:-${K3S_AI_NAMESPACE:-ai-stack}}"
    local backups_ns="${BACKUPS_NAMESPACE:-backups}"
    local logging_ns="${LOGGING_NAMESPACE:-logging}"

    for required_var in AI_STACK_NAMESPACE BACKUPS_NAMESPACE LOGGING_NAMESPACE K3S_KUBECONFIG AI_STACK_CONFIG_DIR AI_STACK_ENV_FILE; do
        if [[ -z "${!required_var:-}" ]]; then
            print_error "Required configuration variable is unset: ${required_var}"
            failures=$((failures + 1))
        fi
    done

    if ! validate_k8s_namespace "$ai_ns"; then
        print_error "Invalid AI stack namespace: $ai_ns"
        failures=$((failures + 1))
    fi

    if ! validate_k8s_namespace "$backups_ns"; then
        print_error "Invalid backups namespace: $backups_ns"
        failures=$((failures + 1))
    fi

    if ! validate_k8s_namespace "$logging_ns"; then
        print_error "Invalid logging namespace: $logging_ns"
        failures=$((failures + 1))
    fi

    for timeout_var in KUBECTL_TIMEOUT CURL_TIMEOUT CURL_CONNECT_TIMEOUT NIXOS_REBUILD_TIMEOUT HOME_MANAGER_TIMEOUT GENERIC_TIMEOUT; do
        local timeout_val="${!timeout_var:-}"
        if [[ -n "$timeout_val" ]] && ! validate_integer "$timeout_val" 1 86400; then
            print_error "Invalid ${timeout_var} value: ${timeout_val} (must be >= 1)"
            failures=$((failures + 1))
        fi
    done

    for port_var in QDRANT_PORT QDRANT_GRPC_PORT LLAMA_CPP_PORT OPEN_WEBUI_PORT POSTGRES_PORT REDIS_PORT GRAFANA_PORT PROMETHEUS_PORT AIDB_PORT HYBRID_COORDINATOR_PORT MINDSDB_PORT; do
        local port_val="${!port_var:-}"
        if [[ -n "$port_val" ]] && ! validate_integer "$port_val" 1 65535; then
            print_error "Invalid ${port_var} value: ${port_val} (must be 1-65535)"
            failures=$((failures + 1))
        fi
    done

    if ! validate_integer "${MIN_PASSWORD_LENGTH:-12}" 8 128; then
        print_error "Invalid MIN_PASSWORD_LENGTH: ${MIN_PASSWORD_LENGTH:-}"
        failures=$((failures + 1))
    fi

    if [[ -n "${AI_STACK_CONFIG_DIR:-}" ]] && ! validate_path "${AI_STACK_CONFIG_DIR}" >/dev/null; then
        print_error "Invalid AI_STACK_CONFIG_DIR path: ${AI_STACK_CONFIG_DIR}"
        failures=$((failures + 1))
    fi

    if [[ -n "${AI_STACK_CONFIG_DIR:-}" ]]; then
        local config_parent
        config_parent="$(dirname "${AI_STACK_CONFIG_DIR}")"
        if [[ -e "${AI_STACK_CONFIG_DIR}" ]]; then
            if [[ ! -w "${AI_STACK_CONFIG_DIR}" ]]; then
                print_error "AI_STACK_CONFIG_DIR is not writable: ${AI_STACK_CONFIG_DIR}"
                failures=$((failures + 1))
            fi
        elif [[ ! -w "${config_parent}" ]]; then
            print_error "Parent directory for AI_STACK_CONFIG_DIR is not writable: ${config_parent}"
            failures=$((failures + 1))
        fi
    fi

    if [[ -n "${AI_STACK_ENV_FILE:-}" ]] && ! validate_path "${AI_STACK_ENV_FILE}" >/dev/null; then
        print_error "Invalid AI_STACK_ENV_FILE path: ${AI_STACK_ENV_FILE}"
        failures=$((failures + 1))
    fi

    if [[ -n "${AI_STACK_ENV_FILE:-}" ]]; then
        local env_parent
        env_parent="$(dirname "${AI_STACK_ENV_FILE}")"
        if [[ -e "${AI_STACK_ENV_FILE}" ]]; then
            if [[ ! -w "${AI_STACK_ENV_FILE}" ]]; then
                print_error "AI_STACK_ENV_FILE is not writable: ${AI_STACK_ENV_FILE}"
                failures=$((failures + 1))
            fi
        elif [[ ! -w "${env_parent}" ]]; then
            print_error "Parent directory for AI_STACK_ENV_FILE is not writable: ${env_parent}"
            failures=$((failures + 1))
        fi
    fi

    if [[ "$failures" -gt 0 ]]; then
        log_error "$err_code" "Configuration validation failed with ${failures} issue(s)"
        return "$err_code"
    fi

    return 0
}

# Backward-compatible entrypoint used by roadmap task 18.5 and startup checks.
validate_config() {
    validate_config_settings
}
