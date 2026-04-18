#!/usr/bin/env bash
# scripts/data/fix-embedding-dimensions.sh
#
# Fixes embedding dimension mismatches after switching embedding models.
# This script:
# 1. Drops Qdrant collections with wrong dimensions
# 2. Clears PostgreSQL embeddings with wrong dimensions
# 3. Lets the system recreate collections and re-embed documents with correct dimensions
#
# Requirements:
#   - Root/sudo access (for systemctl restart)
#   - jq installed (for JSON parsing)
#   - AIDB API key available at /run/secrets/aidb_api_key or via AIDB_API_KEY env var
#   - Services: ai-aidb.service, ai-hybrid-coordinator.service
#
# Usage:
#   sudo bash scripts/data/fix-embedding-dimensions.sh

set -euo pipefail

QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
AIDB_URL="${AIDB_URL:-http://127.0.0.1:8002}"
AIDB_API_KEY="${AIDB_API_KEY:-$(cat /run/secrets/aidb_api_key 2>/dev/null || true)}"
AIDB_API_KEY="${AIDB_API_KEY//[$'\t\r\n ']/}"
CURRENT_DIM=1024  # BGE-M3 dimension

if [[ -z "$AIDB_API_KEY" ]]; then
    echo "ERROR: No API key found. Set AIDB_API_KEY or ensure /run/secrets/aidb_api_key is readable" >&2
    exit 1
fi

echo "=== Embedding Dimension Fix ==="
echo "Current configured dimension: $CURRENT_DIM"
echo ""

# List collections and their dimensions
echo "Checking Qdrant collections..."
collections_json=$(curl -s "$QDRANT_URL/collections")
collection_names=$(echo "$collections_json" | jq -r '.result.collections[].name')

collections_to_drop=()
for collection in $collection_names; do
    dim=$(curl -s "$QDRANT_URL/collections/$collection" | jq -r '.result.config.params.vectors.size')
    if [[ "$dim" != "$CURRENT_DIM" ]]; then
        echo "  ✗ $collection: $dim dimensions (wrong - will drop)"
        collections_to_drop+=("$collection")
    else
        echo "  ✓ $collection: $dim dimensions (correct)"
    fi
done

echo ""

if [[ ${#collections_to_drop[@]} -eq 0 ]]; then
    echo "All collections have correct dimensions!"
else
    echo "Dropping ${#collections_to_drop[@]} collection(s) with wrong dimensions..."
    for collection in "${collections_to_drop[@]}"; do
        echo "  Dropping $collection..."
        response=$(curl -s -X DELETE "$QDRANT_URL/collections/$collection")
        if echo "$response" | jq -e '.result == true' >/dev/null 2>&1; then
            echo "    ✓ Dropped successfully"
        else
            echo "    ✗ Failed: $response" >&2
        fi
    done
fi

echo ""
echo "=== PostgreSQL Embedding Cleanup ==="
echo "Clearing embeddings from imported_documents table..."

# Call AIDB endpoint to clear embeddings (this will prevent HNSW index errors)
# The AIDB service should handle this gracefully
response=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${AIDB_API_KEY}" \
    "$AIDB_URL/admin/clear-embeddings" 2>&1 || echo '{"error":"endpoint may not exist"}')

if echo "$response" | jq -e '.success' >/dev/null 2>&1; then
    echo "  ✓ Embeddings cleared via AIDB"
elif echo "$response" | grep -q "endpoint may not exist"; then
    echo "  ℹ AIDB admin endpoint not available - embeddings will be overwritten on re-index"
else
    echo "  ⚠ Response: $response"
fi

echo ""
echo "=== Restart AI Services ==="
echo "Restarting AI services to recreate collections with correct dimensions..."

systemctl restart ai-aidb.service ai-hybrid-coordinator.service

echo "Waiting for services to stabilize..."
sleep 5

# Check service status
for service in ai-aidb.service ai-hybrid-coordinator.service; do
    if systemctl is-active --quiet "$service"; then
        echo "  ✓ $service is running"
    else
        echo "  ✗ $service failed to start" >&2
        systemctl status "$service" --no-pager || true
    fi
done

echo ""
echo "=== Re-index Documents ==="
echo "Re-indexing all documents with correct embedding dimensions..."
echo "This will populate collections with $CURRENT_DIM-dimensional embeddings."
echo ""

bash "$(dirname "$0")/rebuild-qdrant-collections.sh"

echo ""
echo "=== Fix Complete ==="
echo "All collections should now have $CURRENT_DIM dimensions."
echo "Verify with: curl -s http://127.0.0.1:6333/collections | jq -r '.result.collections[] | \"\\(.name): \\(.vectors_count) vectors\"'"
