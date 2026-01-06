#!/usr/bin/env bash
# Cleanup script for hanging podman-compose processes
# Kills any podman-compose processes that have been running too long

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX_AGE_MINUTES=${1:-30}  # Default: kill processes older than 30 minutes

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
error() { echo "✗ $*"; }

info "Checking for hanging podman-compose processes (max age: ${MAX_AGE_MINUTES} minutes)..."

# Find all podman-compose processes
HANGING_PIDS=()
while IFS= read -r line; do
    if [ -z "$line" ]; then
        continue
    fi

    PID=$(echo "$line" | awk '{print $1}')
    ELAPSED=$(echo "$line" | awk '{print $2}')

    # Parse elapsed time (format: MM:SS or HH:MM:SS or D-HH:MM:SS)
    MINUTES=0
    if [[ "$ELAPSED" =~ ^([0-9]+)-([0-9]+):([0-9]+):([0-9]+)$ ]]; then
        # Days-Hours:Minutes:Seconds
        DAYS="${BASH_REMATCH[1]}"
        HOURS="${BASH_REMATCH[2]}"
        MINUTES=$((DAYS * 1440 + HOURS * 60 + BASH_REMATCH[3]))
    elif [[ "$ELAPSED" =~ ^([0-9]+):([0-9]+):([0-9]+)$ ]]; then
        # Hours:Minutes:Seconds
        HOURS="${BASH_REMATCH[1]}"
        MINUTES=$((HOURS * 60 + BASH_REMATCH[2]))
    elif [[ "$ELAPSED" =~ ^([0-9]+):([0-9]+)$ ]]; then
        # Minutes:Seconds
        MINUTES="${BASH_REMATCH[1]}"
    fi

    if [ "$MINUTES" -ge "$MAX_AGE_MINUTES" ]; then
        HANGING_PIDS+=("$PID")
        warn "Found hanging process: PID $PID (running for $ELAPSED)"
    fi
done < <(ps -eo pid,etime,cmd | grep -E "podman-compose.*up.*-d" | grep -v grep || true)

# Kill hanging processes
if [ ${#HANGING_PIDS[@]} -eq 0 ]; then
    success "No hanging podman-compose processes found"
    exit 0
fi

info "Found ${#HANGING_PIDS[@]} hanging process(es)"

for PID in "${HANGING_PIDS[@]}"; do
    if kill -0 "$PID" 2>/dev/null; then
        info "Killing process $PID..."
        kill -TERM "$PID" 2>/dev/null || true
        sleep 2

        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            warn "Process $PID didn't respond to SIGTERM, forcing..."
            kill -KILL "$PID" 2>/dev/null || true
        fi

        success "Killed process $PID"
    fi
done

success "Cleanup complete"
exit 0
