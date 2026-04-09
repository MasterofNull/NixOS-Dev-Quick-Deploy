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

run_help_smoke() {
  local cmd="$1"
  if [[ "${cmd}" == "gemini" ]]; then
    # Gemini CLI does expensive per-user cleanup during startup before
    # argument handling. Use an isolated HOME so the smoke checks CLI
    # responsiveness rather than local session-history cleanup cost.
    env \
      HOME=/tmp \
      GEMINI_CLI_NO_RELAUNCH=1 \
      GEMINI_SANDBOX=false \
      PATH="${PATH}" \
      timeout --foreground "${help_timeout}" "${cmd}" --help >/dev/null 2>&1
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
    else
      printf 'FAIL: %s --help failed\n' "${cmd}" >&2
    fi
    exit 1
  fi
done

printf 'PASS: flagship CLI surfaces respond to --help\n'
