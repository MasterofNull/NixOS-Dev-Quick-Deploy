#!/usr/bin/env bash
# ingest-trading-knowledge.sh
# Ingests tradingagents documentation and agent prompts into AIDB
# project: trading-knowledge
#
# Usage:
#   scripts/ai/ingest-trading-knowledge.sh
#   scripts/ai/ingest-trading-knowledge.sh --dry-run
#   scripts/ai/ingest-trading-knowledge.sh --verify-only

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

AIDB_URL="${AIDB_URL:-http://127.0.0.1:8002}"
AIDB_KEY_FILE="/run/secrets/aidb_api_key"
PROJECT="trading-knowledge"
TRADING_AGENTS_DIR="${REPO_ROOT}/ai-stack/trading-agents"

if [[ ! -f "$AIDB_KEY_FILE" ]]; then
  printf 'ERROR: %s not found\n' "$AIDB_KEY_FILE" >&2
  exit 1
fi
AIDB_KEY="$(tr -d '[:space:]' < "$AIDB_KEY_FILE")"

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  COUNT=$(curl -sf "${AIDB_URL}/documents?project=${PROJECT}&limit=200" \
    -H "X-API-Key: ${AIDB_KEY}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(len(data.get('documents', [])))
" 2>/dev/null || echo "0")
  printf 'Documents in %s: %s\n' "$PROJECT" "$COUNT"
  [[ "$COUNT" -ge 10 ]] && { printf 'PASS: >= 10 docs\n'; exit 0; }
  printf 'FAIL: < 10 docs\n'; exit 1
fi

# ---------------------------------------------------------------------------
# Collect Python source files as knowledge documents
# ---------------------------------------------------------------------------
INGESTED=0
FAILED=0

printf 'Ingesting trading-agents source as AIDB knowledge (project: %s)...\n' "$PROJECT"

while IFS= read -r -d '' py_file; do
  rel_path="${py_file#${REPO_ROOT}/}"
  filename="$(basename "$py_file")"
  title="tradingagents: ${filename}"
  content="$(cat "$py_file")"

  if [[ -z "$content" || ${#content} -lt 50 ]]; then
    continue
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '  DRY-RUN: %s (%d chars)\n' "$rel_path" "${#content}"
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
    'relative_path': '${rel_path}',
    'title': '${title}'
}))
" <<< "$content")")

  if [[ "$HTTP_STATUS" == "200" || "$HTTP_STATUS" == "201" ]]; then
    printf '  OK  %s\n' "$rel_path"
    INGESTED=$((INGESTED + 1))
  else
    printf '  FAIL %s (HTTP %s)\n' "$rel_path" "$HTTP_STATUS"
    FAILED=$((FAILED + 1))
  fi
  sleep 0.3
done < <(find "$TRADING_AGENTS_DIR" -name "*.py" -not -name "__init__.py" -print0 2>/dev/null)

# Also ingest the skill and plan files
for extra_file in \
  "${REPO_ROOT}/scripts/ai/skills/tradingagents.skill.md" \
  "${REPO_ROOT}/.agents/plans/phase-24-external-framework-integration.md" \
  "${REPO_ROOT}/docs/agent-guides/50-TOOL-SELECTION-MATRIX.md"; do
  [[ -f "$extra_file" ]] || continue
  rel_path="${extra_file#${REPO_ROOT}/}"
  content="$(cat "$extra_file")"
  title="tradingagents: $(basename "$extra_file")"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '  DRY-RUN: %s\n' "$rel_path"
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
    'relative_path': '${rel_path}',
    'title': '${title}'
}))
" <<< "$content")")

  [[ "$HTTP_STATUS" == "200" || "$HTTP_STATUS" == "201" ]] && {
    printf '  OK  %s\n' "$rel_path"
    INGESTED=$((INGESTED + 1))
  } || {
    printf '  FAIL %s (HTTP %s)\n' "$rel_path" "$HTTP_STATUS"
    FAILED=$((FAILED + 1))
  }
  sleep 0.3
done

printf '\nDone. Ingested: %d  Failed: %d\n' "$INGESTED" "$FAILED"
[[ "$DRY_RUN" -eq 0 && "$INGESTED" -gt 0 ]] && bash "$0" --verify-only || true
