#!/usr/bin/env bash
# aq-shim.sh — deprecation/usage shim for aq-* scripts (god-tier prompt 8).
#
# Source this near the top of any aq-<name> script to record DIRECT (non-router)
# invocations, so `aq usage` sees true usage across BOTH paths (aq foo and
# aq-foo). Retirement stays data-driven: a script with zero invocations on
# either path after a telemetry window is a retirement candidate.
#
# One line to adopt (keeps the script fully working — this only logs):
#   source "$(dirname "$(readlink -f "${BASH_SOURCE[0]:-$0}")")/lib/aq-shim.sh"
#
# Opt out: AQ_USAGE_TELEMETRY=0. Never fails the host script.

_aq_shim_record() {
    [[ "${AQ_USAGE_TELEMETRY:-1}" == "0" ]] && return 0
    # Skip when invoked via the router (it logs already; AQ_VIA_ROUTER is set there).
    [[ -n "${AQ_VIA_ROUTER:-}" ]] && return 0
    # Host script is BASH_SOURCE[2]: [0]=this func's file, [1]=the call site
    # (also this file's last line), [2]=the aq-* script that sourced us.
    local host self repo ledger name
    host="${BASH_SOURCE[2]:-${BASH_SOURCE[1]:-$0}}"
    self="$(basename "$host")"
    name="${self#aq-}"; name="${name%.sh}"; name="${name%.py}"
    repo="$(cd "$(dirname "$(readlink -f "$host")")/../.." 2>/dev/null && pwd)" || return 0
    ledger="${AQ_USAGE_LEDGER:-$repo/.agents/telemetry/aq-usage.jsonl}"
    mkdir -p "$(dirname "$ledger")" 2>/dev/null || return 0
    printf '{"ts":%s,"command":"%s","script":"%s","source":"direct"}\n' \
        "$(date +%s)" "${name//\"/}" "${self//\"/}" >> "$ledger" 2>/dev/null || true
}
_aq_shim_record
