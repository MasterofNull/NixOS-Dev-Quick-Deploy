#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOOKS_DIR="${REPO_ROOT}/.githooks"

if [[ ! -d "${HOOKS_DIR}" ]]; then
  printf 'missing hooks directory: %s\n' "${HOOKS_DIR}" >&2
  exit 1
fi

chmod +x "${HOOKS_DIR}"/*
git -C "${REPO_ROOT}" config core.hooksPath "${HOOKS_DIR}"

printf 'Installed git hooks from %s\n' "${HOOKS_DIR}"
printf 'Active hooksPath: %s\n' "$(git -C "${REPO_ROOT}" config core.hooksPath)"
