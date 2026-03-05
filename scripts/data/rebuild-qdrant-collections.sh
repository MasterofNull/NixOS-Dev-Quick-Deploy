#!/usr/bin/env bash
# scripts/data/rebuild-qdrant-collections.sh
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
#   bash scripts/data/rebuild-qdrant-collections.sh
#   AIDB_URL=http://other-host:8002 bash scripts/data/rebuild-qdrant-collections.sh

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
# Re-index documents in batches (much faster than one-at-a-time)
# ---------------------------------------------------------------------------
_embedded=0
_failed=0
_batch_size=10
_batch=()
_batch_ids=()

process_batch() {
    local batch_json="$1"
    local batch_count="$2"
    
    _http_code="$(curl -s --max-time 300 \
        -o /tmp/_aidb_index_resp.json \
        -w '%{http_code}' \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-API-Key: ${AIDB_API_KEY}" \
        -d "$batch_json" \
        "${AIDB_URL}/vector/index")"
    
    if [[ "$_http_code" == "200" ]]; then
        _embedded=$((_embedded + batch_count))
        printf '  ✓ Batch of %d embedded OK\n' "$batch_count"
    else
        _body="$(cat /tmp/_aidb_index_resp.json 2>/dev/null || true)"
        printf '  ✗ Batch failed HTTP %s: %s\n' "$_http_code" "$_body" >&2
        _failed=$((_failed + batch_count))
    fi
}

printf '\nProcessing documents in batches of %d...\n\n' "$_batch_size"

# Initialize counters
_idx=0
_embedded=0
_failed=0

while IFS=$'\t' read -r _doc_id _title; do
    _idx=$((_idx + 1))
    
    if [[ $((_idx % _batch_size)) -eq 1 ]]; then
        # Start new batch
        _batch=("{\"document_id\":$_doc_id}")
        _batch_ids=("$_title")
    else
        # Add to batch
        _batch+=(",{\"document_id\":$_doc_id}")
        _batch_ids+=("$_title")
    fi
    
    # Show progress
    if [[ $((_idx % _batch_size)) -eq 0 ]] || [[ $_idx -eq $_total ]]; then
        printf '[%d/%d] Embedding batch: %s\n' "$_idx" "$_total" "${_batch_ids[0]}"
        if [[ ${#_batch_ids[@]} -gt 1 ]]; then
            printf '         + %d more...\n' "$((${#_batch_ids[@]} - 1))"
        fi
        
        # Process batch
        _batch_json="{\"items\":[$(IFS=; echo "${_batch[*]}")]}"
        process_batch "$_batch_json" "${#_batch_ids[@]}"
        
        # Clear batch
        _batch=()
        _batch_ids=()
        
        # Small delay between batches (not between individual docs)
        sleep 0.5
    fi
done < <(printf '%s' "$_list_resp" | jq -r '.documents[] | [.id, (.title // .relative_path // "untitled")] | @tsv')

rm -f /tmp/_aidb_index_resp.json

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf '\nrebuild-qdrant-collections summary:\n'
printf '  embedded: %d/%d\n' "$_embedded" "$_total"
if [[ $_failed -gt 0 ]]; then
    printf '  failed:   %d\n' "$_failed"
fi

if [[ $_failed -gt 0 ]]; then
    exit 1
fi
printf '\nrebuild-qdrant-collections: complete\n'
