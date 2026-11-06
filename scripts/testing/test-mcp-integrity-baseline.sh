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
# (a) Default MCP_SERVER_DIR (unset) resolves to the repo's real ai-stack/mcp-servers.
expected_count="$(find "$ROOT/ai-stack/mcp-servers" -name '*.py' -type f | wc -l)"
(( expected_count > 0 )) || { echo "FAIL: no .py files under $ROOT/ai-stack/mcp-servers"; exit 1; }
rc=0; env -u MCP_SERVER_DIR MCP_INTEGRITY_BASELINE="$T/default-baseline.sha256" \
  bash "$ROOT/scripts/security/update-mcp-integrity-baseline.sh" >/dev/null 2>&1 || rc=$?
[[ $rc -eq 0 ]] || { echo "FAIL: default MCP_SERVER_DIR update rc=$rc"; exit 1; }
[[ "$(wc -l < "$T/default-baseline.sha256")" -eq "$expected_count" ]] || { echo "FAIL: default baseline line count != $expected_count"; exit 1; }

# (b) A directory with no .py files refuses and leaves an existing baseline byte-identical.
mkdir -p "$T/empty-src"; touch "$T/empty-src/notes.txt"
printf '%s  %s\n' "$(printf 'a%.0s' {1..64})" "$T/src/a.py" > "$T/keep-baseline.sha256"
cp "$T/keep-baseline.sha256" "$T/keep-before.sha256"
rc=0; out="$(MCP_SERVER_DIR="$T/empty-src" MCP_INTEGRITY_BASELINE="$T/keep-baseline.sha256" \
  bash "$ROOT/scripts/security/update-mcp-integrity-baseline.sh" 2>&1)" || rc=$?
[[ $rc -ne 0 ]] && grep -q "$T/empty-src" <<<"$out" || { echo "FAIL: empty dir did not refuse rc=$rc"; echo "$out"; exit 1; }
cmp -s "$T/keep-before.sha256" "$T/keep-baseline.sha256" || { echo "FAIL: empty dir overwrote baseline"; exit 1; }

# (c) No missing files: alert missing_files is an empty JSON list, not [""].
mkdir -p "$T/c-src" "$T/c-alerts"; echo 'print(3)' > "$T/c-src/b.py"
MCP_SERVER_DIR="$T/c-src" MCP_INTEGRITY_BASELINE="$T/c-baseline.sha256" \
  bash "$ROOT/scripts/security/update-mcp-integrity-baseline.sh" >/dev/null
echo 'print(4)' > "$T/c-src/b.py"
rc=0; MCP_SERVER_DIR="$T/c-src" MCP_INTEGRITY_BASELINE="$T/c-baseline.sha256" MCP_INTEGRITY_ALERT_DIR="$T/c-alerts" \
  bash "$ROOT/scripts/testing/check-mcp-integrity.sh" >/dev/null 2>&1 || rc=$?
[[ $rc -eq 1 ]] || { echo "FAIL: tamper case rc=$rc (expected 1)"; exit 1; }
alert=("$T"/c-alerts/mcp-integrity-*.json); [[ -f "${alert[0]}" ]] || { echo "FAIL: no alert file"; exit 1; }
jq -e '.missing_files == [] and (.changed_files | length) == 1' "${alert[0]}" >/dev/null || { echo "FAIL: missing_files not []"; cat "${alert[0]}"; exit 1; }

echo "PASS: mcp-integrity missing/empty/malformed baseline is non-ok, tamper alerts, baseline never auto-created; default path, empty-dir refusal, empty missing_files verified"
