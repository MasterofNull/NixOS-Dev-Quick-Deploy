#!/usr/bin/env bash
# Resolve the shared delegation dir from the repo's MAIN worktree so scripts
# run from a git worktree share one registry/outputs/budget ledger.
# Usage: DELEGATION_DIR="${AQ_DELEGATION_DIR:-$(resolve_delegation_dir "$SCRIPT_DIR")}"
# A derived path under /tmp, /var/tmp or /dev/shm is wiped by a reboot (it took an accepted design once): refuse it.
# An explicit AQ_DELEGATION_DIR is the caller's choice; AQ_ALLOW_VOLATILE_DIR=1 permits a derived one (tests).
resolve_delegation_dir() {
    local d
    d="$(_resolve_delegation_dir_raw "$1")" || return 1
    d="$(realpath -m -- "$d")" || return 1
    case "$d" in
        /tmp|/tmp/*|/var/tmp|/var/tmp/*|/dev/shm|/dev/shm/*)
            if [[ "${AQ_ALLOW_VOLATILE_DIR:-}" != 1 ]]; then
                echo "ERROR: delegation dir $d is under a volatile path (wiped on reboot); place work artifacts under .agents/delegation/ in a durable repo" >&2
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

_durable_path_is_volatile() {
    case "$1" in
        /tmp|/tmp/*|/var/tmp|/var/tmp/*|/dev/shm|/dev/shm/*) return 0 ;;
        *) return 1 ;;
    esac
}

validate_durable_artifact_path() {
    local path="$1" label="${2:-artifact}" delegation_dir="${3:-}" resolved root common main_root script_dir
    [[ "${AQ_ALLOW_VOLATILE_DIR:-}" == 1 ]] && return 0
    resolved="$(realpath -m -- "$path")" || return 1
    script_dir="${SCRIPT_DIR:-$(dirname "${BASH_SOURCE[0]}")/..}"
    if [[ -z "$delegation_dir" ]]; then
        delegation_dir="${AQ_DELEGATION_DIR:-$(resolve_delegation_dir "$script_dir")}" || return 1
    fi
    if ! _durable_path_is_volatile "$resolved"; then
        if common="$(git -C "$script_dir" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" && [[ -n "$common" ]]; then
            main_root="$(dirname "$common")"
        else
            main_root="$(cd "$script_dir/../.." && pwd)" || return 1
        fi
        for root in "$delegation_dir" "$main_root/.agents/plans" "${CLAUDE_CODE_TMPDIR:-$HOME/.local/state/claude-code/tmp}"; do
            root="$(realpath -m -- "$root")" || return 1
            _durable_path_is_volatile "$root" && continue
            case "$resolved" in
                "$root"|"$root"/*) return 0 ;;
            esac
        done
    fi
    printf 'ERROR: %s %s is outside durable work roots (wiped on reboot or untracked); place work artifacts under .agents/delegation/ (e.g. %s/outputs/) or ~/.local/state/claude-code/tmp\n' "$label" "$path" "$delegation_dir" >&2
    return 1
}
