#!/usr/bin/env bash
# Service Registry - Centralized service port and URL management
# Eliminates hard-coded port references across the codebase
# Author: Claude Code (Vibe Coding System)
# Date: 2025-12-31

set -euo pipefail

# Service port registry
# Override any port via environment variable: export AIDB_MCP_PORT=9091
declare -gA SERVICE_PORTS=(
    [AIDB_MCP]="${AIDB_MCP_PORT:-8091}"
    [HYBRID_COORDINATOR]="${HYBRID_COORDINATOR_PORT:-8092}"
    [LLAMA_CPP]="${LLAMA_CPP_PORT:-8080}"
    [QDRANT_HTTP]="${QDRANT_HTTP_PORT:-6333}"
    [QDRANT_GRPC]="${QDRANT_GRPC_PORT:-6334}"
    [POSTGRES]="${POSTGRES_PORT:-5432}"
    [REDIS]="${REDIS_PORT:-6379}"
    [OPEN_WEBUI]="${OPEN_WEBUI_PORT:-3001}"
    [MINDSDB]="${MINDSDB_PORT:-47334}"
    [RALPH_WIGGUM]="${RALPH_WIGGUM_PORT:-8098}"
    [HEALTH_MONITOR]="${HEALTH_MONITOR_PORT:-8099}"
    [AIDER]="${AIDER_PORT:-8093}"
    [AUTOGPT]="${AUTOGPT_PORT:-8097}"
    # Removed unused services: CONTINUE (8094), GOOSE (8095), LANGCHAIN (8096)
)

# Service host registry (for future multi-host support)
declare -gA SERVICE_HOSTS=(
    [AIDB_MCP]="${AIDB_MCP_HOST:-localhost}"
    [HYBRID_COORDINATOR]="${HYBRID_COORDINATOR_HOST:-localhost}"
    [LLAMA_CPP]="${LLAMA_CPP_HOST:-localhost}"
    [QDRANT_HTTP]="${QDRANT_HTTP_HOST:-localhost}"
    [QDRANT_GRPC]="${QDRANT_GRPC_HOST:-localhost}"
    [POSTGRES]="${POSTGRES_HOST:-localhost}"
    [REDIS]="${REDIS_HOST:-localhost}"
    [OPEN_WEBUI]="${OPEN_WEBUI_HOST:-localhost}"
    [MINDSDB]="${MINDSDB_HOST:-localhost}"
    [RALPH_WIGGUM]="${RALPH_WIGGUM_HOST:-localhost}"
    [HEALTH_MONITOR]="${HEALTH_MONITOR_HOST:-localhost}"
    [AIDER]="${AIDER_HOST:-localhost}"
    [AUTOGPT]="${AUTOGPT_HOST:-localhost}"
    # Removed unused services: CONTINUE, GOOSE, LANGCHAIN
)

# Get service URL
# Usage: get_service_url SERVICE_NAME
# Example: get_service_url AIDB_MCP  # Returns: http://localhost:8091
get_service_url() {
    local service="$1"

    if [[ -z "${SERVICE_PORTS[$service]:-}" ]]; then
        echo "ERROR: Unknown service: $service" >&2
        return 1
    fi

    local host="${SERVICE_HOSTS[$service]}"
    local port="${SERVICE_PORTS[$service]}"

    echo "http://${host}:${port}"
}

# Get service port
# Usage: get_service_port SERVICE_NAME
# Example: get_service_port LLAMA_CPP  # Returns: 8080
get_service_port() {
    local service="$1"

    if [[ -z "${SERVICE_PORTS[$service]:-}" ]]; then
        echo "ERROR: Unknown service: $service" >&2
        return 1
    fi

    echo "${SERVICE_PORTS[$service]}"
}

# Get service host
# Usage: get_service_host SERVICE_NAME
# Example: get_service_host POSTGRES  # Returns: localhost
get_service_host() {
    local service="$1"

    if [[ -z "${SERVICE_HOSTS[$service]:-}" ]]; then
        echo "ERROR: Unknown service: $service" >&2
        return 1
    fi

    echo "${SERVICE_HOSTS[$service]}"
}

