#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

run() {
  echo "==> $*"
  "$@"
}

run "${ROOT_DIR}/scripts/testing/check-harness-first-runbook.sh"
run "${ROOT_DIR}/scripts/testing/check-harness-first-evidence-template.sh"
run "${ROOT_DIR}/scripts/testing/check-harness-first-pr-evidence-gate.sh"

echo "PASS: harness-first static gates complete"
