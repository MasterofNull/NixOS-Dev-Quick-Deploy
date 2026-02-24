#!/usr/bin/env bash
set -euo pipefail

# Renew TLS certificates via cert-manager (Kubernetes)
# Usage: ./scripts/renew-tls-certificate.sh [--namespace ai-stack] [--k8s-dir ai-stack/kubernetes/tls] [--force]

NAMESPACE="ai-stack"
K8S_DIR="ai-stack/kubernetes/tls"
FORCE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    --k8s-dir)
      K8S_DIR="$2"
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --help)
      echo "Usage: $0 [--namespace NAMESPACE] [--k8s-dir PATH] [--force]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl not found. K3s/Kubernetes is required." >&2
  exit 1
fi

if [[ ! -d "$K8S_DIR" ]]; then
  echo "TLS manifests not found: $K8S_DIR" >&2
  exit 1
fi

if [[ "$FORCE" == "true" ]]; then
  echo "Forcing certificate re-issuance..."
  kubectl --request-timeout=30s delete certificate -n "$NAMESPACE" --all || true
fi

echo "Applying TLS manifests from $K8S_DIR..."
kubectl --request-timeout=60s apply -k "$K8S_DIR"

echo "Current certificate status:"
kubectl --request-timeout=30s get certificate -n "$NAMESPACE" || true
