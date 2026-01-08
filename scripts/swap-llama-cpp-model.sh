#!/usr/bin/env bash
#
# Swap llama.cpp GGUF model (updates .env + restarts service)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${SCRIPT_DIR}/ai-stack/compose"
ENV_FILE="${AI_STACK_ENV_FILE:-$HOME/.config/nixos-ai-stack/.env}"
MODEL_DIR="${AI_STACK_DATA:-$HOME/.local/share/nixos-ai-stack}/llama-cpp-models"

usage() {
    echo "Usage: $(basename "$0") <gguf-file>"
    echo "Example: $(basename "$0") qwen2.5-coder-7b-instruct-q4_k_m.gguf"
}

if [[ "${1:-}" == "" ]]; then
    usage
    exit 1
fi

model_file="$1"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: Missing env file: $ENV_FILE" >&2
    exit 1
fi

if [[ ! -f "${MODEL_DIR}/${model_file}" ]]; then
    echo "ERROR: Model not found: ${MODEL_DIR}/${model_file}" >&2
    echo "Run: ${SCRIPT_DIR}/scripts/download-llama-cpp-models.sh --list" >&2
    exit 1
fi

if grep -q "^LLAMA_CPP_MODEL_FILE=" "$ENV_FILE"; then
    sed -i "s|^LLAMA_CPP_MODEL_FILE=.*|LLAMA_CPP_MODEL_FILE=${model_file}|" "$ENV_FILE"
else
    printf 'LLAMA_CPP_MODEL_FILE=%s\n' "$model_file" >> "$ENV_FILE"
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

(cd "$COMPOSE_DIR" && $compose_cmd up -d --force-recreate llama-cpp)

echo "Switched llama.cpp to: ${model_file}"
