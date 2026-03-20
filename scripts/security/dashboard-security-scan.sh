#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=config/service-endpoints.sh
source "${ROOT_DIR}/config/service-endpoints.sh"

OUTPUT_DIR="${AI_SECURITY_AUDIT_DIR:-${HOME}/.local/share/nixos-ai-stack/security}"
DASHBOARD_SCAN_URL="${DASHBOARD_SCAN_URL:-${DASHBOARD_URL}}"
REPORT_PATH="${DASHBOARD_SECURITY_SCAN_REPORT_PATH:-${OUTPUT_DIR}/latest-dashboard-security-scan.json}"
TIMESTAMP="$(date -Iseconds)"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 2
  fi
}

usage() {
  cat <<'EOF'
Usage: scripts/security/dashboard-security-scan.sh [--url URL] [--output PATH]

Runs a lightweight dashboard/operator security scan:
  - root security headers
  - rate-limit headers
  - compliance endpoint availability
  - audit integrity endpoint availability

Writes JSON report to latest-dashboard-security-scan.json by default.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      DASHBOARD_SCAN_URL="${2:?missing value for --url}"
      shift 2
      ;;
    --output)
      REPORT_PATH="${2:?missing value for --output}"
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

require_cmd curl
require_cmd jq
require_cmd mktemp

mkdir -p "$(dirname "${REPORT_PATH}")"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

headers_file="${tmp_dir}/headers.txt"
root_url="${DASHBOARD_SCAN_URL%/}/"
compliance_url="${DASHBOARD_SCAN_URL%/}/api/insights/security/compliance"
integrity_url="${DASHBOARD_SCAN_URL%/}/api/audit/operator/integrity"

root_status="unavailable"
root_error=""
if curl -fsS -D "${headers_file}" -o /dev/null --max-time 10 "${root_url}" >/dev/null 2>"${tmp_dir}/root.stderr"; then
  root_status="ok"
else
  root_error="$(tr '\n' ' ' < "${tmp_dir}/root.stderr" | sed 's/[[:space:]]\+/ /g' | sed 's/^ //; s/ $//')"
fi

header_value() {
  local name="$1"
  awk -F': ' -v key="$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')" '
    BEGIN { IGNORECASE = 1 }
    tolower($1) == key { sub(/\r$/, "", $2); print $2; exit }
  ' "${headers_file}" 2>/dev/null || true
}

csp_value="$(header_value "content-security-policy")"
xfo_value="$(header_value "x-frame-options")"
nosniff_value="$(header_value "x-content-type-options")"
rate_limit_category="$(header_value "x-ratelimit-category")"
rate_limit_limit="$(header_value "x-ratelimit-limit")"
rate_limit_remaining="$(header_value "x-ratelimit-remaining")"

compliance_status="unavailable"
compliance_error=""
compliance_json='{}'
if compliance_json="$(curl -fsS --max-time 10 "${compliance_url}" 2>"${tmp_dir}/compliance.stderr")"; then
  compliance_status="ok"
else
  compliance_error="$(tr '\n' ' ' < "${tmp_dir}/compliance.stderr" | sed 's/[[:space:]]\+/ /g' | sed 's/^ //; s/ $//')"
  compliance_json='{}'
fi

integrity_status="unavailable"
integrity_error=""
integrity_json='{}'
if integrity_json="$(curl -fsS --max-time 10 "${integrity_url}" 2>"${tmp_dir}/integrity.stderr")"; then
  integrity_status="ok"
else
  integrity_error="$(tr '\n' ' ' < "${tmp_dir}/integrity.stderr" | sed 's/[[:space:]]\+/ /g' | sed 's/^ //; s/ $//')"
  integrity_json='{}'
fi

jq -n \
  --arg generated_at "${TIMESTAMP}" \
  --arg dashboard_url "${DASHBOARD_SCAN_URL%/}" \
  --arg root_status "${root_status}" \
  --arg root_error "${root_error}" \
  --arg compliance_status "${compliance_status}" \
  --arg compliance_error "${compliance_error}" \
  --arg integrity_status "${integrity_status}" \
  --arg integrity_error "${integrity_error}" \
  --arg csp_value "${csp_value}" \
  --arg xfo_value "${xfo_value}" \
  --arg nosniff_value "${nosniff_value}" \
  --arg rate_limit_category "${rate_limit_category}" \
  --arg rate_limit_limit "${rate_limit_limit}" \
  --arg rate_limit_remaining "${rate_limit_remaining}" \
  --argjson compliance "${compliance_json}" \
  --argjson integrity "${integrity_json}" \
  '
  {
    generated_at: $generated_at,
    target: $dashboard_url,
    status: (
      if ($root_status == "ok" and $compliance_status == "ok" and $integrity_status == "ok")
      then "ok"
      else "degraded"
      end
    ),
    checks: {
      root: {
        status: $root_status,
        error: (if $root_error == "" then null else $root_error end),
        headers: {
          content_security_policy: $csp_value,
          x_frame_options: $xfo_value,
          x_content_type_options: $nosniff_value,
          rate_limit_category: $rate_limit_category,
          rate_limit_limit: $rate_limit_limit,
          rate_limit_remaining: $rate_limit_remaining
        }
      },
      compliance: {
        status: $compliance_status,
        error: (if $compliance_error == "" then null else $compliance_error end),
        controls: ($compliance.controls // {}),
        audit_integrity: ($compliance.audit_integrity // {})
      },
      integrity: {
        status: $integrity_status,
        error: (if $integrity_error == "" then null else $integrity_error end),
        result: $integrity
      }
    },
    summary: {
      security_headers_present: (($csp_value != "") and ($xfo_value != "") and ($nosniff_value != "")),
      rate_limit_headers_present: (($rate_limit_category != "") and ($rate_limit_limit != "")),
      compliance_endpoint_ok: ($compliance_status == "ok"),
      audit_integrity_valid: ($integrity.valid // false)
    }
  }' > "${REPORT_PATH}"

echo "Dashboard security scan report written: ${REPORT_PATH}"
