#!/usr/bin/env bash
# shellcheck source=/dev/null
. "${BASH_SOURCE[0]%/*}/lib/aq-shim.sh" 2>/dev/null || true  # aq-usage-hook
# aq-knowledge-import.sh — import knowledge for a query gap topic into AIDB
#
# Usage:
#   scripts/ai/aq-knowledge-import.sh "what is lib.mkForce"
#   scripts/ai/aq-knowledge-import.sh "NixOS flake"   [--project nixos-docs]
#
# Workflow:
#   1. Use a research delegate to generate an explanation of the topic
#   2. Import the result into AIDB via POST /documents
#   3. Optionally clear matching gap entries from query_gaps table
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/../../config/service-endpoints.sh"
export PATH="$HOME/.npm-global/bin:$PATH"

TOPIC="${1:?Usage: $0 '<topic>' [--project <project>] [--clear-gaps]}"
PROJECT="${AIDB_PROJECT:-knowledge}"
CLEAR_GAPS=false
GAP_IMPORT_LANE="${GAP_IMPORT_LANE:-auto}"
LOCAL_TIMEOUT_SECONDS="${LOCAL_TIMEOUT_SECONDS:-180}"
GEMINI_TIMEOUT_SECONDS="${GEMINI_TIMEOUT_SECONDS:-90}"

shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --clear-gaps) CLEAR_GAPS=true; shift ;;
    *) printf 'Unknown arg: %s\n' "$1" >&2; exit 1 ;;
  esac
done

case "$GAP_IMPORT_LANE" in
  auto|local|gemini) ;;
  *) printf 'ERROR  Invalid GAP_IMPORT_LANE: %s\n' "$GAP_IMPORT_LANE" >&2; exit 1 ;;
esac

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

# ── Generate content via research delegate ──────────────────────────────────
_generate_with_lane() {
  local lane="$1" prompt="$2" delegate mode timeout_seconds output tid
  local tid_pattern
  delegate="${SCRIPT_DIR}/delegate-to-${lane}"
  [[ -x "$delegate" ]] || return 1

  case "$lane" in
    local) mode=direct; timeout_seconds="$LOCAL_TIMEOUT_SECONDS" ;;
    gemini) mode=plan; timeout_seconds="$GEMINI_TIMEOUT_SECONDS" ;;
  esac

  output="$(timeout "$timeout_seconds" "$delegate" \
    --prompt "$prompt" --mode "$mode" --role research --wait 2>/dev/null)" || return 1
  tid_pattern="${lane}-[0-9]{8}-[0-9]{6}-[a-z0-9]{6}"
  [[ "$output" =~ $tid_pattern ]] || return 1
  tid="${BASH_REMATCH[0]}"
  CONTENT="$("$delegate" --check "$tid" 2>/dev/null)" || return 1
  [[ -n "${CONTENT//[[:space:]]/}" ]]
}

printf 'Generating explanation for: %s\n' "${TOPIC}"
PROMPT="You are a NixOS systems expert. Write a comprehensive, accurate reference \
document (600-1200 words) explaining: ${TOPIC}

Include:
- What it is and why it matters
- How to use it (with concrete NixOS examples)
- Common pitfalls and best practices
- Relationship to related concepts

Format as plain text with section headers. Be precise and practical."

if [[ "$GAP_IMPORT_LANE" == auto ]]; then
  if ! _generate_with_lane local "$PROMPT"; then
    printf 'WARN  Local generation failed or is unavailable, trying Gemini\n' >&2
    if ! _generate_with_lane gemini "$PROMPT"; then
      printf 'ERROR  No delegate generated content for: %s\n' "$TOPIC" >&2
      exit 1
    fi
  fi
elif ! _generate_with_lane "$GAP_IMPORT_LANE" "$PROMPT"; then
  printf 'ERROR  delegate-to-%s failed or is unavailable for: %s\n' "$GAP_IMPORT_LANE" "$TOPIC" >&2
  exit 1
fi

WORD_COUNT=$(printf '%s\n' "$CONTENT" | wc -w)
printf 'Generated %s words\n' "${WORD_COUNT}"

# ── Import into AIDB ──────────────────────────────────────────────────────────
TITLE="$(printf '%s\n' "$TOPIC" | sed '1s/^./\u&/')"
HTTP_CODE=$(python3 - "$TOPIC" "$TITLE" "$CONTENT" "$PROJECT" <<'PYEOF' | curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${AIDB_URL}/documents" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${AIDB_KEY}" \
  --data-binary @-
import hashlib
import json
import re
import sys

topic, title, content, project = sys.argv[1:]
slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]
if not slug or slug != title.lower().replace(" ", "-"):
    digest = hashlib.sha256(topic.encode("utf-8")).hexdigest()[:8]
    slug = f"{slug}-{digest}" if slug else digest
print(json.dumps({
    "title": title,
    "content": content,
    "project": project,
    "relative_path": f"knowledge/{slug}.md",
}))
PYEOF
) || { printf 'FAIL  curl request failed\n' >&2; exit 1; }

if [[ "$HTTP_CODE" =~ ^2 ]]; then
  printf 'PASS  Imported %s into AIDB (project=%s)\n' "${TITLE}" "${PROJECT}"
else
  printf 'FAIL  AIDB import returned HTTP %s\n' "${HTTP_CODE}" >&2
  exit 1
fi

# ── Optionally clear matching gaps ────────────────────────────────────────────
if [[ "$CLEAR_GAPS" == "true" ]]; then
  LIKE_PATTERN="$(python3 - "$TOPIC" <<'PYEOF'
import re
import sys

print("%" + re.sub(r"([\\%_])", r"\\\1", sys.argv[1][:40]) + "%")
PYEOF
)"
  PG_PASS_FILE="${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}"
  PG_PASS=""
  [[ -r "$PG_PASS_FILE" ]] && PG_PASS="$(tr -d '[:space:]' < "$PG_PASS_FILE")"
  PG_DSN="postgresql://aidb:${PG_PASS}@${POSTGRES_HOST:-127.0.0.1}:${POSTGRES_PORT}/aidb"
  # psql substitutes variables when reading a script, including stdin.
  DELETED=$(psql "$PG_DSN" --no-psqlrc --quiet --tuples-only --no-align \
    -v ON_ERROR_STOP=1 -v pattern="$LIKE_PATTERN" --file - 2>/dev/null <<'SQL' | python3 -c 'import sys; print(sum(1 for line in sys.stdin if line.strip()))'
DELETE FROM query_gaps WHERE query_text ILIKE :'pattern' ESCAPE '\' RETURNING id;
SQL
  ) || { printf 'FAIL  Could not clear matching gap entries from query_gaps\n' >&2; exit 1; }
  printf 'PASS  Cleared %s matching gap entries from query_gaps\n' "${DELETED}"
fi

printf 'Done.\n'
