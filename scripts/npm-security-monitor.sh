#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${NPM_SECURITY_OUTPUT_DIR:-${HOME}/.local/share/nixos-ai-stack/security/npm}"
LOOKBACK_HOURS="${NPM_SECURITY_LOG_LOOKBACK_HOURS:-24}"
FAIL_ON_HIGH="${NPM_SECURITY_FAIL_ON_HIGH:-false}"
RESPONSE_MODE="${NPM_SECURITY_RESPONSE_MODE:-report}"
REGISTRY_ALLOWLIST="${NPM_SECURITY_REGISTRY_ALLOWLIST:-https://registry.npmjs.org/}"
THREAT_INTEL_FILE="${NPM_SECURITY_THREAT_INTEL_FILE:-config/security/npm-threat-intel.json}"
quarantine_state_env_set="${NPM_SECURITY_QUARANTINE_STATE_FILE+set}"
incident_log_env_set="${NPM_SECURITY_INCIDENT_LOG_FILE+set}"
QUARANTINE_STATE_FILE="${NPM_SECURITY_QUARANTINE_STATE_FILE:-}"
INCIDENT_LOG_FILE="${NPM_SECURITY_INCIDENT_LOG_FILE:-}"

usage() {
  cat <<'EOF'
Usage: scripts/npm-security-monitor.sh [--repo-root PATH] [--output-dir PATH]

Performs npm supply-chain monitoring:
  - npm audit (high/critical)
  - lockfile hygiene checks
  - lifecycle install-script risk scan
  - remote dependency spec detection (git/http/file/link/github)
  - npm config posture checks (registry, ignore-scripts, audit, prefix perms)
  - suspicious npm log pattern scan
  - known-attack IOC matching from threat-intel file

Writes:
  npm-security-YYYY-MM-DDTHHMMSSZ.json
  latest-npm-security.json
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

# Resolve dependent writable paths after repo/output overrides have been parsed.
if [[ -z "${quarantine_state_env_set}" || -z "${QUARANTINE_STATE_FILE}" ]]; then
  QUARANTINE_STATE_FILE="${OUTPUT_DIR}/quarantine-state.json"
fi
if [[ -z "${incident_log_env_set}" || -z "${INCIDENT_LOG_FILE}" ]]; then
  INCIDENT_LOG_FILE="${OUTPUT_DIR}/incidents.jsonl"
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 2
  fi
}

require_cmd jq
require_cmd npm
require_cmd find
require_cmd stat
require_cmd python3

mkdir -p "${OUTPUT_DIR}"
ts_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ts_file="$(date -u +%Y%m%dT%H%M%SZ)"
report_file="${OUTPUT_DIR}/npm-security-${ts_file}.json"
latest_file="${OUTPUT_DIR}/latest-npm-security.json"
tmp_root="$(mktemp -d)"
trap 'rm -rf "${tmp_root}"' EXIT

mapfile -t package_files < <(find "${REPO_ROOT}" -type f -name 'package.json' \
  -not -path '*/node_modules/*' \
  -not -path '*/archive/*' \
  -not -path '*/.git/*' | sort)

project_reports="${tmp_root}/projects.jsonl"
touch "${project_reports}"

total_projects=0
projects_with_lock=0
projects_without_lock=0
total_high=0
total_critical=0
total_remote_specs=0
total_suspicious_scripts=0
total_ioc_package_exact=0
total_ioc_package_pattern=0
total_ioc_script_pattern=0

