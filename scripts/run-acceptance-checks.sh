#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"
MCP_DB_VALIDATE_SCRIPT="${SCRIPT_DIR}/mcp-db-validate"
RAG_SMOKE_TEST_SCRIPT="${SCRIPT_DIR}/rag-smoke-test.sh"
LIBRARY_CATALOG_VALIDATE_SCRIPT="${SCRIPT_DIR}/sync-aidb-library-catalog.sh"
TOOL_POLICY_VALIDATE_SCRIPT="${SCRIPT_DIR}/validate-tool-execution-policy.sh"
AUTONOMOUS_DISCOVERY_TEST_SCRIPT="${SCRIPT_DIR}/test-autonomous-capability-discovery.sh"
INJECTION_TEST_SCRIPT="${SCRIPT_DIR}/test-prompt-injection-resilience.sh"
AGENT_CONTRACT_VALIDATE_SCRIPT="${SCRIPT_DIR}/validate-agent-capability-contract.sh"
OBSERVABILITY_VALIDATE_SCRIPT="${SCRIPT_DIR}/validate-genai-observability.sh"
RESEARCH_SYNC_SCRIPT="${SCRIPT_DIR}/sync-ai-research-knowledge.sh"

"${SCRIPT_DIR}/system-health-check.sh" --detailed

unit_declared() {
  local unit="$1"
  systemctl list-unit-files --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "$unit" \
    || systemctl list-units --all --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "$unit"
}

assert_jq_expr() {
  local label="$1"
  local url="$2"
  local expr="$3"
  local payload=""
  payload="$(curl -fsS --max-time 5 --connect-timeout 3 "$url")"
  if echo "$payload" | jq -e "$expr" >/dev/null 2>&1; then
    printf 'PASS: %s\n' "$label"
  else
    printf 'FAIL: %s (%s)\n' "$label" "$url" >&2
    echo "$payload" | jq . >&2 || echo "$payload" >&2
    exit 1
  fi
}

if command -v curl >/dev/null 2>&1; then
  if unit_declared "ai-aidb.service"; then
    curl -fsS --max-time 5 "${AIDB_URL%/}/health" >/dev/null || {
      echo "AIDB health endpoint failed (${AIDB_URL%/}/health)" >&2
      exit 1
    }
  else
    echo "Skipping AIDB endpoint probe (ai-aidb.service not declared)."
  fi

  if unit_declared "ai-hybrid-coordinator.service"; then
    curl -fsS --max-time 5 "${HYBRID_URL%/}/health" >/dev/null || {
      echo "Hybrid coordinator health endpoint failed (${HYBRID_URL%/}/health)" >&2
      exit 1
    }
    if command -v jq >/dev/null 2>&1; then
      assert_jq_expr "Hybrid AI harness health contract available" \
        "${HYBRID_URL%/}/health" \
        '.status == "healthy" and .ai_harness.enabled == true and .ai_harness.memory_enabled == true and .ai_harness.tree_search_enabled == true and .ai_harness.eval_enabled == true'
    fi
  else
    echo "Skipping hybrid endpoint probe (ai-hybrid-coordinator.service not declared)."
  fi

  if unit_declared "ai-switchboard.service"; then
    curl -fsS --max-time 5 "${SWITCHBOARD_URL%/}/health" >/dev/null || {
      echo "Switchboard health endpoint failed (${SWITCHBOARD_URL%/}/health)" >&2
      exit 1
    }
  else
    echo "Skipping switchboard endpoint probe (ai-switchboard.service not declared)."
  fi

  if unit_declared "llama-cpp-embed.service"; then
    curl -fsS --max-time 5 "${EMBEDDINGS_URL%/}/health" >/dev/null || {
      echo "Embedding endpoint failed (${EMBEDDINGS_URL%/}/health)" >&2
      exit 1
    }
  else
    echo "Skipping embeddings endpoint probe (llama-cpp-embed.service not declared)."
  fi

  if unit_declared "command-center-dashboard-api.service"; then
    assert_jq_expr "Dashboard harness overview endpoint available" \
      "${DASHBOARD_API_URL%/}/api/harness/overview" \
      '.status == "ok" and (.maintenance.total_scripts | tonumber) >= 1 and .harness.scorecard != null'
  else
    echo "Skipping dashboard harness probe (command-center-dashboard-api.service not declared)."
  fi
fi

if [[ ! -x "${MCP_DB_VALIDATE_SCRIPT}" ]]; then
  echo "MCP DB validator not found or not executable: ${MCP_DB_VALIDATE_SCRIPT}" >&2
  exit 1
fi

if [[ ! -x "${RAG_SMOKE_TEST_SCRIPT}" ]]; then
  echo "RAG smoke test script not found or not executable: ${RAG_SMOKE_TEST_SCRIPT}" >&2
  exit 1
fi

for required_script in \
  "${TOOL_POLICY_VALIDATE_SCRIPT}" \
  "${AUTONOMOUS_DISCOVERY_TEST_SCRIPT}" \
  "${INJECTION_TEST_SCRIPT}" \
  "${AGENT_CONTRACT_VALIDATE_SCRIPT}" \
  "${OBSERVABILITY_VALIDATE_SCRIPT}" \
  "${RESEARCH_SYNC_SCRIPT}"; do
  if [[ ! -x "${required_script}" ]]; then
    echo "Required harness gate script missing or not executable: ${required_script}" >&2
    exit 1
  fi
done

echo "Running MCP database validator in non-interactive mode..."
"${MCP_DB_VALIDATE_SCRIPT}" --non-interactive

if unit_declared "qdrant.service" && unit_declared "llama-cpp-embed.service"; then
  echo "Running RAG smoke test..."
  "${RAG_SMOKE_TEST_SCRIPT}"
else
  echo "Skipping RAG smoke test (requires qdrant.service and llama-cpp-embed.service)."
fi

echo "Running tool risk-policy gate..."
"${TOOL_POLICY_VALIDATE_SCRIPT}"

echo "Running prompt-injection resilience gate..."
"${INJECTION_TEST_SCRIPT}"

echo "Running autonomous capability-discovery gate..."
"${AUTONOMOUS_DISCOVERY_TEST_SCRIPT}"

echo "Validating agent capability contract..."
"${AGENT_CONTRACT_VALIDATE_SCRIPT}"

echo "Validating GenAI observability surfaces..."
"${OBSERVABILITY_VALIDATE_SCRIPT}"

if unit_declared "ai-aidb.service"; then
  if [[ ! -x "${LIBRARY_CATALOG_VALIDATE_SCRIPT}" ]]; then
    echo "AIDB library catalog validator not found or not executable: ${LIBRARY_CATALOG_VALIDATE_SCRIPT}" >&2
    exit 1
  fi
  echo "Validating AIDB library catalog..."
  "${LIBRARY_CATALOG_VALIDATE_SCRIPT}" --validate-only
fi

echo "Validating weekly AI research sync scorecard..."
"${RESEARCH_SYNC_SCRIPT}" --validate-only

echo "Acceptance checks passed (declarative mode)."
