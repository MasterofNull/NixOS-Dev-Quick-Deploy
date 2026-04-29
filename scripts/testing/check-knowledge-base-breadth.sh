#!/usr/bin/env bash
# check-knowledge-base-breadth.sh — Phase 13.4 gate
#
# Fails if total AIDB document count is below the minimum threshold.
# Used as a CI/QA gate after running ingest-project-knowledge.py.
#
# Usage:
#   scripts/testing/check-knowledge-base-breadth.sh
#   MIN_DOCS=1000 scripts/testing/check-knowledge-base-breadth.sh

set -euo pipefail

MIN_DOCS="${MIN_DOCS:-500}"
AIDB_URL="${AIDB_URL:-http://localhost:8002}"
AIDB_KEY_FILE="${AIDB_KEY_FILE:-/run/secrets/aidb_api_key}"

_aidb_key=""
if [[ -f "$AIDB_KEY_FILE" ]]; then
  _aidb_key="$(tr -d '[:space:]' < "$AIDB_KEY_FILE")"
elif [[ -n "${AIDB_API_KEY:-}" ]]; then
  _aidb_key="$AIDB_API_KEY"
fi

# Health check
if ! curl -sf --max-time 5 "${AIDB_URL}/health" -H "X-API-Key: ${_aidb_key}" > /dev/null 2>&1; then
  printf '[SKIP] AIDB not reachable at %s — skipping breadth check\n' "$AIDB_URL"
  exit 0
fi

# Count documents in the primary project
_count="$(curl -s --max-time 10 \
  "${AIDB_URL}/documents?limit=1&project=nixos-dev-quick-deploy" \
  -H "X-API-Key: ${_aidb_key}" \
  2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    # The API returns 'total' as count of results in the page for limit=1
    # Use a larger limit to get actual count
    print(len(d.get('documents', [])))
except Exception:
    print(0)
" 2>/dev/null || echo 0)"

# Get a broader count using a large limit
_broad_count="$(curl -s --max-time 15 \
  "${AIDB_URL}/documents?limit=5000&project=nixos-dev-quick-deploy" \
  -H "X-API-Key: ${_aidb_key}" \
  2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(len(d.get('documents', [])))
except Exception:
    print(0)
" 2>/dev/null || echo 0)"

printf 'AIDB nixos-dev-quick-deploy project: %s documents\n' "$_broad_count"

if [[ "$_broad_count" -ge "$MIN_DOCS" ]]; then
  printf '[PASS] Knowledge base breadth: %s >= %s (min)\n' "$_broad_count" "$MIN_DOCS"
  exit 0
else
  printf '[FAIL] Knowledge base breadth: %s < %s (min)\n' "$_broad_count" "$MIN_DOCS" >&2
  printf '  Run: python3 scripts/data/ingest-project-knowledge.py\n' >&2
  exit 1
fi
