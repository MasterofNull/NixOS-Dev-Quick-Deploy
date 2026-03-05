#!/usr/bin/env bash
# aq-knowledge-import.sh — import knowledge for a query gap topic into AIDB
#
# Usage:
#   scripts/ai/aq-knowledge-import.sh "what is lib.mkForce"
#   scripts/ai/aq-knowledge-import.sh "NixOS flake"   [--project nixos-docs]
#
# Workflow:
#   1. Use gemini CLI to generate a comprehensive explanation of the topic
#   2. Import the result into AIDB via POST /documents
#   3. Optionally clear matching gap entries from query_gaps table
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config/service-endpoints.sh"
export PATH="$HOME/.npm-global/bin:$PATH"

TOPIC="${1:?Usage: $0 '<topic>' [--project <project>] [--clear-gaps]}"
PROJECT="${AIDB_PROJECT:-knowledge}"
CLEAR_GAPS=false
GEMINI_TIMEOUT_SECONDS="${GEMINI_TIMEOUT_SECONDS:-90}"

shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --clear-gaps) CLEAR_GAPS=true; shift ;;
    *) printf 'Unknown arg: %s\n' "$1" >&2; exit 1 ;;
  esac
done

# ── API key ──────────────────────────────────────────────────────────────────
AIDB_KEY_FILE="${AIDB_API_KEY_FILE:-/run/secrets/aidb_api_key}"
if [[ -r "$AIDB_KEY_FILE" ]]; then
  AIDB_KEY="${AIDB_API_KEY:-$(tr -d '[:space:]' < "$AIDB_KEY_FILE")}"
else
  AIDB_KEY="${AIDB_API_KEY:-}"
fi
if [[ -z "$AIDB_KEY" ]]; then
  printf 'ERROR: AIDB_API_KEY or AIDB_API_KEY_FILE not set\n' >&2
  exit 1
fi

# ── Generate content via Gemini ───────────────────────────────────────────────
printf 'Generating explanation for: %s\n' "${TOPIC}"
PROMPT="You are a NixOS systems expert. Write a comprehensive, accurate reference \
document (600-1200 words) explaining: ${TOPIC}

Include:
- What it is and why it matters
- How to use it (with concrete NixOS examples)
- Common pitfalls and best practices
- Relationship to related concepts

Format as plain text with section headers. Be precise and practical."

if command -v timeout >/dev/null 2>&1; then
  CONTENT="$(timeout "${GEMINI_TIMEOUT_SECONDS}" gemini -p "$PROMPT" 2>/dev/null)" || {
    printf 'ERROR: gemini CLI timed out after %ss for topic: %s\n' "${GEMINI_TIMEOUT_SECONDS}" "${TOPIC}" >&2
    exit 1
  }
else
  CONTENT="$(gemini -p "$PROMPT" 2>/dev/null)" || {
    printf 'ERROR: gemini CLI failed. Is it installed? export PATH="$HOME/.npm-global/bin:$PATH"\n' >&2
    exit 1
  }
fi

if [[ -z "$CONTENT" ]]; then
  printf 'ERROR: gemini returned empty content\n' >&2
  exit 1
fi

WORD_COUNT=$(echo "$CONTENT" | wc -w)
printf 'Generated %s words\n' "${WORD_COUNT}"

# ── Import into AIDB ──────────────────────────────────────────────────────────
TITLE="$(echo "$TOPIC" | sed 's/^./\u&/')"
TMPFILE=$(mktemp /tmp/aq-knowledge-XXXXXX.json)
trap 'rm -f "$TMPFILE"' EXIT

python3 -c "
import json, sys
data = {
  'title': sys.argv[1],
  'content': sys.argv[2],
  'project': sys.argv[3],
  'relative_path': 'knowledge/' + sys.argv[1].lower().replace(' ', '-') + '.md',
}
print(json.dumps(data))
" "$TITLE" "$CONTENT" "$PROJECT" > "$TMPFILE"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${AIDB_URL}/documents" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${AIDB_KEY}" \
  --data @"$TMPFILE")

if [[ "$HTTP_CODE" =~ ^2 ]]; then
  printf 'PASS  Imported %s into AIDB (project=%s)\n' "${TITLE}" "${PROJECT}"
else
  printf 'FAIL  AIDB import returned HTTP %s\n' "${HTTP_CODE}" >&2
  exit 1
fi

# ── Optionally clear matching gaps ────────────────────────────────────────────
if [[ "$CLEAR_GAPS" == "true" ]]; then
  KEYWORD="${TOPIC:0:40}"
  PG_PASS_FILE="${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}"
  PG_PASS=""
  [[ -r "$PG_PASS_FILE" ]] && PG_PASS="$(tr -d '[:space:]' < "$PG_PASS_FILE")"
  PG_DSN="postgresql://aidb:${PG_PASS}@${POSTGRES_HOST:-127.0.0.1}:${POSTGRES_PORT}/aidb"
  DELETED=$(psql "$PG_DSN" --tuples-only --no-align \
    --command "DELETE FROM query_gaps WHERE query_text ILIKE '%${KEYWORD}%' RETURNING id;" \
    2>/dev/null | grep -c '^' || echo 0)
  printf 'PASS  Cleared %s matching gap entries from query_gaps\n' "${DELETED}"
fi

printf 'Done.\n'
