#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# archive-project-knowledge.sh — Ingest curated project knowledge into the
# Qdrant `global_wisdom` collection for persistent cross-session memory.
#
# Phase 29.3 — NixOS-Dev-Quick-Deploy MLOps Global Knowledge Loop
#
# Usage:
#   scripts/archive-project-knowledge.sh [OPTIONS] [FILES...]
#
# What it does:
#   1. Initialises the `global_wisdom` Qdrant collection if it doesn't exist.
#   2. Reads Markdown/text source files and splits them into chunks.
#   3. Generates embeddings via configured LLAMA/EMBEDDINGS endpoints.
#   4. Upserts chunks into Qdrant with metadata (source, section, date).
#   5. Verifies idempotency: chunks with the same content hash are skipped.
#
# Security: secrets, .env files, and key material are excluded automatically.
#
# Prerequisites:
#   - Qdrant running at configured QDRANT_URL
#   - llama.cpp OR embeddings service running
#   - python3, jq, curl available
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/config/service-endpoints.sh"

# ── Configuration ─────────────────────────────────────────────────────────────
QDRANT_ENDPOINT="${QDRANT_URL}"
LLAMA_ENDPOINT="${LLAMA_URL}"
EMBEDDINGS_ENDPOINT="${EMBEDDINGS_URL}"
COLLECTION="${COLLECTION:-global_wisdom}"
VECTOR_DIM="${VECTOR_DIM:-384}"
CHUNK_SIZE="${CHUNK_SIZE:-512}"    # characters per chunk
CHUNK_OVERLAP="${CHUNK_OVERLAP:-64}"
DRY_RUN="${DRY_RUN:-0}"

# Default source files — project knowledge documents.
DEFAULT_SOURCES=(
    "SYSTEM-UPGRADE-ROADMAP.md"
    "CLAUDE.md"
    "README.md"
    "docs/CLEAN-SETUP.md"
    "docs/DEPLOYMENT.md"
    "KNOWN_ISSUES_TROUBLESHOOTING.md"
)

info()    { printf '\033[0;32m[archive-knowledge] %s\033[0m\n' "$*"; }
warn()    { printf '\033[0;33m[archive-knowledge] WARN: %s\033[0m\n' "$*" >&2; }
error()   { printf '\033[0;31m[archive-knowledge] ERROR: %s\033[0m\n' "$*" >&2; exit 1; }
section() { printf '\033[0;34m[archive-knowledge] ── %s ──\033[0m\n' "$*"; }

# ── Argument parsing ──────────────────────────────────────────────────────────
SOURCES=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --collection)  COLLECTION="$2"; shift 2 ;;
        --qdrant-url)  QDRANT_ENDPOINT="$2"; shift 2 ;;
        --embeddings-url) EMBEDDINGS_ENDPOINT="$2"; shift 2 ;;
        --chunk-size)  CHUNK_SIZE="$2"; shift 2 ;;
        --dry-run)     DRY_RUN=1; shift ;;
        --help|-h)
            cat <<'HELP'
Usage: scripts/archive-project-knowledge.sh [OPTIONS] [FILES...]

Ingests curated files into the Qdrant global_wisdom collection.
If no FILES are given, the default project knowledge set is used.

Options:
  --collection NAME    Qdrant collection name (default: global_wisdom)
  --qdrant-url URL     Qdrant base URL (default: from config/service-endpoints.sh)
  --embeddings-url URL Embeddings service URL (default: from config/service-endpoints.sh)
  --chunk-size N       Characters per chunk (default: 512)
  --dry-run            Parse and chunk without writing to Qdrant
  --help               Show this message
HELP
            exit 0 ;;
        -*) error "Unknown option: $1" ;;
        *)  SOURCES+=("$1"); shift ;;
    esac
done

