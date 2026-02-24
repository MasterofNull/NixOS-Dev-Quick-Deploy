#!/usr/bin/env bash
set -euo pipefail

echo "scripts/count-packages-simple.sh is deprecated." >&2
echo "Use declarative inventory from flake outputs and Nix evaluations." >&2
echo "Example: nix flake show" >&2
exit 2
