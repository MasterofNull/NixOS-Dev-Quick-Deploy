#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v kubectl >/dev/null 2>&1 && [[ -f /etc/rancher/k3s/k3s.yaml ]]; then
    echo "[INFO] K3s detected; starting dashboard services only."
    systemctl --user start dashboard-collector.timer dashboard-server.service dashboard-api-proxy.service >/dev/null 2>&1 || \
        echo "[WARN] Dashboard services failed to start automatically. Run systemctl --user status dashboard-server."
    exit 0
fi

echo "[DEPRECATED] Legacy container runtime startup is disabled (K3s-first architecture)." >&2
echo "Use Kubernetes commands from DEPLOYMENT.md instead." >&2
echo "Dashboard can be started with: ${SCRIPT_DIR}/launch-dashboard.sh" >&2
exit 0
