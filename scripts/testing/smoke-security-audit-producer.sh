#!/usr/bin/env bash
# Validate the raw security-audit.sh producer emits a healthy, well-formed report.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$(mktemp -d /tmp/security-audit-smoke-XXXXXX)"
MAX_AGE_SECONDS="${SECURITY_AUDIT_MAX_AGE_SECONDS:-900}"
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
  and .generated_at != null
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

generated_at="$(jq -r '.generated_at' "${latest}")"
generated_epoch="$(date -d "${generated_at}" +%s 2>/dev/null || true)"
now_epoch="$(date +%s)"
if [[ -z "${generated_epoch}" ]] || (( now_epoch - generated_epoch > MAX_AGE_SECONDS )); then
  echo "FAIL: security audit smoke report is stale or has invalid generated_at (${generated_at})" >&2
  exit 1
fi

echo "PASS: security audit producer smoke"
