#!/usr/bin/env bash
#
# AI Harness Optimization & Validation Script
#
# Purpose: Automate the performance optimization workflow
# - Capture baseline metrics
# - Import knowledge gaps
# - Apply optimizations
# - Validate 50%+ latency reduction
#
# Usage:
#   ./scripts/ai/optimize-and-validate.sh [--baseline-only|--validate-only|--full]
#
# Date: 2026-04-09

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORTS_DIR="$REPO_ROOT/.agent/workflows/optimization-reports"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $*"
}

log_error() {
    echo -e "${RED}[✗]${NC} $*"
}

# Create reports directory
mkdir -p "$REPORTS_DIR"

# Function: Capture baseline metrics
capture_baseline() {
    log_info "Capturing baseline performance metrics..."

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local baseline_file="$REPORTS_DIR/baseline_$timestamp.json"
    local baseline_txt="$REPORTS_DIR/baseline_$timestamp.txt"

    # Capture JSON report
    aq-report --since=7d --format=json > "$baseline_file" || {
        log_error "Failed to capture baseline metrics"
        return 1
    }

    # Capture human-readable report
    aq-report --since=7d --format=text > "$baseline_txt" || {
        log_warning "Failed to capture text baseline"
    }

    log_success "Baseline captured: $baseline_file"

    # Extract key metrics
    log_info "Baseline P95 latencies:"
    jq -r '.tool_performance[] | select(.tool | IN("route_search", "ai_coordinator_delegate", "recall_agent_memory")) | "  \(.tool): \(.p95_ms)ms"' "$baseline_file" || log_warning "Could not parse baseline metrics"

    echo "$baseline_file"
}

# Function: Import knowledge gaps
import_knowledge() {
    log_info "Importing knowledge gaps to AIDB..."

    local query="lesson ref parity smoke harness eval"
    local import_script="$REPO_ROOT/scripts/ai/aq-knowledge-import.sh"

    # Check if AIDB is accessible
    if ! curl -s -f http://127.0.0.1:8002/health > /dev/null 2>&1; then
        log_warning "AIDB not accessible at http://127.0.0.1:8002"
        log_warning "Skipping knowledge import (AIDB may not be running)"
        return 0
    fi

    if [[ ! -x "$import_script" ]]; then
        log_warning "Knowledge import helper not executable: $import_script"
        return 0
    fi

    if ! command -v gemini >/dev/null 2>&1; then
        log_warning "gemini CLI not available in PATH; skipping topic import"
        return 0
    fi

    log_info "Importing topic via repo-native helper: $query"
    if "$import_script" "$query" --clear-gaps; then
        log_success "Knowledge import completed"
    else
        log_warning "Knowledge import helper failed for topic: $query"
    fi
}

# Function: Apply optimizations
apply_optimizations() {
    log_info "Applying performance optimizations..."

    # This is a placeholder - actual optimizations would be code changes
    # For now, we'll document what needs to be done

    cat <<EOF

╔════════════════════════════════════════════════════════════════╗
║  OPTIMIZATION CHECKLIST                                        ║
╚════════════════════════════════════════════════════════════════╝

Manual steps required (or delegate to codex agent):

1. Route Search Fast-Path:
   [ ] Add pattern matching for simple queries in http_server.py
   [ ] Implement cache-first lookup strategy
   [ ] Add direct index lookup for known patterns

2. Delegation Retry Logic:
   [ ] Add exponential backoff in workflow_executor.py
   [ ] Improve error handling with specific error types
   [ ] Validate session state before delegation attempts

3. Context Size Limits:
   [ ] Enforce 1024-token limit in hints_engine.py
   [ ] Implement progressive disclosure (L0-L3)
   [ ] Use compact representations for common data

4. Memory Recall Optimization:
   [ ] Add metadata pre-filtering in temporal_query.py
   [ ] Limit results to top-K (default: 10)
   [ ] Use temporal validity to prune stale facts

Would you like to delegate these to codex agent? (y/n)
EOF

    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Delegating to codex..."

        cd "$REPO_ROOT/ai-stack/mcp-servers/hybrid-coordinator"

        # Delegate via harness-rpc.js
        node "$REPO_ROOT/scripts/ai/harness-rpc.js" sub-agent \
            --task "Apply AI harness performance optimizations per .agent/workflows/harness-optimization-prompt-2026-04-09.md. Focus on route_search fast-path, delegation retry logic, and context size limits. Target: 50% P95 latency reduction." \
            --agent codex \
            --safety-mode execute-mutating \
            --budget-tokens 8000 || {
                log_error "Delegation failed"
                return 1
            }

        log_success "Optimizations delegated to codex"
    else
        log_warning "Skipping automatic optimization application"
        log_info "Apply changes manually, then run: $0 --validate-only"
    fi
}

