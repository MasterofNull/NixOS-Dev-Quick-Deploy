#!/usr/bin/env bash
# Import Qdrant Collections from Repository
# Restores learned patterns from federated data
#
# Usage: bash scripts/import-collections.sh [collection_name]
#
# If no collection specified, imports all available exports

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
QDRANT_URL="${QDRANT_URL:-http://${SERVICE_HOST:-localhost}:6333}"
INPUT_DIR="$REPO_ROOT/data/collections/snapshots"
CURL_TIMEOUT="${CURL_TIMEOUT:-10}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-3}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Collections that can be imported
FEDERATED_COLLECTIONS=(
    "skills-patterns"
    "error-solutions"
    "best-practices"
)

# ==============================================================================
# Check Qdrant Availability
# ==============================================================================
check_qdrant() {
    log_info "Checking Qdrant availability..."

    if ! curl -sf --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT_TIMEOUT" "$QDRANT_URL/healthz" >/dev/null 2>&1; then
        log_error "Qdrant is not accessible at $QDRANT_URL"
        log_info "Start Qdrant with: kubectl apply -k ai-stack/kubernetes"
        return 1
    fi

    log_success "Qdrant is accessible"
    return 0
}

# ==============================================================================
# Ensure Collection Exists
# ==============================================================================
ensure_collection() {
    local collection=$1

    # Check if collection exists
    if curl -sf --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT_TIMEOUT" "$QDRANT_URL/collections/$collection" >/dev/null 2>&1; then
        log_info "Collection '$collection' already exists"
        return 0
    fi

    # Create collection (768-dim vectors for nomic-embed-text)
    log_info "Creating collection: $collection"

    curl -sf --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT_TIMEOUT" -X PUT "$QDRANT_URL/collections/$collection" \
        -H "Content-Type: application/json" \
        -d '{
            "vectors": {
                "size": 768,
                "distance": "Cosine"
            }
        }' >/dev/null

    log_success "Created collection: $collection"
}

# ==============================================================================
# Import Single Collection
# ==============================================================================
import_collection() {
    local collection=$1
    local snapshot=$(ls -t "$INPUT_DIR/${collection}"-*.json 2>/dev/null | grep -v latest | head -1)

    if [[ ! -f "$snapshot" ]]; then
        log_warning "No export found for collection '$collection', skipping"
        return
    fi

    log_info "Importing collection: $collection from $(basename "$snapshot")"

    # Ensure collection exists
    ensure_collection "$collection"

    # Extract and import points
    local points=$(jq -c '.result.points[]' "$snapshot" 2>/dev/null)

    if [[ -z "$points" ]]; then
        log_warning "No points found in export, skipping"
        return
    fi

    local count=0
    local batch=()
    local batch_size=100

    while IFS= read -r point; do
        batch+=("$point")
        ((count++))

        # Import in batches of 100
        if [[ ${#batch[@]} -ge $batch_size ]]; then
            local batch_json=$(printf '%s\n' "${batch[@]}" | jq -s -c '{points: .}')

            curl -sf --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT_TIMEOUT" -X PUT "$QDRANT_URL/collections/$collection/points" \
                -H "Content-Type: application/json" \
                -d "$batch_json" >/dev/null

            batch=()
        fi
    done <<< "$points"

    # Import remaining points
    if [[ ${#batch[@]} -gt 0 ]]; then
        local batch_json=$(printf '%s\n' "${batch[@]}" | jq -s -c '{points: .}')

        curl -sf --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT_TIMEOUT" -X PUT "$QDRANT_URL/collections/$collection/points" \
            -H "Content-Type: application/json" \
            -d "$batch_json" >/dev/null
    fi

    log_success "Imported $collection: $count points"
}

# ==============================================================================
# Import All Collections
# ==============================================================================
import_all() {
    log_info "Importing federated collections..."
    echo

    local success_count=0

    for collection in "${FEDERATED_COLLECTIONS[@]}"; do
        if import_collection "$collection"; then
            ((success_count++))
        fi
    done

    echo
    log_success "Imported $success_count collections"
}

# ==============================================================================
# Main Execution
# ==============================================================================
main() {
    log_info "Qdrant Collection Import"
    echo

    # Check input directory exists
    if [[ ! -d "$INPUT_DIR" ]]; then
        log_error "No collection exports found at $INPUT_DIR"
        log_info "Export collections first with: bash scripts/export-collections.sh"
        exit 1
    fi

    # Check Qdrant is running
    if ! check_qdrant; then
        exit 1
    fi

    echo

    # Import collections
    if [[ $# -gt 0 ]]; then
        # Import specific collection
        import_collection "$1"
    else
        # Import all available exports
        import_all
    fi

    echo
    log_success "✅ Import complete!"
    echo
    log_info "Verify collections:"
    echo "  curl $QDRANT_URL/collections"
    echo
    log_info "View collection details:"
    echo "  curl $QDRANT_URL/collections/skills-patterns"
    echo
}

main "$@"
