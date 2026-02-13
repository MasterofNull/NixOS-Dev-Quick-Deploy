#!/usr/bin/env bash
# Generate Test Telemetry Events
# This script creates sample telemetry events to test the continuous learning pipeline

set -euo pipefail

TELEMETRY_DIR="${HOME}/.local/share/nixos-ai-stack/telemetry"
TEST_TELEMETRY_DIR="${HOME}/.local/share/nixos-ai-stack/test-telemetry"
mkdir -p "$TEST_TELEMETRY_DIR"

# Check if we can write to the main telemetry directory
if [[ -w "$TELEMETRY_DIR" ]]; then
    WRITE_DIR="$TELEMETRY_DIR"
else
    echo "⚠️  Cannot write to $TELEMETRY_DIR (owned by container user)"
    echo "   Writing to $TEST_TELEMETRY_DIR instead"
    WRITE_DIR="$TEST_TELEMETRY_DIR"
fi

echo "🔄 Generating test telemetry events..."

# Function to create a telemetry event
create_event() {
    local service="$1"
    local event_type="$2"
    local metadata="$3"
    local timestamp=$(date +%s)

    local event=$(cat <<EOF
{"timestamp": $timestamp, "service": "$service", "event_type": "$event_type", "metadata": $metadata}
EOF
)
    echo "$event"
}

# Generate AIDB events
echo "📊 AIDB telemetry events..."
AIDB_FILE="$WRITE_DIR/aidb-events.jsonl"

# Context retrieval events
for i in {1..5}; do
    metadata=$(cat <<EOF
{"query": "NixOS configuration", "results_count": 3, "response_time_ms": 45, "cache_hit": false}
EOF
)
    create_event "aidb" "context_retrieval" "$metadata" >> "$AIDB_FILE"
done

# Vector search events
for i in {1..3}; do
    metadata=$(cat <<EOF
{"search_term": "kubernetes", "similarity_threshold": 0.8, "results": 5, "collection": "codebase-context"}
EOF
)
    create_event "aidb" "vector_search" "$metadata" >> "$AIDB_FILE"
done

echo "  ✓ Generated 8 AIDB events"

# Generate Hybrid Coordinator events
echo "🔀 Hybrid Coordinator telemetry events..."
HYBRID_FILE="$WRITE_DIR/hybrid-events.jsonl"

# Query augmentation events
for i in {1..10}; do
    metadata=$(cat <<EOF
{"agent_type": "local", "context_count": 2, "collections": ["best-practices", "error-solutions"], "query_length": 45}
EOF
)
    create_event "hybrid-coordinator" "context_augmented" "$metadata" >> "$HYBRID_FILE"
done

# Routing decisions
for i in {1..5}; do
    local_pref=$((50 + RANDOM % 50))
    metadata=$(cat <<EOF
{"route": "local", "confidence": 0.$local_pref, "query_complexity": "simple", "local_model": "llama-3.2"}
EOF
)
    create_event "hybrid-coordinator" "routing_decision" "$metadata" >> "$HYBRID_FILE"
done

echo "  ✓ Generated 15 Hybrid Coordinator events"

# Generate Ralph Wiggum events (simulated agent activity)
echo "🤖 Ralph Wiggum telemetry events..."
RALPH_FILE="$WRITE_DIR/ralph-events.jsonl"

# Learning-compatible task completion event (matches hybrid pipeline expectations)
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
task_id="test-task-$(date +%s)"
cat <<EOF >> "$RALPH_FILE"
{"event":"task_completed","task_id":"$task_id","status":"completed","total_iterations":2,"task":{"task_id":"$task_id","prompt":"Update README deployment steps and verify service health endpoints.","output":"Updated documentation and confirmed health endpoints respond with OK.","iteration":2,"backend":"aider","context":{"source":"test-telemetry-script"}},"timestamp":"$timestamp"}
EOF

# Agent task executions
tasks=("fix_linting_errors" "update_documentation" "refactor_config" "add_tests" "optimize_imports")
backends=("aider" "continue" "autogpt")

for i in {1..7}; do
    task_idx=$((RANDOM % ${#tasks[@]}))
    backend_idx=$((RANDOM % ${#backends[@]}))
    task="${tasks[$task_idx]}"
    backend="${backends[$backend_idx]}"
    success=$((RANDOM % 2))
    outcome=$([ "$success" -eq 1 ] && echo "success" || echo "failure")

    metadata=$(cat <<EOF
{"task": "$task", "backend": "$backend", "outcome": "$outcome", "iterations": $((1 + RANDOM % 3)), "duration_seconds": $((30 + RANDOM % 120))}
EOF
)
    create_event "ralph-wiggum" "agent_task_execution" "$metadata" >> "$RALPH_FILE"
done

# Learning loop iterations
for i in {1..3}; do
    metadata=$(cat <<EOF
{"iteration": $i, "patterns_extracted": $((RANDOM % 5)), "high_value_interactions": $((RANDOM % 3)), "qdrant_updates": $((RANDOM % 4))}
EOF
)
    create_event "ralph-wiggum" "learning_iteration" "$metadata" >> "$RALPH_FILE"
done

echo "  ✓ Generated 10 Ralph Wiggum events"

# Show file sizes
echo ""
echo "📁 Telemetry files:"
ls -lh "$WRITE_DIR"/*.jsonl 2>/dev/null || echo "  (no files yet)"

echo ""
echo "✅ Test telemetry generation complete!"
echo ""
echo "Next steps:"
echo "  1. Check learning daemon processes these: podman logs local-ai-hybrid-coordinator -f"
echo "  2. Verify metrics update: curl http://${SERVICE_HOST:-localhost}:8092/stats"
echo "  3. Check for fine-tuning samples in daemon logs"
