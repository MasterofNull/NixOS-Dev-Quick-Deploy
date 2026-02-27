#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${AI_SECURITY_AUDIT_DIR:-${HOME}/.local/share/nixos-ai-stack/security}"
HIGH_CVSS_THRESHOLD="${AI_SECURITY_AUDIT_HIGH_CVSS_THRESHOLD:-7.0}"
NOTIFY_USER="${AI_SECURITY_AUDIT_NOTIFY_USER:-}"

usage() {
  cat <<'EOF'
Usage: scripts/security-audit.sh [--repo-root PATH] [--output-dir PATH] [--notify-user USER]

Runs pip-audit on requirements.lock files and npm audit on package.json roots.
Writes JSON report: audit-YYYY-MM-DD.json and latest-security-audit.json.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      REPO_ROOT="${2:?missing value for --repo-root}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:?missing value for --output-dir}"
      shift 2
      ;;
    --notify-user)
      NOTIFY_USER="${2:?missing value for --notify-user}"
      shift 2
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

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 2
  fi
}

require_cmd jq
require_cmd python3
require_cmd npm
require_cmd pip-audit

mkdir -p "${OUTPUT_DIR}"
today="$(date +%F)"
timestamp="$(date -Iseconds)"
report_file="${OUTPUT_DIR}/audit-${today}.json"
latest_file="${OUTPUT_DIR}/latest-security-audit.json"
tmp_root="$(mktemp -d)"
trap 'rm -rf "${tmp_root}"' EXIT

pip_results_dir="${tmp_root}/pip"
npm_results_dir="${tmp_root}/npm"
mkdir -p "${pip_results_dir}" "${npm_results_dir}"

mapfile -t lockfiles < <(find "${REPO_ROOT}/ai-stack/mcp-servers" -type f -name 'requirements.lock' | sort)
mapfile -t package_files < <(find "${REPO_ROOT}" -type f -name 'package.json' \
  -not -path '*/node_modules/*' \
  -not -path '*/archive/*' \
  -not -path '*/.git/*' | sort)

pip_total_vulns=0
pip_files_scanned=0

for lockfile in "${lockfiles[@]}"; do
  base="$(echo "${lockfile#"${REPO_ROOT}/"}" | tr '/' '_')"
  out_json="${pip_results_dir}/${base}.json"
  set +e
  pip-audit -r "${lockfile}" --format json > "${out_json}" 2>"${out_json}.stderr"
  rc=$?
  set -e
  if [[ ${rc} -ne 0 && ${rc} -ne 1 ]]; then
    jq -n --arg lockfile "${lockfile}" --arg err "$(cat "${out_json}.stderr")" \
      '{dependencies: [], error: $err, lockfile: $lockfile}' > "${out_json}"
  fi
  count="$(jq '[.dependencies[]?.vulns[]?] | length' "${out_json}")"
  pip_total_vulns=$((pip_total_vulns + count))
  pip_files_scanned=$((pip_files_scanned + 1))
done

npm_total_high=0
npm_total_critical=0
npm_files_scanned=0

for package_file in "${package_files[@]}"; do
  dir="$(dirname "${package_file}")"
  if [[ ! -f "${dir}/package-lock.json" ]]; then
    continue
  fi
  base="$(echo "${dir#"${REPO_ROOT}/"}" | tr '/' '_')"
  out_json="${npm_results_dir}/${base}.json"
  set +e
  (cd "${dir}" && npm audit --omit=dev --json > "${out_json}" 2>"${out_json}.stderr")
  rc=$?
  set -e
  if [[ ${rc} -ne 0 && ${rc} -ne 1 ]]; then
    jq -n --arg project_dir "${dir}" --arg err "$(cat "${out_json}.stderr")" \
      '{metadata: {vulnerabilities: {info: 0, low: 0, moderate: 0, high: 0, critical: 0, total: 0}}, error: $err, project_dir: $project_dir}' > "${out_json}"
  fi
  high="$(jq '.metadata.vulnerabilities.high // 0' "${out_json}")"
  critical="$(jq '.metadata.vulnerabilities.critical // 0' "${out_json}")"
  npm_total_high=$((npm_total_high + high))
  npm_total_critical=$((npm_total_critical + critical))
  npm_files_scanned=$((npm_files_scanned + 1))
done

high_or_critical=$((npm_total_high + npm_total_critical))
overall_status="ok"
if [[ ${pip_total_vulns} -gt 0 || ${high_or_critical} -gt 0 ]]; then
  overall_status="findings"
fi

jq -n \
  --arg generated_at "${timestamp}" \
  --arg repo_root "${REPO_ROOT}" \
  --arg threshold "${HIGH_CVSS_THRESHOLD}" \
  --arg status "${overall_status}" \
  --argjson pip_total_vulns "${pip_total_vulns}" \
  --argjson pip_files_scanned "${pip_files_scanned}" \
  --argjson npm_total_high "${npm_total_high}" \
  --argjson npm_total_critical "${npm_total_critical}" \
  --argjson npm_files_scanned "${npm_files_scanned}" \
  --argjson pip_reports "$(find "${pip_results_dir}" -type f -name '*.json' | sort | jq -R . | jq -s .)" \
  --argjson npm_reports "$(find "${npm_results_dir}" -type f -name '*.json' | sort | jq -R . | jq -s .)" \
  '{
    generated_at: $generated_at,
    repo_root: $repo_root,
    high_cvss_threshold: ($threshold | tonumber),
    status: $status,
    summary: {
      pip: {
        files_scanned: $pip_files_scanned,
        vulnerabilities_total: $pip_total_vulns
      },
      npm: {
        files_scanned: $npm_files_scanned,
        high: $npm_total_high,
        critical: $npm_total_critical
      }
    },
    reports: {
      pip: $pip_reports,
      npm: $npm_reports
    }
  }' > "${report_file}"

cp "${report_file}" "${latest_file}"
echo "Security audit report written: ${report_file}"
echo "Latest report: ${latest_file}"

if [[ ${high_or_critical} -gt 0 ]]; then
  alert_file="${OUTPUT_DIR}/latest-high-cve-alert.json"
  jq -n \
    --arg generated_at "${timestamp}" \
    --arg message "Security audit detected ${high_or_critical} npm high/critical vulnerabilities." \
    --argjson high "${npm_total_high}" \
    --argjson critical "${npm_total_critical}" \
    --arg report_file "${report_file}" \
    '{generated_at: $generated_at, message: $message, high: $high, critical: $critical, report_file: $report_file}' \
    > "${alert_file}"
  echo "High severity alert written: ${alert_file}"

  if [[ -n "${NOTIFY_USER}" ]]; then
    user_id="$(id -u "${NOTIFY_USER}" 2>/dev/null || true)"
    if [[ -n "${user_id}" ]] && [[ -S "/run/user/${user_id}/bus" ]]; then
      su - "${NOTIFY_USER}" -c \
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${user_id}/bus DISPLAY=:0 notify-send 'AI Security Audit' 'High/Critical vulnerabilities detected (${high_or_critical}).'" \
        >/dev/null 2>&1 || true
    fi
  fi
fi

exit 0
