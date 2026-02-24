#!/usr/bin/env bash
set -euo pipefail

script_name="$(basename "$0")"

echo "ERROR: ${script_name} is deprecated." >&2
echo "This system now uses declarative secrets via sops-nix and /run/secrets." >&2
echo "Do not create or read ~/.config/nixos-ai-stack/.env for secrets." >&2
echo "Configure encrypted secrets in your SOPS file and rebuild NixOS." >&2
exit 2
