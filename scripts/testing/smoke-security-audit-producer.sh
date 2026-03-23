#!/usr/bin/env bash
# Validate the raw security-audit.sh producer emits a healthy, well-formed report.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$(mktemp -d /tmp/security-audit-smoke-XXXXXX)"
trap 'rm -rf "${OUT_DIR}"' EXIT

bash "${ROOT_DIR}/scripts/security/security-audit.sh" \
  --repo-root "${ROOT_DIR}" \
  --output-dir "${OUT_DIR}" >/dev/null

latest="${OUT_DIR}/latest-security-audit.json"
[[ -f "${latest}" ]] || {
  echo "FAIL: security audit smoke missing latest report" >&2
  exit 1
}

jq -e '
  .status != null
  and .summary != null
  and (.summary.pip.scanner_available | type == "boolean")
  and (.summary.pip.files_scanned | type == "number")
  and (.summary.npm.scanner_available | type == "boolean")
  and (.summary.npm.files_scanned | type == "number")
  and (.summary.dashboard_operator.status | type == "string")
  and (.summary.secrets_rotation.status | type == "string")
  and (.reports.dashboard_operator | type == "string")
  and (.reports.secrets_rotation | type == "string")
  and (.summary.dashboard_operator.status != "error")
  and (.summary.secrets_rotation.status != "error")
' "${latest}" >/dev/null || {
  echo "FAIL: security audit smoke report shape or status invalid" >&2
  exit 1
}

echo "PASS: security audit producer smoke"
