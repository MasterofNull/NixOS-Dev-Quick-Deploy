#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "scripts/deploy-clean.sh is deprecated; use ./nixos-quick-deploy.sh" >&2
exec "${REPO_ROOT}/nixos-quick-deploy.sh" "$@"
