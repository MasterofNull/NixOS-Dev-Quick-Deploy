#!/usr/bin/env bash
# Verifies tier0 QA admission control: N=1 serializes, N=2 overlaps, wait message printed,
# and the max-wait path reports an admission timeout.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
export AQ_TIER0_QA_LOCK_DIR="${WORK}/locks" AQ_TIER0_QA_POLL_S=0.1

worker() { # name sleep_s
  (
    # shellcheck source=../governance/lib/qa-admission.sh
    source "${ROOT}/scripts/governance/lib/qa-admission.sh"
    qa_admission_acquire 2>"${WORK}/$1.err" || exit $?
    date +%s.%N >"${WORK}/$1.start"; sleep "$2"; date +%s.%N >"${WORK}/$1.end"
    qa_admission_release
  )
}
run_pair() {
  rm -f "${WORK}"/a.* "${WORK}"/b.*
  worker a 1 & local pa=$!
  sleep 0.3
  worker b 1 & local pb=$!
  wait "${pa}" "${pb}"
}
fail() { echo "FAIL: $*" >&2; exit 1; }
lt() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a<b)}'; }

AQ_TIER0_QA_SLOTS=1 run_pair
lt "$(cat "${WORK}/a.end")" "$(cat "${WORK}/b.start")" || fail "N=1: b started before a ended"
grep -q "waiting for QA slot (held by pid" "${WORK}/b.err" || fail "N=1: no wait message"
grep -q "acquired after" "${WORK}/b.err" || fail "N=1: no acquired-after message"
echo "PASS N=1 serializes (b waited, message: $(head -1 "${WORK}/b.err"))"

AQ_TIER0_QA_SLOTS=2 run_pair
lt "$(cat "${WORK}/b.start")" "$(cat "${WORK}/a.end")" || fail "N=2: no overlap"
[[ ! -s "${WORK}/b.err" ]] || fail "N=2: unexpected wait message"
echo "PASS N=2 overlaps"

( source "${ROOT}/scripts/governance/lib/qa-admission.sh"
  AQ_TIER0_QA_SLOTS=1 qa_admission_acquire 2>/dev/null
  rc=0
  ( AQ_TIER0_QA_SLOTS=1 AQ_TIER0_QA_WAIT_S=1 qa_admission_acquire 2>"${WORK}/t.err" ) || rc=$?
  [[ "${rc}" -eq 3 ]] || exit 10
  grep -q "admission timeout" "${WORK}/t.err" || exit 11
) || fail "max-wait timeout path (rc=$?)"
echo "PASS admission timeout reported"
