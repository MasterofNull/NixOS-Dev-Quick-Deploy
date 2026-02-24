#!/usr/bin/env bash
set -euo pipefail

echo "scripts/ai-model-setup.sh is deprecated." >&2
echo "Model lifecycle is declared in NixOS (llama-cpp-model-fetch service with pinned SHA256)." >&2
echo "Use: sudo nixos-rebuild switch --flake .#${HOSTNAME:-nixos}" >&2
exit 2
