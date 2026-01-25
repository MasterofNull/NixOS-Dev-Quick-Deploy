#!/usr/bin/env bash
#
# Ralph Wiggum Task Orchestrator
# Submits tasks from task definitions to Ralph for execution
#

set -euo pipefail

# Configuration
RALPH_BASE_URL="${RALPH_BASE_URL:-http://localhost:8098}"
TASK_DIR="${TASK_DIR:-./ai-stack/ralph-tasks}"
LOG_DIR="${LOG_DIR:-$HOME/.local/share/nixos-ai-stack/logs}"
TELEMETRY_DIR="${TELEMETRY_DIR:-$HOME/.local/share/nixos-ai-stack/telemetry}"

# Ensure directories exist
mkdir -p "$LOG_DIR"
mkdir -p "$TELEMETRY_DIR"

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

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Ralph is healthy
check_ralph_health() {
    log_info "Checking Ralph Wiggum health..."

    if ! response=$(curl -s -f "$RALPH_BASE_URL/health"); then
        log_error "Ralph Wiggum is not responding at $RALPH_BASE_URL"
        return 1
    fi

    status=$(echo "$response" | jq -r '.status')
    if [ "$status" != "healthy" ]; then
        log_error "Ralph Wiggum status: $status"
        return 1
    fi

    log_success "Ralph Wiggum is healthy"
    return 0
}

# Submit a task to Ralph
submit_task() {
    local task_file="$1"
    local task_name=$(basename "$task_file" .json)

    log_info "Submitting task: $task_name"

    # Read task definition
    if ! task_json=$(cat "$task_file"); then
        log_error "Failed to read task file: $task_file"
        return 1
    fi

    # Extract task properties
    local description=$(echo "$task_json" | jq -r '.description // "No description"')
    local backend=$(echo "$task_json" | jq -r '.backend // "aider"')
    local max_iterations=$(echo "$task_json" | jq -r '.max_iterations // 10')
    local require_approval=$(echo "$task_json" | jq -r '.require_approval // false')

    log_info "  Description: $description"
    log_info "  Backend: $backend"
    log_info "  Max iterations: $max_iterations"
    log_info "  Require approval: $require_approval"

    # Build task payload for Ralph
    # Ralph expects: prompt, backend, max_iterations, require_approval
    local context=$(echo "$task_json" | jq -r '.context // {}')
    local goal=$(echo "$context" | jq -r '.goal // ""')

    # Create the prompt from the task definition
    local prompt="Task: $description

Goal: $goal

Task Definition:
$(echo "$task_json" | jq -c '.')"

    # Submit to Ralph
    local payload=$(jq -n \
        --arg prompt "$prompt" \
        --arg backend "$backend" \
        --argjson max_iterations "$max_iterations" \
        --argjson require_approval "$require_approval" \
        '{prompt: $prompt, backend: $backend, max_iterations: $max_iterations, require_approval: $require_approval}')

    log_info "Submitting to Ralph API..."

    if ! response=$(curl -s -f -X POST "$RALPH_BASE_URL/tasks" \
        -H "Content-Type: application/json" \
        -d "$payload"); then
        log_error "Failed to submit task to Ralph"
        return 1
    fi

    # Extract task ID from response
    local task_id=$(echo "$response" | jq -r '.task_id // .id // "unknown"')

    log_success "Task submitted successfully"
    log_info "Task ID: $task_id"

    # Log to telemetry
    local timestamp=$(date -Iseconds)
    echo "{\"timestamp\": \"$timestamp\", \"task_name\": \"$task_name\", \"task_id\": \"$task_id\", \"action\": \"submitted\"}" \
        >> "$TELEMETRY_DIR/ralph_orchestrator.jsonl"

    echo "$task_id"
}

