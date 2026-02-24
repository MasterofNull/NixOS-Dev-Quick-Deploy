#!/usr/bin/env bash
set -euo pipefail

echo "scripts/sync-npm-ai-tools.sh is deprecated." >&2
echo "Global npm package installs are not allowed in declarative mode." >&2
echo "Declare required tools in NixOS/Home Manager modules instead." >&2
exit 2
