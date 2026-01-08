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

missing=()
for key in "${required_keys[@]}"; do
    if ! grep -qE "^${key}=" "$ENV_FILE"; then
        missing+=("$key")
    fi
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
