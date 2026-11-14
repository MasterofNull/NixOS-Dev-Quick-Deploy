#!/usr/bin/env bash
# Resolve the shared delegation dir from the repo's MAIN worktree so scripts
# run from a git worktree share one registry/outputs/budget ledger.
# Usage: DELEGATION_DIR="${AQ_DELEGATION_DIR:-$(resolve_delegation_dir "$SCRIPT_DIR")}"
# A derived path under /tmp, /var/tmp or /dev/shm is wiped by a reboot (it took an accepted design once): refuse it.
# An explicit AQ_DELEGATION_DIR is the caller's choice; AQ_ALLOW_VOLATILE_DIR=1 permits a derived one (tests).
resolve_delegation_dir() {
    local d
    d="$(_resolve_delegation_dir_raw "$1")" || return 1
    case "$d" in
        /tmp|/tmp/*|/var/tmp|/var/tmp/*|/dev/shm|/dev/shm/*)
            if [[ "${AQ_ALLOW_VOLATILE_DIR:-}" != 1 ]]; then
                echo "ERROR: delegation dir $d is under a volatile path (wiped on reboot); use a repo outside /tmp or set AQ_DELEGATION_DIR" >&2
                return 1
            fi ;;
    esac
    printf '%s\n' "$d"
}
_resolve_delegation_dir_raw() {
    local script_dir="$1" common
    if common="$(git -C "$script_dir" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" && [[ -n "$common" ]]; then
        printf '%s\n' "$(dirname "$common")/.agents/delegation"
        return 0
    fi
    echo "WARN: git unavailable; delegation dir falls back to script-relative path" >&2
    printf '%s\n' "$(cd "$script_dir/../.." && pwd)/.agents/delegation"
}
