#!/usr/bin/env bash
# Tests for the unified `aq` router: auto-discovery, usage telemetry,
# `aq usage`, `aq --commands`, and the deprecation shim (god-tier prompt 8).
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AQ="$REPO/scripts/ai/aq"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export AQ_USAGE_LEDGER="$TMP/usage.jsonl"
fail=0
_ok()   { echo "PASS $1"; }
_bad()  { echo "FAIL $1" >&2; fail=1; }

# 1. --commands lists discovered subcommands NOT in the curated map.
cmds="$("$AQ" --commands 2>/dev/null)"
if grep -qx event <<<"$cmds" && grep -qx cascade <<<"$cmds"; then
  _ok "--commands includes discovered event + cascade"
else
  _bad "--commands missing discovered subcommands"
fi

# 2. Auto-discovery routes a non-map command (aq event -> aq-event) + logs it.
if "$AQ" event tail -n 1 >/dev/null 2>&1; then
  if grep -q '"command":"event","script":"aq-event","source":"discovered"' "$AQ_USAGE_LEDGER"; then
    _ok "auto-discovery routes + logs 'aq event' as discovered"
  else
    _bad "auto-discovery did not log usage"
  fi
else
  _bad "auto-discovery failed to route 'aq event'"
fi

# 3. Unknown command errors and is logged as unknown.
"$AQ" definitely-not-a-real-command >/dev/null 2>&1
if grep -q '"command":"definitely-not-a-real-command","script":"","source":"unknown"' "$AQ_USAGE_LEDGER"; then
  _ok "unknown command logged as unknown"
else
  _bad "unknown command not logged"
fi

# 4. `aq usage` aggregates counts.
usage_out="$("$AQ" usage 2>/dev/null)"
if grep -q 'event' <<<"$usage_out" && grep -q 'distinct commands' <<<"$usage_out"; then
  _ok "aq usage aggregates telemetry"
else
  _bad "aq usage did not aggregate"
fi

# 5. Kill switch: AQ_USAGE_TELEMETRY=0 records nothing.
rm -f "$AQ_USAGE_LEDGER"
AQ_USAGE_TELEMETRY=0 "$AQ" event tail -n 1 >/dev/null 2>&1
if [[ ! -s "$AQ_USAGE_LEDGER" ]]; then
  _ok "kill switch AQ_USAGE_TELEMETRY=0 disables logging"
else
  _bad "kill switch did not disable logging"
fi

# 6. Deprecation shim: direct aq-qa logs source=direct; router-marked suppresses.
rm -f "$AQ_USAGE_LEDGER"
timeout 20 "$REPO/scripts/ai/aq-qa" 999 >/dev/null 2>&1
if grep -q '"command":"qa","script":"aq-qa","source":"direct"' "$AQ_USAGE_LEDGER"; then
  _ok "shim logs direct aq-qa invocation"
else
  _bad "shim did not log direct invocation"
fi
rm -f "$AQ_USAGE_LEDGER"
AQ_VIA_ROUTER=1 timeout 20 "$REPO/scripts/ai/aq-qa" 999 >/dev/null 2>&1
if ! grep -q '"source":"direct"' "$AQ_USAGE_LEDGER" 2>/dev/null; then
  _ok "shim suppresses double-log under router (AQ_VIA_ROUTER)"
else
  _bad "shim double-logged under router"
fi

if [[ $fail -eq 0 ]]; then echo "ALL PASS"; else echo "SOME FAILED"; exit 1; fi
