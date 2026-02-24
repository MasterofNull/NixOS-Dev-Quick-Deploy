#!/usr/bin/env bash
set -euo pipefail

echo "scripts/setup-dashboard.sh is deprecated." >&2
echo "Dashboard setup is declarative in NixOS modules." >&2
echo "Use: sudo nixos-rebuild switch --flake .#${HOSTNAME:-nixos}" >&2
exit 2
