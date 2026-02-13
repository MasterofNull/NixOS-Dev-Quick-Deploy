#!/usr/bin/env bash
#
# Timeout Wrappers - Prevent indefinite hangs on external calls
# Purpose: Wrap kubectl, curl, and other commands with configurable timeouts
# Version: 6.1.0
#
# ============================================================================

# Default timeouts (seconds) - override via config/settings.sh or env vars
: "${KUBECTL_TIMEOUT:=60}"
: "${CURL_TIMEOUT:=10}"
: "${CURL_CONNECT_TIMEOUT:=5}"
: "${NIXOS_REBUILD_TIMEOUT:=3600}"
: "${HOME_MANAGER_TIMEOUT:=1800}"
: "${GENERIC_TIMEOUT:=120}"

# ============================================================================
# Run a command with a hard timeout
# ============================================================================
# Usage: run_with_timeout <seconds> <command> [args...]
# Returns: Command exit code, or 124 on timeout
# ============================================================================
run_with_timeout() {
    local timeout_seconds="${1:?timeout seconds required}"
    shift

    if ! command -v timeout >/dev/null 2>&1; then
        # Fallback: run without timeout if coreutils timeout not available
        log WARN "timeout command not available; running without timeout guard"
        "$@"
        return $?
    fi

    timeout --signal=TERM --kill-after=10 "$timeout_seconds" "$@"
    local exit_code=$?

    if [[ $exit_code -eq 124 ]]; then
        if declare -F log >/dev/null 2>&1; then
            log ERROR "Command timed out after ${timeout_seconds}s: $*"
        fi
    fi

    return $exit_code
}

# ============================================================================
# kubectl with timeout
# ============================================================================
# Usage: kubectl_safe [kubectl args...]
# Adds --request-timeout automatically
# ============================================================================
kube_timeout_log() {
    local timeout_seconds="$1"
    local command_display="$2"
    local stderr_file="$3"
    local exit_code="$4"

    if [[ $exit_code -ne 0 ]] && grep -Eiq "context deadline exceeded|timed out" "$stderr_file"; then
        if declare -F log_error >/dev/null 2>&1; then
            log_error "${ERR_TIMEOUT:-70}" "${command_display} timed out after ${timeout_seconds}s"
        elif declare -F print_warning >/dev/null 2>&1; then
            print_warning "${command_display} timed out after ${timeout_seconds}s"
        else
            echo "WARNING: ${command_display} timed out after ${timeout_seconds}s" >&2
        fi
    fi
}

kubectl_safe() {
    if ! command -v kubectl >/dev/null 2>&1; then
        if declare -F print_warning >/dev/null 2>&1; then
            print_warning "kubectl not available"
        fi
        return "${ERR_MISSING_COMMAND:-15}"
    fi
    if [[ -z "${KUBECONFIG:-}" && -f /etc/rancher/k3s/k3s.yaml ]]; then
        export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    fi

    local stderr_file
    local tmp_root="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
    stderr_file=$(mktemp 2>/dev/null || echo "${tmp_root}/kubectl_safe_stderr.$$") || true
    kubectl --request-timeout="${KUBECTL_TIMEOUT}s" "$@" 2> "$stderr_file"
    local exit_code=$?
    if [[ -s "$stderr_file" ]]; then
        cat "$stderr_file" >&2
    fi
    kube_timeout_log "$KUBECTL_TIMEOUT" "kubectl $*" "$stderr_file" "$exit_code"
    rm -f "$stderr_file" 2>/dev/null || true
    return $exit_code
}

# ============================================================================
# curl with timeout
# ============================================================================
# Usage: curl_safe [curl args...]
# Adds --max-time and --connect-timeout automatically
# ============================================================================
curl_safe() {
    if ! command -v curl >/dev/null 2>&1; then
        if declare -F print_warning >/dev/null 2>&1; then
            print_warning "curl not available"
        fi
        return "${ERR_MISSING_COMMAND:-15}"
    fi

    local stderr_file
    local tmp_root="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
    stderr_file=$(mktemp 2>/dev/null || echo "${tmp_root}/curl_safe_stderr.$$") || true
    curl --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT_TIMEOUT" "$@" 2> "$stderr_file"
    local exit_code=$?
    if [[ -s "$stderr_file" ]]; then
        cat "$stderr_file" >&2
    fi
    if [[ $exit_code -eq 28 ]]; then
        if declare -F log_error >/dev/null 2>&1; then
            log_error "${ERR_TIMEOUT:-70}" "curl timed out after ${CURL_TIMEOUT}s (connect timeout ${CURL_CONNECT_TIMEOUT}s): curl $*"
        elif declare -F print_warning >/dev/null 2>&1; then
            print_warning "curl timed out after ${CURL_TIMEOUT}s (connect timeout ${CURL_CONNECT_TIMEOUT}s)"
        else
            echo "WARNING: curl timed out after ${CURL_TIMEOUT}s (connect timeout ${CURL_CONNECT_TIMEOUT}s)" >&2
        fi
    fi
    rm -f "$stderr_file" 2>/dev/null || true
    return $exit_code
}

# ============================================================================
# nixos-rebuild with timeout
# ============================================================================
# Usage: nixos_rebuild_safe [nixos-rebuild args...]
# Wraps with NIXOS_REBUILD_TIMEOUT
# ============================================================================
nixos_rebuild_safe() {
    run_with_timeout "$NIXOS_REBUILD_TIMEOUT" sudo nixos-rebuild "$@"
    local exit_code=$?

    if [[ $exit_code -eq 124 ]]; then
        if declare -F print_error >/dev/null 2>&1; then
            print_error "nixos-rebuild timed out after ${NIXOS_REBUILD_TIMEOUT}s"
        fi
        return "${ERR_TIMEOUT_REBUILD:-72}"
    fi

    return $exit_code
}

# ============================================================================
# home-manager with timeout
# ============================================================================
# Usage: home_manager_safe [home-manager args...]
# Wraps with HOME_MANAGER_TIMEOUT
# ============================================================================
home_manager_safe() {
    local hm_cmd="${1:?home-manager command required}"
    shift

    run_with_timeout "$HOME_MANAGER_TIMEOUT" "$hm_cmd" "$@"
    local exit_code=$?

    if [[ $exit_code -eq 124 ]]; then
        if declare -F print_error >/dev/null 2>&1; then
            print_error "home-manager timed out after ${HOME_MANAGER_TIMEOUT}s"
        fi
        return "${ERR_TIMEOUT:-70}"
    fi

    return $exit_code
}
