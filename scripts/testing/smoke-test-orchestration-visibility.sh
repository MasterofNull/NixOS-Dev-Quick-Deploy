#!/usr/bin/env bash
set -euo pipefail

echo "=== Orchestration Visibility Smoke Test (Code Validation) ==="
echo ""

# Test 1: Verify UI elements in dashboard HTML
echo "Test 1: UI elements in dashboard.html..."
grep -q 'id="orchestrationTeamGrid"' dashboard.html
echo "  ✓ Orchestration team grid element present"

grep -q 'function loadOrchestrationDetails()' dashboard.html
echo "  ✓ loadOrchestrationDetails function present"

grep -q 'function loadAgentEvaluationTrends()' dashboard.html
echo "  ✓ loadAgentEvaluationTrends function present"

# Test 2: Verify endpoint handlers in hybrid coordinator
echo ""
echo "Test 2: Hybrid coordinator endpoint handlers..."
grep -q 'async def handle_workflow_run_team_detailed' ai-stack/mcp-servers/hybrid-coordinator/http_server.py
echo "  ✓ Team detailed handler defined"

grep -q 'async def handle_ai_coordinator_evaluation_trends' ai-stack/mcp-servers/hybrid-coordinator/http_server.py
echo "  ✓ Evaluation trends handler defined"

# Test 3: Verify dashboard proxy endpoints
echo ""
echo "Test 3: Dashboard proxy endpoints..."
grep -q '/orchestration/team/' dashboard/backend/api/routes/aistack.py
echo "  ✓ Team proxy endpoint defined"

grep -q '/orchestration/evaluations/trends' dashboard/backend/api/routes/aistack.py
echo "  ✓ Evaluation trends proxy endpoint defined"

# Test 4: Verify Python syntax
echo ""
echo "Test 4: Python syntax validation..."
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/http_server.py 2>/dev/null
echo "  ✓ Hybrid coordinator syntax valid"

python3 -m py_compile dashboard/backend/api/routes/aistack.py 2>/dev/null
echo "  ✓ Dashboard backend syntax valid"

# Test 5: Verify documentation
echo ""
echo "Test 5: Documentation files..."
[ -f docs/api/orchestration-visibility.md ]
echo "  ✓ API documentation present"

[ -f docs/operations/orchestration-visibility-guide.md ]
echo "  ✓ Operator guide present"

echo ""
echo "=================================================="
echo "✓ All smoke tests passed!"
echo ""
echo "Note: Service restart required for endpoints:"
echo "  sudo systemctl restart ai-hybrid-coordinator.service"
echo "  sudo systemctl restart command-center-dashboard-api.service"
echo "=================================================="
