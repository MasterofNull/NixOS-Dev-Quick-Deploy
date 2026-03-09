#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORKFLOW_SMOKE="${ROOT_DIR}/scripts/testing/test-real-world-workflows.sh"
AQ_QA="${SCRIPT_DIR}/aq-qa"
PHASES_ONLY=false

usage() {
  cat <<'EOF'
Usage: scripts/ai/ai-stack-e2e-test.sh [--phases-only] [aq-qa args...]

Compatibility shim for current end-to-end declarative validation.

Default behavior:
  1. aq-qa 0 --json
  2. aq-qa 1 --json
  3. scripts/testing/test-real-world-workflows.sh
EOF
}

QA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --phases-only)
      PHASES_ONLY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      QA_ARGS+=("$1")
      shift
      ;;
  esac
done

[[ -x "${AQ_QA}" ]] || { echo "Missing ${AQ_QA}" >&2; exit 1; }
[[ -x "${WORKFLOW_SMOKE}" ]] || { echo "Missing ${WORKFLOW_SMOKE}" >&2; exit 1; }

echo "scripts/ai/ai-stack-e2e-test.sh is a compatibility shim over aq-qa and real-world workflow smoke tests." >&2
"${AQ_QA}" 0 --json "${QA_ARGS[@]}"
"${AQ_QA}" 1 --json "${QA_ARGS[@]}"
if [[ "${PHASES_ONLY}" == false ]]; then
  "${WORKFLOW_SMOKE}"
fi
