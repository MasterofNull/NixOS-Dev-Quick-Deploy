#!/usr/bin/env bash
#
# Validate AI stack env drift between .env and compose defaults
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${AI_STACK_ENV_FILE:-$HOME/.config/nixos-ai-stack/.env}"
COMPOSE_FILE="${SCRIPT_DIR}/ai-stack/compose/docker-compose.yml"
TEMPLATE_ENV="${SCRIPT_DIR}/templates/local-ai-stack/.env.example"

error() { echo "[ERROR] $*" >&2; }
info() { echo "[INFO] $*"; }

if [[ ! -f "$ENV_FILE" ]]; then
    error "Missing env file: $ENV_FILE"
    exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
    error "Missing compose file: $COMPOSE_FILE"
    exit 1
fi

required_keys=(
    "AI_STACK_DATA"
    "POSTGRES_DB"
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "GRAFANA_ADMIN_USER"
    "GRAFANA_ADMIN_PASSWORD"
    "LLAMA_CPP_DEFAULT_MODEL"
    "LLAMA_CPP_MODEL_FILE"
    "EMBEDDING_MODEL"
)

compose_has_default() {
    local key="$1"
    grep -qE "\\$\\{${key}:-[^}]+\\}" "$COMPOSE_FILE"
}

env_has_key() {
    local key="$1"
    grep -qE "^${key}=" "$ENV_FILE"
}

secret_exists() {
    local name="$1"
    local secrets_dir="${SCRIPT_DIR}/ai-stack/compose/secrets"
    [[ -f "${secrets_dir}/${name}" ]]
}

missing=()
for key in "${required_keys[@]}"; do
    if env_has_key "$key"; then
        continue
    fi

    case "$key" in
        POSTGRES_DB|POSTGRES_USER)
            if compose_has_default "$key"; then
                continue
            fi
            ;;
        POSTGRES_PASSWORD)
            if env_has_key "POSTGRES_PASSWORD_FILE" || secret_exists "postgres_password"; then
                continue
            fi
            ;;
        GRAFANA_ADMIN_PASSWORD)
            if env_has_key "GRAFANA_ADMIN_PASSWORD_FILE" || secret_exists "grafana_admin_password"; then
                continue
            fi
            ;;
        *)
            ;;
    esac

    missing+=("$key")
done

if (( ${#missing[@]} > 0 )); then
    error "Missing required keys in $ENV_FILE: ${missing[*]}"
    exit 1
fi

if grep -qE "EMBEDDING_MODEL: [^$]" "$COMPOSE_FILE"; then
    error "Compose file still hardcodes EMBEDDING_MODEL; expected env interpolation."
    exit 1
fi

if [[ -f "$TEMPLATE_ENV" ]]; then
    if ! grep -qE "^EMBEDDING_MODEL=" "$TEMPLATE_ENV"; then
        error "Template env missing EMBEDDING_MODEL: $TEMPLATE_ENV"
        exit 1
    fi
fi

info "AI stack env drift check: OK"
