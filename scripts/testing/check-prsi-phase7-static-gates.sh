#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

run() {
  echo "==> $*"
  "$@"
}

run "${ROOT_DIR}/scripts/testing/check-prsi-cycle-contract.sh"
run "${ROOT_DIR}/scripts/testing/check-prsi-bootstrap-integrity.sh"
run "${ROOT_DIR}/scripts/testing/check-prsi-validation-matrix.sh"
run "${ROOT_DIR}/scripts/automation/run-prsi-eval-integrity-gate.sh"
run "${ROOT_DIR}/scripts/testing/check-prsi-eval-pinning.sh"
run "${ROOT_DIR}/scripts/automation/run-prsi-canary-suite.sh"
run "${ROOT_DIR}/scripts/testing/check-prsi-confidence-calibration.sh"
run "${ROOT_DIR}/scripts/testing/check-prsi-quarantine-workflow.sh"
run "${ROOT_DIR}/scripts/testing/check-prsi-high-risk-approval-rubric.sh"
run "${ROOT_DIR}/scripts/testing/check-prsi-budget-discipline.sh"
run "${ROOT_DIR}/scripts/automation/run-prsi-stop-condition-drill.sh"
run "${ROOT_DIR}/scripts/automation/run-prsi-discovery-slice.sh"

echo "PASS: PRSI Phase 7 static/gated checks complete"