# Function: Validate performance improvement
validate_performance() {
    log_info "Validating performance improvements..."

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local optimized_file="$REPORTS_DIR/optimized_$timestamp.json"
    local optimized_txt="$REPORTS_DIR/optimized_$timestamp.txt"

    # Capture post-optimization metrics
    aq-report --since=1d --format=json > "$optimized_file" || {
        log_error "Failed to capture optimized metrics"
        return 1
    }

    aq-report --since=1d --format=text > "$optimized_txt" || {
        log_warning "Failed to capture text report"
    }

    log_success "Optimized metrics captured: $optimized_file"

    # Find most recent baseline
    local baseline_file=$(ls -t "$REPORTS_DIR"/baseline_*.json 2>/dev/null | head -1)

    if [[ -z "$baseline_file" ]]; then
        log_warning "No baseline file found - showing current metrics only"
        jq -r '.tool_performance[] | select(.tool | IN("route_search", "ai_coordinator_delegate", "recall_agent_memory")) | "  \(.tool): \(.p95_ms)ms (\(.success_rate)% success)"' "$optimized_file"
        return 0
    fi

    log_info "Comparing against baseline: $(basename "$baseline_file")"

    # Compare metrics
    python3 <<PYTHON
import json
import sys

with open("$baseline_file") as f:
    baseline = json.load(f)

with open("$optimized_file") as f:
    optimized = json.load(f)

def find_tool(data, tool_name):
    for tool in data.get("tool_performance", []):
        if tool["tool"] == tool_name:
            return tool
    return None

tools_to_check = ["route_search", "ai_coordinator_delegate", "recall_agent_memory"]

print("\n╔════════════════════════════════════════════════════════════════╗")
print("║  PERFORMANCE COMPARISON                                        ║")
print("╚════════════════════════════════════════════════════════════════╝\n")

improvements = []
for tool_name in tools_to_check:
    base = find_tool(baseline, tool_name)
    opt = find_tool(optimized, tool_name)

    if not base or not opt:
        continue

    base_p95 = base.get("p95_ms", 0)
    opt_p95 = opt.get("p95_ms", 0)

    if base_p95 == 0:
        continue

    improvement_pct = ((base_p95 - opt_p95) / base_p95) * 100
    improvements.append(improvement_pct)

    status = "✓" if improvement_pct >= 50 else "⚠" if improvement_pct > 0 else "✗"

    print(f"{status} {tool_name}:")
    print(f"    Baseline P95: {base_p95:,.0f}ms")
    print(f"    Optimized P95: {opt_p95:,.0f}ms")
    print(f"    Improvement: {improvement_pct:+.1f}%")
    print()

if improvements:
    avg_improvement = sum(improvements) / len(improvements)
    print(f"\nAverage Improvement: {avg_improvement:+.1f}%")

    if avg_improvement >= 50:
        print("✓ SUCCESS: Met 50% latency reduction target!")
        sys.exit(0)
    elif avg_improvement > 0:
        print("⚠ PARTIAL: Some improvement, but target not met")
        sys.exit(1)
    else:
        print("✗ FAILURE: No improvement or regression")
        sys.exit(2)
else:
    print("⚠ WARNING: Could not compare metrics (insufficient data)")
    sys.exit(1)
PYTHON

    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "Validation PASSED - performance target achieved!"
    elif [[ $exit_code -eq 1 ]]; then
        log_warning "Validation PARTIAL - some improvement but target not fully met"
    else
        log_error "Validation FAILED - no improvement detected"
    fi

    return $exit_code
}

# Function: Run health check
run_health_check() {
    log_info "Running system health check..."

    aq-qa all || {
        log_warning "Health check reported issues (non-fatal)"
    }

    log_success "Health check complete"
}

# Main workflow
main() {
    local mode="${1:---full}"

    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  AI HARNESS OPTIMIZATION & VALIDATION                          ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo

    case "$mode" in
        --baseline-only)
            capture_baseline
            ;;

        --validate-only)
            validate_performance
            run_health_check
            ;;

        --full)
            capture_baseline
            import_knowledge
            apply_optimizations

            log_info "Waiting 60s for metrics to accumulate..."
            sleep 60

            validate_performance
            run_health_check
            ;;

        --help|-h)
            cat <<EOF
Usage: $0 [MODE]

Modes:
  --baseline-only    Capture baseline metrics only
  --validate-only    Validate current performance against baseline
  --full            Run full optimization workflow (default)
  --help            Show this help message

Examples:
  # Capture baseline before making changes
  $0 --baseline-only

  # After applying optimizations, validate
  $0 --validate-only

  # Run complete workflow with delegation
  $0 --full
EOF
            ;;

        *)
            log_error "Unknown mode: $mode"
            log_info "Use --help for usage information"
            exit 1
            ;;
    esac
}

main "$@"
