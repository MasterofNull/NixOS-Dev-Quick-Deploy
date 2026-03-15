#!/usr/bin/env bash
#
# Autonomous CLI Coordinator - 100% Local (No API Keys)
# Uses only local CLI tools: aq-hints, local models, git, etc.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
LOG_FILE=".agents/coordinator.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

find_next_batch() {
    # Find first pending batch in roadmap
    grep -B 2 "Status: pending" .agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md | \
        grep "^###" | \
        head -1 | \
        sed 's/^### Batch //' || true
}

execute_batch_locally() {
    local batch_id="$1"
    local batch_desc="$2"

    log "Starting batch: $batch_id - $batch_desc"

    # 1. Query hints for context (using existing aq-hints CLI)
    log "  Gathering context via aq-hints..."
    local hints
    hints=$(scripts/ai/aq-hints \
        --query "how to implement $batch_desc" \
        --compact \
        --max-tokens 1000 2>/dev/null || echo "No hints available")

    log "  Context gathered: ${#hints} chars"

    # 2. Find related files to modify
    log "  Identifying files to modify..."
    local -a relevant_files=()

    # Extract file patterns from batch description
    case "$batch_id" in
        1.1)
            relevant_files=(
                "ai-stack/aidb/server.py"
                "ai-stack/mcp-servers/hybrid-coordinator/http_server.py"
            )
            ;;
        1.2)
            relevant_files=(
                "ai-stack/observability/baseline_profiler.py"
                "ai-stack/observability/anomaly_alert_integration.py"
            )
            ;;
        *)
            # Generic search based on description
            mapfile -t relevant_files < <(
                grep -rl --include="*.py" --include="*.sh" \
                    "$(echo "$batch_desc" | awk '{print tolower($1)}')" \
                    ai-stack/ scripts/ 2>/dev/null | head -5
            )
            ;;
    esac

    log "  Files to modify: ${#relevant_files[@]}"

    # 3. Create simple implementation tasks
    # Since we don't have Claude for planning, use template-based tasks
    local -a tasks
    case "$batch_id" in
        1.1)
            tasks=(
                "Add OpenTelemetry imports to server.py"
                "Add metrics collection middleware"
                "Export metrics to Prometheus endpoint"
                "Add tests for metrics"
                "Update documentation"
            )
            ;;
        *)
            # Generic tasks based on batch type
            tasks=(
                "Review existing implementation in ${relevant_files[0]:-codebase}"
                "Add necessary imports and dependencies"
                "Implement core functionality"
                "Add error handling"
                "Add tests"
                "Update documentation"
            )
            ;;
    esac

    log "  Tasks: ${#tasks[@]}"

    # 4. Execute tasks using local tools
    local completed=0
    local failed=0
    local skipped=0

    for task in "${tasks[@]}"; do
        log "    Task: $task"

        # For now, mark as "needs manual implementation"
        # In a full local setup, you'd call local model here via:
        #   - scripts/ai/complete-via-ralph.sh (local model)
        #   - or manual TODO creation

        # Create TODO for human/local-model follow-up
        local todo_file=".agents/todos/batch-${batch_id}-tasks.md"
        mkdir -p .agents/todos

        if [[ ! -f "$todo_file" ]]; then
            cat > "$todo_file" <<EOF
# Batch $batch_id: $batch_desc

## Tasks

EOF
        fi

        echo "- [ ] $task" >> "$todo_file"

        log "      → Added to TODO list"
        ((skipped++))
    done

    # 5. For now, mark batch as "in progress" not completed
    # Since we're creating TODOs for manual work
    log "  Created task list: $todo_file"
    log "  Status: ${completed} completed, ${failed} failed, ${skipped} queued"

    # Commit the TODO list
    git add "$todo_file"
    git commit -m "auto($batch_id): create task list for manual implementation

Batch: $batch_desc
Tasks: ${#tasks[@]}
Context hints: ${#hints} chars

Tasks queued in: $todo_file

Next: Review and implement tasks manually or via local model" || true

    log "✅ Batch $batch_id task list created"
    return 0
}

execute_batch_with_local_model() {
    local batch_id="$1"
    local batch_desc="$2"

    log "Starting batch (local model): $batch_id - $batch_desc"

    # Use ralph-orchestrator or complete-via-ralph for local execution
    if [[ -x scripts/ai/ralph-orchestrator.sh ]]; then
        log "  Using ralph-orchestrator for local execution..."

        # Create prompt for local model
        local prompt="Implement the following batch from the roadmap:

Batch: $batch_id
Description: $batch_desc

Requirements:
1. Review relevant files
2. Make necessary code changes
3. Add tests
4. Update documentation

Please provide implementation steps."

        # Call local model via ralph
        local response
        response=$(scripts/ai/ralph-orchestrator.sh --prompt "$prompt" 2>&1 || echo "Failed to get response")

        log "  Local model response: ${#response} chars"

        # For now, save response to review file
        local review_file=".agents/reviews/batch-${batch_id}-plan.md"
        mkdir -p .agents/reviews

        cat > "$review_file" <<EOF
# Batch $batch_id Implementation Plan

## Description
$batch_desc

## Local Model Response
$response

## Next Steps
Review the plan above and implement manually or refine with local model.
EOF

        git add "$review_file"
        git commit -m "auto($batch_id): generate implementation plan via local model

Batch: $batch_desc
Generated by: ralph-orchestrator (local)

Review plan in: $review_file" || true

        log "✅ Implementation plan generated: $review_file"
    else
        log "  ⚠️  ralph-orchestrator not available, falling back to task list"
        execute_batch_locally "$batch_id" "$batch_desc"
    fi

    return 0
}

main() {
    log "🤖 Autonomous Local Coordinator starting (100% local, no API keys)"

    local iteration=1
    local max_iterations=50  # Safety limit

    while [[ $iteration -le $max_iterations ]]; do
        log ""
        log "=== Iteration $iteration ==="

        # Find next batch
        local next_batch
        next_batch=$(find_next_batch)

        if [[ -z "$next_batch" ]]; then
            log "✅ All batches complete (or all in progress)!"

            # Run QA checks
            log "Running QA checks..."
            scripts/ai/aq-qa 0 --json > .agents/qa-results.json 2>&1 || true

            log "System status check complete. Exiting gracefully."
            break
        fi

        # Parse batch ID and description
        local batch_id
        local batch_desc
        batch_id=$(echo "$next_batch" | awk '{print $1}')
        batch_desc=$(echo "$next_batch" | sed "s/^$batch_id: //")

        log "Next batch: $batch_id - $batch_desc"

        # Execute using local tools
        if execute_batch_with_local_model "$batch_id" "$batch_desc"; then
            log "✅ Batch processing complete"

            # Mark as in-progress (not completed, since manual review needed)
            sed -i "s/Status: pending/Status: in_progress/g" \
                .agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md 2>/dev/null || true

            git add .agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md 2>/dev/null
            git commit -m "roadmap: mark batch $batch_id as in-progress

Local coordinator created task list or plan.
Review and complete manually." 2>/dev/null || true
        else
            log "❌ Batch processing failed"
        fi

        ((iteration++))

        # Small delay between batches
        sleep 5
    done

    log "🏁 Coordinator completed $iteration iterations"
    log "📋 Review task lists in: .agents/todos/"
    log "📋 Review plans in: .agents/reviews/"
}

main "$@"
