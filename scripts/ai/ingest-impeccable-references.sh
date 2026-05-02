#!/usr/bin/env bash
# ingest-impeccable-references.sh
# Fetches and ingests impeccable design reference docs into AIDB
# project: impeccable-design
#
# Usage:
#   scripts/ai/ingest-impeccable-references.sh
#   scripts/ai/ingest-impeccable-references.sh --dry-run
#   scripts/ai/ingest-impeccable-references.sh --verify-only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DRY_RUN=0
VERIFY_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)     DRY_RUN=1 ;;
    --verify-only) VERIFY_ONLY=1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
AIDB_URL="${AIDB_URL:-http://127.0.0.1:8002}"
AIDB_KEY_FILE="/run/secrets/aidb_api_key"
PROJECT="impeccable-design"
RAW_BASE="https://raw.githubusercontent.com/pbakaus/impeccable/main/source/skills/impeccable/reference"
CACHE_DIR="${REPO_ROOT}/.agent/impeccable-cache"

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
if [[ ! -f "$AIDB_KEY_FILE" ]]; then
  printf 'ERROR: %s not found\n' "$AIDB_KEY_FILE" >&2
  exit 1
fi
AIDB_KEY="$(tr -d '[:space:]' < "$AIDB_KEY_FILE")"

# ---------------------------------------------------------------------------
# Reference file list (35 docs from impeccable repo)
# ---------------------------------------------------------------------------
REFS=(
  adapt animate audit bolder brand clarify cognitive-load color-and-contrast
  craft critique delight distill document extract harden heuristics-scoring
  interaction-design layout live motion-design onboard overdrive personas
  polish product quieter responsive-design shape spatial-design teach
  typography typeset ux-writing
)

# ---------------------------------------------------------------------------
# Verify only
# ---------------------------------------------------------------------------
if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  printf 'Checking AIDB project "%s"...\n' "$PROJECT"
  COUNT=$(curl -sf "${AIDB_URL}/documents?project=${PROJECT}&limit=200" \
    -H "X-API-Key: ${AIDB_KEY}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
docs = data.get('documents', [])
print(len(docs))
" 2>/dev/null || echo "0")
  printf 'Documents in %s: %s\n' "$PROJECT" "$COUNT"
  if [[ "$COUNT" -ge 30 ]]; then
    printf 'PASS: >= 30 docs\n'
    exit 0
  else
    printf 'FAIL: < 30 docs (need to run ingestion)\n'
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Fetch + ingest
# ---------------------------------------------------------------------------
mkdir -p "$CACHE_DIR"

INGESTED=0
FAILED=0

printf 'Ingesting impeccable reference docs into AIDB project "%s"...\n' "$PROJECT"

for ref in "${REFS[@]}"; do
  url="${RAW_BASE}/${ref}.md"
  cache_file="${CACHE_DIR}/${ref}.md"

  # Fetch if not cached
  if [[ ! -f "$cache_file" ]]; then
    if ! curl -sf "$url" -o "$cache_file" 2>/dev/null; then
      printf '  SKIP %s (fetch failed)\n' "$ref"
      FAILED=$((FAILED + 1))
      continue
    fi
  fi

  CONTENT="$(cat "$cache_file")"
  if [[ -z "$CONTENT" ]]; then
    printf '  SKIP %s (empty content)\n' "$ref"
    FAILED=$((FAILED + 1))
    continue
  fi

  TITLE="impeccable: ${ref}"
  RELATIVE_PATH="source/skills/impeccable/reference/${ref}.md"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '  DRY-RUN: would ingest "%s" (%d chars)\n' "$TITLE" "${#CONTENT}"
    INGESTED=$((INGESTED + 1))
    continue
  fi

  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${AIDB_URL}/documents" \
    -H "X-API-Key: ${AIDB_KEY}" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "
import json, sys
print(json.dumps({
    'content': sys.stdin.read(),
    'project': '${PROJECT}',
    'relative_path': '${RELATIVE_PATH}',
    'title': '${TITLE}'
}))
" <<< "$CONTENT")")

  if [[ "$HTTP_STATUS" == "200" || "$HTTP_STATUS" == "201" ]]; then
    printf '  OK  %s\n' "$ref"
    INGESTED=$((INGESTED + 1))
  else
    printf '  FAIL %s (HTTP %s)\n' "$ref" "$HTTP_STATUS"
    FAILED=$((FAILED + 1))
  fi

  # Rate limit guard
  sleep 0.3
done

printf '\nDone. Ingested: %d  Failed: %d\n' "$INGESTED" "$FAILED"

if [[ "$DRY_RUN" -eq 0 && "$INGESTED" -gt 0 ]]; then
  printf '\nVerifying...\n'
  bash "$0" --verify-only
fi
