#!/usr/bin/env bash
#
# Swap embeddings model (updates .env + restarts service)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${SCRIPT_DIR}/ai-stack/compose"
ENV_FILE="${AI_STACK_ENV_FILE:-$HOME/.config/nixos-ai-stack/.env}"

usage() {
    echo "Usage: $(basename "$0") <embedding-model-id>"
    echo "Example: $(basename "$0") sentence-transformers/all-MiniLM-L6-v2"
}

if [[ "${1:-}" == "" ]]; then
    usage
    exit 1
fi

model_id="$1"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: Missing env file: $ENV_FILE" >&2
    exit 1
fi

if grep -q "^EMBEDDING_MODEL=" "$ENV_FILE"; then
    sed -i "s|^EMBEDDING_MODEL=.*|EMBEDDING_MODEL=${model_id}|" "$ENV_FILE"
else
    printf 'EMBEDDING_MODEL=%s\n' "$model_id" >> "$ENV_FILE"
fi

export AI_STACK_ENV_FILE="$ENV_FILE"

compose_cmd=""
if command -v podman-compose >/dev/null 2>&1; then
    compose_cmd="podman-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    compose_cmd="docker compose"
else
    echo "ERROR: podman-compose or docker compose required" >&2
    exit 1
fi

(cd "$COMPOSE_DIR" && $compose_cmd up -d --force-recreate embeddings)

echo "Switched embeddings model to: ${model_id}"
