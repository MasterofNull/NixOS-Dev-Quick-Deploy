#!/usr/bin/env bash
# Deprecated governance helper retained for compatibility guidance.
set -euo pipefail

echo "scripts/count-packages-accurately.sh is deprecated." >&2
echo "Use declarative inventory from flake outputs and Nix evaluations." >&2
echo "Example: nix flake show" >&2
exit 2
