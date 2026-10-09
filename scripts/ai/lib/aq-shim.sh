#!/usr/bin/env bash
# aq-shim.sh — usage telemetry for DIRECT aq-* invocations (producer side).
#
# Every executable aq-<name> script carries one line near its top:
#   . "${BASH_SOURCE[0]%/*}/lib/aq-shim.sh" 2>/dev/null || true   # aq-usage-hook
# which appends ONE JSON line per invocation to the usage ledger:
#   {"ts","command","script","source","tool","argv0","cwd","agent","lane"}
# Argument VALUES are never logged (they may hold secrets). Exit code is not
# logged: a trap here would clobber the host script's own EXIT trap.
#
# Pure bash, no forks: one O_APPEND write of a short line (atomic, no flock).
# Skipped when the `aq` router already logged (AQ_VIA_ROUTER) or when
# AQ_USAGE_TELEMETRY=0. Never fails the host script.
#
# Why this exists as a per-script hook: before 2026-10 only aq-qa sourced it,
# and agents call aq-* directly (PATH), bypassing the `aq` router that logs —
# so the ledger held aq-qa's own self-invocations and nothing else.

_aq_shim_record() {
    [[ "${AQ_USAGE_TELEMETRY:-1}" == "0" ]] && return 0
    [[ -n "${AQ_VIA_ROUTER:-}" ]] && return 0
    local host="${BASH_SOURCE[2]:-${BASH_SOURCE[1]:-$0}}" dir repo ledger self name ts
    [[ "$host" == /* ]] || host="$PWD/${host#./}"
    dir="${host%/*}"
    self="${host##*/}"
    if [[ "$dir" != */scripts/ai ]]; then
        host="$(readlink -f "$host" 2>/dev/null)" || return 0
        dir="${host%/*}"
    fi
    repo="${dir%/scripts/ai}"
    ledger="${AQ_USAGE_LEDGER:-$repo/.agents/telemetry/aq-usage.jsonl}"
    name="${self#aq-}"; name="${name%.sh}"; name="${name%.py}"
    # djb2 hash of cwd: correlate without recording paths.
    local h=5381 i c LC_ALL=C
    for ((i = 0; i < ${#PWD}; i++)); do
        printf -v c '%d' "'${PWD:i:1}"
        h=$(( (h * 33 + c) & 0xffffffff ))
    done
    local agent="${AQ_AGENT_NAME:-${AQ_AGENT:-${AGENT_NAME:-}}}" lane="${AQ_LANE:-${AQ_AGENT_ROLE:-}}"
    [[ -z "$agent" && -n "${CLAUDECODE:-}" ]] && agent="claude"
    agent="${agent//[^A-Za-z0-9._:@-]/}"; lane="${lane//[^A-Za-z0-9._:@-]/}"
    printf -v ts '%(%s)T' -1
    mkdir -p "${ledger%/*}" 2>/dev/null || return 0
    printf '{"ts":%s,"command":"%s","script":"%s","source":"direct","tool":"%s","argv0":"%s","cwd":"%08x","agent":"%s","lane":"%s"}\n' \
        "$ts" "${name//[^A-Za-z0-9._-]/}" "${self//[^A-Za-z0-9._-]/}" "${self//[^A-Za-z0-9._-]/}" \
        "${self//[^A-Za-z0-9._-]/}" "$h" "$agent" "$lane" >> "$ledger" 2>/dev/null || true
}
_aq_shim_record
