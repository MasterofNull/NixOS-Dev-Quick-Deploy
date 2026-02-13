#!/usr/bin/env bash
#
# Validate AI stack env drift between .env and k8s defaults
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${AI_STACK_ENV_FILE:-$HOME/.config/nixos-ai-stack/.env}"
TEMPLATE_ENV="${SCRIPT_DIR}/templates/local-ai-stack/.env.example"
K8S_ENV_CONFIGMAP="${SCRIPT_DIR}/ai-stack/kubernetes/kompose/env-configmap.yaml"

error() { echo "[ERROR] $*" >&2; }
info() { echo "[INFO] $*"; }

if [[ ! -f "$ENV_FILE" ]]; then
    error "Missing env file: $ENV_FILE"
    exit 1
fi

if [[ ! -f "$K8S_ENV_CONFIGMAP" ]]; then
    error "Missing k8s env configmap; cannot validate drift."
    exit 1
fi
info "Using k8s env configmap for defaults."

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

configmap_has_key() {
    local key="$1"
    grep -qE "^[[:space:]]+${key}:[[:space:]]+.+$" "$K8S_ENV_CONFIGMAP"
}

env_has_key() {
    local key="$1"
    grep -qE "^${key}=" "$ENV_FILE"
}

secret_exists() {
    local name="$1"
    local k8s_secrets_file="${SCRIPT_DIR}/ai-stack/kubernetes/secrets/secrets.sops.yaml"
    [[ -f "$k8s_secrets_file" ]] && rg -q "^[[:space:]]+${name}:" "$k8s_secrets_file"
}

missing=()
for key in "${required_keys[@]}"; do
    if env_has_key "$key"; then
        continue
    fi

    case "$key" in
        POSTGRES_DB|POSTGRES_USER)
            if configmap_has_key "$key"; then
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

if ! grep -qE "^[[:space:]]+EMBEDDING_MODEL:[[:space:]]+.+$" "$K8S_ENV_CONFIGMAP"; then
    error "K8s env configmap missing EMBEDDING_MODEL."
    exit 1
fi

if [[ -f "$TEMPLATE_ENV" ]]; then
    if ! grep -qE "^EMBEDDING_MODEL=" "$TEMPLATE_ENV"; then
        error "Template env missing EMBEDDING_MODEL: $TEMPLATE_ENV"
        exit 1
    fi
fi

info "AI stack env drift check: OK"
