#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../../config/service-endpoints.sh
source "${SCRIPT_DIR}/../../config/service-endpoints.sh"
MCP_DB_VALIDATE_SCRIPT="${REPO_ROOT}/scripts/ai/mcp-db-validate"
RAG_SMOKE_TEST_SCRIPT="${REPO_ROOT}/scripts/testing/rag-smoke-test.sh"
LIBRARY_CATALOG_VALIDATE_SCRIPT="${REPO_ROOT}/scripts/data/sync-aidb-library-catalog.sh"
TOOL_POLICY_VALIDATE_SCRIPT="${REPO_ROOT}/scripts/testing/validate-tool-execution-policy.sh"
AUTONOMOUS_DISCOVERY_TEST_SCRIPT="${REPO_ROOT}/scripts/testing/test-autonomous-capability-discovery.sh"
INJECTION_TEST_SCRIPT="${REPO_ROOT}/scripts/testing/test-prompt-injection-resilience.sh"
AGENT_CONTRACT_VALIDATE_SCRIPT="${REPO_ROOT}/scripts/testing/validate-agent-capability-contract.sh"
OBSERVABILITY_VALIDATE_SCRIPT="${REPO_ROOT}/scripts/testing/validate-genai-observability.sh"
RESEARCH_SYNC_SCRIPT="${REPO_ROOT}/scripts/data/sync-ai-research-knowledge.sh"
SYSTEM_HEALTH_CHECK_SCRIPT="${REPO_ROOT}/scripts/health/system-health-check.sh"

HYBRID_API_KEY="${HYBRID_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi
if [[ -z "${HYBRID_API_KEY}" && -r "/run/secrets/hybrid_api_key" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < /run/secrets/hybrid_api_key)"
fi

AIDB_API_KEY="${AIDB_API_KEY:-}"
AIDB_API_KEY_FILE="${AIDB_API_KEY_FILE:-/run/secrets/aidb_api_key}"
if [[ -z "${AIDB_API_KEY}" && -r "${AIDB_API_KEY_FILE}" ]]; then
  AIDB_API_KEY="$(tr -d '[:space:]' < "${AIDB_API_KEY_FILE}")"
fi

hybrid_auth_args=()
if [[ -n "${HYBRID_API_KEY}" ]]; then
  hybrid_auth_args=(-H "X-API-Key: ${HYBRID_API_KEY}")
fi

aidb_auth_args=()
if [[ -n "${AIDB_API_KEY}" ]]; then
  aidb_auth_args=(-H "X-API-Key: ${AIDB_API_KEY}")
fi

"${SYSTEM_HEALTH_CHECK_SCRIPT}" --detailed

unit_declared() {
  local unit="$1"
  systemctl list-unit-files --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "$unit" \
    || systemctl list-units --all --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "$unit"
}

assert_file_has_literal() {
  local file="$1"
  local needle="$2"
  local label="$3"
  if grep -Fq "$needle" "$file"; then
    printf 'PASS: %s\n' "$label"
  else
    printf 'FAIL: %s (missing literal in %s)\n' "$label" "$file" >&2
    exit 1
  fi
}

assert_jq_expr() {
  local label="$1"
  local url="$2"
  local expr="$3"
  shift 3
  local -a extra_args=("$@")
  local payload=""
  payload="$(curl -fsS --max-time 5 --connect-timeout 3 "${extra_args[@]}" "$url")"
  if echo "$payload" | jq -e "$expr" >/dev/null 2>&1; then
    printf 'PASS: %s\n' "$label"
  else
    printf 'FAIL: %s (%s)\n' "$label" "$url" >&2
    echo "$payload" | jq . >&2 || echo "$payload" >&2
    exit 1
  fi
}

assert_file_has_literal \
  "${REPO_ROOT}/nix/modules/roles/ai-stack.nix" \
  'ExecStart = "${pkgs.python3}/bin/python3 ${cfg.mcpServers.repoPath}/scripts/automation/prsi-orchestrator.py cycle --since=1d --execute-limit=5";' \
  "Declarative PRSI unit uses explicit python3 ExecStart"

assert_file_has_literal \
  "${REPO_ROOT}/nix/modules/roles/ai-stack.nix" \
  'ExecStart = "${pkgs.python3}/bin/python3 ${cfg.mcpServers.repoPath}/scripts/ai/aq-optimizer --since=1d";' \
  "Declarative optimizer unit uses explicit python3 ExecStart"

if command -v curl >/dev/null 2>&1; then
  if unit_declared "ai-aidb.service"; then
    curl -fsS --max-time 5 "${aidb_auth_args[@]}" "${AIDB_URL%/}/health" >/dev/null || {
      echo "AIDB health endpoint failed (${AIDB_URL%/}/health)" >&2
      exit 1
    }
  else
    echo "Skipping AIDB endpoint probe (ai-aidb.service not declared)."
  fi

  if unit_declared "ai-hybrid-coordinator.service"; then
    curl -fsS --max-time 5 "${hybrid_auth_args[@]}" "${HYBRID_URL%/}/health" >/dev/null || {
      echo "Hybrid coordinator health endpoint failed (${HYBRID_URL%/}/health)" >&2
      exit 1
    }
    if command -v jq >/dev/null 2>&1; then
      assert_jq_expr "Hybrid AI harness health contract available" \
        "${HYBRID_URL%/}/health" \
        '.status == "healthy" and .ai_harness.enabled == true and .ai_harness.memory_enabled == true and .ai_harness.tree_search_enabled == true and .ai_harness.eval_enabled == true' \
        "${hybrid_auth_args[@]}"
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
