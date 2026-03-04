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
  "${ROOT}/scripts/check-aq-report-contract.sh" \
  "${ROOT}/scripts/check-prsi-cycle-contract.sh" \
  "${ROOT}/scripts/check-prsi-bootstrap-integrity.sh" \
  "${ROOT}/scripts/check-prsi-phase7-program.sh" \
  "${ROOT}/scripts/check-harness-first-static-gates.sh" \
  "${ROOT}/scripts/run-prsi-discovery-slice.sh" \
  "${ROOT}/scripts/check-aq-report-runtime-sections.sh" \
  "${ROOT}/scripts/check-aq-report-metric-smoke.sh" \
  "${ROOT}/scripts/check-routing-fallback.sh" \
  "${ROOT}/scripts/validate-ai-slo-runtime.sh" \
  "${ROOT}/scripts/smoke-cross-client-compat.sh" \
  "${ROOT}/scripts/smoke-focused-parity.sh"

run "${ROOT}/nixos-quick-deploy.sh" --self-check
run "${ROOT}/scripts/check-dryrun-failure-modes.sh" --flake-ref . --nixos-target nixos-ai-dev

run python -m py_compile \
  "${ROOT}/scripts/skill-bundle-registry.py" \
  "${ROOT}/scripts/evaluate-agent-policy.py" \
  "${ROOT}/scripts/route-reasoning-mode.py" \
  "${ROOT}/scripts/test-tool-security-auditor.py"

run "${ROOT}/scripts/aqd" workflows list
run "${ROOT}/scripts/run-harness-regression-gate.sh" --offline
run "${ROOT}/scripts/generate-harness-sdk-provenance.sh"
run "${ROOT}/scripts/smoke-skill-bundle-distribution.sh"
run "${ROOT}/scripts/check-boot-shutdown-integration.sh"
run "${ROOT}/scripts/check-failed-units-classification.sh"
run "${ROOT}/scripts/check-api-auth-hardening.sh"
run "${ROOT}/scripts/check-aq-report-contract.sh"
run "${ROOT}/scripts/check-prsi-cycle-contract.sh"
run "${ROOT}/scripts/check-prsi-bootstrap-integrity.sh"
run "${ROOT}/scripts/check-prsi-phase7-program.sh"
run "${ROOT}/scripts/check-harness-first-static-gates.sh"
run "${ROOT}/scripts/run-prsi-discovery-slice.sh"
run env ALLOW_EMPTY=true "${ROOT}/scripts/check-aq-report-runtime-sections.sh"
run "${ROOT}/scripts/check-aq-report-metric-smoke.sh"
run "${ROOT}/scripts/check-routing-fallback.sh"
run python3 "${ROOT}/scripts/test-tool-security-auditor.py"
run "${ROOT}/scripts/validate-ai-slo-runtime.sh"
run "${ROOT}/scripts/smoke-cross-client-compat.sh"
run "${ROOT}/scripts/smoke-focused-parity.sh"

echo ""
echo "Advanced parity suite completed."
