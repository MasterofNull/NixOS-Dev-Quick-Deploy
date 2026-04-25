#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

run() {
  echo ""
  echo "==> $*"
  "$@"
}

run bash -n \
  "${ROOT}/scripts/ai/aqd" \
  "${ROOT}/scripts/automation/run-harness-regression-gate.sh" \
  "${ROOT}/scripts/testing/chaos-harness-smoke.sh" \
  "${ROOT}/scripts/testing/check-boot-shutdown-integration.sh" \
  "${ROOT}/scripts/testing/check-failed-units-classification.sh" \
  "${ROOT}/scripts/testing/check-api-auth-hardening.sh" \
  "${ROOT}/scripts/testing/check-aq-report-contract.sh" \
  "${ROOT}/scripts/testing/check-prsi-cycle-contract.sh" \
  "${ROOT}/scripts/testing/check-prsi-bootstrap-integrity.sh" \
  "${ROOT}/scripts/testing/check-prsi-phase7-program.sh" \
  "${ROOT}/scripts/testing/check-harness-first-static-gates.sh" \
  "${ROOT}/scripts/automation/run-prsi-discovery-slice.sh" \
  "${ROOT}/scripts/testing/check-aq-report-runtime-sections.sh" \
  "${ROOT}/scripts/testing/check-aq-report-metric-smoke.sh" \
  "${ROOT}/scripts/testing/check-routing-fallback.sh" \
  "${ROOT}/scripts/testing/validate-ai-slo-runtime.sh" \
  "${ROOT}/scripts/testing/smoke-cross-client-compat.sh" \
  "${ROOT}/scripts/testing/smoke-focused-parity.sh"

run "${ROOT}/nixos-quick-deploy.sh" --self-check
run "${ROOT}/scripts/testing/check-dryrun-failure-modes.sh" --flake-ref . --nixos-target nixos-ai-dev

run python -m py_compile \
  "${ROOT}/scripts/governance/skill-bundle-registry.py" \
  "${ROOT}/scripts/governance/evaluate-agent-policy.py" \
  "${ROOT}/scripts/ai/route-reasoning-mode.py" \
  "${ROOT}/scripts/testing/test-tool-security-auditor.py"

run "${ROOT}/scripts/ai/aqd" workflows list
run "${ROOT}/scripts/automation/run-harness-regression-gate.sh" --offline
run "${ROOT}/scripts/data/generate-harness-sdk-provenance.sh"
run "${ROOT}/scripts/testing/smoke-skill-bundle-distribution.sh"
run "${ROOT}/scripts/testing/check-boot-shutdown-integration.sh"
run "${ROOT}/scripts/testing/check-failed-units-classification.sh"
run "${ROOT}/scripts/testing/check-api-auth-hardening.sh"
run "${ROOT}/scripts/testing/check-aq-report-contract.sh"
run "${ROOT}/scripts/testing/check-prsi-cycle-contract.sh"
run "${ROOT}/scripts/testing/check-prsi-bootstrap-integrity.sh"
run "${ROOT}/scripts/testing/check-prsi-phase7-program.sh"
run "${ROOT}/scripts/testing/check-harness-first-static-gates.sh"
run "${ROOT}/scripts/automation/run-prsi-discovery-slice.sh"
run env ALLOW_EMPTY=true "${ROOT}/scripts/testing/check-aq-report-runtime-sections.sh"
run "${ROOT}/scripts/testing/check-aq-report-metric-smoke.sh"
run "${ROOT}/scripts/testing/check-routing-fallback.sh"
run python3 "${ROOT}/scripts/testing/test-tool-security-auditor.py"
run "${ROOT}/scripts/testing/validate-ai-slo-runtime.sh"
run "${ROOT}/scripts/testing/smoke-cross-client-compat.sh"
run "${ROOT}/scripts/testing/smoke-focused-parity.sh"
run "${ROOT}/scripts/testing/check-ai-coordinator-delegate-smoke.sh"
run "${ROOT}/scripts/testing/test-local-orchestrator-frontdoor.sh"
# warn-only: remote routing is deliberately prefer_local=true on this hardware
"${ROOT}/scripts/testing/check-remote-profiles.sh" || true

echo ""
echo "Advanced parity suite completed."
