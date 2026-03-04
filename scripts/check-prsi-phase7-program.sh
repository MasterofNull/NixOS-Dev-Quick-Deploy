#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SWB_URL="${SWB_URL:-http://127.0.0.1:8085}"
PRSI_REQUIRE_AGENT_HARNESS_PARITY="${PRSI_REQUIRE_AGENT_HARNESS_PARITY:-false}"

run() {
  echo "==> $*"
  "$@"
}

run "${ROOT_DIR}/scripts/check-prsi-cycle-contract.sh"
run "${ROOT_DIR}/scripts/check-prsi-bootstrap-integrity.sh"
run "${ROOT_DIR}/scripts/check-prsi-validation-matrix.sh"
run "${ROOT_DIR}/scripts/check-api-auth-hardening.sh"
run "${ROOT_DIR}/scripts/chaos-harness-smoke.sh"
run "${ROOT_DIR}/scripts/smoke-focused-parity.sh"
if curl --max-time 5 --connect-timeout 2 -fsS "${SWB_URL%/}/v1/models" >/dev/null 2>&1; then
  run "${ROOT_DIR}/scripts/smoke-agent-harness-parity.sh"
else
  if [[ "${PRSI_REQUIRE_AGENT_HARNESS_PARITY}" == "true" ]]; then
    echo "FAIL: switchboard unavailable at ${SWB_URL}; strict parity gate required" >&2
    exit 1
  fi
  echo "WARN: switchboard unavailable at ${SWB_URL}; gating smoke-agent-harness-parity in this run"
fi
run "${ROOT_DIR}/scripts/run-prsi-eval-integrity-gate.sh"
run "${ROOT_DIR}/scripts/check-prsi-eval-pinning.sh"
run "${ROOT_DIR}/scripts/run-prsi-canary-suite.sh"
run "${ROOT_DIR}/scripts/check-prsi-confidence-calibration.sh"
run "${ROOT_DIR}/scripts/check-prsi-quarantine-workflow.sh"
run "${ROOT_DIR}/scripts/check-prsi-high-risk-approval-rubric.sh"
run "${ROOT_DIR}/scripts/check-prsi-budget-discipline.sh"
run "${ROOT_DIR}/scripts/run-prsi-stop-condition-drill.sh"
run "${ROOT_DIR}/scripts/run-prsi-discovery-slice.sh"

echo ""
echo "PASS: PRSI Phase 7 program checks complete"
