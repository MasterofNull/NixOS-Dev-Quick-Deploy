#!/usr/bin/env bash
#
# Local AI Starter Toolkit
# Helps new users scaffold local AI agents, OpenSkills, and MCP server templates
# without needing the private AI-Optimizer repository.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_STACK_DIR="${LOCAL_STACK_DIR:-$HOME/Documents/local-ai-stack}"
MCP_TEMPLATE_ROOT="${SCRIPT_DIR}/templates"
EDGE_MODEL_REGISTRY="${EDGE_MODEL_REGISTRY:-$SCRIPT_DIR/config/edge-model-registry.json}"
AI_PROFILE="${AI_PROFILE:-cpu_full}"
AI_STACK_PROFILE="${AI_STACK_PROFILE:-personal}"

if ! command -v ss >/dev/null 2>&1; then
    echo "[ERROR] ss command is required (from iproute2)." >&2
    exit 1
fi

info()    { printf '\033[0;34m[INFO]\033[0m %s\n' "$*"; }
success() { printf '\033[0;32m[ OK ]\033[0m %s\n' "$*"; }
warn()    { printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2; }
err()     { printf '\033[0;31m[ERR]\033[0m %s\n' "$*" >&2; }

ensure_hooks_loaded() {
    if [[ ! -f "${SCRIPT_DIR}/lib/ai-optimizer-hooks.sh" ]]; then
        err "lib/ai-optimizer-hooks.sh not found"
        exit 1
    fi
    # shellcheck source=/dev/null
    source "${SCRIPT_DIR}/lib/ai-optimizer-hooks.sh"
}

action_prepare_environment() {
    ensure_hooks_loaded
    info "Creating shared data directories..."
    prepare_shared_data_directories
    success "Shared directories ready at ${AI_OPTIMIZER_DATA_ROOT}"

    info "Current AI profile for this host: ${AI_PROFILE}"
    info "Current AI stack profile: ${AI_STACK_PROFILE} (personal, guest, or none)."

    info "Current AI profile for this host: ${AI_PROFILE}"
    if [[ -f "$EDGE_MODEL_REGISTRY" ]]; then
        info "Edge model registry detected at ${EDGE_MODEL_REGISTRY}"
        info "Use this file to declare which external Podman/Docker models should be available for AI_PROFILE=${AI_PROFILE}."
    else
        warn "Edge model registry not found at ${EDGE_MODEL_REGISTRY}; create it to track which external models your stacks host."
    fi

    if detect_port_conflicts; then
        success "No conflicting ports detected."
    else
        warn "Conflicts detected. Resolve them before launching containers."
    fi

    if check_docker_podman_ready; then
        success "Docker/Podman detected."
    else
        warn "Docker or Podman not found. Install one before continuing."
    fi

    if check_nvidia_container_toolkit; then
        success "NVIDIA container toolkit detected."
    else
        warn "NVIDIA container toolkit not detected (optional)."
    fi

    save_integration_status
    success "Environment preparation complete."
}

copy_local_stack_templates() {
    local data_root="$1"
    mkdir -p "$LOCAL_STACK_DIR"
    cp "${SCRIPT_DIR}/templates/local-ai-stack/docker-compose.yml" "$LOCAL_STACK_DIR/docker-compose.yml"
    if [[ -f "$LOCAL_STACK_DIR/.env" ]]; then
        warn ".env already exists in ${LOCAL_STACK_DIR}, leaving it untouched."
    else
        cp "${SCRIPT_DIR}/templates/local-ai-stack/.env.example" "$LOCAL_STACK_DIR/.env"
        sed -i "s|/home/your-user/.local/share/ai-stack|${data_root}|g" "$LOCAL_STACK_DIR/.env"
    fi

    mkdir -p "$LOCAL_STACK_DIR/mcp-servers"
    if [[ -d "${SCRIPT_DIR}/ai-stack/mcp-servers/aidb" ]]; then
        rm -rf "$LOCAL_STACK_DIR/mcp-servers/aidb"
        cp -R "${SCRIPT_DIR}/ai-stack/mcp-servers/aidb" "$LOCAL_STACK_DIR/mcp-servers/aidb"
    fi
    if [[ -d "${SCRIPT_DIR}/ai-stack/mcp-servers/config" ]]; then
        rm -rf "$LOCAL_STACK_DIR/mcp-servers/config"
        cp -R "${SCRIPT_DIR}/ai-stack/mcp-servers/config" "$LOCAL_STACK_DIR/mcp-servers/config"
    fi
}

