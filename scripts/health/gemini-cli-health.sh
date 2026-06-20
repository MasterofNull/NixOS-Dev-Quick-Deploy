#!/usr/bin/env bash
# DEPRECATED (2026-06-20): delegate-to-gemini (npm CLI) is retired.
# Use scripts/health/antigravity-health.sh for the current delegation path.
# This script is kept for historical reference only and will not succeed
# because the gemini npm CLI auth is broken (credits exhausted, OAuth sunset).
#
# Check and optionally repair Gemini CLI state-directory corruption that causes
# `gemini --help` to hang under the real home directory.
#
# Usage:
#   scripts/health/gemini-cli-health.sh --check
#   scripts/health/gemini-cli-health.sh --repair
#   scripts/health/gemini-cli-health.sh --check --json
#
# Exit codes:
#   0 healthy
#   1 degraded / unhealthy
#   2 repaired successfully
#   3 usage error
#   4 repair attempted but failed

set -euo pipefail

MODE="check"
JSON_OUTPUT=0
# gemini --help takes ~39s on the current host with the live state directory.
# Keep the default above observed latency so the health check measures hangs,
# not ordinary startup cost.
HELP_TIMEOUT_SECONDS="${GEMINI_HEALTH_TIMEOUT_SECONDS:-45}"
PRIMARY_HOME="${AQ_PRIMARY_HOME:-${HOME:-}}"
PRIMARY_USER="${AQ_PRIMARY_USER:-${USER:-}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      MODE="check"
      ;;
    --repair)
      MODE="repair"
      ;;
    --json)
      JSON_OUTPUT=1
      ;;
    --help|-h)
      cat <<'EOF'
Usage: gemini-cli-health.sh [--check|--repair] [--json]
EOF
      exit 0
      ;;
    *)
      printf 'ERROR: unknown argument: %s\n' "$1" >&2
      exit 3
      ;;
  esac
  shift
done

GEMINI_BIN="$(command -v gemini 2>/dev/null || true)"
GEMINI_DIR="${PRIMARY_HOME}/.gemini"
BACKUP_PATH=""
STATUS="unknown"
REASON=""

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().rstrip("\n")))' <<<"${1:-}"
}

emit_result() {
  local exit_code="$1"
  if [[ "${JSON_OUTPUT}" -eq 1 ]]; then
    printf '{'
    printf '"status":%s,' "$(json_escape "${STATUS}")"
    printf '"mode":%s,' "$(json_escape "${MODE}")"
    printf '"reason":%s,' "$(json_escape "${REASON}")"
    printf '"gemini_bin":%s,' "$(json_escape "${GEMINI_BIN}")"
    printf '"gemini_dir":%s,' "$(json_escape "${GEMINI_DIR}")"
    printf '"backup_path":%s' "$(json_escape "${BACKUP_PATH}")"
    printf '}\n'
  else
    printf 'status=%s\n' "${STATUS}"
    printf 'reason=%s\n' "${REASON}"
    printf 'gemini_bin=%s\n' "${GEMINI_BIN}"
    printf 'gemini_dir=%s\n' "${GEMINI_DIR}"
    if [[ -n "${BACKUP_PATH}" ]]; then
      printf 'backup_path=%s\n' "${BACKUP_PATH}"
    fi
  fi
  exit "${exit_code}"
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    STATUS="unhealthy"
    REASON="missing dependency: ${cmd}"
    emit_result 1
  fi
}

gemini_help_ok() {
  env \
    HOME="${PRIMARY_HOME}" \
    USER="${PRIMARY_USER}" \
    LOGNAME="${PRIMARY_USER}" \
    GEMINI_CLI_NO_RELAUNCH=1 \
    GEMINI_SANDBOX=false \
    timeout --foreground "${HELP_TIMEOUT_SECONDS}" "${GEMINI_BIN}" --help >/dev/null 2>&1
}

