#!/usr/bin/env bash
# Clean restart of AI stack deployments (Kubernetes)
# Part of: NixOS-Dev-Quick-Deploy

set -euo pipefail

NAMESPACE="${AI_STACK_NAMESPACE:-ai-stack}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl not found. K3s/Kubernetes is required." >&2
  exit 1
fi

echo "==> Clean restart: scaling down deployments..."
kubectl --request-timeout=30s scale deploy -n "$NAMESPACE" --replicas=0 --all || true

echo "==> Clean restart: deleting pods..."
kubectl --request-timeout=30s delete pod -n "$NAMESPACE" --all || true

echo "==> Clean restart: scaling up deployments..."
kubectl --request-timeout=30s scale deploy -n "$NAMESPACE" --replicas=1 --all || true

echo "==> Clean restart complete"
