#!/usr/bin/env bash
# Tier 0.d check: check-commit-evidence-warn (DEC-S9 advisory commit-evidence check)
# WARN-only per aq-decide DESIGN.md DEC-S9 / Section 10.2
set -euo pipefail

COMMIT_MSG_FILE="${1:-}"
if [[ -z "${COMMIT_MSG_FILE}" || ! -f "${COMMIT_MSG_FILE}" ]]; then
  # Non-hook or direct execution mode
  exit 0
fi

# Check if commit message contains evidence markers
if ! grep -qE "(Review-Disposition:|Reviewed-head-sha:|Reviewed-subject-sha256:|Reviewed-by:)" "${COMMIT_MSG_FILE}"; then
  echo "WARN: [tier0.d/check-commit-evidence-warn] Commit message does not contain independent review trailers."
  echo "      Per .agents/plans/aq-decide/DESIGN.md DEC-S9, this is advisory only."
fi

exit 0
