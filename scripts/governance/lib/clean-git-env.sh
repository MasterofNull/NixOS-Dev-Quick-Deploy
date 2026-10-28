#!/usr/bin/env bash
# Launch test/QA subprocesses with the repository-locating GIT_* variables removed.
# Git hooks export GIT_DIR/GIT_INDEX_FILE/GIT_WORK_TREE; a test that git-inits a temp
# repo while they are set operates on the REAL repository (2026-10-28 incident).
# Use only for test/QA launches; the gate's own staged-file git calls keep GIT_*.
# Usage: source this file, then `clean_git_env_run <cmd> [args...]`.
# Keep the variable list in sync with scripts/governance/lib/clean_git_env.py.
CLEAN_GIT_ENV_VARS=(
  GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY
  GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_PREFIX GIT_NAMESPACE
  GIT_CEILING_DIRECTORIES
)

clean_git_env_run() {
  local -a unset_args=() v
  for v in "${CLEAN_GIT_ENV_VARS[@]}"; do unset_args+=(-u "$v"); done
  env "${unset_args[@]}" "$@"
}
