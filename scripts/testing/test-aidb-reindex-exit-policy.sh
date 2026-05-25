#!/usr/bin/env bash
# Verify aidb-reindex distinguishes degraded telemetry from service failure.
set -euo pipefail

script="scripts/automation/aidb-reindex.sh"

grep -q 'OVERALL="failed"' "$script" \
  || { echo "FAIL: aidb-reindex must expose a failed overall state"; exit 1; }

grep -q 'partial)' "$script" \
  || { echo "FAIL: aidb-reindex must handle partial status explicitly"; exit 1; }

grep -A4 'partial)' "$script" | grep -q 'exit 0' \
  || { echo "FAIL: partial reindex should exit 0 and rely on telemetry for degraded state"; exit 1; }

grep -A4 '*)' "$script" | grep -q 'exit 1' \
  || { echo "FAIL: total reindex failure should still exit non-zero"; exit 1; }

echo "PASS: aidb-reindex exit policy"
