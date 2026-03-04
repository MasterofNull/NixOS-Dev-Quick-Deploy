#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

run() {
  echo "==> $*"
  "$@"
}

run "${ROOT_DIR}/scripts/check-prsi-cycle-contract.sh"
run "${ROOT_DIR}/scripts/check-prsi-bootstrap-integrity.sh"
run "${ROOT_DIR}/scripts/check-prsi-validation-matrix.sh"
run "${ROOT_DIR}/scripts/run-prsi-eval-integrity-gate.sh"
run "${ROOT_DIR}/scripts/check-prsi-eval-pinning.sh"
run "${ROOT_DIR}/scripts/run-prsi-canary-suite.sh"
run "${ROOT_DIR}/scripts/check-prsi-confidence-calibration.sh"
run "${ROOT_DIR}/scripts/check-prsi-quarantine-workflow.sh"
run "${ROOT_DIR}/scripts/check-prsi-high-risk-approval-rubric.sh"
run "${ROOT_DIR}/scripts/check-prsi-budget-discipline.sh"
run "${ROOT_DIR}/scripts/run-prsi-stop-condition-drill.sh"
run "${ROOT_DIR}/scripts/run-prsi-discovery-slice.sh"

echo "PASS: PRSI Phase 7 static/gated checks complete"
