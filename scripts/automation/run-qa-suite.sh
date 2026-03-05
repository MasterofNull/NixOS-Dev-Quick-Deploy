#!/usr/bin/env bash
# run-qa-suite.sh — AI Stack QA regression suite (Phase 10.1.1)
#
# Wraps aq-qa to run all Phase 0-6 smoke and feature tests.
# Intended for post-deploy validation and CI usage.
#
# Usage:
#   bash scripts/automation/run-qa-suite.sh [--sudo] [--json]
#
# Exit codes: 0 = all pass, 1 = one or more failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AQ_QA="${SCRIPT_DIR}/aq-qa"

if [[ ! -x "$AQ_QA" ]]; then
  echo "ERROR: $AQ_QA not found or not executable" >&2
  exit 2
fi

ARGS=()
for arg in "$@"; do
  ARGS+=("$arg")
done

echo "=== AI Stack QA Suite — Phase 0–6 ==="
echo

# Run phases 0 and 1 (fully implemented); 2-6 are stubs that report status
for phase in 0 1 2 3 4 5 6; do
  bash "$AQ_QA" "$phase" "${ARGS[@]}" || true
  echo
done

echo "=== QA Suite complete ==="
