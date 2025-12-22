#!/usr/bin/env bash
# Export Qdrant Collections to Repository
# Creates JSON exports of learned patterns for federation
#
# Usage: bash scripts/export-collections.sh [collection_name]
#
# If no collection specified, exports all federated collections

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
OUTPUT_DIR="$REPO_ROOT/data/collections/snapshots"
DATE=$(date +%Y-%m-%d)

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

# Collections to export (high-value learning data)
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

    if ! curl -sf "$QDRANT_URL/healthz" >/dev/null 2>&1; then
        log_error "Qdrant is not accessible at $QDRANT_URL"
        log_info "Start Qdrant with: podman-compose -f ai-stack/compose/docker-compose.yml up -d qdrant"
        return 1
    fi

    log_success "Qdrant is accessible"
    return 0
}

# ==============================================================================
# Export Single Collection
# ==============================================================================
export_collection() {
    local collection=$1
    local output="$OUTPUT_DIR/${collection}-${DATE}.json"

    log_info "Exporting collection: $collection"

    # Check if collection exists
    if ! curl -sf "$QDRANT_URL/collections/$collection" >/dev/null 2>&1; then
        log_warning "Collection '$collection' does not exist, skipping"
        return
    fi

    # Get collection info
    local info=$(curl -sf "$QDRANT_URL/collections/$collection")
    local points_count=$(echo "$info" | jq -r '.result.points_count // 0')

    if [[ "$points_count" -eq 0 ]]; then
        log_warning "Collection '$collection' is empty, skipping"
        return
    fi

    # Export points (payload only, no vectors to save space)
    local export_data=$(curl -sf -X POST "$QDRANT_URL/collections/$collection/points/scroll" \
        -H "Content-Type: application/json" \
        -d '{
            "limit": 10000,
            "with_payload": true,
            "with_vector": false
        }')

    # Save to file
    echo "$export_data" > "$output"

    local exported_count=$(echo "$export_data" | jq -r '.result.points | length')
    log_success "Exported $collection: $exported_count points → $output"

    # Create latest symlink
    ln -sf "$(basename "$output")" "$OUTPUT_DIR/${collection}-latest.json"
}

# ==============================================================================
# Export All Collections
# ==============================================================================
export_all() {
    log_info "Exporting federated collections..."
    echo

    local success_count=0

    for collection in "${FEDERATED_COLLECTIONS[@]}"; do
        if export_collection "$collection"; then
            ((success_count++))
        fi
    done

    echo
    log_success "Exported $success_count collections"

    # Cleanup old exports (keep last 10)
    for collection in "${FEDERATED_COLLECTIONS[@]}"; do
        ls -t "$OUTPUT_DIR/${collection}"-*.json 2>/dev/null | \
            grep -v latest | \
            tail -n +11 | \
            xargs rm -f 2>/dev/null || true
    done
}

# ==============================================================================
# Main Execution
# ==============================================================================
main() {
    log_info "Qdrant Collection Export"
    echo

    # Ensure output directory exists
    mkdir -p "$OUTPUT_DIR"

    # Check Qdrant is running
    if ! check_qdrant; then
        exit 1
    fi

    echo

    # Export collections
    if [[ $# -gt 0 ]]; then
        # Export specific collection
        export_collection "$1"
    else
        # Export all federated collections
        export_all
    fi

    echo
    log_success "✅ Export complete!"
    echo
    log_info "Next steps:"
    echo "  1. Review exports in data/collections/snapshots/"
    echo "  2. Commit to git: git add data/ && git commit -m 'Export collection snapshots'"
    echo "  3. Push to share: git push"
    echo
    log_info "To import on another system:"
    echo "  bash scripts/import-collections.sh"
    echo
}

main "$@"
