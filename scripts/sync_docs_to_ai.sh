#!/usr/bin/env bash
#
# Sync NixOS-Dev-Quick-Deploy documentation into the AIDB (AI-Optimizer) catalog.
#
# Usage:
#   ./scripts/sync_docs_to_ai.sh [--docs DIR] [--project NAME]
#
# Environment variables:
#   AIDB_BASE_URL   - Base URL for the AIDB MCP API (default: http://localhost:8091)
#   DOCS_DIR        - Documentation directory to sync (default: ./docs)
#   PROJECT_NAME    - Logical project name within AIDB (default: NixOS-Dev-Quick-Deploy)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AIDB_BASE_URL="${AIDB_BASE_URL:-http://localhost:8091}"
DOCS_DIR="${DOCS_DIR:-${SCRIPT_DIR}/docs}"
PROJECT_NAME="${PROJECT_NAME:-${AIDB_PROJECT_NAME:-NixOS-Dev-Quick-Deploy}}"
AIDB_API_KEY="${AIDB_API_KEY:-}"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --docs DIR        Documentation directory to import (default: ${DOCS_DIR})
  --project NAME    Project name recorded in AIDB (default: ${PROJECT_NAME})
  -h, --help        Show this message

Environment variables:
  AIDB_BASE_URL   Override the MCP API endpoint
  DOCS_DIR        Default documentation directory
  PROJECT_NAME    Default project name
EOF
}

log_info()    { printf '[INFO] %s\n' "$*"; }
log_warning() { printf '[WARN] %s\n' "$*" >&2; }
log_error()   { printf '[ERROR] %s\n' "$*" >&2; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --docs)
            DOCS_DIR="$2"
            shift 2
            ;;
        --project)
            PROJECT_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if ! command -v jq >/dev/null 2>&1; then
    log_error "jq is required for JSON encoding"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    log_error "curl is required to communicate with AIDB"
    exit 1
fi

if [[ ! -d "$DOCS_DIR" ]]; then
    log_error "Documentation directory not found: $DOCS_DIR"
    exit 1
fi

log_info "Verifying AI-Optimizer availability at ${AIDB_BASE_URL}"
if ! curl -fs --max-time 5 "${AIDB_BASE_URL}/health" >/dev/null 2>&1; then
    log_error "Unable to reach AI-Optimizer at ${AIDB_BASE_URL}/health"
    exit 1
fi

log_info "Syncing markdown files from ${DOCS_DIR} (project: ${PROJECT_NAME})"
synced=0
skipped=0
curl_headers=(-H "Content-Type: application/json")
if [[ -n "$AIDB_API_KEY" ]]; then
    curl_headers+=(-H "Authorization: Bearer ${AIDB_API_KEY}")
fi

while IFS= read -r -d '' doc_file; do
    relative_path="${doc_file#${DOCS_DIR}/}"
    content_json=$(jq -Rs . < "$doc_file")
    checksum=$(sha256sum "$doc_file" | awk '{print $1}')

    payload=$(jq -n \
        --arg project "$PROJECT_NAME" \
        --arg relpath "$relative_path" \
        --arg title "$(basename "$doc_file" .md)" \
        --arg checksum "$checksum" \
        --arg content "$content_json" \
        '{
            project: $project,
            relative_path: $relpath,
            title: $title,
            content_type: "text/markdown",
            checksum: $checksum,
            content: ($content | fromjson)
        }')

    response=$(curl -fsS -X POST "${AIDB_BASE_URL}/documents" \
        "${curl_headers[@]}" \
        -d "$payload" \
        || true)

    if [[ -z "$response" ]]; then
        log_warning "No response for ${relative_path}; skipping"
        ((skipped++)) || true
        continue
    fi

    status=$(echo "$response" | jq -r '.status // .message // "ok"' 2>/dev/null || echo "ok")
    log_info "Imported ${relative_path} (${status})"
    ((synced++)) || true
done < <(find "$DOCS_DIR" -type f -name '*.md' -print0)

log_info "Documentation sync complete: ${synced} files processed, ${skipped} skipped."
