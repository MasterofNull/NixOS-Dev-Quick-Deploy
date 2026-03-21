#!/usr/bin/env bash
# Phase 5.2 Validation Script
# Validates all deliverables are in place and functional

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }
log_info() { echo -e "${YELLOW}ℹ${NC} $*"; }

passed=0
failed=0

check_file() {
    local file="$1"
    local min_lines="${2:-1}"

    if [ -f "$REPO_ROOT/$file" ]; then
        local lines=$(wc -l < "$REPO_ROOT/$file")
        if [ "$lines" -ge "$min_lines" ]; then
            log_success "$file ($lines lines)"
            ((passed++))
        else
            log_error "$file (only $lines lines, expected >=$min_lines)"
            ((failed++))
        fi
    else
        log_error "$file (not found)"
        ((failed++))
    fi
}

echo "=========================================="
echo "Phase 5.2 Validation"
echo "=========================================="
echo ""

echo "1. Core Library Components (lib/search/):"
check_file "lib/search/__init__.py" 20
check_file "lib/search/vector_search_optimizer.py" 450
check_file "lib/search/query_cache.py" 400
check_file "lib/search/query_batcher.py" 350
check_file "lib/search/embedding_optimizer.py" 150
check_file "lib/search/lazy_loader.py" 100
check_file "lib/search/query_profiler.py" 150
echo ""

echo "2. Dashboard API Integration:"
check_file "dashboard/backend/api/routes/search_performance.py" 200
echo ""

echo "3. Configuration:"
check_file "config/query-performance.yaml" 200
echo ""

echo "4. Testing & Benchmarking:"
check_file "scripts/testing/test-query-performance.py" 300
check_file "scripts/testing/benchmark-query-performance.sh" 200
echo ""

echo "5. Documentation:"
check_file "docs/performance/query-retrieval-optimization.md" 500
check_file "docs/operations/query-performance-tuning.md" 400
echo ""

echo "6. Implementation Summary:"
check_file ".agents/plans/PHASE-5.2-IMPLEMENTATION-SUMMARY.md" 500
echo ""

echo "=========================================="
echo "Validation Summary"
echo "=========================================="
echo "Passed: $passed"
echo "Failed: $failed"
echo "Total:  $((passed + failed))"
echo ""

if [ "$failed" -eq 0 ]; then
    echo -e "${GREEN}Phase 5.2 Implementation: COMPLETE ✓${NC}"
    exit 0
else
    echo -e "${RED}Phase 5.2 Implementation: INCOMPLETE${NC}"
    exit 1
fi
