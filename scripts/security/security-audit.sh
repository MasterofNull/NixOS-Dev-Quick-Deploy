#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${AI_SECURITY_AUDIT_DIR:-${HOME}/.local/share/nixos-ai-stack/security}"
HIGH_CVSS_THRESHOLD="${AI_SECURITY_AUDIT_HIGH_CVSS_THRESHOLD:-7.0}"
NOTIFY_USER="${AI_SECURITY_AUDIT_NOTIFY_USER:-}"
DASHBOARD_SCAN_SCRIPT="${DASHBOARD_SCAN_SCRIPT:-${REPO_ROOT}/scripts/security/dashboard-security-scan.sh}"
SECRETS_ROTATION_PLAN_SCRIPT="${SECRETS_ROTATION_PLAN_SCRIPT:-${REPO_ROOT}/scripts/security/secrets-rotation-plan.sh}"

usage() {
  cat <<'EOF'
Usage: scripts/security/security-audit.sh [--repo-root PATH] [--output-dir PATH] [--notify-user USER]

Runs pip-audit on ai-stack requirements.txt files and npm audit on package.json roots. Exits 1 on blocking findings. Under CI=true, zero pip coverage or an npm audit error is also blocking. Lock-integrity is not applicable (Nix-only, 2026-10-01; closure scanning lives in scripts/security/aq-closure-scan).
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

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

require_cmd jq
require_cmd python3

pip_audit_available=false
npm_available=false
pip_audit_cmd=()
if has_cmd pip-audit; then
  pip_audit_available=true
  pip_audit_cmd=(pip-audit)
elif has_cmd nix; then
  pip_audit_available=true
  pip_audit_cmd=(nix shell nixpkgs#pip-audit --command pip-audit)
fi
if has_cmd npm; then
  npm_available=true
fi

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

mapfile -t requirements_files < <(find "${REPO_ROOT}/ai-stack/mcp-servers" -type f -name 'requirements.txt' | sort)
if git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  mapfile -t package_files < <(
    {
      git -C "${REPO_ROOT}" ls-files -- '**/package.json' 'package.json'
      git -C "${REPO_ROOT}" ls-files --others --exclude-standard -- '**/package.json' 'package.json'
    } | sort -u | while IFS= read -r rel; do
      [[ -n "${rel}" && -f "${REPO_ROOT}/${rel}" ]] && echo "${REPO_ROOT}/${rel}"
    done
  )
else
  mapfile -t package_files < <(find "${REPO_ROOT}" -type f -name 'package.json' \
    -not -path '*/node_modules/*' \
    -not -path '*/archive/*' \
    -not -path '*/.forks/*' \
    -not -path '*/.agents/*' \
    -not -path '*/.claude/*' \
    -not -path '*/.codex/*' \
    -not -path '*/.review-worktrees/*' \
    -not -path '*/.venv/*' \
    -not -path '*/.git/*' | sort)
fi

pip_total_vulns=0
pip_files_scanned=0
pip_errors=0

# Time-boxed exceptions: applied only while unexpired, valid YYYY-MM-DD (UTC) and <= 90 days out,
# and only to a finding whose package name matches the exception's package.
EXCEPTIONS_FILE="${SECURITY_EXCEPTIONS_FILE:-${REPO_ROOT}/config/security-exceptions.json}"
EXCEPTION_MAX_DAYS=90
applied_exceptions=()
expired_exceptions=()
exceptions_json='[]'
if [[ -f "${EXCEPTIONS_FILE}" ]]; then
  today_epoch="$(date -u -d "$(date -u +%F)" +%s)"
  max_epoch=$((today_epoch + EXCEPTION_MAX_DAYS * 86400))
  while IFS=$'\t' read -r ex_id ex_pkg ex_expires; do
    [[ -n "${ex_id}" ]] || continue
    ex_epoch=""
    if [[ "${ex_expires}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
      ex_epoch="$(date -u -d "${ex_expires}" +%s 2>/dev/null || true)"
    fi
    if [[ -n "${ex_epoch}" && "$(date -u -d "@${ex_epoch}" +%F)" == "${ex_expires}" && ${ex_epoch} -ge ${today_epoch} && ${ex_epoch} -le ${max_epoch} ]]; then
      exceptions_json="$(jq -c --arg id "${ex_id}" --arg pkg "${ex_pkg}" '. + [{id: $id, package: $pkg}]' <<<"${exceptions_json}")"
      applied_exceptions+=("${ex_id} (${ex_pkg}, expires ${ex_expires})")
    else
      expired_exceptions+=("${ex_id} (${ex_pkg}, expiry '${ex_expires:-unset}' expired, malformed or >${EXCEPTION_MAX_DAYS}d out)")
    fi
  done < <(jq -r '.exceptions[]? | [.id, .package, (.expires // "")] | @tsv' "${EXCEPTIONS_FILE}")
fi
mismatch_warnings=()

if [[ "${pip_audit_available}" == true ]]; then
  for req in "${requirements_files[@]}"; do
    base="$(echo "${req#"${REPO_ROOT}/"}" | tr '/' '_')"
    out_json="${pip_results_dir}/${base}.json"
    set +e
    "${pip_audit_cmd[@]}" -r "${req}" --format json > "${out_json}" 2>"${out_json}.stderr"
    rc=$?
    set -e
    if [[ ${rc} -ne 0 && ${rc} -ne 1 ]] || ! jq -e '.dependencies' "${out_json}" >/dev/null 2>&1; then
      jq -n --arg req "${req}" --arg err "$(cat "${out_json}.stderr")" \
        '{dependencies: [], error: $err, requirements: $req}' > "${out_json}"
      pip_errors=$((pip_errors + 1))
      continue
    fi
    while IFS= read -r mm; do
      [[ -n "${mm}" ]] && mismatch_warnings+=("${mm}")
    done < <(jq -r --argjson ex "${exceptions_json}" '
      def norm: ascii_downcase | gsub("_"; "-");
      .dependencies[]? as $d | $d.vulns[]? as $v | $ex[]?
      | select(.id == $v.id and (.package | norm) != ($d.name | norm))
      | "\(.id) excepted for \(.package) but found in \($d.name)"' "${out_json}")
    jq --argjson ex "${exceptions_json}" '
      def norm: ascii_downcase | gsub("_"; "-");
      .dependencies |= map(. as $d | .vulns |= map(select(.id as $i
        | ($ex | any(.id == $i and (.package | norm) == ($d.name | norm))) | not)))' \
      "${out_json}" > "${out_json}.f" && mv "${out_json}.f" "${out_json}"
    count="$(jq '[.dependencies[]?.vulns[]?] | length' "${out_json}")"
    pip_total_vulns=$((pip_total_vulns + count))
    pip_files_scanned=$((pip_files_scanned + 1))
  done
else
  jq -n --arg error "pip-audit not installed" '{dependencies: [], error: $error}' > "${pip_results_dir}/scanner-unavailable.json"
fi

lock_results_dir="${tmp_root}/lock-integrity"
mkdir -p "${lock_results_dir}"
lock_integrity_issues=0
lock_integrity_scanned=0
jq -n '{event: "not_applicable", reason: "Nix-only, no lock files"}' > "${lock_results_dir}/not-applicable.json"

npm_total_high=0
npm_total_critical=0
npm_files_scanned=0
npm_errors=0
npm_unscanned=0

if [[ "${npm_available}" == true ]]; then
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
    if jq -e 'has("error") or (.metadata.vulnerabilities == null)' "${out_json}" >/dev/null 2>&1; then
      npm_errors=$((npm_errors + 1))
    fi
    high="$(jq '.metadata.vulnerabilities.high // 0' "${out_json}")"
    critical="$(jq '.metadata.vulnerabilities.critical // 0' "${out_json}")"
    npm_total_high=$((npm_total_high + high))
    npm_total_critical=$((npm_total_critical + critical))
    npm_files_scanned=$((npm_files_scanned + 1))
  done
else
  # Scanner unavailable: every npm project that needs scanning is unscanned, which is a
  # coverage gap (counted as an error so CI fails closed and status cannot be ok).
  for package_file in "${package_files[@]}"; do
    [[ -f "$(dirname "${package_file}")/package-lock.json" ]] && npm_unscanned=$((npm_unscanned + 1))
  done
  npm_errors=$((npm_errors + npm_unscanned))
  jq -n --arg error "npm not installed" '{metadata: {vulnerabilities: {info: 0, low: 0, moderate: 0, high: 0, critical: 0, total: 0}}, error: $error}' > "${npm_results_dir}/scanner-unavailable.json"
fi

persist_results_dir() {
  local src_dir="$1"
  local dest_dir="$2"
  local final_dir="${dest_dir}"
  if ! rm -rf "${final_dir}" 2>/dev/null; then
    final_dir="${dest_dir}-${timestamp//[^[:alnum:]]/-}-$$"
    echo "WARN: could not replace ${dest_dir}; writing audit results to ${final_dir}" >&2
  fi
  mkdir -p "${final_dir}"
  find "${src_dir}" -maxdepth 1 -type f -name '*.json' -exec cp {} "${final_dir}/" \;
  printf '%s\n' "${final_dir}"
}

persisted_pip_dir="$(persist_results_dir "${pip_results_dir}" "${OUTPUT_DIR}/pip-audit")"
persisted_lock_dir="$(persist_results_dir "${lock_results_dir}" "${OUTPUT_DIR}/lock-integrity")"
persisted_npm_dir="$(persist_results_dir "${npm_results_dir}" "${OUTPUT_DIR}/npm-audit")"

dashboard_scan_report="${OUTPUT_DIR}/latest-dashboard-security-scan.json"
dashboard_scan_status="unavailable"
if [[ -x "${DASHBOARD_SCAN_SCRIPT}" ]]; then
  set +e
  "${DASHBOARD_SCAN_SCRIPT}" --output "${dashboard_scan_report}" >"${tmp_root}/dashboard-scan.stdout" 2>"${tmp_root}/dashboard-scan.stderr"
  dashboard_rc=$?
  set -e
  if [[ ${dashboard_rc} -eq 0 && -f "${dashboard_scan_report}" ]]; then
    dashboard_scan_status="$(jq -r '.status // "unknown"' "${dashboard_scan_report}")"
  else
    jq -n \
      --arg generated_at "${timestamp}" \
      --arg status "error" \
      --arg error "$(cat "${tmp_root}/dashboard-scan.stderr" 2>/dev/null)" \
      --arg target "${DASHBOARD_URL:-}" \
      '{generated_at: $generated_at, status: $status, target: $target, error: $error}' \
      > "${dashboard_scan_report}"
    dashboard_scan_status="error"
  fi
fi

secrets_rotation_report="${OUTPUT_DIR}/latest-secrets-rotation-plan.json"
secrets_rotation_status="unavailable"
if [[ -x "${SECRETS_ROTATION_PLAN_SCRIPT}" ]]; then
  set +e
  "${SECRETS_ROTATION_PLAN_SCRIPT}" --output "${secrets_rotation_report}" >"${tmp_root}/secrets-plan.stdout" 2>"${tmp_root}/secrets-plan.stderr"
  secrets_plan_rc=$?
  set -e
  if [[ ${secrets_plan_rc} -eq 0 && -f "${secrets_rotation_report}" ]]; then
    secrets_rotation_status="$(jq -r 'if .rotation_ready then "ready" else "planning_required" end' "${secrets_rotation_report}")"
  else
    jq -n \
      --arg generated_at "${timestamp}" \
      --arg status "error" \
      --arg error "$(cat "${tmp_root}/secrets-plan.stderr" 2>/dev/null)" \
      '{generated_at: $generated_at, status: $status, error: $error}' \
      > "${secrets_rotation_report}"
    secrets_rotation_status="error"
  fi
fi

high_or_critical=$((npm_total_high + npm_total_critical))
overall_status="ok"
if [[ ${pip_total_vulns} -gt 0 || ${high_or_critical} -gt 0 || "${dashboard_scan_status}" == "error" || "${secrets_rotation_status}" == "error" ]]; then
  overall_status="findings"
fi
# "Could not scan" is distinct from "scanned and clean" and from "found vulns".
# A genuine finding keeps status=findings; otherwise any coverage gap is degraded.
degraded_reasons=()
if [[ "${pip_audit_available}" != true ]]; then
  degraded_reasons+=("pip-audit scanner missing")
elif [[ ${pip_files_scanned} -eq 0 ]]; then
  degraded_reasons+=("zero pip-audit coverage (0 requirements files scanned)")
fi
[[ ${pip_errors} -gt 0 ]] && degraded_reasons+=("pip-audit failed on ${pip_errors} requirements files")
[[ ${npm_unscanned} -gt 0 ]] && degraded_reasons+=("npm scanner missing (${npm_unscanned} npm projects unscanned)")
[[ $((npm_errors - npm_unscanned)) -gt 0 ]] && degraded_reasons+=("npm audit errored on $((npm_errors - npm_unscanned)) projects")
[[ "${dashboard_scan_status}" == "error" ]] && degraded_reasons+=("dashboard security scan errored")
[[ "${secrets_rotation_status}" == "error" ]] && degraded_reasons+=("secrets rotation plan errored")
# Exit-code decision is independent of the presentation status: any scanner error,
# missing scanner or zero coverage means the audit is incomplete.
coverage_incomplete=false
[[ ${#degraded_reasons[@]} -gt 0 ]] && coverage_incomplete=true
if [[ "${overall_status}" == "ok" && ${#degraded_reasons[@]} -gt 0 ]]; then
  overall_status="degraded"
fi
degraded_reasons_json="$(printf '%s\n' "${degraded_reasons[@]+"${degraded_reasons[@]}"}" | jq -R . | jq -s 'map(select(length > 0))')"

jq -n \
  --arg generated_at "${timestamp}" \
  --arg repo_root "${REPO_ROOT}" \
  --arg threshold "${HIGH_CVSS_THRESHOLD}" \
  --arg status "${overall_status}" \
  --argjson degraded_reasons "${degraded_reasons_json}" \
  --argjson pip_total_vulns "${pip_total_vulns}" \
  --argjson pip_files_scanned "${pip_files_scanned}" \
  --argjson lock_integrity_scanned "${lock_integrity_scanned}" \
  --argjson lock_integrity_issues "${lock_integrity_issues}" \
  --argjson npm_total_high "${npm_total_high}" \
  --argjson npm_total_critical "${npm_total_critical}" \
  --argjson npm_files_scanned "${npm_files_scanned}" \
  --argjson pip_audit_available "$( [[ "${pip_audit_available}" == true ]] && echo true || echo false )" \
  --argjson npm_available "$( [[ "${npm_available}" == true ]] && echo true || echo false )" \
  --arg dashboard_scan_status "${dashboard_scan_status}" \
  --arg dashboard_scan_report "${dashboard_scan_report}" \
  --arg secrets_rotation_status "${secrets_rotation_status}" \
  --arg secrets_rotation_report "${secrets_rotation_report}" \
  --argjson pip_reports "$(find "${persisted_pip_dir}" -type f -name '*.json' | sort | jq -R . | jq -s .)" \
  --argjson lock_integrity_reports "$(find "${persisted_lock_dir}" -type f -name '*.json' | sort | jq -R . | jq -s .)" \
  --argjson npm_reports "$(find "${persisted_npm_dir}" -type f -name '*.json' | sort | jq -R . | jq -s .)" \
  '{
    generated_at: $generated_at,
    repo_root: $repo_root,
    high_cvss_threshold: ($threshold | tonumber),
    status: $status,
    degraded_reasons: $degraded_reasons,
    summary: {
      pip: {
        scanner_available: $pip_audit_available,
        files_scanned: $pip_files_scanned,
        vulnerabilities_total: $pip_total_vulns
      },
      lock_integrity: {
        files_scanned: $lock_integrity_scanned,
        issues_total: $lock_integrity_issues
      },
      npm: {
        scanner_available: $npm_available,
        files_scanned: $npm_files_scanned,
        high: $npm_total_high,
        critical: $npm_total_critical
      },
      dashboard_operator: {
        status: $dashboard_scan_status,
        report_path: $dashboard_scan_report
      },
      secrets_rotation: {
        status: $secrets_rotation_status,
        report_path: $secrets_rotation_report
      }
    },
    reports: {
      pip: $pip_reports,
      lock_integrity: $lock_integrity_reports,
      npm: $npm_reports,
      dashboard_operator: $dashboard_scan_report,
      secrets_rotation: $secrets_rotation_report
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

  # Record failure into RSI lifecycle ledger so PRSI tracks and remediates the CVEs
  if [[ -x "${REPO_ROOT}/scripts/ai/aq-rsi" ]]; then
    "${REPO_ROOT}/scripts/ai/aq-rsi" report \
      "Security audit detected ${high_or_critical} high/critical CVEs (critical=${npm_total_critical}, high=${npm_total_high})" \
      --agent "security-audit" \
      --subject "security-audit:npm-cve" \
      --producer "security-audit:npm" \
      --path "${report_file}" \
      --authority "npm-audit" \
      --severity "$([[ ${npm_total_critical} -gt 0 ]] && echo critical || echo high)" \
      --root-fix "Review vulnerable npm dependencies; run npm audit fix or update package versions" \
      >/dev/null 2>&1 || true
  fi

  if [[ -n "${NOTIFY_USER}" ]]; then
    user_id="$(id -u "${NOTIFY_USER}" 2>/dev/null || true)"
    if [[ -n "${user_id}" ]] && [[ -S "/run/user/${user_id}/bus" ]]; then
      su - "${NOTIFY_USER}" -c \
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${user_id}/bus DISPLAY=:0 notify-send 'AI Security Audit' 'High/Critical vulnerabilities detected (${high_or_critical}).'" \
        >/dev/null 2>&1 || true
    fi
  fi
fi

# Gate: blocking = what overall_status already treats as findings from the
# vulnerability checks (pip vulns, npm high/critical); under CI=true also zero pip
# coverage and npm audit errors (fail-closed).
# dashboard/secrets-rotation errors and unavailable scanners stay warnings.
blocking=0
if [[ ${pip_total_vulns} -gt 0 ]]; then
  echo "BLOCKING: pip-audit reported ${pip_total_vulns} vulnerabilities"; blocking=$((blocking + 1))
  echo "--- Gate-Triggered Dependency Hygiene Ladder ---"
  echo "Trigger: Blocking pip vulnerability detected."
  echo "Ladder steps: (1) Check if fixed version exists -> bump floor; (2) Active upstream, unreleased fix -> mitigate + exception (<=90d); (3) Abandoned/stale -> replace package; (4) Upstream help is owner-authored."
  # Print details from pip results to surface fix versions and affected packages
  if compgen -G "${pip_results_dir}/*.json" >/dev/null; then
    for pf in "${pip_results_dir}"/*.json; do
      [[ -f "${pf}" ]] || continue
      jq -r '.dependencies[]? | select(.vulns | length > 0) | "Package: \(.name) (\(.version)) | Vulns: \([.vulns[].id] | join(", ")) | Fix versions: \([.vulns[].fix_versions[]?] | unique | join(", "))"' "${pf}" 2>/dev/null || true
    done
  fi
  echo "------------------------------------------------"
fi
if [[ ${high_or_critical} -gt 0 ]]; then
  echo "BLOCKING: npm audit reported ${npm_total_critical} critical / ${npm_total_high} high vulnerabilities"; blocking=$((blocking + 1))
  echo "--- Gate-Triggered Dependency Hygiene Ladder ---"
  echo "Trigger: Blocking npm vulnerability detected."
  echo "Ladder steps: (1) Check if fixed version exists -> bump floor; (2) Active upstream, unreleased fix -> mitigate + exception (<=90d); (3) Abandoned/stale -> replace package; (4) Upstream help is owner-authored."
  if compgen -G "${npm_results_dir}/*.json" >/dev/null; then
    for nf in "${npm_results_dir}"/*.json; do
      [[ -f "${nf}" ]] || continue
      jq -r '.vulnerabilities[]? | select(.severity == "high" or .severity == "critical") | "Package: \(.name) | Severity: \(.severity) | Fix available: \(.fixAvailable)"' "${nf}" 2>/dev/null || true
    done
  fi
  echo "------------------------------------------------"
fi
for ex in "${applied_exceptions[@]}"; do echo "EXCEPTION applied: ${ex}"; done
for ex in "${expired_exceptions[@]}"; do echo "WARNING: security exception EXPIRED, not applied: ${ex}"; done
echo "pip coverage: ${pip_files_scanned} files"
echo "lock-integrity: not applicable (Nix-only, no lock files)"
ci="${CI:-false}"
if [[ ${pip_files_scanned} -eq 0 ]]; then
  if [[ "${ci}" == "true" ]]; then
    echo "BLOCKING: zero pip-audit coverage in CI"; blocking=$((blocking + 1))
  else
    echo "WARNING: zero pip-audit coverage (scanner missing or requirements unscannable)"
  fi
fi
for mm in "${mismatch_warnings[@]}"; do echo "WARNING: security exception package mismatch, not applied: ${mm}"; done
if [[ ${pip_errors} -gt 0 ]]; then
  if [[ "${ci}" == "true" ]]; then
    echo "BLOCKING: pip-audit failed on ${pip_errors} requirements files in CI"; blocking=$((blocking + 1))
  else
    echo "WARNING: pip-audit failed on ${pip_errors} requirements files"
  fi
fi
if [[ ${npm_errors} -gt 0 ]]; then
  if [[ "${ci}" == "true" ]]; then
    echo "BLOCKING: npm audit errored on ${npm_errors} projects in CI"; blocking=$((blocking + 1))
  else
    echo "WARNING: npm audit errored on ${npm_errors} projects"
  fi
fi
[[ "${dashboard_scan_status}" == "error" ]] && echo "WARNING: dashboard security scan errored (non-blocking)"
[[ "${secrets_rotation_status}" == "error" ]] && echo "WARNING: secrets rotation plan errored (non-blocking)"
echo "Security audit summary: blocking=${blocking} status=${overall_status}"
[[ ${blocking} -eq 0 ]] || exit 1
# Scheduled runs set SECURITY_AUDIT_FAIL_ON_DEGRADED=1 so a scan that checked
# nothing fails the unit (picked up by systemctl --failed / aq-health-spider).
if [[ "${coverage_incomplete}" == true && "${SECURITY_AUDIT_FAIL_ON_DEGRADED:-0}" == "1" ]]; then
  echo "DEGRADED: audit could not fully scan: $(IFS='; '; echo "${degraded_reasons[*]}")" >&2
  exit 3
fi
exit 0
