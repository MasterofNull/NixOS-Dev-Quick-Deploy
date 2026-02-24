#!/usr/bin/env bash
set -euo pipefail

echo "scripts/install-lemonade-gui.sh is deprecated." >&2
echo "Imperative npm/electron app setup is not allowed in declarative mode." >&2
echo "Package Lemonade declaratively in flake modules before enabling it." >&2
exit 2
