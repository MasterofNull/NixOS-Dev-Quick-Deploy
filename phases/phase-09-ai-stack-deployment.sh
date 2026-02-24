#!/usr/bin/env bash
set -euo pipefail

echo "phases/phase-09-ai-stack-deployment.sh is deprecated." >&2
echo "AI stack deployment is declarative via NixOS modules + systemd targets." >&2
return 2 2>/dev/null || exit 2
