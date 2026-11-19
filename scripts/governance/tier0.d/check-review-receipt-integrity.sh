#!/usr/bin/env bash
# Tier0 extension: flag review-receipt fabrication signals (bursts, missing wrapper-recorded hashes,
# unverifiable CI claims). WARN-only on pre-commit (Rule 19: never fail a commit on history it did
# not touch); the hard check is CI's review-disposition plus aq-land's pre-merge verify.
set -uo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}" || exit 1
TOOL="scripts/ai/aq-review-receipt"
[[ -f "${TOOL}" ]] || { echo "[tier0.d/check-review-receipt-integrity] FAIL: ${TOOL} missing"; exit 1; }
since="${AQ_RECEIPT_AUDIT_SINCE:-$(date -u -d '3 days ago' +%F)}"
out="$(timeout 120 python3 "${TOOL}" audit --branch --since "${since}" 2>&1)"; rc=$?
if [[ ${rc} -ne 0 || "${out}" == *WARN* ]]; then
  echo "[tier0.d/check-review-receipt-integrity] WARN: receipt audit since ${since} flagged items (not blocking):"
  printf '%s\n' "${out}" | grep -E 'FAIL|BURST|WARN' | head -20
else
  echo "[tier0.d/check-review-receipt-integrity] OK: no receipt integrity flags since ${since}"
fi
exit 0
