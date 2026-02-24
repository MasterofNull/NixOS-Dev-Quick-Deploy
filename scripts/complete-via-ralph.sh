#!/usr/bin/env bash
#
# Complete Remaining Work via AI Stack Workflow
# Uses Ralph Wiggum → Aider → llama-cpp pipeline for autonomous completion
#
# Workflow: Tasks → Ralph → Aider-wrapper → llama-cpp → Code Changes → 
#           Telemetry → Continuous Learning → Optimization Proposals
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=config/service-endpoints.sh
if [[ -f "${SCRIPT_DIR}/config/service-endpoints.sh" ]]; then
    source "${SCRIPT_DIR}/config/service-endpoints.sh"
fi

SERVICE_HOST="${SERVICE_HOST:-localhost}"
RALPH_API="${RALPH_URL}"
TASK_DIR="ai-stack/ralph-tasks/completion-workflow"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/${TMP_FALLBACK:-tmp}}}"

info() { echo -e "\033[0;34mℹ\033[0m $1"; }
success() { echo -e "\033[0;32m✓\033[0m $1"; }
error() { echo -e "\033[0;31m✗\033[0m $1"; }

submit_task() {
    local task_file=$1
    local task_name=$(basename "$task_file" .json)
    
    info "Submitting task: $task_name"
    
    # Read task definition
    local task_json=$(cat "$task_file")
    
    # Submit to Ralph
    local response=$(curl -s --max-time 15 --connect-timeout 3 -X POST "${RALPH_API}/tasks" \
        -H "Content-Type: application/json" \
        -d "$task_json")
    
    local task_id=$(echo "$response" | jq -r '.task_id')
    local status=$(echo "$response" | jq -r '.status')
    
    if [[ "$status" == "queued" ]]; then
        success "Task queued: $task_id"
        echo "$task_id" > "${RUNTIME_DIR}/ralph-task-${task_name}.id"
        return 0
    else
        error "Failed to queue task: $response"
        return 1
    fi
}

wait_for_task() {
    local task_id=$1
    local task_name=$2
    local max_wait=600  # 10 minutes
    local elapsed=0
    
    info "Waiting for task $task_name ($task_id) to complete..."
    
    while [[ $elapsed -lt $max_wait ]]; do
        local status_response=$(curl -s --max-time 10 --connect-timeout 3 "${RALPH_API}/tasks/${task_id}")
        local status=$(echo "$status_response" | jq -r '.status')
        local iteration=$(echo "$status_response" | jq -r '.iteration // 0')
        
        if [[ "$status" == "completed" ]]; then
            success "Task $task_name completed (iterations: $iteration)"
            return 0
        elif [[ "$status" == "failed" ]]; then
            error "Task $task_name failed"
            echo "$status_response" | jq .
            return 1
        fi
        
        echo "  Status: $status, Iteration: $iteration"
        sleep 10
        elapsed=$((elapsed + 10))
    done
    
    error "Task $task_name timed out after ${max_wait}s"
    return 1
}

check_ralph_health() {
    info "Checking Ralph health..."
    local health=$(curl -s --max-time 5 --connect-timeout 3 "${RALPH_API}/health")
    local status=$(echo "$health" | jq -r '.status')
    
    if [[ "$status" == "healthy" ]]; then
        success "Ralph is healthy"
        echo "$health" | jq .
        return 0
    else
        error "Ralph is not healthy"
        return 1
    fi
}

main() {
    echo "════════════════════════════════════════════════════════════"
    echo "  AI Stack Self-Completion Workflow"
    echo "  Using: Ralph Wiggum → Aider → llama-cpp → Learning"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    
    # Verify Ralph is running
    if ! check_ralph_health; then
        error "Ralph is not running. Start with: ./scripts/hybrid-ai-stack.sh up"
        exit 1
    fi
    echo ""
    
    # Submit tasks in dependency order
    local tasks=(
        "01-api-contract-tests.json"
        "02-adaptive-iteration-logic.json"
        "03-dashboard-controls.json"
        "04-learning-optimization-proposals.json"
    )
    
    local task_ids=()
    
    # Submit all tasks
    for task_file in "${tasks[@]}"; do
        if submit_task "${TASK_DIR}/${task_file}"; then
            task_ids+=("$(cat "${RUNTIME_DIR}/ralph-task-$(basename "$task_file" .json).id")")
        else
            error "Failed to submit $task_file"
            exit 1
        fi
        echo ""
        sleep 2  # Rate limit submissions
    done
    
    echo ""
    info "All tasks submitted. Monitoring completion..."
    echo ""
    
    # Monitor tasks
    local i=0
    for task_id in "${task_ids[@]}"; do
        local task_name=$(basename "${tasks[$i]}" .json)
        if ! wait_for_task "$task_id" "$task_name"; then
            error "Task $task_name failed. Check logs for details."
            # Continue with other tasks instead of exiting
        fi
        echo ""
        i=$((i + 1))
    done
    
    echo "════════════════════════════════════════════════════════════"
    echo "  Workflow Complete!"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    info "Next steps:"
    echo "  1. Check telemetry: tail -f ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl"
    echo "  2. View results: git diff"
    echo "  3. Run tests: pytest ai-stack/tests/test_api_contracts.py -v"
    echo "  4. Check learning: ls ~/.local/share/nixos-ai-stack/fine-tuning/"
    echo ""
}

main "$@"
