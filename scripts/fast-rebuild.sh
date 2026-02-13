#!/usr/bin/env bash
# Fast redeploy script for the AI stack (Kubernetes)
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Apply manifests and restart deployments quickly

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
K8S_DIR="${AI_STACK_K8S_DIR:-$PROJECT_ROOT/ai-stack/kubernetes}"
NAMESPACE="${AI_STACK_NAMESPACE:-ai-stack}"

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
error() { echo "✗ $*"; }

if ! command -v kubectl >/dev/null 2>&1; then
  error "kubectl not found. K3s/Kubernetes is required."
  exit 1
fi

info "Applying manifests from: $K8S_DIR"
kubectl --request-timeout=60s apply -k "$K8S_DIR"

info "Rolling out restarts for deployments..."
kubectl --request-timeout=60s rollout restart deploy -n "$NAMESPACE" --all

success "Redeploy complete"
info "Check status:"
echo "  kubectl get pods -n $NAMESPACE"
