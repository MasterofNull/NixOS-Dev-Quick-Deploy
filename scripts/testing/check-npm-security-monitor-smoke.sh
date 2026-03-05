#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$(mktemp -d /tmp/npm-security-smoke-XXXXXX)"
trap 'rm -rf "${OUT_DIR}"' EXIT

"${ROOT_DIR}/scripts/npm-security-monitor.sh" \
  --repo-root "${ROOT_DIR}" \
  --output-dir "${OUT_DIR}" >/dev/null

latest="${OUT_DIR}/latest-npm-security.json"
[[ -f "${latest}" ]] || {
  echo "FAIL: npm security smoke missing latest report" >&2
  exit 1
}

jq -e '
  .summary
  and (.summary.projects_total | type == "number")
  and (.summary.projects_total >= 0)
  and (.summary.projects_with_lockfile | type == "number")
  and (.summary.projects_without_lockfile | type == "number")
' "${latest}" >/dev/null || {
  echo "FAIL: npm security smoke report shape invalid" >&2
  exit 1
}

echo "PASS: npm security monitor smoke"
