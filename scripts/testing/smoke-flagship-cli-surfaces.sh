#!/usr/bin/env bash
set -euo pipefail

# Smoke-test flagship agent CLI surfaces that are either declarative or
# explicitly classified as external-but-integrated.

# Extend PATH with common install locations for npm-global CLIs
export PATH="${HOME}/.npm-global/bin:${HOME}/.local/bin:${HOME}/.nix-profile/bin:${PATH}"

commands=(cn codex qwen gemini claude pi)

for cmd in "${commands[@]}"; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    printf 'FAIL: %s missing from PATH\n' "${cmd}" >&2
    exit 1
  fi
  if ! "${cmd}" --help >/dev/null 2>&1; then
    printf 'FAIL: %s --help failed\n' "${cmd}" >&2
    exit 1
  fi
done

printf 'PASS: flagship CLI surfaces respond to --help\n'
