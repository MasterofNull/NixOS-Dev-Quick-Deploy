#!/usr/bin/env bats

setup() {
    # Load environment and helpers
    # Assuming standard project structure
    PROJECT_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    export PROJECT_ROOT
    
    # Check if hybrid coordinator is reachable
    # Port 8003 is used in the SystemD service
    HYBRID_URL="http://127.0.0.1:8003"
    export HYBRID_URL
    
    # Static API key for testing based on systemd cat
    HYBRID_KEY="=txgtAyyZJA4K.uwlqfIwrmh7xtA.FXkR1cq.K=iZwEgxZey"
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
    run curl -s "$HYBRID_URL/harness/stats" -H "X-API-Key: $HYBRID_KEY"
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.total_runs'
}
