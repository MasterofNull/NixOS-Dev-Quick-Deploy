#!/usr/bin/env bash
# Resolve the shared delegation dir from the repo's MAIN worktree so scripts
# run from a git worktree share one registry/outputs/budget ledger.
# Usage: DELEGATION_DIR="${AQ_DELEGATION_DIR:-$(resolve_delegation_dir "$SCRIPT_DIR")}"
resolve_delegation_dir() {
    local script_dir="$1" common
    if common="$(git -C "$script_dir" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" && [[ -n "$common" ]]; then
        printf '%s\n' "$(dirname "$common")/.agents/delegation"
        return 0
    fi
    echo "WARN: git unavailable; delegation dir falls back to script-relative path" >&2
    printf '%s\n' "$(cd "$script_dir/../.." && pwd)/.agents/delegation"
}
