#!/usr/bin/env bash
#
# Podman AI Stack Helper Script
# Simplified wrapper for the canonical hybrid-ai-stack.sh helper.
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<USAGE >&2
Usage: $(basename "$0") <command>

Commands:
  up         Start all containers
  down       Stop all containers
  restart    Restart all containers
  status     Show container status + health
  logs       Show logs (add service name for specific service)
  ps         List containers
USAGE
}

cmd="${1:-}"
shift || true

if [[ -z "$cmd" ]]; then
    usage
    exit 1
fi

echo "ℹ podman-ai-stack now delegates to hybrid-ai-stack.sh for a single workflow."

case "$cmd" in
    up|down|restart|status|logs|ps)
        exec "${SCRIPT_DIR}/hybrid-ai-stack.sh" "$cmd" "$@"
        ;;
    *)
        usage
        exit 1
        ;;
esac
