#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${KUBECONFIG:-}" && -f /etc/rancher/k3s/k3s.yaml ]]; then
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
fi

# K3s-first architecture: if kubectl exists, we treat Kubernetes as the runtime
# source of truth and only start local dashboard services.
if command -v kubectl >/dev/null 2>&1; then
    echo "[INFO] Kubernetes tooling detected; starting dashboard services only."
    systemctl --user start dashboard-collector.timer dashboard-server.service dashboard-api-proxy.service >/dev/null 2>&1 || \
        echo "[WARN] Dashboard services failed to start automatically. Run systemctl --user status dashboard-server."
    exit 0
fi

echo "[INFO] Container runtime bootstrap is not used in K3s-first mode." >&2
echo "Install kubectl/k3s access and use Kubernetes commands from DEPLOYMENT.md instead." >&2
echo "Dashboard can be started with: ${SCRIPT_DIR}/launch-dashboard.sh" >&2
exit 0
