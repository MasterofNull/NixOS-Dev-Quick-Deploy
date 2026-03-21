#!/usr/bin/env bash
# Smoke Test for Local Agent Agentic Capabilities
# Quick validation of local agent setup

set -euo pipefail

echo "=== Local Agent Smoke Test ==="
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() {
    echo -e "${GREEN}✓${NC} $1"
}

fail() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check Python
echo "Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    pass "Python found: $PYTHON_VERSION"
else
    fail "Python3 not found"
fi

# Check services
echo
echo "Checking services..."

check_service() {
    local url=$1
    local name=$2

    if curl -s -f "$url" > /dev/null 2>&1; then
        pass "$name is responding"
    else
        warn "$name is not responding at $url"
    fi
}

check_service "http://127.0.0.1:8080/health" "llama.cpp"
check_service "http://127.0.0.1:8003/health" "Hybrid Coordinator"
check_service "http://127.0.0.1:8002/health" "AIDB"

# Check tool registry
echo
echo "Checking tool registry..."

python3 << 'EOPYTHON'
import sys
sys.path.insert(0, "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack")

try:
    from local_agents import get_registry, initialize_builtin_tools

    registry = get_registry()
    initialize_builtin_tools(registry)

    stats = registry.get_statistics()

    print(f"✓ Tool registry initialized")
    print(f"  Total tools: {stats['total_tools']}")
    print(f"  Enabled: {stats['enabled_tools']}")

    if stats['total_tools'] < 20:
        print("⚠ Warning: Less than 20 tools registered")
        sys.exit(1)

except Exception as e:
    print(f"✗ Tool registry failed: {e}")
    sys.exit(1)
EOPYTHON

if [ $? -eq 0 ]; then
    pass "Tool registry validated"
else
    fail "Tool registry validation failed"
fi

# Check code executor
echo
echo "Checking code executor..."

python3 << 'EOPYTHON'
import asyncio
import sys
sys.path.insert(0, "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack")

async def test_code_executor():
    from local_agents import get_code_executor, Language

    executor = get_code_executor()

    # Test Python execution
    result = await executor.execute(
        "print('Hello from Python!')",
        Language.PYTHON
    )

    if result.success and "Hello from Python!" in result.stdout:
        print("✓ Code executor working")
        return 0
    else:
        print(f"✗ Code executor failed: {result.error}")
        return 1

sys.exit(asyncio.run(test_code_executor()))
EOPYTHON

if [ $? -eq 0 ]; then
    pass "Code executor validated"
else
    fail "Code executor validation failed"
fi

# Check database
echo
echo "Checking databases..."

DB_DIR="$HOME/.local/share/nixos-ai-stack/local-agents"
mkdir -p "$DB_DIR"

if [ -f "$DB_DIR/tool_audit.db" ]; then
    COUNT=$(sqlite3 "$DB_DIR/tool_audit.db" "SELECT COUNT(*) FROM tool_calls;" 2>/dev/null || echo "0")
    pass "Tool audit database exists ($COUNT calls logged)"
else
    warn "Tool audit database not yet created"
fi

if [ -f "$DB_DIR/improvement.db" ]; then
    COUNT=$(sqlite3 "$DB_DIR/improvement.db" "SELECT COUNT(*) FROM quality_scores;" 2>/dev/null || echo "0")
    pass "Improvement database exists ($COUNT scores recorded)"
else
    warn "Improvement database not yet created"
fi

# Check file permissions
echo
echo "Checking permissions..."

if [ -w "$DB_DIR" ]; then
    pass "Database directory writable"
else
    fail "Database directory not writable: $DB_DIR"
fi

# Check built-in tools files
echo
echo "Checking tool files..."

TOOLS_DIR="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents"

check_file() {
    if [ -f "$1" ]; then
        pass "$(basename $1) exists"
    else
        fail "$(basename $1) missing"
    fi
}

check_file "$TOOLS_DIR/tool_registry.py"
check_file "$TOOLS_DIR/agent_executor.py"
check_file "$TOOLS_DIR/task_router.py"
check_file "$TOOLS_DIR/monitoring_agent.py"
check_file "$TOOLS_DIR/self_improvement.py"
check_file "$TOOLS_DIR/code_executor.py"

# Summary
echo
echo "=== Smoke Test Summary ==="
echo -e "${GREEN}All critical checks passed${NC}"
echo
echo "Next steps:"
echo "1. Run full test suite: python3 scripts/testing/test-local-agent-capabilities.py"
echo "2. Start monitoring: See docs/operations/local-agent-operations-guide.md"
echo "3. Deploy to production"
echo

exit 0
