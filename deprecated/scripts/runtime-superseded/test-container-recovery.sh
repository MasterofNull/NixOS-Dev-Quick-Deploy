#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=${NAMESPACE:-ai-stack}
SERVICE_LABEL=${SERVICE_LABEL:-io.kompose.service=hybrid-coordinator}
TIMEOUT_SECONDS=${TIMEOUT_SECONDS:-300}
KUBECTL_TIMEOUT="${KUBECTL_TIMEOUT:-60}"

log() {
  printf "[%s] %s\n" "$(date +"%Y-%m-%d %H:%M:%S")" "$*"
}

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not found" >&2
  exit 1
fi

current_pod=$(kubectl --request-timeout="${KUBECTL_TIMEOUT}s" get pods -n "$NAMESPACE" -l "$SERVICE_LABEL" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [[ -z "$current_pod" ]]; then
  echo "No pods found for label '$SERVICE_LABEL' in namespace '$NAMESPACE'" >&2
  exit 1
fi

log "Selected pod: $current_pod"
log "Deleting pod to trigger recovery..."
kubectl --request-timeout="${KUBECTL_TIMEOUT}s" delete pod -n "$NAMESPACE" "$current_pod" --wait=true

log "Waiting for replacement pod to become Ready..."
kubectl --request-timeout="${KUBECTL_TIMEOUT}s" wait -n "$NAMESPACE" --for=condition=Ready pod -l "$SERVICE_LABEL" --timeout="${TIMEOUT_SECONDS}s"

new_pod=$(kubectl --request-timeout="${KUBECTL_TIMEOUT}s" get pods -n "$NAMESPACE" -l "$SERVICE_LABEL" -o jsonpath='{.items[0].metadata.name}')
log "Replacement pod Ready: $new_pod"

if [[ "$new_pod" == "$current_pod" ]]; then
  echo "Recovery validation failed: pod name did not change" >&2
  exit 1
fi

log "Container recovery test PASSED"
