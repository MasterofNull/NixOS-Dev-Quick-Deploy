#!/usr/bin/env bash
# Qdrant Collections Initialization Script
# Creates and populates the 5 core RAG collections for the hybrid AI learning stack
# Based on COMPREHENSIVE-SYSTEM-ANALYSIS.md specifications

set -euo pipefail

QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-nomic-embed-text}"
VECTOR_SIZE=768  # nomic-embed-text dimension

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Qdrant is accessible
check_qdrant() {
    log_info "Checking Qdrant availability at $QDRANT_URL..."
    if curl -sf "$QDRANT_URL/healthz" > /dev/null 2>&1; then
        log_success "Qdrant is accessible"
        return 0
    else
        log_error "Qdrant is not accessible at $QDRANT_URL"
        return 1
    fi
}

# Create collection if it doesn't exist
create_collection() {
    local collection_name="$1"
    local distance="${2:-Cosine}"

    log_info "Creating collection: $collection_name"

    # Check if collection exists
    if curl -sf "$QDRANT_URL/collections/$collection_name" > /dev/null 2>&1; then
        log_warning "Collection '$collection_name' already exists, skipping creation"
        return 0
    fi

    # Create collection
    local payload=$(cat <<EOF
{
  "vectors": {
    "size": $VECTOR_SIZE,
    "distance": "$distance"
  },
  "optimizers_config": {
    "indexing_threshold": 10000
  },
  "hnsw_config": {
    "m": 16,
    "ef_construct": 100
  }
}
EOF
)

    if curl -sf -X PUT "$QDRANT_URL/collections/$collection_name" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null 2>&1; then
        log_success "Created collection: $collection_name"
        return 0
    else
        log_error "Failed to create collection: $collection_name"
        return 1
    fi
}

# Create payload index for filtering
create_payload_index() {
    local collection_name="$1"
    local field_name="$2"
    local field_type="$3"

    log_info "Creating payload index on $collection_name.$field_name ($field_type)"

    local payload=$(cat <<EOF
{
  "field_name": "$field_name",
  "field_schema": "$field_type"
}
EOF
)

    if curl -sf -X PUT "$QDRANT_URL/collections/$collection_name/index" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null 2>&1; then
        log_success "Created index on $field_name"
        return 0
    else
        log_warning "Failed to create index on $field_name (may already exist)"
        return 0
    fi
}

# Initialize codebase-context collection
init_codebase_context() {
    local collection="codebase-context"

    create_collection "$collection" "Cosine"

    # Create indexes for common filters
    create_payload_index "$collection" "language" "keyword"
    create_payload_index "$collection" "category" "keyword"
    create_payload_index "$collection" "usage_count" "integer"
    create_payload_index "$collection" "success_rate" "float"

    log_success "Initialized $collection collection"
}

# Initialize skills-patterns collection
init_skills_patterns() {
    local collection="skills-patterns"

    create_collection "$collection" "Cosine"

    create_payload_index "$collection" "skill_name" "keyword"
    create_payload_index "$collection" "value_score" "float"

    log_success "Initialized $collection collection"
}

# Initialize error-solutions collection
init_error_solutions() {
    local collection="error-solutions"

    create_collection "$collection" "Cosine"

    create_payload_index "$collection" "error_type" "keyword"
    create_payload_index "$collection" "confidence_score" "float"

    log_success "Initialized $collection collection"
}

# Initialize interaction-history collection
init_interaction_history() {
    local collection="interaction-history"

    create_collection "$collection" "Cosine"

    create_payload_index "$collection" "agent_type" "keyword"
    create_payload_index "$collection" "outcome" "keyword"
    create_payload_index "$collection" "value_score" "float"
    create_payload_index "$collection" "tokens_used" "integer"

    log_success "Initialized $collection collection"
}

# Initialize best-practices collection
init_best_practices() {
    local collection="best-practices"

    create_collection "$collection" "Cosine"

    create_payload_index "$collection" "category" "keyword"
    create_payload_index "$collection" "endorsement_count" "integer"

    log_success "Initialized $collection collection"
}

# Seed initial best practices (NixOS and AI stack guidelines)
seed_best_practices() {
    local collection="best-practices"

    log_info "Seeding best practices into $collection..."

    # Note: This would require embedding generation
    # For now, we'll just log the intent
    log_warning "Best practices seeding requires embedding generation (not implemented yet)"
    log_info "Manual seeding can be done via hybrid coordinator or AIDB endpoints"
}

# Main execution
main() {
    log_info "Starting Qdrant collections initialization..."
    echo

    # Check Qdrant availability
    if ! check_qdrant; then
        log_error "Please ensure Qdrant is running before initializing collections"
        exit 1
    fi

    echo
    log_info "Initializing 5 core RAG collections..."
    echo

    # Initialize all collections
    init_codebase_context
    init_skills_patterns
    init_error_solutions
    init_interaction_history
    init_best_practices

    echo
    log_info "Checking collection status..."

    # List all collections
    local collections
    collections=$(curl -sf "$QDRANT_URL/collections" | jq -r '.result.collections[] | "\(.name): \(.points_count) points"' 2>/dev/null || echo "Unable to fetch collection info")

    echo "$collections"

    echo
    log_success "✅ All collections initialized successfully!"
    echo
    log_info "Next steps:"
    echo "  1. Deploy hybrid coordinator: podman-compose up -d hybrid-coordinator"
    echo "  2. Populate collections via AIDB or hybrid coordinator endpoints"
    echo "  3. Test RAG workflow with sample queries"
    echo
    log_info "Collection URLs:"
    echo "  - Qdrant Dashboard: $QDRANT_URL/dashboard"
    echo "  - Collections API: $QDRANT_URL/collections"
}

main "$@"