if [[ "${THREAT_INTEL_FILE}" != /* ]]; then
  THREAT_INTEL_FILE="${REPO_ROOT}/${THREAT_INTEL_FILE}"
fi

# Backward-compatible behavior: failOnHigh=true upgrades report mode to fail.
if [[ "${FAIL_ON_HIGH}" == "true" && "${RESPONSE_MODE}" == "report" ]]; then
  RESPONSE_MODE="fail"
fi

case "${RESPONSE_MODE}" in
  report|fail|quarantine) ;;
  *)
    echo "Invalid NPM_SECURITY_RESPONSE_MODE='${RESPONSE_MODE}', using 'report'" >&2
    RESPONSE_MODE="report"
    ;;
esac

threat_intel_loaded=false
if [[ -r "${THREAT_INTEL_FILE}" ]]; then
  threat_intel_loaded=true
fi

for package_file in "${package_files[@]}"; do
  total_projects=$((total_projects + 1))
  dir="$(dirname "${package_file}")"
  rel="${dir#"${REPO_ROOT}/"}"
  [[ "${rel}" == "${dir}" ]] && rel="."
  lock_file="${dir}/package-lock.json"
  has_lock=false
  lock_ver=0
  high=0
  critical=0
  audit_error=""

  if [[ -f "${lock_file}" ]]; then
    has_lock=true
    projects_with_lock=$((projects_with_lock + 1))
    lock_ver="$(jq -r '.lockfileVersion // 0' "${lock_file}" 2>/dev/null || echo 0)"
    out_json="${tmp_root}/audit-${total_projects}.json"
    set +e
    (cd "${dir}" && npm audit --omit=dev --json > "${out_json}" 2>"${out_json}.stderr")
    rc=$?
    set -e
    if [[ ${rc} -ne 0 && ${rc} -ne 1 ]]; then
      audit_error="$(cat "${out_json}.stderr" 2>/dev/null || true)"
      jq -n --arg e "${audit_error}" \
        '{metadata:{vulnerabilities:{high:0,critical:0}},error:$e}' > "${out_json}"
    fi
    high="$(jq '.metadata.vulnerabilities.high // 0' "${out_json}")"
    critical="$(jq '.metadata.vulnerabilities.critical // 0' "${out_json}")"
  else
    projects_without_lock=$((projects_without_lock + 1))
  fi

  total_high=$((total_high + high))
  total_critical=$((total_critical + critical))

  lifecycle_json="$(jq -c '
    .scripts // {}
    | {
        preinstall: (.preinstall // ""),
        install: (.install // ""),
        postinstall: (.postinstall // ""),
        prepare: (.prepare // "")
      }' "${package_file}" 2>/dev/null || echo '{}')"

  suspicious_lifecycle_count="$(printf '%s\n' "${lifecycle_json}" | python3 - <<'PY'
import json, re, sys
try:
    scripts = json.load(sys.stdin)
except Exception:
    print(0)
    raise SystemExit(0)
patterns = [
    r"\bcurl\b", r"\bwget\b", r"\bnc\b", r"/dev/tcp/",
    r"\bpython\s+-c\b", r"\bnode\s+-e\b", r"\bbash\s+-c\b",
    r"\bpowershell\b", r"\beval\s*\(", r"\bbase64\s+-d\b",
]
count = 0
for _, value in scripts.items():
    text = str(value or "").lower()
    if any(re.search(p, text) for p in patterns):
        count += 1
print(count)
PY
)"
  total_suspicious_scripts=$((total_suspicious_scripts + suspicious_lifecycle_count))

  remote_specs="$(jq -r '
    [
      (.dependencies // {}),
      (.devDependencies // {}),
      (.optionalDependencies // {}),
      (.peerDependencies // {})
    ]
    | map(to_entries) | add
    | map(select((.value|type) == "string"))
    | map(select(.value | test("^(git\\+|https?://|file:|link:|github:)")))
    | length
  ' "${package_file}" 2>/dev/null || echo 0)"
  total_remote_specs=$((total_remote_specs + remote_specs))

  ioc_json="$(python3 - <<'PY' "${package_file}" "${THREAT_INTEL_FILE}" "${threat_intel_loaded}"
import json
import re
import sys
from pathlib import Path

pkg_path = Path(sys.argv[1])
intel_path = Path(sys.argv[2])
intel_enabled = (sys.argv[3].lower() == "true")

out = {
    "package_exact_hits": 0,
    "package_pattern_hits": 0,
    "script_pattern_hits": 0,
    "package_matches": [],
    "script_matches": [],
}

if not intel_enabled:
    print(json.dumps(out))
    raise SystemExit(0)

try:
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    intel = json.loads(intel_path.read_text(encoding="utf-8"))
except Exception:
    print(json.dumps(out))
    raise SystemExit(0)

deps = {}
for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
    value = pkg.get(key) or {}
    if isinstance(value, dict):
        deps.update(value)

blocked = {str(x).strip().lower() for x in intel.get("blockedPackageNames", []) if str(x).strip()}
patts = [str(x) for x in intel.get("suspiciousPackageNamePatterns", []) if str(x).strip()]
script_patts = [str(x) for x in intel.get("suspiciousScriptPatterns", []) if str(x).strip()]

for name in deps.keys():
    lname = str(name).strip().lower()
    if lname in blocked:
        out["package_exact_hits"] += 1
        out["package_matches"].append({"name": name, "reason": "blocked_exact"})
        continue
    for patt in patts:
        try:
            if re.search(patt, lname):
                out["package_pattern_hits"] += 1
                out["package_matches"].append({"name": name, "reason": f"pattern:{patt}"})
                break
        except re.error:
            continue

scripts = pkg.get("scripts") or {}
if isinstance(scripts, dict):
    for key, value in scripts.items():
        text = str(value or "")
        for patt in script_patts:
            try:
                if re.search(patt, text, flags=re.IGNORECASE):
                    out["script_pattern_hits"] += 1
                    out["script_matches"].append({"script": key, "reason": f"pattern:{patt}"})
                    break
            except re.error:
                continue

print(json.dumps(out, separators=(",", ":")))
PY
)"
  ioc_pkg_exact="$(jq -r '.package_exact_hits // 0' <<<"${ioc_json}")"
  ioc_pkg_pattern="$(jq -r '.package_pattern_hits // 0' <<<"${ioc_json}")"
  ioc_script_pattern="$(jq -r '.script_pattern_hits // 0' <<<"${ioc_json}")"
  total_ioc_package_exact=$((total_ioc_package_exact + ioc_pkg_exact))
  total_ioc_package_pattern=$((total_ioc_package_pattern + ioc_pkg_pattern))
  total_ioc_script_pattern=$((total_ioc_script_pattern + ioc_script_pattern))

  jq -n \
    --arg path "${rel}" \
    --argjson has_lock "$( [[ "${has_lock}" == true ]] && echo true || echo false )" \
    --argjson lockfile_version "${lock_ver}" \
    --argjson high "${high}" \
    --argjson critical "${critical}" \
    --arg audit_error "${audit_error}" \
    --argjson suspicious_lifecycle "${suspicious_lifecycle_count}" \
    --argjson remote_specs "${remote_specs}" \
    --argjson lifecycle_scripts "${lifecycle_json}" \
    --argjson ioc "${ioc_json}" \
    '{
      project: $path,
      lockfile: { present: $has_lock, version: $lockfile_version },
      vulnerabilities: { high: $high, critical: $critical },
      suspicious_lifecycle_scripts: $suspicious_lifecycle,
      remote_dependency_specs: $remote_specs,
      attack_ioc: $ioc,
      lifecycle_scripts: $lifecycle_scripts,
      audit_error: (if ($audit_error|length) > 0 then $audit_error else null end)
    }' >> "${project_reports}"
done

npm_registry="$(npm config get registry 2>/dev/null || echo "unknown")"
npm_ignore_scripts="$(npm config get ignore-scripts 2>/dev/null || echo "unknown")"
npm_audit_cfg="$(npm config get audit 2>/dev/null || echo "unknown")"
npm_prefix="$(npm config get prefix 2>/dev/null || echo "")"
prefix_mode=""
prefix_world_writable=false
if [[ -n "${npm_prefix}" && -e "${npm_prefix}" ]]; then
  prefix_mode="$(stat -c '%a' "${npm_prefix}" 2>/dev/null || echo "")"
  if [[ -n "${prefix_mode}" ]]; then
    other_bits="${prefix_mode: -1}"
    if [[ "${other_bits}" =~ [2367] ]]; then
      prefix_world_writable=true
    fi
  fi
fi

log_matches_file="${tmp_root}/npm-log-matches.txt"
log_matches_unique_file="${tmp_root}/npm-log-matches-unique.txt"
lookback_minutes=$((LOOKBACK_HOURS * 60))
if [[ -d "${HOME}/.npm/_logs" ]]; then
  find "${HOME}/.npm/_logs" -type f -name '*.log' -mmin "-${lookback_minutes}" -print0 \
    | xargs -0 -r rg -n -i \
      "curl\\s+.*\\|\\s*(bash|sh)|wget\\s+.*\\|\\s*(bash|sh)|node\\s+-e|python\\s+-c|bash\\s+-c|/dev/tcp/|\\bnc\\s+-e\\b|\\bchmod\\s+\\+s\\b" \
      > "${log_matches_file}" || true
else
  : > "${log_matches_file}"
fi
# De-noise repetitive npm log entries by counting unique matched payload lines.
awk -F: '
  {
    line = $0
    sub(/^[^:]*:[0-9]+:/, "", line)
    gsub(/[[:space:]]+/, " ", line)
    if (length(line) > 0) print line
  }
' "${log_matches_file}" | sort -u > "${log_matches_unique_file}"
suspicious_log_lines="$(wc -l < "${log_matches_unique_file}" | tr -d '[:space:]')"

critical_findings=0
high_findings=0
medium_findings=0

if [[ "${npm_registry}" != "${REGISTRY_ALLOWLIST}" ]]; then
  critical_findings=$((critical_findings + 1))
fi
if [[ ${total_critical} -gt 0 ]]; then
  critical_findings=$((critical_findings + total_critical))
fi
if [[ ${total_high} -gt 0 ]]; then
  high_findings=$((high_findings + total_high))
fi
if [[ ${projects_without_lock} -gt 0 ]]; then
  high_findings=$((high_findings + projects_without_lock))
fi
if [[ ${total_suspicious_scripts} -gt 0 ]]; then
  high_findings=$((high_findings + total_suspicious_scripts))
fi
if [[ ${total_remote_specs} -gt 0 ]]; then
  medium_findings=$((medium_findings + total_remote_specs))
fi
if [[ "${threat_intel_loaded}" != "true" ]]; then
  high_findings=$((high_findings + 1))
fi
if [[ ${total_ioc_package_exact} -gt 0 ]]; then
  critical_findings=$((critical_findings + total_ioc_package_exact))
fi
if [[ ${total_ioc_package_pattern} -gt 0 ]]; then
  high_findings=$((high_findings + total_ioc_package_pattern))
fi
if [[ ${total_ioc_script_pattern} -gt 0 ]]; then
  high_findings=$((high_findings + total_ioc_script_pattern))
fi
if [[ "${npm_ignore_scripts}" == "false" ]]; then
  medium_findings=$((medium_findings + 1))
fi
if [[ "${npm_audit_cfg}" == "false" ]]; then
  medium_findings=$((medium_findings + 1))
fi
if [[ "${prefix_world_writable}" == "true" ]]; then
  medium_findings=$((medium_findings + 1))
fi
if [[ ${suspicious_log_lines} -gt 0 ]]; then
  medium_findings=$((medium_findings + 1))
fi

status="ok"
if [[ ${critical_findings} -gt 0 || ${high_findings} -gt 0 || ${medium_findings} -gt 0 ]]; then
  status="findings"
fi

jq -n \
  --arg generated_at "${ts_iso}" \
  --arg repo_root "${REPO_ROOT}" \
  --arg status "${status}" \
  --arg npm_registry "${npm_registry}" \
  --arg npm_ignore_scripts "${npm_ignore_scripts}" \
  --arg npm_audit_cfg "${npm_audit_cfg}" \
  --arg npm_prefix "${npm_prefix}" \
  --arg prefix_mode "${prefix_mode}" \
  --argjson prefix_world_writable "${prefix_world_writable}" \
  --argjson total_projects "${total_projects}" \
  --argjson projects_with_lock "${projects_with_lock}" \
  --argjson projects_without_lock "${projects_without_lock}" \
  --argjson total_high "${total_high}" \
  --argjson total_critical "${total_critical}" \
  --argjson total_remote_specs "${total_remote_specs}" \
  --argjson total_suspicious_scripts "${total_suspicious_scripts}" \
  --argjson total_ioc_package_exact "${total_ioc_package_exact}" \
  --argjson total_ioc_package_pattern "${total_ioc_package_pattern}" \
  --argjson total_ioc_script_pattern "${total_ioc_script_pattern}" \
  --argjson suspicious_log_lines "${suspicious_log_lines}" \
  --argjson critical_findings "${critical_findings}" \
  --argjson high_findings "${high_findings}" \
  --argjson medium_findings "${medium_findings}" \
  --arg threat_intel_file "${THREAT_INTEL_FILE}" \
  --argjson threat_intel_loaded "$( [[ "${threat_intel_loaded}" == "true" ]] && echo true || echo false )" \
  --argjson projects "$(jq -s . "${project_reports}")" \
  --arg response_mode "${RESPONSE_MODE}" \
  --arg quarantine_state_file "${QUARANTINE_STATE_FILE}" \
  --arg incident_log_file "${INCIDENT_LOG_FILE}" \
  --argjson suspicious_log_samples "$(head -n 30 "${log_matches_unique_file}" | jq -R . | jq -s .)" \
  '{
    generated_at: $generated_at,
    repo_root: $repo_root,
    status: $status,
    severity_counts: {
      critical: $critical_findings,
      high: $high_findings,
      medium: $medium_findings
    },
    npm_config: {
      registry: $npm_registry,
      ignore_scripts: $npm_ignore_scripts,
      audit: $npm_audit_cfg,
      prefix: $npm_prefix,
      prefix_mode: $prefix_mode,
      prefix_world_writable: $prefix_world_writable
    },
    summary: {
      projects_total: $total_projects,
      projects_with_lockfile: $projects_with_lock,
      projects_without_lockfile: $projects_without_lock,
      vulnerabilities_high: $total_high,
      vulnerabilities_critical: $total_critical,
      remote_dependency_specs: $total_remote_specs,
      suspicious_lifecycle_scripts: $total_suspicious_scripts,
      ioc_package_exact_hits: $total_ioc_package_exact,
      ioc_package_pattern_hits: $total_ioc_package_pattern,
      ioc_script_pattern_hits: $total_ioc_script_pattern,
      suspicious_npm_log_lines: $suspicious_log_lines
    },
    threat_intel: {
      file: $threat_intel_file,
      loaded: $threat_intel_loaded
    },
    response: {
      mode: $response_mode,
      quarantine_state_file: $quarantine_state_file,
      incident_log_file: $incident_log_file
    },
    projects: $projects,
    suspicious_log_samples: $suspicious_log_samples
  }' > "${report_file}"

cp "${report_file}" "${latest_file}"
echo "npm security report written: ${report_file}"
echo "latest npm security report: ${latest_file}"

# Emit incident record for downstream ingestion and operator visibility.
mkdir -p "$(dirname "${INCIDENT_LOG_FILE}")" "$(dirname "${QUARANTINE_STATE_FILE}")"
has_high_or_critical=false
if [[ $((critical_findings + high_findings)) -gt 0 ]]; then
  has_high_or_critical=true
fi

incident_json="$(jq -c -n \
  --arg generated_at "${ts_iso}" \
  --arg status "${status}" \
  --arg response_mode "${RESPONSE_MODE}" \
  --arg report_file "${report_file}" \
  --argjson has_high_or_critical "$( [[ "${has_high_or_critical}" == "true" ]] && echo true || echo false )" \
  --argjson critical "${critical_findings}" \
  --argjson high "${high_findings}" \
  --argjson medium "${medium_findings}" \
  --argjson ioc_exact "${total_ioc_package_exact}" \
  --argjson ioc_pattern "${total_ioc_package_pattern}" \
  --argjson ioc_script "${total_ioc_script_pattern}" \
  '{
    generated_at: $generated_at,
    category: "npm_supply_chain_security",
    status: $status,
    response_mode: $response_mode,
    has_high_or_critical: $has_high_or_critical,
    severity_counts: { critical: $critical, high: $high, medium: $medium },
    ioc_summary: {
      package_exact_hits: $ioc_exact,
      package_pattern_hits: $ioc_pattern,
      script_pattern_hits: $ioc_script
    },
    report_file: $report_file
  }')"
printf '%s\n' "${incident_json}" >> "${INCIDENT_LOG_FILE}"

if [[ "${RESPONSE_MODE}" == "quarantine" ]]; then
  if [[ "${has_high_or_critical}" == "true" ]]; then
    jq -n \
      --arg generated_at "${ts_iso}" \
      --arg status "active" \
      --arg reason "npm high/critical findings detected" \
      --arg report_file "${report_file}" \
      --argjson critical "${critical_findings}" \
      --argjson high "${high_findings}" \
      --argjson medium "${medium_findings}" \
      '{
        generated_at: $generated_at,
        status: $status,
        reason: $reason,
        report_file: $report_file,
        severity_counts: {critical: $critical, high: $high, medium: $medium}
      }' > "${QUARANTINE_STATE_FILE}"
    echo "npm security quarantine activated: ${QUARANTINE_STATE_FILE}" >&2
    exit 1
  else
    jq -n \
      --arg generated_at "${ts_iso}" \
      --arg status "clear" \
      --arg reason "no npm high/critical findings in latest run" \
      --arg report_file "${report_file}" \
      --argjson critical "${critical_findings}" \
      --argjson high "${high_findings}" \
      --argjson medium "${medium_findings}" \
      '{
        generated_at: $generated_at,
        status: $status,
        reason: $reason,
        report_file: $report_file,
        severity_counts: {critical: $critical, high: $high, medium: $medium}
      }' > "${QUARANTINE_STATE_FILE}"
  fi
fi

if [[ "${RESPONSE_MODE}" == "fail" && "${has_high_or_critical}" == "true" ]]; then
  echo "npm security monitor detected high/critical findings (response-mode=fail)." >&2
  exit 1
fi

exit 0