# Monitor task progress
monitor_task() {
    local task_id="$1"
    local poll_interval="${2:-10}"  # Default: poll every 10 seconds

    log_info "Monitoring task: $task_id"

    while true; do
        if ! response=$(curl -s -f "$RALPH_BASE_URL/tasks/$task_id"); then
            log_error "Failed to get task status"
            return 1
        fi

        local status=$(echo "$response" | jq -r '.status // "unknown"')
        local iteration=$(echo "$response" | jq -r '.iteration // 0')

        case "$status" in
            "running")
                log_info "Task $task_id: Running (iteration $iteration)"
                ;;
            "completed")
                log_success "Task $task_id: Completed"

                # Log completion
                local timestamp=$(date -Iseconds)
                echo "{\"timestamp\": \"$timestamp\", \"task_id\": \"$task_id\", \"action\": \"completed\", \"iterations\": $iteration}" \
                    >> "$TELEMETRY_DIR/ralph_orchestrator.jsonl"

                return 0
                ;;
            "failed")
                log_error "Task $task_id: Failed"
                local error=$(echo "$response" | jq -r '.error // "Unknown error"')
                log_error "Error: $error"

                # Log failure
                local timestamp=$(date -Iseconds)
                echo "{\"timestamp\": \"$timestamp\", \"task_id\": \"$task_id\", \"action\": \"failed\", \"error\": \"$error\"}" \
                    >> "$TELEMETRY_DIR/ralph_orchestrator.jsonl"

                return 1
                ;;
            *)
                log_warn "Task $task_id: Unknown status: $status"
                ;;
        esac

        sleep "$poll_interval"
    done
}

# Submit and monitor a task
run_task() {
    local task_file="$1"
    local monitor="${2:-false}"

    # Submit the task
    local task_id=$(submit_task "$task_file")
    if [ $? -ne 0 ]; then
        return 1
    fi

    # Monitor if requested
    if [ "$monitor" = "true" ]; then
        monitor_task "$task_id"
    else
        log_info "Task submitted. Monitor with: $0 monitor $task_id"
    fi
}

# List all available tasks
list_tasks() {
    log_info "Available tasks in $TASK_DIR:"

    if [ ! -d "$TASK_DIR" ]; then
        log_warn "Task directory not found: $TASK_DIR"
        return 1
    fi

    for task_file in "$TASK_DIR"/*.json; do
        if [ -f "$task_file" ]; then
            local task_name=$(basename "$task_file" .json)
            local description=$(jq -r '.description // "No description"' "$task_file")
            echo "  • $task_name: $description"
        fi
    done
}

# Main command dispatcher
main() {
    local command="${1:-help}"

    case "$command" in
        submit)
            shift
            local task_file="${1:-}"
            if [ -z "$task_file" ]; then
                log_error "Usage: $0 submit <task_file.json>"
                exit 1
            fi

            # Check health first
            check_ralph_health || exit 1

            run_task "$task_file" false
            ;;

        run)
            shift
            local task_file="${1:-}"
            if [ -z "$task_file" ]; then
                log_error "Usage: $0 run <task_file.json>"
                exit 1
            fi

            # Check health first
            check_ralph_health || exit 1

            run_task "$task_file" true
            ;;

        monitor)
            shift
            local task_id="${1:-}"
            if [ -z "$task_id" ]; then
                log_error "Usage: $0 monitor <task_id>"
                exit 1
            fi

            monitor_task "$task_id"
            ;;

        list)
            list_tasks
            ;;

        health)
            check_ralph_health
            ;;

        help|*)
            echo "Ralph Wiggum Task Orchestrator"
            echo ""
            echo "Usage: $0 <command> [args]"
            echo ""
            echo "Commands:"
            echo "  submit <task.json>  - Submit a task to Ralph (don't wait)"
            echo "  run <task.json>     - Submit and monitor a task"
            echo "  monitor <task_id>   - Monitor a running task"
            echo "  list                - List available task definitions"
            echo "  health              - Check Ralph Wiggum health"
            echo "  help                - Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  RALPH_BASE_URL      - Ralph API URL (default: http://localhost:8098)"
            echo "  TASK_DIR            - Task definitions directory (default: ./ai-stack/ralph-tasks)"
            echo "  LOG_DIR             - Log directory (default: ~/.local/share/nixos-ai-stack/logs)"
            ;;
    esac
}

# Run main
main "$@"