# Export all service URLs as environment variables
# Usage: export_service_urls
# Exports: AIDB_MCP_URL, LLAMA_CPP_URL, etc.
export_service_urls() {
    for service in "${!SERVICE_PORTS[@]}"; do
        export "${service}_URL=$(get_service_url "$service")"
        export "${service}_PORT=$(get_service_port "$service")"
        export "${service}_HOST=$(get_service_host "$service")"
    done
}

# List all registered services
# Usage: list_services
list_services() {
    echo "Registered Services:"
    echo "===================="
    for service in "${!SERVICE_PORTS[@]}"; do
        printf "%-25s %s\n" "$service" "$(get_service_url "$service")"
    done | sort
}

# Generate VSCode terminal environment section
# Usage: generate_vscode_env
generate_vscode_env() {
    echo '"terminal.integrated.env.linux": {'
    for service in "${!SERVICE_PORTS[@]}"; do
        echo "  \"${service}_URL\": \"$(get_service_url "$service")\","
    done | sort | sed '$ s/,$//'
    echo '}'
}

# Check if a service port is available
# Usage: check_service_port SERVICE_NAME
# Returns: 0 if port is available, 1 if in use
check_service_port() {
    local service="$1"
    local port=$(get_service_port "$service")

    if command -v nc >/dev/null 2>&1; then
        nc -z localhost "$port" 2>/dev/null && return 1 || return 0
    elif command -v ss >/dev/null 2>&1; then
        ss -ltn | grep -q ":${port} " && return 1 || return 0
    else
        echo "WARNING: Cannot check port availability (nc or ss not found)" >&2
        return 0
    fi
}

# Validate all service configurations
# Usage: validate_services
validate_services() {
    local errors=0

    echo "Validating service registry..."

    for service in "${!SERVICE_PORTS[@]}"; do
        local port="${SERVICE_PORTS[$service]}"

        # Check port is numeric
        if ! [[ "$port" =~ ^[0-9]+$ ]]; then
            echo "ERROR: Invalid port for $service: $port (not numeric)" >&2
            ((errors++))
        fi

        # Check port range (1-65535)
        if (( port < 1 || port > 65535 )); then
            echo "ERROR: Invalid port for $service: $port (out of range 1-65535)" >&2
            ((errors++))
        fi
    done

    if (( errors > 0 )); then
        echo "Validation failed with $errors error(s)" >&2
        return 1
    else
        echo "✓ All services validated successfully"
        return 0
    fi
}

# If sourced interactively, export URLs automatically
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being executed directly
    case "${1:-}" in
        list)
            list_services
            ;;
        validate)
            validate_services
            ;;
        vscode-env)
            generate_vscode_env
            ;;
        check)
            if [[ -n "${2:-}" ]]; then
                if check_service_port "$2"; then
                    echo "✓ Port for $2 is available"
                else
                    echo "✗ Port for $2 is in use"
                fi
            else
                echo "Usage: $0 check SERVICE_NAME"
                exit 1
            fi
            ;;
        url)
            if [[ -n "${2:-}" ]]; then
                get_service_url "$2"
            else
                echo "Usage: $0 url SERVICE_NAME"
                exit 1
            fi
            ;;
        port)
            if [[ -n "${2:-}" ]]; then
                get_service_port "$2"
            else
                echo "Usage: $0 port SERVICE_NAME"
                exit 1
            fi
            ;;
        *)
            echo "Service Registry - NixOS-Dev-Quick-Deploy AI Stack"
            echo ""
            echo "Usage: $0 <command> [args]"
            echo ""
            echo "Commands:"
            echo "  list              List all registered services"
            echo "  validate          Validate service configurations"
            echo "  vscode-env        Generate VSCode terminal environment JSON"
            echo "  check SERVICE     Check if service port is available"
            echo "  url SERVICE       Get service URL"
            echo "  port SERVICE      Get service port"
            echo ""
            echo "Or source this file to use functions in scripts:"
            echo "  source lib/service-registry.sh"
            echo "  export_service_urls"
            ;;
    esac
fi
