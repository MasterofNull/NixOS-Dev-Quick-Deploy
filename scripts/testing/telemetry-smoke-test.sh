#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OBS_SCRIPT="${ROOT_DIR}/scripts/testing/validate-genai-observability.sh"
AQ_REPORT_RUNTIME_SCRIPT="${ROOT_DIR}/scripts/testing/check-aq-report-runtime-sections.sh"
METRIC_SMOKE_SCRIPT="${ROOT_DIR}/scripts/testing/check-aq-report-metric-smoke.sh"
COLLECT_SCRIPT="${ROOT_DIR}/scripts/observability/collect-ai-metrics.sh"
ALLOW_EMPTY=false

usage() {
  cat <<'EOF'
Usage: scripts/testing/telemetry-smoke-test.sh [--allow-empty]

Compatibility shim over current telemetry and observability smoke checks:
  1. validate-genai-observability.sh
  2. check-aq-report-runtime-sections.sh
  3. check-aq-report-metric-smoke.sh
  4. collect-ai-metrics.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow-empty)
      ALLOW_EMPTY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for required in "${OBS_SCRIPT}" "${AQ_REPORT_RUNTIME_SCRIPT}" "${METRIC_SMOKE_SCRIPT}" "${COLLECT_SCRIPT}"; do
  [[ -x "${required}" ]] || { echo "Missing ${required}" >&2; exit 1; }
done

echo "scripts/testing/telemetry-smoke-test.sh is a compatibility shim over current observability smoke checks." >&2
"${OBS_SCRIPT}"
ALLOW_EMPTY="${ALLOW_EMPTY}" "${AQ_REPORT_RUNTIME_SCRIPT}"
"${METRIC_SMOKE_SCRIPT}"
"${COLLECT_SCRIPT}"
