#!/usr/bin/env bash
# check-mcp-integrity.sh must fail (never silently exit 0) when the baseline is missing,
# must not create it, and must still pass/alert correctly with a baseline.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/src"; echo 'print(1)' > "$T/src/a.py"
export MCP_SERVER_DIR="$T/src" MCP_INTEGRITY_BASELINE="$T/baseline.sha256" MCP_INTEGRITY_ALERT_DIR="$T/alerts"

rc=0; out="$(bash "$ROOT/scripts/testing/check-mcp-integrity.sh" 2>&1)" || rc=$?
[[ $rc -ne 0 ]] && grep -q "integrity NOT verified" <<<"$out" || { echo "FAIL: missing baseline exit rc=$rc"; echo "$out"; exit 1; }
[[ ! -e "$T/baseline.sha256" ]] || { echo "FAIL: check created the baseline"; exit 1; }
jq -e '.alert == "mcp_integrity_baseline_missing"' "$T/alerts/mcp-integrity-baseline-missing.json" >/dev/null || { echo "FAIL: no alert file"; exit 1; }

MCP_INTEGRITY_BASELINE="$T/baseline.sha256" bash "$ROOT/scripts/security/update-mcp-integrity-baseline.sh" >/dev/null
rc=0; out="$(bash "$ROOT/scripts/testing/check-mcp-integrity.sh" 2>&1)" || rc=$?
[[ $rc -eq 0 ]] && grep -q PASS <<<"$out" || { echo "FAIL: matching baseline rc=$rc"; echo "$out"; exit 1; }
echo 'print(2)' > "$T/src/a.py"
rc=0; out="$(bash "$ROOT/scripts/testing/check-mcp-integrity.sh" 2>&1)" || rc=$?
[[ $rc -eq 1 ]] && grep -q ALERT <<<"$out" || { echo "FAIL: tamper not alerted rc=$rc"; exit 1; }
# Empty and malformed baselines verify nothing: exit 2, distinct alert, never auto-created/rewritten.
for kind in empty malformed blank; do
  case "$kind" in
    empty) : > "$T/baseline.sha256" ;;
    malformed) printf 'not-a-hash /nonexistent\ngarbage\n' > "$T/baseline.sha256" ;;
    blank) printf '\n\n' > "$T/baseline.sha256" ;;
  esac
  rc=0; out="$(MCP_INTEGRITY_ALERT_DIR="$T/alerts-$kind" bash "$ROOT/scripts/testing/check-mcp-integrity.sh" 2>&1)" || rc=$?
  [[ $rc -eq 2 ]] && grep -q "integrity NOT verified" <<<"$out" || { echo "FAIL: $kind baseline rc=$rc"; echo "$out"; exit 1; }
  jq -e '.alert == "mcp_integrity_baseline_invalid"' "$T/alerts-$kind/mcp-integrity-baseline-invalid.json" >/dev/null || { echo "FAIL: $kind baseline: no invalid alert"; exit 1; }
done
echo "PASS: mcp-integrity missing/empty/malformed baseline is non-ok, tamper alerts, baseline never auto-created"
