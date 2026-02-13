#!/usr/bin/env bats

setup() {
  if [ "${RUN_K3S_INTEGRATION:-}" != "true" ]; then
    skip "Set RUN_K3S_INTEGRATION=true to enable K3s integration checks"
  fi

  if [ "${RUN_PHASE_09_GATE_TEST:-}" != "true" ]; then
    skip "Set RUN_PHASE_09_GATE_TEST=true to enable Phase 9 gate-only checks"
  fi

  if ! command -v kubectl >/dev/null 2>&1; then
    skip "kubectl not found"
  fi

  if ! kubectl get nodes >/dev/null 2>&1; then
    skip "kubectl cannot reach cluster"
  fi
}

@test "phase 9 gate-only mode fails when TLS secrets are missing" {
  local ns="ai-stack-gate-test-${RANDOM}"
  local backups="backups-gate-test-${RANDOM}"

  run env \
    AI_STACK_NAMESPACE="$ns" \
    BACKUPS_NAMESPACE="$backups" \
    REQUIRE_ENCRYPTED_SECRETS=true \
    PHASE_09_GATE_ONLY=true \
    bash -c '\
      set -euo pipefail; \
      export SCRIPT_DIR="$PWD"; \
      source lib/colors.sh; \
      source lib/logging.sh; \
      source lib/user-interaction.sh; \
      source lib/error-codes.sh; \
      source lib/timeout.sh; \
      source lib/retry-backoff.sh; \
      source phases/phase-09-k3s-portainer.sh; \
      phase_09_k3s_portainer \
    '

  [ "$status" -ne 0 ]
  echo "$output" | grep -q "TLS secrets not available"

  kubectl delete namespace "$ns" --ignore-not-found --wait=false >/dev/null
  kubectl delete namespace "$backups" --ignore-not-found --wait=false >/dev/null
}
