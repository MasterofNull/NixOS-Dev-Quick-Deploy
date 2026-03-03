#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/hyperd/Documents/NixOS-Dev-Quick-Deploy}"

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

need_file() {
  local path="$1"
  [[ -f "$path" ]] || fail "missing file: $path"
}

need_pattern() {
  local path="$1"
  local pattern="$2"
  rg -n --fixed-strings "$pattern" "$path" >/dev/null || fail "missing pattern '$pattern' in $path"
}

need_file "${ROOT}/nix/modules/core/options.nix"
need_file "${ROOT}/nix/modules/services/mcp-servers.nix"
need_file "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py"
need_file "${ROOT}/config/runtime-safety-policy.json"
need_file "${ROOT}/config/runtime-isolation-profiles.json"
need_file "${ROOT}/config/workflow-blueprints.json"
need_file "${ROOT}/config/runtime-scheduler-policy.json"
need_file "${ROOT}/config/parity-scorecard.json"
need_file "${ROOT}/config/runtime-tool-security-policy.json"

need_pattern "${ROOT}/nix/modules/core/options.nix" "aiHarness = {"
need_pattern "${ROOT}/nix/modules/core/options.nix" "runtime = {"
need_pattern "${ROOT}/nix/modules/core/options.nix" "defaultSafetyMode"
need_pattern "${ROOT}/nix/modules/core/options.nix" "safetyPolicy"
need_pattern "${ROOT}/nix/modules/core/options.nix" "isolationProfiles"
need_pattern "${ROOT}/nix/modules/core/options.nix" "workflowBlueprints"
need_pattern "${ROOT}/nix/modules/core/options.nix" "schedulerPolicy"
need_pattern "${ROOT}/nix/modules/core/options.nix" "semanticToolingAutorun"
need_pattern "${ROOT}/nix/modules/core/options.nix" "aiderToolingPlanEnabled"
need_pattern "${ROOT}/nix/modules/core/options.nix" "aiderSmallScopeSubtreeOnly"
need_pattern "${ROOT}/nix/modules/core/options.nix" "aiderSmallScopeMapTokens"
need_pattern "${ROOT}/nix/modules/core/options.nix" "aiderAnalysisFastMode"
need_pattern "${ROOT}/nix/modules/core/options.nix" "aiderAnalysisMapTokens"
need_pattern "${ROOT}/nix/modules/core/options.nix" "aiderAnalysisMaxRuntimeSeconds"
need_pattern "${ROOT}/nix/modules/core/options.nix" "aiderAnalysisRouteToHybrid"
need_pattern "${ROOT}/nix/modules/core/options.nix" "toolSecurity = {"
need_pattern "${ROOT}/nix/modules/core/options.nix" "parityScorecard"

need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_RUN_DEFAULT_SAFETY_MODE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_RUN_DEFAULT_TOKEN_LIMIT="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_RUN_DEFAULT_TOOL_CALL_LIMIT="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "RUNTIME_SAFETY_POLICY_FILE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "RUNTIME_ISOLATION_PROFILES_FILE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "WORKFLOW_BLUEPRINTS_FILE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "RUNTIME_SCHEDULER_POLICY_FILE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_SEMANTIC_TOOLING_AUTORUN="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_TOOLING_PLAN_ENABLED="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_AIDER_SMALL_SCOPE_SUBTREE_ONLY="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AIDER_SMALL_SCOPE_MAP_TOKENS="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_AIDER_ANALYSIS_FAST_MODE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AIDER_ANALYSIS_MAP_TOKENS="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AIDER_ANALYSIS_MAX_RUNTIME_SECONDS="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_AIDER_ANALYSIS_ROUTE_TO_HYBRID="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_TOOL_SECURITY_AUDIT_ENABLED="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_TOOL_SECURITY_AUDIT_ENFORCE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_TOOL_SECURITY_CACHE_TTL_HOURS="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "RUNTIME_TOOL_SECURITY_POLICY_FILE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "PARITY_SCORECARD_FILE="

need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "AI_RUN_DEFAULT_SAFETY_MODE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "RUNTIME_SAFETY_POLICY_FILE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "RUNTIME_ISOLATION_PROFILES_FILE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "WORKFLOW_BLUEPRINTS_FILE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "RUNTIME_SCHEDULER_POLICY_FILE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "PARITY_SCORECARD_FILE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "_audit_planned_tools"
need_pattern "${ROOT}/ai-stack/mcp-servers/aider-wrapper/server.py" "AI_AIDER_SMALL_SCOPE_SUBTREE_ONLY"
need_pattern "${ROOT}/ai-stack/mcp-servers/aider-wrapper/server.py" "_is_analysis_only_task"
need_pattern "${ROOT}/ai-stack/mcp-servers/aider-wrapper/server.py" "subtree-only"
need_pattern "${ROOT}/ai-stack/mcp-servers/aider-wrapper/server.py" "_run_analysis_fastpath"

jq . "${ROOT}/config/runtime-safety-policy.json" >/dev/null
jq . "${ROOT}/config/runtime-isolation-profiles.json" >/dev/null
jq . "${ROOT}/config/workflow-blueprints.json" >/dev/null
jq . "${ROOT}/config/runtime-scheduler-policy.json" >/dev/null
jq . "${ROOT}/config/parity-scorecard.json" >/dev/null
jq . "${ROOT}/config/runtime-tool-security-policy.json" >/dev/null

pass "Declarative runtime wiring and fallback artifacts validated"
