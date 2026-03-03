#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/hyperd/Documents/NixOS-Dev-Quick-Deploy}"

run() {
  echo ""
  echo "==> $*"
  "$@"
}

run bash -n \
  "${ROOT}/scripts/aqd" \
  "${ROOT}/scripts/run-harness-regression-gate.sh" \
  "${ROOT}/scripts/chaos-harness-smoke.sh" \
  "${ROOT}/scripts/check-boot-shutdown-integration.sh" \
  "${ROOT}/scripts/check-failed-units-classification.sh" \
  "${ROOT}/scripts/check-api-auth-hardening.sh" \
  "${ROOT}/scripts/validate-ai-slo-runtime.sh" \
  "${ROOT}/scripts/smoke-cross-client-compat.sh" \
  "${ROOT}/scripts/smoke-focused-parity.sh"

run python -m py_compile \
  "${ROOT}/scripts/skill-bundle-registry.py" \
  "${ROOT}/scripts/evaluate-agent-policy.py" \
  "${ROOT}/scripts/route-reasoning-mode.py"

run "${ROOT}/scripts/aqd" workflows list
run "${ROOT}/scripts/run-harness-regression-gate.sh" --offline
run "${ROOT}/scripts/generate-harness-sdk-provenance.sh"
run "${ROOT}/scripts/smoke-skill-bundle-distribution.sh"
run "${ROOT}/scripts/check-boot-shutdown-integration.sh"
run "${ROOT}/scripts/check-failed-units-classification.sh"
run "${ROOT}/scripts/check-api-auth-hardening.sh"
run "${ROOT}/scripts/validate-ai-slo-runtime.sh"
run "${ROOT}/scripts/smoke-cross-client-compat.sh"
run "${ROOT}/scripts/smoke-focused-parity.sh"

echo ""
echo "Advanced parity suite completed."