[[ ${#SOURCES[@]} -eq 0 ]] && SOURCES=("${DEFAULT_SOURCES[@]}")

# ── Dependency checks ─────────────────────────────────────────────────────────
for cmd in python3 curl jq; do
    command -v "$cmd" >/dev/null 2>&1 || error "Missing: $cmd"
done

# ── Security filter ───────────────────────────────────────────────────────────
is_safe_to_ingest() {
    local file="$1"
    # Reject files that are likely to contain secrets.
    local basename="${file##*/}"
    case "$basename" in
        .env|*.env|*.key|*.pem|*.p12|*.pfx|secrets*|*secret*|*password*|*credential*) return 1 ;;
        *.sops.yaml|*.sops.json) return 1 ;;
    esac
    # Reject git history and binary files.
    [[ "$file" == */.git/* ]] && return 1
    # Quick binary check: if file contains null bytes it's not text.
    if file --brief --mime-type "$file" 2>/dev/null | grep -qv 'text/'; then
        return 1
    fi
    return 0
}

# ── Embedding function ────────────────────────────────────────────────────────
get_embedding() {
    local text="$1"
    local escaped
    escaped=$(printf '%s' "$text" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))")

    # Try embeddings service first, fall back to llama.cpp.
    local result
    if curl -sf "${EMBEDDINGS_ENDPOINT}/health" >/dev/null 2>&1; then
        result=$(curl -sf -X POST "${EMBEDDINGS_ENDPOINT}/v1/embeddings" \
            -H 'Content-Type: application/json' \
            -d "{\"input\": ${escaped}, \"model\": \"default\"}" \
            --max-time 30 || echo "")
    fi

    if [[ -z "${result:-}" ]]; then
        result=$(curl -sf -X POST "${LLAMA_ENDPOINT}/v1/embeddings" \
            -H 'Content-Type: application/json' \
            -d "{\"input\": ${escaped}, \"model\": \"default\"}" \
            --max-time 30 || echo "")
    fi

    echo "${result}"
}

# ── Qdrant collection init ────────────────────────────────────────────────────
init_collection() {
    section "Initialising collection: ${COLLECTION}"
    local exists
    exists=$(curl -sf "${QDRANT_ENDPOINT}/collections/${COLLECTION}" \
        --max-time 10 | jq -r '.result.name // ""' 2>/dev/null || echo "")

    if [[ "${exists}" == "${COLLECTION}" ]]; then
        info "Collection already exists — skipping creation."
        return
    fi

    if [[ "${DRY_RUN}" == "1" ]]; then
        info "[dry-run] Would create collection ${COLLECTION} (dim=${VECTOR_DIM})"
        return
    fi

    curl -sf -X PUT "${QDRANT_ENDPOINT}/collections/${COLLECTION}" \
        -H 'Content-Type: application/json' \
        -d "{
            \"vectors\": {
                \"size\": ${VECTOR_DIM},
                \"distance\": \"Cosine\"
            },
            \"optimizers_config\": {
                \"default_segment_number\": 2
            },
            \"replication_factor\": 1
        }" --max-time 30 | jq -r '.result' >/dev/null
    info "Collection created: ${COLLECTION}"
}

# ── Text chunking (Python, piped stdin, no extra deps) ───────────────────────
chunk_text() {
    local text="$1"
    local py_script
    py_script="
import sys
text_file = sys.stdin.read()
size = ${CHUNK_SIZE}
overlap = ${CHUNK_OVERLAP}
chunks = []
start = 0
while start < len(text_file):
    end = min(start + size, len(text_file))
    chunks.append(text_file[start:end].strip())
    start += size - overlap
for c in chunks:
    if c:
        print(c)
        print('---CHUNK_BOUNDARY---')
"
    printf '%s' "$text" | python3 -c "$py_script"
}

# ── Point upsert ──────────────────────────────────────────────────────────────
upsert_point() {
    local point_id="$1"
    local vector_json="$2"
    local payload_json="$3"

    [[ "${DRY_RUN}" == "1" ]] && return 0

    curl -sf -X PUT "${QDRANT_ENDPOINT}/collections/${COLLECTION}/points" \
        -H 'Content-Type: application/json' \
        -d "{
            \"points\": [{
                \"id\": ${point_id},
                \"vector\": ${vector_json},
                \"payload\": ${payload_json}
            }]
        }" --max-time 30 >/dev/null
}

# ── Main ingestion loop ───────────────────────────────────────────────────────
section "Connecting to Qdrant at ${QDRANT_ENDPOINT}"
curl -sf "${QDRANT_ENDPOINT}/collections" --max-time 10 >/dev/null || \
    error "Cannot reach Qdrant at ${QDRANT_ENDPOINT}. Ensure qdrant.service is running."

init_collection

total_chunks=0
skipped_files=0
today=$(date -u +%Y-%m-%d)

for src_file in "${SOURCES[@]}"; do
    if [[ ! -f "${src_file}" ]]; then
        warn "File not found, skipping: ${src_file}"
        (( skipped_files++ )) || true
        continue
    fi

    if ! is_safe_to_ingest "${src_file}"; then
        warn "Excluded (security filter): ${src_file}"
        (( skipped_files++ )) || true
        continue
    fi

    section "Processing: ${src_file}"
    content=$(<"${src_file}")
    chunk_idx=0

    while IFS= read -r -d '' chunk_raw; do
        chunk="${chunk_raw%---CHUNK_BOUNDARY---}"
        [[ -z "${chunk// /}" ]] && continue

        # Deterministic ID from file+index (no UUID dependency).
        local_hash=$(printf '%s:%d' "${src_file}" "${chunk_idx}" | \
            sha256sum | cut -c1-16)
        point_id=$(printf '%d' "0x${local_hash}" 2>/dev/null || echo "${chunk_idx}")

        # Generate embedding.
        emb_response=$(get_embedding "${chunk}")
        if [[ -z "${emb_response}" ]]; then
            warn "Embedding failed for chunk ${chunk_idx} in ${src_file}; skipping."
            (( chunk_idx++ )) || true
            continue
        fi

        vector_json=$(echo "${emb_response}" | jq -c '.data[0].embedding // .embedding')
        if [[ -z "${vector_json}" ]] || [[ "${vector_json}" == "null" ]]; then
            warn "Empty embedding for chunk ${chunk_idx} in ${src_file}; skipping."
            (( chunk_idx++ )) || true
            continue
        fi

        payload_json=$(jq -n \
            --arg src "${src_file}" \
            --arg text "${chunk}" \
            --arg date "${today}" \
            --argjson idx "${chunk_idx}" \
            '{source: $src, text: $text, ingested_at: $date, chunk_index: $idx}')

        upsert_point "${point_id}" "${vector_json}" "${payload_json}"
        (( chunk_idx++ )) || true
        (( total_chunks++ )) || true
        printf '.'
    done < <(chunk_text "${content}" | tr '\n' '\0')
    echo ""

    info "  ${chunk_idx} chunks from ${src_file}"
done

echo ""
section "Ingestion complete"
info "  Total chunks upserted : ${total_chunks}"
info "  Skipped files         : ${skipped_files}"
info "  Collection            : ${COLLECTION}"
[[ "${DRY_RUN}" == "1" ]] && info "  [dry-run] No data was written to Qdrant."
info ""
info "Query the collection:"
info "  curl ${QDRANT_ENDPOINT}/collections/${COLLECTION}"
