#!/usr/bin/env bash
set -euo pipefail

# Smoke-test flagship agent CLI surfaces that are either declarative or
# explicitly classified as external-but-integrated.

primary_user="${AQ_PRIMARY_USER:-${SUDO_USER:-${USER:-$(id -un)}}}"
primary_home="${AQ_PRIMARY_HOME:-$(getent passwd "${primary_user}" 2>/dev/null | cut -d: -f6)}"
if [[ -n "${primary_home}" ]]; then
  export HOME="${primary_home}"
fi

# Extend PATH with common install locations for npm-global CLIs
export PATH="${HOME}/.npm-global/bin:${HOME}/.local/bin:${HOME}/.nix-profile/bin:${PATH}"

help_timeout="${AQ_FLAGSHIP_HELP_TIMEOUT_SECONDS:-8}"
commands=(cn codex qwen gemini claude pi)
gemini_health_script="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/health/gemini-cli-health.sh"

run_help_smoke() {
  local cmd="$1"
  if [[ "${cmd}" == "gemini" ]]; then
    AQ_PRIMARY_HOME="${HOME}" \
    AQ_PRIMARY_USER="${primary_user}" \
    GEMINI_HEALTH_TIMEOUT_SECONDS="${help_timeout}" \
    bash "${gemini_health_script}" --check >/dev/null 2>&1
    return $?
  fi
  timeout --foreground "${help_timeout}" "${cmd}" --help >/dev/null 2>&1
}

for cmd in "${commands[@]}"; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    printf 'FAIL: %s missing from PATH\n' "${cmd}" >&2
    exit 1
  fi
  if run_help_smoke "${cmd}"; then
    continue
  else
    status=$?
    if [[ "${status}" -eq 124 ]]; then
      printf 'FAIL: %s --help timed out after %ss\n' "${cmd}" "${help_timeout}" >&2
    elif [[ "${cmd}" == "gemini" ]]; then
      printf 'FAIL: gemini CLI health check failed; run scripts/health/gemini-cli-health.sh --check\n' >&2
    else
      printf 'FAIL: %s --help failed\n' "${cmd}" >&2
    fi
    exit 1
  fi
done

printf 'PASS: flagship CLI surfaces respond to --help\n'
