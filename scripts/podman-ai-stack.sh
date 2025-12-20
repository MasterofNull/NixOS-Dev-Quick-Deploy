#!/usr/bin/env bash
#
# Podman AI Stack Helper Script
# Simplified management for NixOS Hybrid Learning AI Stack
#
# Usage:
#   ./scripts/podman-ai-stack.sh up      # Start all containers
#   ./scripts/podman-ai-stack.sh down    # Stop all containers
#   ./scripts/podman-ai-stack.sh restart # Restart all containers
#   ./scripts/podman-ai-stack.sh status  # Show container status
#   ./scripts/podman-ai-stack.sh logs    # Show logs from all containers
#   ./scripts/podman-ai-stack.sh ps      # List containers
#   ./scripts/podman-ai-stack.sh clean   # Stop and remove containers

set -euo pipefail

SCRIPT_NAME=$(basename "$0")
NETWORK_DEFAULT="local-ai"
DATA_ROOT_DEFAULT="$HOME/.local/share/podman-ai-stack"
LABEL_KEY_DEFAULT="nixos.quick-deploy.ai-stack"
LABEL_VALUE_DEFAULT="true"
PREFERENCE_DIRS=(
  "$HOME/.cache/nixos-quick-deploy/preferences"
  "$HOME/.config/nixos-quick-deploy"
)

error() {
    echo "${SCRIPT_NAME}: $*" >&2
}

warn() {
    echo "${SCRIPT_NAME}: $*" >&2
}

usage() {
    cat <<USAGE >&2
Usage: ${SCRIPT_NAME} <command>

Commands:
  up         Create/start the Podman network and all containers
  down       Stop every managed service (keeps volumes intact)
  restart    Shortcut for down + up
  status     Show systemd status plus managed podman containers
  logs       Tail journald logs for all managed units (args passed through)
USAGE
}

require_prereqs() {
    if ! command -v podman >/dev/null 2>&1; then
        error "podman CLI is required"
        exit 127
    fi

    if ! systemctl --user --help >/dev/null 2>&1; then
        error "systemd --user is unavailable; log into a graphical session or enable linger"
        exit 1
    fi
}

read_pref_var() {
    local file_stem="$1"
    local var_name="$2"
    local file
    for dir in "${PREFERENCE_DIRS[@]}"; do
        file="$dir/${file_stem}.env"
        if [[ -r "$file" ]]; then
            awk -F'=' -v key="$var_name" '$1 == key {print $2}' "$file" 2>/dev/null | tail -n1 | tr -d '\r'
            return 0
        fi
    done
    return 1
}

resolve_llm_backend() {
    if [[ -n "${LLM_BACKEND:-}" ]]; then
        echo "$LLM_BACKEND"
        return
    fi

    local pref
    if pref=$(read_pref_var "llm-backend" "LLM_BACKEND" 2>/dev/null) && [[ -n "$pref" ]]; then
        echo "$pref"
        return
    fi

    echo "ollama"
}

resolve_network() {
    echo "${PODMAN_AI_STACK_NETWORK:-$NETWORK_DEFAULT}"
}

resolve_data_root() {
    echo "${PODMAN_AI_STACK_DATA_ROOT:-$DATA_ROOT_DEFAULT}"
}

resolve_label_key() {
    echo "${PODMAN_AI_STACK_LABEL_KEY:-$LABEL_KEY_DEFAULT}"
}

resolve_label_value() {
    echo "${PODMAN_AI_STACK_LABEL_VALUE:-$LABEL_VALUE_DEFAULT}"
}

unit_exists() {
    local unit="$1"
    systemctl --user show "$unit" >/dev/null 2>&1
}

ensure_directories() {
    local root="$1"
    mkdir -p \
        "$root/ollama" \
        "$root/lemonade-models" \
        "$root/open-webui" \
        "$root/qdrant" \
        "$root/mindsdb"
}

start_units() {
    local unit
    for unit in "$@"; do
        if unit_exists "$unit"; then
            systemctl --user start "$unit"
        else
            warn "unit ${unit} not found; run scripts/enable-podman-containers.sh and rebuild Home Manager"
        fi
    done
}

stop_units() {
    local unit
    for unit in "$@"; do
        if unit_exists "$unit"; then
            systemctl --user stop "$unit" || true
        else
            warn "unit ${unit} not found; nothing to stop"
        fi
    done
}

show_status() {
    local network_unit="$1"
    shift

    echo "-- systemd unit status --"
    local unit
    for unit in "$network_unit" "$@"; do
        if unit_exists "$unit"; then
            echo "[$unit]"
            systemctl --user --no-pager status "$unit" || true
            echo
        else
            echo "[$unit] missing (enable LOCAL_AI_STACK_ENABLED=true and rebuild)"
            echo
        fi
    done
}

show_podman_status() {
    local label_key="$1"
    local label_value="$2"
    echo "-- podman ps (running) --"
    podman ps --filter "label=${label_key}=${label_value}" \
        --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo
    echo "-- podman ps -a (all managed containers) --"
    podman ps -a --filter "label=${label_key}=${label_value}" \
        --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"
}

stream_logs() {
    local network_unit="$1"
    shift

    local units=("$network_unit")
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--" ]]; then
            shift
            break
        fi
        units+=("$1")
        shift
    done

    local extra_args=("$@")
    local args=()
    local unit
    for unit in "${units[@]}"; do
        if unit_exists "$unit"; then
            args+=("-u" "$unit")
        fi
    done

    if (( ${#args[@]} == 0 )); then
        error "no managed units found; ensure the stack is enabled"
        exit 1
    fi

    exec journalctl --user -f "${args[@]}" "${extra_args[@]}"
}

main() {
    require_prereqs

    local cmd="${1:-}"
    if [[ -z "$cmd" ]]; then
        usage
        exit 1
    fi
    shift || true

    local network
    network=$(resolve_network)
    local data_root
    data_root=$(resolve_data_root)
    local label_key
    label_key=$(resolve_label_key)
    local label_value
    label_value=$(resolve_label_value)
    local backend
    backend=$(resolve_llm_backend)

    local llm_container="${network}-ollama"
    if [[ "$backend" == "lemonade" ]]; then
        llm_container="${network}-lemonade"
    fi

    local containers=(
        "$llm_container"
        "${network}-open-webui"
        "${network}-qdrant"
        "${network}-mindsdb"
    )
    local container_units=()
    local name
    for name in "${containers[@]}"; do
        container_units+=("podman-${name}.service")
    done
    local network_unit="podman-${network}-network.service"

    case "$cmd" in
        up)
            ensure_directories "$data_root"
            start_units "$network_unit"
            start_units "${container_units[@]}"
            echo "${SCRIPT_NAME}: started services: ${containers[*]}"
            ;;
        down)
            stop_units "${container_units[@]}"
            stop_units "$network_unit"
            ;;
        restart)
            "$0" down
            "$0" up
            ;;
        status)
            show_status "$network_unit" "${container_units[@]}"
            show_podman_status "$label_key" "$label_value"
            ;;
        logs)
            stream_logs "$network_unit" "${container_units[@]}" -- "$@"
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
