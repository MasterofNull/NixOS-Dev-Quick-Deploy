#!/usr/bin/env bash
set -euo pipefail

echo "scripts/download-llama-cpp-models.sh is deprecated." >&2
echo "Imperative model downloads are disabled. Models must be declared and hash-pinned in Nix." >&2
exit 2
