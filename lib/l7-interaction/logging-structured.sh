#!/usr/bin/env bash
#
# Structured Logging Helpers
# Purpose: Provide JSON log lines compatible with Loki/ELK pipelines
# Version: 1.0.0
#
# ============================================================================

: "${LOG_FORMAT:=json}"
: "${LOG_COMPONENT:=nixos-quick-deploy}"
: "${CORRELATION_ID:=}"

generate_correlation_id() {
    if command -v uuidgen >/dev/null 2>&1; then
        uuidgen
        return 0
    fi
    if [[ -r /proc/sys/kernel/random/uuid ]]; then
        cat /proc/sys/kernel/random/uuid
        return 0
    fi
    date +%s%N
}

init_structured_logging() {
    if [[ -z "${CORRELATION_ID:-}" ]]; then
        CORRELATION_ID="$(generate_correlation_id)"
        export CORRELATION_ID
    fi
}

json_escape() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//$'\n'/\\n}"
    value="${value//$'\r'/\\r}"
    value="${value//$'\t'/\\t}"
    echo "$value"
}

log_json_line() {
    local level="$1"
    local message="$2"
    local caller="${3:-}"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    init_structured_logging

    local level_esc
    local msg_esc
    local comp_esc
    local caller_esc
    level_esc="$(json_escape "$level")"
    msg_esc="$(json_escape "$message")"
    comp_esc="$(json_escape "${LOG_COMPONENT}")"
    caller_esc="$(json_escape "$caller")"

    if [[ -n "$caller" ]]; then
        printf '{"timestamp":"%s","level":"%s","component":"%s","message":"%s","correlation_id":"%s","caller":"%s"}\n' \
            "$timestamp" "$level_esc" "$comp_esc" "$msg_esc" "$CORRELATION_ID" "$caller_esc"
    else
        printf '{"timestamp":"%s","level":"%s","component":"%s","message":"%s","correlation_id":"%s"}\n' \
            "$timestamp" "$level_esc" "$comp_esc" "$msg_esc" "$CORRELATION_ID"
    fi
}
