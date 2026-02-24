#!/usr/bin/env bash
set -euo pipefail

echo "scripts/k8s-clean-restart.sh is deprecated." >&2
echo "Kubernetes/K3s runtime orchestration is removed from declarative path." >&2
echo "Use: sudo systemctl restart ai-stack.target" >&2
exit 2
