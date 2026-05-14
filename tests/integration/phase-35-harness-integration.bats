#!/usr/bin/env bats

setup() {
    PROJECT_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    export PROJECT_ROOT

    HYBRID_URL="http://127.0.0.1:${HYBRID_COORDINATOR_PORT:-8003}"
    export HYBRID_URL

    # Read API key from secrets file; fall back to env var if set (CI).
    _key_file="${HYBRID_COORDINATOR_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
    if [[ -r "$_key_file" ]]; then
        HYBRID_KEY="$(tr -d '[:space:]' < "$_key_file")"
    else
        HYBRID_KEY="${HYBRID_API_KEY:-}"
    fi
    export HYBRID_KEY
}

@test "Phase 35: Hybrid Coordinator /health endpoint returns healthy" {
    run curl -s "$HYBRID_URL/health" -H "X-API-Key: $HYBRID_KEY"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.status == "healthy"'
}

@test "Phase 35: Memory storage and recall via MCP tools" {
    # Store a fact (using valid type: semantic)
    run curl -s -X POST "$HYBRID_URL/memory/store" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $HYBRID_KEY" \
        -d '{"content": "Phase 35 integration test fact", "memory_type": "semantic"}'
    [ "$status" -eq 0 ]
    
    # Recall the fact
    run curl -s -X POST "$HYBRID_URL/memory/recall" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $HYBRID_KEY" \
        -d '{"query": "integration test fact"}'
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.results'
    echo "$output" | grep -q "Phase 35"
}

@test "Phase 35: Tree-search retrieval endpoint responds" {
    run curl -s -X POST "$HYBRID_URL/search/tree" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $HYBRID_KEY" \
        -d '{"query": "NixOS deployment", "depth": 2}'
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.combined_results'
}

@test "Phase 35: Harness evaluation endpoint responds" {
    run curl -s -X POST "$HYBRID_URL/harness/eval" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $HYBRID_KEY" \
        -d '{"query": "Test query", "expected_relevance": 0.8}'
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.passed'
}

@test "Phase 35: Harness stats endpoint responds" {
    run curl -s -X GET "$HYBRID_URL/harness/stats" -H "X-API-Key: $HYBRID_KEY"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.total_runs'
}
