#!/usr/bin/env bash
#
# ai-stack-manage.sh
# Thin CLI wrapper to manage the local AI stack (AIDB + models)
# scaffolded by scripts/local-ai-starter.sh.
#

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_STACK_DIR="${LOCAL_STACK_DIR:-$HOME/Documents/local-ai-stack}"
REPO_STACK_DIR="${SCRIPT_DIR}/ai-stack/compose"
COMPOSE_FILE_NAME="docker-compose.yml"

print_usage() {
    cat <<EOF
Usage: $(basename "$0") {up|down|restart|clean-restart|status|logs|health|sync} [service]

Subcommands:
  up         Start the local AI stack (docker compose / podman-compose up -d)
  down       Stop the local AI stack (docker compose / podman-compose down)
  restart    Restart the stack (down then up)
  clean-restart
            Restart with container cleanup to avoid name conflicts (Podman)
  status     Show container status (compose ps)
  logs       Tail logs (all services or a single service if provided)
  health     Run AI stack health checks
  sync       Sync repo docs into AIDB (runs scripts/sync_docs_to_ai.sh)

Environment:
  LOCAL_STACK_DIR   Directory containing ${COMPOSE_FILE_NAME}
                    (default: \$HOME/Documents/local-ai-stack or ${REPO_STACK_DIR})
EOF
}

find_compose_cmd() {
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        echo "docker compose"
        return 0
    fi
    if command -v podman-compose >/dev/null 2>&1; then
        echo "podman-compose"
        return 0
    fi
    echo ""  # not found
}

ensure_stack_dir() {
    if [[ -d "$LOCAL_STACK_DIR" ]] && [[ -f "$LOCAL_STACK_DIR/$COMPOSE_FILE_NAME" ]]; then
        return 0
    fi

    if [[ -d "$REPO_STACK_DIR" ]] && [[ -f "$REPO_STACK_DIR/$COMPOSE_FILE_NAME" ]]; then
        LOCAL_STACK_DIR="$REPO_STACK_DIR"
        return 0
    fi

    echo "[ERROR] Local AI stack directory or ${COMPOSE_FILE_NAME} not found at:" >&2
    echo "        $LOCAL_STACK_DIR" >&2
    echo "" >&2
    echo "Run scripts/local-ai-starter.sh or set LOCAL_STACK_DIR to a valid stack directory." >&2
    exit 1
}

cmd_compose() {
    local compose_cmd
    compose_cmd=$(find_compose_cmd)
    if [[ -z "$compose_cmd" ]]; then
        echo "[ERROR] Neither 'docker compose' nor 'podman-compose' is available in PATH." >&2
        echo "Install Docker or Podman + podman-compose to manage the local AI stack." >&2
        exit 1
    fi

    (cd "$LOCAL_STACK_DIR" && $compose_cmd "$@")
}

subcmd_up() {
    ensure_stack_dir
    cmd_compose up -d --build
}

subcmd_down() {
    ensure_stack_dir
    cmd_compose down
}

subcmd_restart() {
    subcmd_down || true
    subcmd_up
}

subcmd_clean_restart() {
    local clean_script="$SCRIPT_DIR/scripts/compose-clean-restart.sh"
    if [[ ! -x "$clean_script" ]]; then
        echo "[ERROR] Clean restart script not found at: $clean_script" >&2
        exit 1
    fi
    "$clean_script" "$@"
}

subcmd_status() {
    ensure_stack_dir
    cmd_compose ps
}

subcmd_logs() {
    ensure_stack_dir
    local service="${1:-}"
    if [[ -n "$service" ]]; then
        cmd_compose logs -f "$service"
    else
        cmd_compose logs -f
    fi
}

subcmd_health() {
    local health_script="$SCRIPT_DIR/scripts/check-ai-stack-health-v2.py"
    if [[ ! -f "$health_script" ]]; then
        echo "[ERROR] Health check script not found at: $health_script" >&2
        exit 1
    fi
    if [[ -x "$health_script" ]]; then
        "$health_script"
    else
        python3 "$health_script"
    fi
}

subcmd_sync() {
    local sync_script="$SCRIPT_DIR/scripts/sync_docs_to_ai.sh"
    if [[ ! -x "$sync_script" ]]; then
        echo "[ERROR] Sync script not found or not executable at: $sync_script" >&2
        exit 1
    fi
    "$sync_script"
}

main() {
    local cmd="${1:-}"
    shift || true

    case "$cmd" in
        up)       subcmd_up ;;
        down)     subcmd_down ;;
        restart)  subcmd_restart ;;
        clean-restart) subcmd_clean_restart "$@" ;;
        status)   subcmd_status ;;
        logs)     subcmd_logs "$@" ;;
        health)   subcmd_health ;;
        sync)     subcmd_sync ;;
        -h|--help|"") print_usage ;;
        *)
            echo "[ERROR] Unknown subcommand: $cmd" >&2
            echo "" >&2
            print_usage
            exit 1
            ;;
    esac
}

main "$@"
