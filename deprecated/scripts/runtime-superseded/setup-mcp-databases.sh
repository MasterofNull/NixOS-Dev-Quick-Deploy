#!/usr/bin/env bash
#
# Deprecated: MCP databases are now declared in NixOS modules.
# Use nixos-rebuild to converge services, then validate with scripts/mcp-db-setup.

set -euo pipefail

echo "setup-mcp-databases.sh is deprecated."
echo "MCP PostgreSQL/Redis are managed declaratively via:"
echo "  - nix/modules/services/mcp-servers.nix"
echo "  - mySystem.mcpServers.postgres.*"
echo "  - mySystem.mcpServers.redis.*"
echo
echo "Next steps:"
echo "  1) sudo nixos-rebuild switch --flake .#\${HOSTNAME:-nixos}"
echo "  2) ./scripts/mcp-db-setup"
