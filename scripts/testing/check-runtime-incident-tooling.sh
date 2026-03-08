#!/usr/bin/env bash
# Purpose: Run full runtime incident tooling test suite
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

"${ROOT_DIR}/scripts/testing/check-runtime-plan-catalog.sh"
"${ROOT_DIR}/scripts/testing/check-runtime-diagnose-classifications.sh"
"${ROOT_DIR}/scripts/testing/check-runtime-loop-integration.sh"
"${ROOT_DIR}/scripts/testing/check-runtime-remediation-runner.sh"
bash "${ROOT_DIR}/scripts/testing/check-runtime-act-wrapper.sh"
bash "${ROOT_DIR}/scripts/testing/check-agent-context-tooling.sh"
bash "${ROOT_DIR}/scripts/testing/check-context-bootstrap.sh"
bash "${ROOT_DIR}/scripts/testing/check-capability-gap.sh"
bash "${ROOT_DIR}/scripts/testing/check-capability-promotion.sh"
bash "${ROOT_DIR}/scripts/testing/check-capability-stub.sh"
bash "${ROOT_DIR}/scripts/testing/check-capability-catalog-append.sh"
bash "${ROOT_DIR}/scripts/testing/check-capability-patch-prep.sh"
bash "${ROOT_DIR}/scripts/testing/check-capability-patch-apply.sh"
bash "${ROOT_DIR}/scripts/testing/check-capability-remediation.sh"
bash "${ROOT_DIR}/scripts/testing/check-system-act.sh"
