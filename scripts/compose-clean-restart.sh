#!/usr/bin/env bash
#
# compose-clean-restart.sh
# Clean restart for AI stack services to avoid Podman container name conflicts.
#

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_ROOT/ai-stack/compose/docker-compose.yml}"
SERVICES=("$@")

log() {
    printf '%s\n' "$*"
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
    return 1
}

container_name_for_service() {
    local service="$1"
    case "$service" in
        open-webui) echo "local-ai-open-webui" ;;
        *) echo "local-ai-${service}" ;;
    esac
}

compose_cmd="$(find_compose_cmd || true)"
if [[ -z "${compose_cmd:-}" ]]; then
    log "[ERROR] Neither 'docker compose' nor 'podman-compose' found in PATH."
    exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
    log "[ERROR] Compose file not found at: $COMPOSE_FILE"
    exit 1
fi

if [[ "$compose_cmd" == "podman-compose" ]]; then
    if [[ ${#SERVICES[@]} -eq 0 ]]; then
        log "[INFO] Clean restart: full stack (podman-compose down/up)."
        podman-compose -f "$COMPOSE_FILE" down --remove-orphans || true
        podman-compose -f "$COMPOSE_FILE" up -d --build
        exit 0
    fi

    log "[INFO] Clean restart: services ${SERVICES[*]} (podman-compose)."
    # Ensure dependency containers exist before starting dependent services.
    for service in "${SERVICES[@]}"; do
        case "$service" in
            llama-cpp)
                # llama-cpp is a core service, start it without deps
                ;;
            aidb|open-webui|hybrid-coordinator|ralph-wiggum)
                # These need core infrastructure services
                podman-compose -f "$COMPOSE_FILE" up -d qdrant postgres redis >/dev/null 2>&1 || true
                ;;
            aider|autogpt)
                # Optional agent services - no dependencies needed (use host network)
                ;;
        esac
    done
    # Remove old containers that might have conflicts
    for service in "${SERVICES[@]}"; do
        name="$(container_name_for_service "$service")"
        if podman ps -a --format '{{.Names}}' | grep -q "^${name}\$"; then
            log "[INFO] Removing old container: $name"
            podman rm -f "$name" >/dev/null 2>&1 || true
        fi
    done
    # Remove problematic autogpt image if starting autogpt
    if [[ " ${SERVICES[*]} " =~ " autogpt " ]]; then
        log "[INFO] Removing problematic autogpt image layers..."
        podman rmi -f $(podman images | grep -i auto-gpt | awk '{print $3}') 2>/dev/null || true
    fi
    podman-compose -f "$COMPOSE_FILE" up -d --build --no-deps "${SERVICES[@]}"
    exit 0
fi

if [[ ${#SERVICES[@]} -eq 0 ]]; then
    log "[INFO] Clean restart: full stack (docker compose down/up)."
    $compose_cmd -f "$COMPOSE_FILE" down --remove-orphans || true
    $compose_cmd -f "$COMPOSE_FILE" up -d --build --remove-orphans
    exit 0
fi

log "[INFO] Clean restart: services ${SERVICES[*]} (docker compose)."
$compose_cmd -f "$COMPOSE_FILE" up -d --build --force-recreate --no-deps "${SERVICES[@]}"
