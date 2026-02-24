#!/usr/bin/env bash
set -euo pipefail

echo "ERROR: scripts/start-ai-stack-and-dashboard.sh is deprecated." >&2
echo "AI stack orchestration is declarative and managed by systemd + NixOS modules." >&2
echo "Use: sudo systemctl start ai-stack.target" >&2
echo "Use: sudo systemctl status ai-stack.target" >&2
exit 2
