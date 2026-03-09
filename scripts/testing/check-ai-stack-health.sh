#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HEALTH_SCRIPT="${ROOT_DIR}/scripts/ai/ai-stack-health.sh"
QA_SCRIPT="${ROOT_DIR}/scripts/ai/aq-qa"
RUN_QA=false
QA_ARGS=()

usage() {
  cat <<'EOF'
Usage: scripts/testing/check-ai-stack-health.sh [--with-qa] [aq-qa args...]

Compatibility shim over the supported declarative health tooling:
  1. scripts/ai/ai-stack-health.sh
  2. scripts/ai/aq-qa 0 (optional)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-qa)
      RUN_QA=true
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

[[ -x "${HEALTH_SCRIPT}" ]] || { echo "Missing ${HEALTH_SCRIPT}" >&2; exit 1; }
[[ -x "${QA_SCRIPT}" ]] || { echo "Missing ${QA_SCRIPT}" >&2; exit 1; }

echo "scripts/testing/check-ai-stack-health.sh is a compatibility shim over ai-stack-health.sh." >&2
"${HEALTH_SCRIPT}"
if [[ "${RUN_QA}" == true ]]; then
  "${QA_SCRIPT}" 0 "${QA_ARGS[@]}"
fi
