#!/usr/bin/env bash
# Cleanup orphaned AI stack processes
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Kill orphaned processes from crashed AI stack containers
# Can be run standalone or called from systemd on boot

set -euo pipefail

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
error() { echo "✗ $*"; }

info "Scanning for orphaned AI stack processes..."

# Track if we found and killed anything
killed_count=0

# AI stack ports that should not have orphaned processes
# Format: port:service_name
declare -A AI_PORTS=(
    [8091]="aidb-http"
    [8791]="aidb-websocket"
    [8092]="hybrid-coordinator"
    [8094]="nixos-docs"
    [3001]="open-webui"
    [8098]="ralph-wiggum"
    [6333]="qdrant"
    [8080]="llama-cpp"
    [5432]="postgres"
    [6379]="redis"
    [47334]="mindsdb"
)

# Check each port for orphaned processes
for port in "${!AI_PORTS[@]}"; do
    service="${AI_PORTS[$port]}"

    # Use ss (faster) or fallback to lsof
    if pid=$(lsof -ti:$port 2>/dev/null); then
        # Get process details
        process_cmd=$(ps -p "$pid" -o cmd= 2>/dev/null || echo "unknown")
        process_name=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")

        # Check if this is likely an orphaned AI stack process
        # (not running inside a container, but looks like our stack)
        if echo "$process_cmd" | grep -qE "(server\.py|uvicorn.*open_webui|tool_discovery|continuous_learning|self_healing)"; then
            warn "Found orphaned $service process on port $port"
            echo "    PID: $pid"
            echo "    Command: $process_cmd"

            # Kill the process
            if kill -9 "$pid" 2>/dev/null; then
                success "Killed orphaned process $pid"
                ((killed_count++))
            else
                error "Failed to kill process $pid (insufficient permissions?)"
            fi

            # Give it a moment to release the port
            sleep 0.5
        fi
    fi
done

# Also check for orphaned processes by pattern (not necessarily holding ports)
info "Checking for orphaned processes by pattern..."

orphaned_patterns=(
    "start_with_discovery.sh"
    "start_with_learning.sh"
    "tool_discovery_daemon.py"
    "continuous_learning_daemon.py"
    "self_healing_daemon.py"
)

for pattern in "${orphaned_patterns[@]}"; do
    if pids=$(pgrep -f "$pattern" 2>/dev/null); then
        for pid in $pids; do
            # Verify it's not running inside a container
            # (container processes have different cgroup paths)
            cgroup=$(cat /proc/$pid/cgroup 2>/dev/null | head -1 || echo "")

            # If cgroup doesn't contain "podman", "docker", or "libpod", it's likely orphaned
            if ! echo "$cgroup" | grep -qE "(podman|docker|libpod)"; then
                process_cmd=$(ps -p "$pid" -o cmd= 2>/dev/null || echo "unknown")
                warn "Found orphaned process: $pattern"
                echo "    PID: $pid"
                echo "    Command: $process_cmd"

                if kill -9 "$pid" 2>/dev/null; then
                    success "Killed orphaned process $pid"
                    ((killed_count++))
                else
                    error "Failed to kill process $pid"
                fi

                sleep 0.5
            fi
        done
    fi
done

# Final verification - check if all AI stack ports are free
info "Verifying AI stack ports are free..."
still_in_use=()

for port in "${!AI_PORTS[@]}"; do
    if lsof -ti:$port >/dev/null 2>&1; then
        service="${AI_PORTS[$port]}"
        pid=$(lsof -ti:$port 2>/dev/null || echo "unknown")
        still_in_use+=("$port($service, PID:$pid)")
    fi
done

# Summary
echo ""
echo "=== Cleanup Summary ==="
echo "Processes killed: $killed_count"

if [ ${#still_in_use[@]} -eq 0 ]; then
    success "All AI stack ports are free"
    exit 0
else
    warn "Some ports are still in use:"
    for item in "${still_in_use[@]}"; do
        echo "  - Port $item"
    done
    exit 1
fi
