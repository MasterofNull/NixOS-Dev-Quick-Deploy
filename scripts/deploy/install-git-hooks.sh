#!/usr/bin/env bash
# Installs the repo git hooks by setting core.hooksPath to the RELATIVE value `.githooks`.
# Relative resolves against each worktree's own tree; an absolute value pins every worktree to the
# primary checkout's hooks (tier0 check-lane-hook-parity GAP). Idempotent; also the self-heal used by
# aq-session-start (--quiet) when drift to an absolute or foreign value is detected.
set -euo pipefail

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HOOKS_DIR="${REPO_ROOT}/.githooks"

if [[ ! -d "${HOOKS_DIR}" ]]; then
  printf 'missing hooks directory: %s\n' "${HOOKS_DIR}" >&2
  exit 1
fi

# A relative hooksPath has no meaning without a work tree (it would resolve against $GIT_DIR).
if [[ "$(git -C "${REPO_ROOT}" rev-parse --is-bare-repository 2>/dev/null)" != "false" ]]; then
  printf 'refusing: %s is not a non-bare work tree; relative core.hooksPath needs one\n' "${REPO_ROOT}" >&2
  exit 1
fi

current="$(git -C "${REPO_ROOT}" config --local --get core.hooksPath 2>/dev/null || true)"
if [[ "${current}" != ".githooks" ]]; then
  find "${HOOKS_DIR}" -maxdepth 1 -type f ! -name README.md -exec chmod +x {} +
  git -C "${REPO_ROOT}" config --local core.hooksPath .githooks  # RELATIVE: each worktree uses its own tree's hooks
fi
# A per-worktree override would shadow the shared value.
if [[ "$(git -C "${REPO_ROOT}" config --local --get extensions.worktreeConfig 2>/dev/null || true)" == "true" ]]; then
  git -C "${REPO_ROOT}" config --worktree --unset core.hooksPath 2>/dev/null || true
fi

if [[ ${QUIET} -eq 0 ]]; then
  printf 'Installed git hooks from %s\n' "${HOOKS_DIR}"
  printf 'Active hooksPath: %s\n' "$(git -C "${REPO_ROOT}" config core.hooksPath)"
elif [[ "${current}" != ".githooks" ]]; then
  printf '[install-git-hooks] healed core.hooksPath: %s -> .githooks\n' "${current:-<unset>}" >&2
fi
