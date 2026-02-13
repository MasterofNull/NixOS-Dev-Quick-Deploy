#!/usr/bin/env bash
# AI-Optimizer Integration Hooks for NixOS-Dev-Quick-Deploy
# Version: 1.0.0
# Purpose: Prepare NixOS system for seamless AI-Optimizer installation
#
# This ensures the "hand" (NixOS) is ready to receive the "glove" (AI-Optimizer):
# - System prerequisites are met
# - No conflicts with AI-Optimizer services
# - Shared data directories prepared
# - Proper permissions and networking configured

# ============================================================================
# Configuration
# ============================================================================

# Shared persistent data paths (consistent with AI-Optimizer expectations)
AI_OPTIMIZER_DATA_ROOT="${AI_OPTIMIZER_DATA_ROOT:-$HOME/.local/share/ai-optimizer}"
AI_OPTIMIZER_CONFIG_ROOT="${AI_OPTIMIZER_CONFIG_ROOT:-$HOME/.config/ai-optimizer}"

# AI-Optimizer expected location
AI_OPTIMIZER_DIR="${AI_OPTIMIZER_DIR:-$HOME/Documents/AI-Optimizer}"

# Logical stack profile (personal, guest, none)
AI_STACK_PROFILE="${AI_STACK_PROFILE:-personal}"
KUBECTL_TIMEOUT="${KUBECTL_TIMEOUT:-60}"

# ============================================================================
# Prerequisite Checks
# ============================================================================

check_container_runtime_ready() {
    # Check if a container runtime is available — prefer K3s (kubectl)
    if command -v kubectl &> /dev/null && kubectl --request-timeout="${KUBECTL_TIMEOUT}s" cluster-info &>/dev/null; then
        return 0
    elif command -v docker &> /dev/null; then
        return 0
    elif command -v podman &> /dev/null; then
        return 0
    else
        return 1
    fi
}

