#!/usr/bin/env bash
# Guards that tier0's focused-CI gate surfaces "[focused-ci] FAIL" lines (with context) instead of swallowing them.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GATE="${ROOT}/scripts/governance/tier0-validation-gate.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "${tmp}"' EXIT

eval "$(awk '/^print_focused_ci_failures\(\) \{/{p=1} p{print} p&&/^}/{exit}' "${GATE}")"
printf '%s\n' noise1 noise2 ctxA ctxB ctxC '[focused-ci] FAIL: first thing' mid '[focused-ci] FAIL: second thing' tail > "${tmp}/out"
got="$(print_focused_ci_failures "${tmp}/out" 2>&1)"

fail() { echo "FAIL: $*"; echo "${got}"; exit 1; }
[[ "${got}" == *"FAIL: first thing"* ]] || fail "first FAIL line missing"
[[ "${got}" == *"FAIL: second thing"* ]] || fail "second FAIL line missing"
[[ "${got}" == *ctxA* && "${got}" == *ctxC* ]] || fail "context lines before a FAIL missing"
[[ "${got}" != *noise1* && "${got}" != *tail* ]] || fail "unrelated lines leaked"
[[ "$(grep -c 'ctxC' <<<"${got}")" == 1 && "$(grep -c 'mid' <<<"${got}")" == 1 ]] || fail "a line was printed twice"
printf '%s\n' 'all good' > "${tmp}/ok"
[[ -z "$(print_focused_ci_failures "${tmp}/ok" 2>&1)" ]] || fail "printed something for a clean run"

# The gate must capture to a file, print on failure, and clean up; a bare /dev/null swallow must not return.
block="$(awk '/^gate_focused_ci_checks\(\) \{/{p=1} p{print} p&&/^}/{exit}' "${GATE}")"
[[ "${block}" != *'>/dev/null 2>&1'* ]] || fail "gate_focused_ci_checks swallows output again"
[[ "${block}" == *'print_focused_ci_failures "${_ci_out}"'* && "${block}" == *'rm -f "${_ci_out}"'* ]] || fail "gate does not print failures / clean up"
echo "PASS: tier0 focused-CI failure output"
