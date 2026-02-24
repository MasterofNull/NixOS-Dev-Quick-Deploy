#!/usr/bin/env bash
set -euo pipefail

echo "scripts/setup-mcp-databases.sh is deprecated." >&2
echo "PostgreSQL/Redis are declared in NixOS modules and converge via nixos-rebuild." >&2
echo "Use: sudo nixos-rebuild switch --flake .#${HOSTNAME:-nixos}" >&2
exit 2
