#!/usr/bin/env bash
# Scan recent logs for TLS/certificate warnings across critical AI stack services.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/timeout.sh
source "$PROJECT_ROOT/lib/timeout.sh"

NAMESPACE="${AI_STACK_NAMESPACE:-ai-stack}"
TAIL_LINES="${TAIL_LINES:-200}"

info() { echo "ℹ $*"; }
warn() { echo "⚠ $*"; }
success() { echo "✓ $*"; }

patterns='x509|unknown authority|certificate.*(expired|not yet valid|verify|validation)|tls:|handshake|ssl:'
services=(
  aidb
  qdrant
  postgres
  redis
  nginx
  grafana
  prometheus
)

status=0

info "Scanning TLS/certificate warnings in ${NAMESPACE} (tail=${TAIL_LINES})..."
for svc in "${services[@]}"; do
  if ! kubectl_safe -n "$NAMESPACE" get deploy "$svc" >/dev/null 2>&1; then
    warn "deploy/$svc not found (skipping)"
    continue
  fi

  if kubectl_safe -n "$NAMESPACE" logs "deploy/$svc" --tail="$TAIL_LINES" --all-containers 2>/dev/null \
    | grep -Eiq "$patterns"; then
    warn "TLS/cert warnings detected in deploy/$svc logs"
    status=1
  else
    success "No TLS/cert warnings detected in deploy/$svc logs"
  fi
done

if [[ "$status" -eq 0 ]]; then
  success "TLS log scan completed with no warnings"
else
  warn "TLS log scan detected warnings; review deployment logs"
fi

exit "$status"
