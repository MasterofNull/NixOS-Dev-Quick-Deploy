#!/usr/bin/env bash
set -euo pipefail

REGISTRY_NAME="${REGISTRY_NAME:-local-registry}"
REGISTRY_PORT="${REGISTRY_PORT:-5000}"
REGISTRY_NAMESPACE="${REGISTRY_NAMESPACE:-ai-stack}"
REGISTRY_MANIFEST="${REGISTRY_MANIFEST:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/ai-stack/kubernetes/registry/registry.yaml}"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/${TMP_FALLBACK:-tmp}}}"
PORT_FORWARD_PID_FILE="${PORT_FORWARD_PID_FILE:-${RUNTIME_DIR}/local-registry-portforward.pid}"
KUBECTL_TIMEOUT="${KUBECTL_TIMEOUT:-60}"
KUBECONFIG="${KUBECONFIG:-}"

if [[ -z "$KUBECONFIG" && -f "/etc/rancher/k3s/k3s.yaml" ]]; then
  KUBECONFIG="/etc/rancher/k3s/k3s.yaml"
fi

usage() {
  cat <<USAGE
Usage: $0 <start|stop|status>

Env overrides:
  REGISTRY_NAME (default: local-registry)
  REGISTRY_PORT (default: 5000)
  REGISTRY_NAMESPACE (default: ai-stack)
  REGISTRY_MANIFEST (default: ai-stack/kubernetes/registry/registry.yaml)
  PORT_FORWARD_PID_FILE (default: ${XDG_RUNTIME_DIR:-${TMPDIR:-/${TMP_FALLBACK:-tmp}}}/local-registry-portforward.pid)
USAGE
}

cmd="${1:-}"
if [[ -z "$cmd" ]]; then
  usage
  exit 1
fi

case "$cmd" in
  start)
    if [[ ! -f "$REGISTRY_MANIFEST" ]]; then
      echo "[ERROR] Registry manifest not found: $REGISTRY_MANIFEST" >&2
      exit 1
    fi
    echo "[INFO] Applying registry manifest"
    KUBECONFIG="$KUBECONFIG" kubectl --request-timeout="${KUBECTL_TIMEOUT}s" apply --validate=false -f "$REGISTRY_MANIFEST" >/dev/null
    echo "[INFO] Starting port-forward on localhost:${REGISTRY_PORT}"
    KUBECONFIG="$KUBECONFIG" kubectl --request-timeout="${KUBECTL_TIMEOUT}s" -n "$REGISTRY_NAMESPACE" port-forward "svc/${REGISTRY_NAME}" "${REGISTRY_PORT}:5000" >/dev/null 2>&1 &
    echo $! > "$PORT_FORWARD_PID_FILE"
    echo "[OK] Registry available on localhost:${REGISTRY_PORT}"
    ;;
  stop)
    if [[ -f "$PORT_FORWARD_PID_FILE" ]]; then
      kill "$(cat "$PORT_FORWARD_PID_FILE")" >/dev/null 2>&1 || true
      rm -f "$PORT_FORWARD_PID_FILE"
    fi
    KUBECONFIG="$KUBECONFIG" kubectl --request-timeout="${KUBECTL_TIMEOUT}s" delete -f "$REGISTRY_MANIFEST" >/dev/null 2>&1 || true
    echo "[OK] Registry stopped"
    ;;
  status)
    KUBECONFIG="$KUBECONFIG" kubectl --request-timeout="${KUBECTL_TIMEOUT}s" -n "$REGISTRY_NAMESPACE" get deploy,svc -l app="${REGISTRY_NAME}"
    if [[ -f "$PORT_FORWARD_PID_FILE" ]]; then
      echo "[INFO] Port-forward PID: $(cat "$PORT_FORWARD_PID_FILE")"
    fi
    ;;
  *)
    usage
    exit 1
    ;;
esac
