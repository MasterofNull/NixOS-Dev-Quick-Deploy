#!/usr/bin/env bash
# llama-model - GGUF Model Manager for llama.cpp
# Inspired by Docker Model Runner
# Version: 1.0.0 (December 2025)

set -euo pipefail

# Configuration
AI_STACK_DATA="${AI_STACK_DATA:-${HOME}/.local/share/nixos-ai-stack}"
MODEL_DIR="${AI_STACK_DATA}/llama-cpp-models"
CONTAINER_NAME="local-ai-llama-cpp"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ${NC} $*"; }
print_success() { echo -e "${GREEN}✓${NC} $*"; }
print_error() { echo -e "${RED}✗${NC} $*" >&2; }

# Show help
show_help() {
    cat <<EOF
llama-model - GGUF Model Manager (Docker Model Runner style)

USAGE:
    llama-model <COMMAND> [OPTIONS]

COMMANDS:
    pull <name>     Download GGUF model
    list            List cached models  
    logs [n]        View container logs (default: 50 lines)
    prune           Remove old models (30+ days)

EXAMPLES:
    llama-model pull qwen2.5-coder-7b-instruct-q4_k_m
    llama-model list
    llama-model logs 100
EOF
}

# Main
case "${1:-help}" in
    pull) print_info "Use existing ai-model-manager.sh for downloads" ;;
    list) ls -lh "$MODEL_DIR"/*.gguf 2>/dev/null || print_info "No models" ;;
    logs) podman logs --tail "${2:-50}" -f "$CONTAINER_NAME" ;;
    prune) find "$MODEL_DIR" -name "*.gguf" -atime +30 -exec rm -i {} \; ;;
    *) show_help ;;
esac
