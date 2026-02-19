#!/usr/bin/env bash
set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${KUBECONFIG:-}" && -f /etc/rancher/k3s/k3s.yaml ]]; then
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
fi

if ! command -v kubectl >/dev/null 2>&1; then
    echo "[ERROR] kubectl is required for K3s-first runtime but was not found." >&2
    exit 1
fi

if ! kubectl --request-timeout=30s cluster-info >/dev/null 2>&1; then
    echo "[ERROR] Kubernetes API is not reachable." >&2
    echo "[ERROR] Ensure k3s is running and KUBECONFIG points to /etc/rancher/k3s/k3s.yaml." >&2
    exit 1
fi

echo "[INFO] Kubernetes API reachable; ensuring dashboard user services are installed and started."

if ! systemctl --user list-unit-files | grep -q '^dashboard-server\.service'; then
    echo "[INFO] Dashboard units missing; running setup-dashboard.sh"
    "${SCRIPT_ROOT}/scripts/setup-dashboard.sh"
fi

systemctl --user daemon-reload >/dev/null 2>&1 || true
if ! systemctl --user start dashboard-collector.timer dashboard-server.service dashboard-api-proxy.service >/dev/null 2>&1; then
    echo "[ERROR] Dashboard services failed to start." >&2
    systemctl --user status dashboard-server.service dashboard-api-proxy.service --no-pager -l || true
    exit 1
fi

echo "[INFO] Dashboard services started successfully."
