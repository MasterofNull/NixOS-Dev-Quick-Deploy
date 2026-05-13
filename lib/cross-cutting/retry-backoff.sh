#!/usr/bin/env bash
#
# Compatibility retry/backoff helpers used by unit tests and legacy callers.
#

if [[ -n "${_LIB_RETRY_BACKOFF_SH_LOADED:-}" ]]; then
    return 0
fi
_LIB_RETRY_BACKOFF_SH_LOADED=1

: "${MAX_RETRY_ATTEMPTS:=3}"
: "${RETRY_BASE_DELAY:=2}"
: "${RETRY_MAX_DELAY:=60}"
: "${CIRCUIT_BREAKER_THRESHOLD:=5}"

declare -gA _CIRCUIT_BREAKER_FAILURES=()

retry_with_backoff() {
    local attempts="${MAX_RETRY_ATTEMPTS}"
    local delay="${RETRY_BASE_DELAY}"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --attempts)
                attempts="${2:?missing value for --attempts}"
                shift 2
                ;;
            --delay)
                delay="${2:?missing value for --delay}"
                shift 2
                ;;
            --)
                shift
                break
                ;;
            *)
                break
                ;;
        esac
    done

    if [[ $# -eq 0 ]]; then
        return 1
    fi

    local try=1
    local rc=0
    while (( try <= attempts )); do
        "$@"
        rc=$?
        if (( rc == 0 )); then
            return 0
        fi

        if (( try == attempts )); then
            return "$rc"
        fi

        if [[ "${delay}" != "0" ]]; then
            sleep "${delay}"
        fi

        try=$((try + 1))
    done

    return "$rc"
}

circuit_breaker_check() {
    local operation="${1:?missing operation name}"
    local failures="${_CIRCUIT_BREAKER_FAILURES[$operation]:-0}"
    (( failures < CIRCUIT_BREAKER_THRESHOLD ))
}

circuit_breaker_record_failure() {
    local operation="${1:?missing operation name}"
    local failures="${_CIRCUIT_BREAKER_FAILURES[$operation]:-0}"
    _CIRCUIT_BREAKER_FAILURES[$operation]=$((failures + 1))
}

circuit_breaker_reset() {
    local operation="${1:?missing operation name}"
    _CIRCUIT_BREAKER_FAILURES[$operation]=0
}
