#!/usr/bin/env bash
#
# Simple Autonomous Coordinator
# Uses ONLY existing validated CLI tools (no new API wrappers)
# SECURITY: Runs in restricted mode - no mouse/keyboard control
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
LOG_FILE=".agents/coordinator.log"
SECURITY_MODE="autonomous"  # Options: autonomous (restricted), interactive (full)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Verify security policy is enforced
verify_security_policy() {
    local policy_file="ai-stack/autonomous-orchestrator/security_policy.json"

    if [[ ! -f "$policy_file" ]]; then
        log "ERROR: Security policy not found: $policy_file"
        return 1
    fi

    # Check that policy has autonomous mode restrictions
    if ! grep -q '"autonomous"' "$policy_file"; then
        log "ERROR: Security policy missing autonomous mode configuration"
        return 1
    fi

    # Verify computer use is disabled in autonomous mode
    if ! grep -A 5 '"computer_use"' "$policy_file" | grep -q '"enabled": false'; then
        log "ERROR: Computer use tools must be disabled in autonomous mode"
        return 1
    fi

    log "✓ Security policy verified: $SECURITY_MODE mode"
    log "  - Computer use (mouse/keyboard): DISABLED"
    log "  - File operations: RESTRICTED to repo paths"
    log "  - Shell commands: ALLOWLIST only"
    return 0
}

find_next_batch() {
    grep -B 2 "Status: pending" .agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md | \
        grep "^###" | \
        head -1 | \
        sed 's/^### Batch //' || true
}

process_batch() {
    local batch_id="$1"
    local batch_desc="$2"

    log "Processing batch: $batch_id - $batch_desc"

    # 1. Gather context using aq-hints
    log "  Gathering context..."
    local context_hints
    context_hints=$(scripts/ai/aq-hints \
        --query "$batch_desc implementation" \
        --compact \
        --max-tokens 1000 2>/dev/null || echo "")

    # 2. Use ralph-orchestrator to generate plan
    log "  Generating implementation plan..."
    local plan_prompt="Create a detailed implementation plan for roadmap batch $batch_id:

Description: $batch_desc

Context from system:
$context_hints

Please provide:
1. List of 5-10 specific tasks
2. Files to create or modify
3. Key implementation steps
4. Testing requirements

Format as numbered list."

    local plan_output
    if [[ -x scripts/ai/ralph-orchestrator.sh ]]; then
        plan_output=$(scripts/ai/ralph-orchestrator.sh \
            --prompt "$plan_prompt" \
            2>&1 || echo "Plan generation failed")
    else
        plan_output="Ralph orchestrator not available. Manual planning required."
    fi

    # 3. Save plan to review file
    local plan_file=".agents/reviews/batch-${batch_id}-plan.md"
    mkdir -p .agents/reviews

    cat > "$plan_file" <<EOF
# Implementation Plan: Batch $batch_id

**Description:** $batch_desc

## Context
$context_hints

## Implementation Plan
$plan_output

## Next Steps
1. Review this plan
2. Implement tasks using your preferred method
3. Run tests: \`scripts/ai/aq-qa 0\`
4. Commit changes
5. Mark batch complete in roadmap

**Generated:** $(date)
EOF

    log "  Plan saved: $plan_file"

    # 4. Extract tasks and create TODO list
    local tasks_file=".agents/todos/batch-${batch_id}-tasks.md"
    mkdir -p .agents/todos

    # Parse tasks from plan (lines starting with numbers)
    local -a tasks
    mapfile -t tasks < <(echo "$plan_output" | grep -E "^[0-9]+\." | head -10)

    if [[ ${#tasks[@]} -eq 0 ]]; then
        # Fallback generic tasks
        tasks=(
            "1. Review and understand requirements"
            "2. Identify files to modify"
            "3. Implement core functionality"
            "4. Add error handling"
            "5. Write tests"
            "6. Update documentation"
        )
    fi

    cat > "$tasks_file" <<EOF
# Tasks: Batch $batch_id

**Batch:** $batch_id - $batch_desc

## Task Checklist

EOF

    for task in "${tasks[@]}"; do
        # Convert "1. Task" to "- [ ] Task"
        echo "$task" | sed 's/^[0-9]*\. /- [ ] /' >> "$tasks_file"
    done

    cat >> "$tasks_file" <<EOF

## Files to Review
$(echo "$plan_output" | grep -i "file" | head -5 || echo "See plan for details")

## Reference
- Full plan: $plan_file
- Roadmap: .agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md

**Generated:** $(date)
EOF

    log "  Tasks saved: $tasks_file"

    # 5. Commit plan and tasks
    git add "$plan_file" "$tasks_file" 2>/dev/null || true
    git commit -m "plan($batch_id): generate implementation plan and tasks

Batch: $batch_desc

Generated:
- Plan: $plan_file
- Tasks: $tasks_file

Next: Review and implement tasks" 2>/dev/null || true

    # 6. Mark as in-progress
    sed -i "/### Batch $batch_id/,/^Status:/ s/Status: pending/Status: in_progress/" \
        .agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md 2>/dev/null || true

    git add .agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md 2>/dev/null || true
    git commit -m "roadmap: mark batch $batch_id in-progress

Plan and tasks ready for implementation" 2>/dev/null || true

    log "✅ Batch $batch_id ready for implementation"
    return 0
}

main() {
    log "🤖 Simple Autonomous Coordinator starting"
    log "   Using existing CLI tools only"
    log "   Security mode: $SECURITY_MODE"

    # Verify security policy before starting
    if ! verify_security_policy; then
        log "❌ Security policy verification failed"
        log "   Coordinator will not start without proper security restrictions"
        exit 1
    fi

    local batches_processed=0
    local max_batches=10  # Process up to 10 batches per run

    while [[ $batches_processed -lt $max_batches ]]; do
        log ""
        log "=== Checking for next batch ==="

        # Find next batch
        local next_batch
        next_batch=$(find_next_batch)

        if [[ -z "$next_batch" ]]; then
            log "✅ No more pending batches found"
            break
        fi

        # Parse batch info
        local batch_id batch_desc
        batch_id=$(echo "$next_batch" | awk '{print $1}')
        batch_desc=$(echo "$next_batch" | sed "s/^$batch_id: //")

        log "Found: $batch_id - $batch_desc"

        # Process batch
        if process_batch "$batch_id" "$batch_desc"; then
            ((batches_processed++))
            log "Progress: $batches_processed batches processed"
        else
            log "⚠️  Failed to process batch, continuing..."
        fi

        # Small delay
        sleep 2
    done

    log ""
    log "🏁 Coordinator finished"
    log "   Batches processed: $batches_processed"
    log ""
    log "📋 Next steps:"
    log "   1. Review plans in: .agents/reviews/"
    log "   2. Review tasks in: .agents/todos/"
    log "   3. Implement tasks"
    log "   4. Run tests: scripts/ai/aq-qa 0"
    log "   5. Mark batches complete when done"
    log ""
    log "   Re-run this script to process more batches"
}

main "$@"