start_local_stack() {
    local compose_cmd=""
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        compose_cmd="docker compose"
    elif command -v podman-compose >/dev/null 2>&1; then
        compose_cmd="podman-compose"
    fi

    if [[ -z "$compose_cmd" ]]; then
        warn "docker compose or podman-compose not available. Start the stack manually."
        return
    fi

    info "Starting local AI stack using ${compose_cmd}"
    (cd "$LOCAL_STACK_DIR" && $compose_cmd up -d)
    success "Containers launching in background."
}

action_scaffold_local_stack() {
    info "Scaffolding local AI stack at ${LOCAL_STACK_DIR}"
    local data_root="${AI_STACK_DATA:-$HOME/.local/share/ai-stack}"
    mkdir -p "${data_root}"/{postgres,redis,redisinsight,lemonade-models,aidb,aidb-cache,telemetry}
    copy_local_stack_templates "$data_root"

    info "AI_PROFILE=${AI_PROFILE} (override in environment to change edge AI behavior hints)."
    if [[ -f "$EDGE_MODEL_REGISTRY" ]]; then
        info "After your external containers are configured, update ${EDGE_MODEL_REGISTRY} so agents can discover which models are actually served for this profile."
    fi

    read -rp "Start the stack now? [Y/n]: " start_choice
    if [[ -z "$start_choice" || "$start_choice" =~ ^[Yy]$ ]]; then
        start_local_stack
    else
        info "Skipping automatic start. Run 'docker compose up -d' inside ${LOCAL_STACK_DIR} later."
    fi
    success "Local AI stack files ready."
}

action_install_openskills() {
    if ! command -v npm >/dev/null 2>&1; then
        err "npm is required to install OpenSkills."
        return
    fi

    info "Installing OpenSkills CLI (npm i -g openskills)..."
    npm install -g openskills >/dev/null
    success "OpenSkills CLI installed."

    read -rp "Directory to run 'openskills init' in [$SCRIPT_DIR]: " init_dir
    init_dir=${init_dir:-$SCRIPT_DIR}

    if [[ ! -d "$init_dir" ]]; then
        err "Directory not found: $init_dir"
        return
    fi

    info "Initializing OpenSkills in ${init_dir}"
    (cd "$init_dir" && openskills init >/dev/null)
    success "OpenSkills initialized."
}

scaffold_mcp_template() {
    local target_dir="$1"
    local language="$2"
    mkdir -p "$target_dir"

    case "$language" in
        ts|TS|deno)
            cp "${MCP_TEMPLATE_ROOT}/mcp-server-template.ts" "${target_dir}/server.ts"
            cat > "${target_dir}/README.md" <<EOF
# MCP Server (TypeScript / Deno)

## Quick Start
\`\`\`bash
deno run --allow-net --allow-env --allow-read --allow-write server.ts
\`\`\`

Configure DSNs via environment variables such as MCP_POSTGRES_DSN and MCP_REDIS_HOST.
EOF
            ;;
        py|python)
            cp "${MCP_TEMPLATE_ROOT}/mcp-server-template.py" "${target_dir}/server.py"
            cat > "${target_dir}/requirements.txt" <<'EOF'
sqlalchemy
asyncpg
redis
httpx
websockets
pydantic
EOF
            cat > "${target_dir}/README.md" <<EOF
# MCP Server (Python)

## Quick Start
\`\`\`bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
\`\`\`

Set MCP_POSTGRES_DSN, MCP_REDIS_URL, and MCP_QDRANT_URL to point at your local services.
EOF
            ;;
        *)
            err "Unsupported language option."
            return 1
            ;;
    esac
    success "MCP server template created at ${target_dir}"
}

action_scaffold_mcp() {
    read -rp "Target directory for MCP project [$HOME/Documents/mcp-sample]: " target
    target=${target:-$HOME/Documents/mcp-sample}
    read -rp "Template language (ts/py) [ts]: " lang
    lang=${lang:-ts}
    scaffold_mcp_template "$target" "$lang"
}

show_menu() {
    cat <<'EOF'

Local AI Starter Toolkit
=======================================
1) Prepare shared directories & prerequisites
2) Scaffold local AI stack (docker-compose)
3) Install OpenSkills CLI and init project
4) Scaffold MCP server template
5) Exit
EOF
}

main() {
    while true; do
        show_menu
        read -rp "Select an option: " choice
        case "$choice" in
            1) action_prepare_environment ;;
            2) action_scaffold_local_stack ;;
            3) action_install_openskills ;;
            4) action_scaffold_mcp ;;
            5|"") break ;;
            *) warn "Invalid choice: $choice" ;;
        esac
    done
}

main "$@"
