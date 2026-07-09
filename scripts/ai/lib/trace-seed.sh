#!/usr/bin/env bash
# trace-seed.sh — seed AQ_TRACE_ID so every run is traced (RSI-Readiness R5.1).
#
# Source near the top of any entrypoint (aq router, delegate-* shims, aq-loop):
#   source "$(dirname "$0")/lib/trace-seed.sh"   # or the correct lib path
#
# Idempotent: if AQ_TRACE_ID is already set (inherited from a parent entrypoint),
# it is preserved so a whole CLI->delegate->dispatch chain shares ONE trace.
# Uses the kernel uuid source (no python spawn on the hot path). Kill switch:
# AQ_TRACE_DISABLE=1 leaves it unset (tracing stays opt-in / off).
if [[ "${AQ_TRACE_DISABLE:-0}" != "1" && -z "${AQ_TRACE_ID:-}" ]]; then
    if [[ -r /proc/sys/kernel/random/uuid ]]; then
        AQ_TRACE_ID="$(tr -d '-' < /proc/sys/kernel/random/uuid)"
    else
        AQ_TRACE_ID="$(date +%s%N)$RANDOM"
    fi
    export AQ_TRACE_ID
fi
