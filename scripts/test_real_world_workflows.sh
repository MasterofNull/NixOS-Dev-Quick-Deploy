#!/usr/bin/env bash
#
# Smoke-test real-world declarative workflows and monitoring surfaces.
# Fails fast on regressions; avoids deprecated imperative scripts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "$REPO_ROOT/config/service-endpoints.sh"

AQD_CLI="$REPO_ROOT/scripts/aqd"
ACCEPTANCE_SCRIPT="$REPO_ROOT/scripts/run-acceptance-checks.sh"

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Required command not found: $1" >&2
        exit 1
    }
}

assert_jq_expr() {
    local label="$1"
    local url="$2"
    local expr="$3"
    local payload=""

    payload="$(curl -fsS --max-time 5 --connect-timeout 3 "$url")"
    if echo "$payload" | jq -e "$expr" >/dev/null 2>&1; then
        printf '✅ %s\n' "$label"
    else
        printf '❌ %s (%s)\n' "$label" "$url" >&2
        echo "$payload" | jq . >&2 || echo "$payload" >&2
        exit 1
    fi
}

assert_output_contains() {
    local label="$1"
    local output="$2"
    local needle="$3"
    if grep -Fq "$needle" <<<"$output"; then
        printf '✅ %s\n' "$label"
    else
        printf '❌ %s (missing: %s)\n' "$label" "$needle" >&2
        echo "$output" >&2
        exit 1
    fi
}

unit_declared() {
    local unit="$1"
    systemctl list-unit-files --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "$unit" \
      || systemctl list-units --all --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "$unit"
}

require_cmd curl
require_cmd jq

if [[ ! -x "$AQD_CLI" ]]; then
    echo "AQD CLI not found or not executable: $AQD_CLI" >&2
    exit 1
fi

if [[ ! -x "$ACCEPTANCE_SCRIPT" ]]; then
    echo "Acceptance script not found or not executable: $ACCEPTANCE_SCRIPT" >&2
    exit 1
fi

echo "🔎 Workflow example 1: AQD workflow discovery"
workflows_output="$("$AQD_CLI" workflows list)"
echo "$workflows_output"
assert_output_contains "AQD workflow list includes skill validation path" "$workflows_output" "skill validate"
assert_output_contains "AQD workflow list includes MCP deployment path" "$workflows_output" "mcp deploy-aidb"

echo "🧪 Workflow example 2: AQD skill validation"
"$AQD_CLI" skill validate
echo "✅ AQD skill validation completed"

echo "🩺 Workflow example 3: declarative acceptance checks"
"$ACCEPTANCE_SCRIPT"
echo "✅ Acceptance checks completed"

echo "📊 Monitoring assertions (dashboard + stack APIs)"
assert_jq_expr "Dashboard API health status is healthy" "${DASHBOARD_API_URL%/}/api/health" '.status == "healthy"'
assert_jq_expr "Dashboard aggregate reports overall healthy" "${DASHBOARD_API_URL%/}/api/health/aggregate" '.overall_status == "healthy"'
assert_jq_expr "Dashboard AI metrics endpoint responds" "${DASHBOARD_API_URL%/}/api/ai/metrics" '.services.aidb.status == "online" and .services.hybrid_coordinator.status == "healthy"'
assert_jq_expr "AIDB service health is ok" "${AIDB_URL%/}/health" '.status == "ok"'
assert_jq_expr "AIDB exposes tool risk policy" "${AIDB_URL%/}/health" '.tool_execution_policy.allow_high_risk_tools == false and .tool_execution_policy.allow_medium_risk_tools == true'
assert_jq_expr "AIDB exposes outbound egress policy" "${AIDB_URL%/}/health" '.outbound_http_policy.block_private_ranges == true'
assert_jq_expr "Hybrid service health is healthy" "${HYBRID_URL%/}/health" '.status == "healthy"'
assert_jq_expr "Hybrid AI harness reports all core features enabled" "${HYBRID_URL%/}/health" '.ai_harness.enabled == true and .ai_harness.memory_enabled == true and .ai_harness.tree_search_enabled == true and .ai_harness.eval_enabled == true'
assert_jq_expr "Hybrid selective capability discovery gate is enabled" "${HYBRID_URL%/}/health" '.ai_harness.capability_discovery_enabled == true and (.ai_harness.capability_discovery_ttl_seconds | tonumber) >= 60'
assert_jq_expr "Hybrid capability discovery stats are exposed" "${HYBRID_URL%/}/health" '.capability_discovery.invoked >= 0 and .capability_discovery.skipped >= 0 and .capability_discovery.cache_hits >= 0 and .capability_discovery.errors >= 0'
assert_jq_expr "Hybrid harness stats endpoint responds" "${HYBRID_URL%/}/stats" '.harness_stats.total_runs >= 0 and .capability_discovery.invoked >= 0'
assert_jq_expr "Monitoring service list reports core units running" "${DASHBOARD_API_URL%/}/api/services" '(map(select(.id == "ai-aidb" and .status == "running")) | length > 0) and (map(select(.id == "ai-hybrid-coordinator" and .status == "running")) | length > 0) and (map(select(.id == "ai-ralph-wiggum" and .status == "running")) | length > 0) and (map(select(.id == "llama-cpp" and .status == "running")) | length > 0)'

if unit_declared "ai-switchboard.service"; then
    assert_jq_expr "Dashboard AI metrics reports switchboard healthy" "${DASHBOARD_API_URL%/}/api/ai/metrics" '.services.switchboard.status == "ok" or .services.switchboard.status == "healthy"'
fi

if unit_declared "llama-cpp-embed.service"; then
    assert_jq_expr "Dashboard AI metrics reports embeddings healthy" "${DASHBOARD_API_URL%/}/api/ai/metrics" '.services.embeddings.status == "ok" or .services.embeddings.status == "healthy"'
    assert_jq_expr "Dashboard AI metrics reports embeddings model name" "${DASHBOARD_API_URL%/}/api/ai/metrics" '.services.embeddings.model != null and .services.embeddings.model != "" and .services.embeddings.model != "unknown"'
fi

if unit_declared "qdrant.service" && unit_declared "llama-cpp-embed.service"; then
    assert_jq_expr "Dashboard AI metrics reports non-zero vectors after RAG smoke" "${DASHBOARD_API_URL%/}/api/ai/metrics" '.services.qdrant.metrics.total_vectors >= 1'
fi

echo "🎯 Workflow smoke test complete."
