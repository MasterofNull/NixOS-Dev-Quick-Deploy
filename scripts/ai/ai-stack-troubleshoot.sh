#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPORT_DIR="${PROJECT_ROOT}/artifacts/troubleshooting"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
REPORT_PATH="${REPORT_DIR}/ai-stack-troubleshoot-${TIMESTAMP}.txt"

mkdir -p "${REPORT_DIR}"

{
    echo "AI Stack Troubleshooting Report"
    echo "Generated: $(date --iso-8601=seconds)"
    echo "Project root: ${PROJECT_ROOT}"
    echo
    echo "[systemctl]"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --no-pager --type=service --state=failed 2>/dev/null || true
    else
        echo "systemctl unavailable"
    fi
    echo
    echo "[aq-qa 0]"
    if command -v aq-qa >/dev/null 2>&1; then
        aq-qa 0 --json 2>/dev/null || true
    else
        echo "aq-qa unavailable"
    fi
    echo
    echo "[dashboard health]"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS http://127.0.0.1:8889/api/health 2>/dev/null || true
    else
        echo "curl unavailable"
    fi
} > "${REPORT_PATH}"

echo "Troubleshooting report written to: ${REPORT_PATH}"