check_nvidia_container_toolkit() {
    # Check if NVIDIA container toolkit is configured
    if command -v nvidia-container-cli &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# Shared Data Directory Preparation
# ============================================================================

prepare_shared_data_directories() {
    # Create shared persistent data directories
    # These persist across AI-Optimizer reinstalls
    mkdir -p "$AI_OPTIMIZER_DATA_ROOT"/{postgres,redis,qdrant,llama-cpp-models,imports,exports,backups}
    mkdir -p "$AI_OPTIMIZER_CONFIG_ROOT"

    # Set proper permissions
    chmod 700 "$AI_OPTIMIZER_DATA_ROOT"
    chmod 700 "$AI_OPTIMIZER_CONFIG_ROOT"

    # Create marker file
    cat > "$AI_OPTIMIZER_DATA_ROOT/README.txt" <<EOF
AI-Optimizer Shared Persistent Data Directory
==============================================

This directory contains persistent data for AI-Optimizer AIDB MCP Server.

Data persists across AI-Optimizer reinstalls and updates.

Contents:
  - postgres/     PostgreSQL database files
  - redis/        Redis persistence (AOF + RDB)
  - qdrant/       Qdrant vector database
  - llama-cpp-models/  Downloaded llama.cpp GGUF cache
  - imports/      Imported documents and catalogs
  - exports/      Exported data and reports
  - backups/      Database backups

Created by: NixOS-Dev-Quick-Deploy v$(cat ~/.cache/nixos-quick-deploy/state.json 2>/dev/null | jq -r '.version // "unknown"')
Date: $(date)

⚠️  Do not delete this directory unless you want to lose all AI-Optimizer data!
EOF

    return 0
}

# ============================================================================
# Port Conflict Detection
# ============================================================================

detect_port_conflicts() {
    # Check if AI-Optimizer required ports are available
    # This prevents conflicts with existing NixOS services

    local ports=(5432 6379 8080 8091 8791 5540)
    local conflicts=()

    for port in "${ports[@]}"; do
        if ss -tuln 2>/dev/null | grep -q ":$port "; then
            local process
            process=$(ss -tlnp 2>/dev/null | grep ":$port " | awk '{print $6}' | cut -d'"' -f2 || echo "unknown")
            conflicts+=("$port:$process")
        fi
    done

    if [ ${#conflicts[@]} -gt 0 ]; then
        echo "WARNING: Port conflicts detected:" >&2
        for conflict in "${conflicts[@]}"; do
            echo "  - Port ${conflict%:*} used by: ${conflict#*:}" >&2
        done
        return 1
    fi

    return 0
}

# ============================================================================
# Network Configuration
# ============================================================================

ensure_container_network_ready() {
    # Ensure container networking is properly configured
    # K3s: networking handled by flannel/CNI automatically
    # Docker/Podman: AI-Optimizer creates 'aidb-network' bridge

    if command -v kubectl &> /dev/null && kubectl --request-timeout="${KUBECTL_TIMEOUT}s" cluster-info &>/dev/null; then
        # K3s handles networking via flannel CNI
        return 0
    elif command -v docker &> /dev/null; then
        # Docker is available - nothing to do, AI-Optimizer will create network
        return 0
    elif command -v podman &> /dev/null; then
        # Podman - ensure CNI plugins are available
        if [ ! -d "/etc/cni/net.d" ]; then
            echo "WARNING: CNI network configuration directory missing" >&2
            return 1
        fi
        return 0
    fi

    return 1
}

# ============================================================================
# Integration Status
# ============================================================================

save_integration_status() {
    # Save status to NixOS-Dev cache for reference
    mkdir -p "$HOME/.cache/nixos-quick-deploy/integration"

    cat > "$HOME/.cache/nixos-quick-deploy/integration/ai-optimizer.json" <<EOF
{
  "prepared": true,
  "prepared_at": "$(date -Iseconds)",
  "data_root": "$AI_OPTIMIZER_DATA_ROOT",
  "config_root": "$AI_OPTIMIZER_CONFIG_ROOT",
  "expected_location": "$AI_OPTIMIZER_DIR",
   "stack_profile": "$AI_STACK_PROFILE",
  "k3s_available": $(command -v kubectl &> /dev/null && kubectl --request-timeout="${KUBECTL_TIMEOUT}s" cluster-info &>/dev/null && echo "true" || echo "false"),
  "docker_available": $(command -v docker &> /dev/null && echo "true" || echo "false"),
  "podman_available": $(command -v podman &> /dev/null && echo "true" || echo "false"),
  "nvidia_toolkit_available": $(command -v nvidia-container-cli &> /dev/null && echo "true" || echo "false"),
  "gpu_detected": $(command -v nvidia-smi &> /dev/null && echo "true" || echo "false")
}
EOF

    return 0
}

check_ai_optimizer_installed() {
    # Check if AI-Optimizer is already installed — K3s deployment
    if command -v kubectl &>/dev/null && kubectl --request-timeout="${KUBECTL_TIMEOUT}s" get deploy -n ai-stack aidb &>/dev/null 2>&1; then
        return 0
    fi
    return 1
}

get_ai_optimizer_status() {
    # Get current status of AI-Optimizer services
    if ! check_ai_optimizer_installed; then
        echo "not_installed"
        return 1
    fi

    # Check if services are running — K3s only
    if command -v kubectl &> /dev/null && kubectl --request-timeout="${KUBECTL_TIMEOUT}s" cluster-info &>/dev/null; then
        if kubectl --request-timeout="${KUBECTL_TIMEOUT}s" get deploy -n ai-stack aidb -o jsonpath='{.status.readyReplicas}' 2>/dev/null | grep -q '[1-9]'; then
            echo "running"
            return 0
        else
            echo "stopped"
            return 1
        fi
    fi

    echo "unknown"
    return 1
}

# ============================================================================
# User Notification
# ============================================================================

show_ai_optimizer_info() {
    local status
    status=$(get_ai_optimizer_status)

    case "$status" in
        not_installed)
            cat <<EOF

╭────────────────────────────────────────────────────────────────────────────╮
│ AI-Optimizer AIDB MCP Server - Not Installed                              │
╰────────────────────────────────────────────────────────────────────────────╯

NixOS system is ready for AI-Optimizer installation.

To install AI-Optimizer:
  1. Clone repository:
     git clone <your-repo-url> ~/Documents/AI-Optimizer

  2. Deploy stack:
     cd ~/Documents/AI-Optimizer
     kubectl --request-timeout="${KUBECTL_TIMEOUT}s" apply -k ai-stack/kubernetes/

Shared data directories prepared:
  • Data:   $AI_OPTIMIZER_DATA_ROOT
  • Config: $AI_OPTIMIZER_CONFIG_ROOT

EOF
            ;;
        running)
            cat <<EOF

╭────────────────────────────────────────────────────────────────────────────╮
│ AI-Optimizer AIDB MCP Server - Running                                    │
╰────────────────────────────────────────────────────────────────────────────╯

Services:
  • AIDB MCP Server:  http://localhost:8091
  • llama.cpp Inference: http://localhost:8080
  • PostgreSQL:       localhost:5432
  • Redis:            localhost:6379

Check status:
  curl http://localhost:8091/health | jq .

EOF
            ;;
        stopped)
            cat <<EOF

╭────────────────────────────────────────────────────────────────────────────╮
│ AI-Optimizer AIDB MCP Server - Installed but Stopped                      │
╰────────────────────────────────────────────────────────────────────────────╯

To start services (K3s):
  kubectl --request-timeout="${KUBECTL_TIMEOUT}s" apply -k ai-stack/kubernetes/
  kubectl --request-timeout="${KUBECTL_TIMEOUT}s" get pods -n ai-stack

EOF
            ;;
    esac

    return 0
}

# ============================================================================
# Export Functions
# ============================================================================

export -f check_container_runtime_ready
export -f check_nvidia_container_toolkit
export -f prepare_shared_data_directories
export -f detect_port_conflicts
export -f ensure_container_network_ready
export -f save_integration_status
export -f check_ai_optimizer_installed
export -f get_ai_optimizer_status
export -f show_ai_optimizer_info