copied_state_help_ok() {
  local temp_home temp_state
  temp_home="$(mktemp -d)"
  trap 'rm -rf "${temp_home}"' RETURN
  temp_state="${temp_home}/.gemini"
  mkdir -p "${temp_state}"
  if [[ -d "${GEMINI_DIR}" ]]; then
    # Only copy the minimal state needed to exercise Gemini startup.  The
    # history/tmp trees can grow to multiple GiB and are irrelevant to `--help`;
    # copying them into tmpfs made this health check capable of exhausting /tmp.
    local state_file
    for state_file in \
      google_accounts.json \
      oauth_creds.json \
      projects.json \
      settings.json \
      state.json \
      trustedFolders.json
    do
      if [[ -f "${GEMINI_DIR}/${state_file}" ]]; then
        cp -a "${GEMINI_DIR}/${state_file}" "${temp_state}/"
      fi
    done
  fi
  env \
    HOME="${temp_home}" \
    USER="${PRIMARY_USER}" \
    LOGNAME="${PRIMARY_USER}" \
    GEMINI_CLI_NO_RELAUNCH=1 \
    GEMINI_SANDBOX=false \
    timeout --foreground "${HELP_TIMEOUT_SECONDS}" "${GEMINI_BIN}" --help >/dev/null 2>&1
  local status=$?
  return "${status}"
}

repair_state_dir() {
  local stamp
  stamp="$(date +%Y%m%d-%H%M%S)"
  BACKUP_PATH="${GEMINI_DIR}.pre-repair-${stamp}"
  mv "${GEMINI_DIR}" "${BACKUP_PATH}"
  cp -a "${BACKUP_PATH}" "${GEMINI_DIR}"
}

require_cmd timeout

if [[ -z "${GEMINI_BIN}" ]]; then
  STATUS="unhealthy"
  REASON="gemini CLI not found in PATH"
  emit_result 1
fi

if [[ -z "${PRIMARY_HOME}" ]]; then
  STATUS="unhealthy"
  REASON="HOME is not set"
  emit_result 1
fi

if [[ ! -d "${GEMINI_DIR}" ]]; then
  STATUS="healthy"
  REASON="no ${GEMINI_DIR} state directory present"
  emit_result 0
fi

# Detect oauth-personal auth type — sunset 2026-06-18, always fails on
# cloudcode-pa.googleapis.com/v1internal:onboardUser with "Resource has been
# exhausted". Report unhealthy immediately so callers don't waste a delegation.
SETTINGS_FILE="${GEMINI_DIR}/settings.json"
if [[ -f "${SETTINGS_FILE}" ]]; then
  SELECTED_TYPE="$(python3 -c "
import json, sys
try:
    d = json.load(open('${SETTINGS_FILE}'))
    print(d.get('security', {}).get('auth', {}).get('selectedType', ''))
except Exception:
    pass
" 2>/dev/null || true)"
  if [[ "${SELECTED_TYPE}" == "oauth-personal" ]]; then
    STATUS="unhealthy"
    REASON="auth.selectedType=oauth-personal: cloudcode-pa.googleapis.com sunset 2026-06-18. Fix: run 'gemini' interactively with GEMINI_API_KEY set from https://aistudio.google.com/apikey"
    emit_result 1
  fi
fi

if gemini_help_ok; then
  STATUS="healthy"
  REASON="gemini --help succeeds with live state directory"
  emit_result 0
fi

if copied_state_help_ok; then
  STATUS="degraded"
  REASON="live ${GEMINI_DIR} appears corrupted; copied state succeeds"
  if [[ "${MODE}" == "repair" ]]; then
    repair_state_dir
    if gemini_help_ok; then
      STATUS="repaired"
      REASON="rebuilt live ${GEMINI_DIR} from a clean copy"
      emit_result 2
    fi
    STATUS="unhealthy"
    REASON="repair attempted but gemini --help still fails"
    emit_result 4
  fi
  emit_result 1
fi

STATUS="unhealthy"
REASON="gemini --help fails for both live and copied state"
emit_result 1
