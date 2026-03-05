#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

COLLECTION="${RAG_SMOKE_COLLECTION:-ops-rag-smoke}"
INPUT_TEXT="${RAG_SMOKE_INPUT:-rag smoke test}"
POINT_ID="${RAG_SMOKE_POINT_ID:-1}"

usage() {
  cat <<'USAGE'
Usage: rag-smoke-test.sh [--collection NAME] [--input TEXT] [--point-id ID]

Performs deterministic RAG smoke validation:
1) Generate embedding from EMBEDDINGS_URL
2) Create/validate Qdrant collection
3) Upsert sentinel vector
4) Query top match and assert sentinel is retrievable
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --collection)
      COLLECTION="$2"
      shift 2
      ;;
    --input)
      INPUT_TEXT="$2"
      shift 2
      ;;
    --point-id)
      POINT_ID="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd jq

echo "RAG smoke: generating embedding via ${EMBEDDINGS_URL%/}/v1/embeddings"
embedding="$(curl -fsS --max-time 10 --connect-timeout 3 \
  "${EMBEDDINGS_URL%/}/v1/embeddings" \
  -H 'Content-Type: application/json' \
  -d "{\"input\":\"${INPUT_TEXT}\",\"model\":\"text-embedding\"}" \
  | jq -c '.data[0].embedding')"

if [[ -z "$embedding" || "$embedding" == "null" ]]; then
  echo "Failed to generate embedding payload" >&2
  exit 1
fi

dim="$(jq 'length' <<<"$embedding")"
if [[ "$dim" -le 0 ]]; then
  echo "Invalid embedding dimension: $dim" >&2
  exit 1
fi
echo "RAG smoke: embedding dimension=${dim}"

collection_info="$(curl -fsS --max-time 5 --connect-timeout 3 \
  "${QDRANT_URL%/}/collections/${COLLECTION}" 2>/dev/null || true)"
if [[ -n "$collection_info" ]]; then
  existing_dim="$(jq -r '.result.config.params.vectors.size // empty' <<<"$collection_info")"
  if [[ -n "$existing_dim" && "$existing_dim" != "$dim" ]]; then
    echo "Collection ${COLLECTION} dimension mismatch: existing=${existing_dim} expected=${dim}" >&2
    exit 1
  fi
else
  echo "RAG smoke: creating collection ${COLLECTION}"
  curl -fsS --max-time 10 --connect-timeout 3 \
    -X PUT "${QDRANT_URL%/}/collections/${COLLECTION}" \
    -H 'Content-Type: application/json' \
    -d "{\"vectors\":{\"size\":${dim},\"distance\":\"Cosine\"}}" >/dev/null
fi

upsert_payload="$(jq -nc \
  --argjson vec "$embedding" \
  --arg id "$POINT_ID" \
  --arg txt "$INPUT_TEXT" \
  '{points:[{id:($id|tonumber),vector:$vec,payload:{source:"rag-smoke",text:$txt}}]}')"

curl -fsS --max-time 10 --connect-timeout 3 \
  -X PUT "${QDRANT_URL%/}/collections/${COLLECTION}/points" \
  -H 'Content-Type: application/json' \
  -d "$upsert_payload" >/dev/null

query_payload="$(jq -nc --argjson vec "$embedding" '{vector:$vec,limit:1,with_payload:true}')"
query_result="$(curl -fsS --max-time 10 --connect-timeout 3 \
  -X POST "${QDRANT_URL%/}/collections/${COLLECTION}/points/query" \
  -H 'Content-Type: application/json' \
  -d "$query_payload")"

top_id="$(jq -r '.result.points[0].id // .result[0].id // empty' <<<"$query_result")"
if [[ -z "$top_id" ]]; then
  echo "RAG smoke query returned no results" >&2
  jq . <<<"$query_result" >&2 || true
  exit 1
fi

if [[ "$top_id" != "$POINT_ID" ]]; then
  echo "RAG smoke top hit mismatch: expected=${POINT_ID} got=${top_id}" >&2
  jq . <<<"$query_result" >&2 || true
  exit 1
fi

echo "RAG smoke test passed: collection=${COLLECTION} top_id=${top_id} dim=${dim}"
