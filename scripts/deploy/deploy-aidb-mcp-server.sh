#!/usr/bin/env bash
# Deprecated: imperative MCP deployment is removed in flake-first mode.
# Use declarative NixOS modules instead.
set -euo pipefail

echo "deploy-aidb-mcp-server.sh is deprecated and disabled."
echo "MCP services are managed declaratively via:"
echo "  - nix/modules/services/mcp-servers.nix"
echo "  - nix/modules/roles/ai-stack.nix"
echo
echo "Apply with:"
echo "  sudo nixos-rebuild switch --flake .#\${HOSTNAME:-nixos}"
exit 2
