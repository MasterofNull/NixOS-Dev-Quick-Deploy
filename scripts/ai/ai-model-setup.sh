#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL_MANAGER="${REPO_ROOT}/scripts/ai/ai-model-manager.sh"
UPDATE_TOOL="${REPO_ROOT}/scripts/ai/update-llama-cpp.sh"

usage() {
  cat <<'EOF'
scripts/ai/ai-model-setup.sh

Legacy compatibility shim over current declarative model tooling.

Usage:
  scripts/ai/ai-model-setup.sh [status]
  scripts/ai/ai-model-setup.sh check
  scripts/ai/ai-model-setup.sh update
  scripts/ai/ai-model-setup.sh switch
  scripts/ai/ai-model-setup.sh --help

Commands:
  status  Show current model/runtime status through ai-model-manager.sh.
  check   Run the supported llama.cpp update availability check.
  update  Run the supported llama.cpp/model update workflow.
  switch  Print the declarative NixOS apply command for pinned model changes.
EOF
}

cmd="${1:-status}"

case "$cmd" in
  -h|--help|help)
    usage
    ;;
  status)
    exec "$MODEL_MANAGER" status
    ;;
  check)
    exec "$MODEL_MANAGER" check-update
    ;;
  update)
    exec "$UPDATE_TOOL"
    ;;
  switch)
    echo "Model lifecycle is declarative. Apply pinned model changes with:"
    echo "  sudo nixos-rebuild switch --flake .#${HOSTNAME:-nixos}"
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
