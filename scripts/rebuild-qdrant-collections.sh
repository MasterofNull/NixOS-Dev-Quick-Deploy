#!/usr/bin/env bash
# scripts/rebuild-qdrant-collections.sh
#
# Re-indexes all AIDB imported_documents into the vector store (Qdrant via AIDB).
#
# How it works:
#   1. GET $AIDB_URL/documents  — list all approved documents
#   2. For each document, POST $AIDB_URL/vector/index with {"items":[{"document_id":N}]}
#      The AIDB async handler auto-fetches content from PostgreSQL and computes the
#      embedding via the configured llama-embed backend — no separate /vector/embed
#      call is needed.
#
# Environment:
#   AIDB_URL   Override AIDB base URL (default: http://127.0.0.1:8002)
#
# Usage:
#   bash scripts/rebuild-qdrant-collections.sh
#   AIDB_URL=http://other-host:8002 bash scripts/rebuild-qdrant-collections.sh

set -euo pipefail

AIDB_URL="${AIDB_URL:-http://127.0.0.1:8002}"
AIDB_API_KEY="${AIDB_API_KEY:-$(cat /run/secrets/aidb_api_key 2>/dev/null || true)}"
AIDB_API_KEY="${AIDB_API_KEY//[$'\t\r\n ']/}"

if [[ -z "$AIDB_API_KEY" ]]; then
    printf 'rebuild-qdrant-collections: ERROR — no API key found; set AIDB_API_KEY or ensure /run/secrets/aidb_api_key is readable\n' >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Fetch document list (no content needed — AIDB fetches it server-side)
# ---------------------------------------------------------------------------
printf 'rebuild-qdrant-collections: fetching document list from %s/documents\n' "$AIDB_URL"
_list_resp="$(curl -s --max-time 30 \
    -H "X-API-Key: ${AIDB_API_KEY}" \
    "${AIDB_URL}/documents?include_content=false&limit=10000")"

if ! printf '%s' "$_list_resp" | jq -e '.documents' >/dev/null 2>&1; then
    printf 'rebuild-qdrant-collections: ERROR — unexpected response from /documents:\n%s\n' "$_list_resp" >&2
    exit 1
fi

_total="$(printf '%s' "$_list_resp" | jq '.total')"
printf 'rebuild-qdrant-collections: %d document(s) to re-index\n' "$_total"

if [[ "$_total" -eq 0 ]]; then
    printf 'rebuild-qdrant-collections: nothing to do\n'
    exit 0
fi

# ---------------------------------------------------------------------------
# Re-index each document
# ---------------------------------------------------------------------------
_embedded=0
_failed=0
_idx=0

while IFS=$'\t' read -r _doc_id _title; do
    _idx=$((_idx + 1))
    printf 'embedding doc %d/%d: %s\n' "$_idx" "$_total" "$_title"

    _payload="$(printf '{"items":[{"document_id":%s}]}' "$_doc_id")"

    _http_code="$(curl -s --max-time 60 \
        -o /tmp/_aidb_index_resp.json \
        -w '%{http_code}' \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-API-Key: ${AIDB_API_KEY}" \
        -d "$_payload" \
        "${AIDB_URL}/vector/index")"

    if [[ "$_http_code" == "200" ]]; then
        _embedded=$((_embedded + 1))
    else
        _body="$(cat /tmp/_aidb_index_resp.json 2>/dev/null || true)"
        printf 'rebuild-qdrant-collections: WARN — doc %s returned HTTP %s: %s\n' \
            "$_doc_id" "$_http_code" "$_body" >&2
        _failed=$((_failed + 1))
    fi

    # Gentle rate limiting to avoid overwhelming the embedding backend
    sleep 0.1

done < <(printf '%s' "$_list_resp" | jq -r '.documents[] | [.id, (.title // .relative_path // "untitled")] | @tsv')

rm -f /tmp/_aidb_index_resp.json

# ---------------------------------------------------------------------------
printf 'rebuild: %d documents embedded' "$_embedded"
if [[ $_failed -gt 0 ]]; then
    printf ', %d failed' "$_failed"
fi
printf '\n'

if [[ $_failed -gt 0 ]]; then
    exit 1
fi
