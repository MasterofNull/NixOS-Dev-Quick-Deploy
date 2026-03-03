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

need_pattern "${ROOT}/nix/modules/core/options.nix" "aiHarness = {"
need_pattern "${ROOT}/nix/modules/core/options.nix" "runtime = {"
need_pattern "${ROOT}/nix/modules/core/options.nix" "defaultSafetyMode"
need_pattern "${ROOT}/nix/modules/core/options.nix" "safetyPolicy"
need_pattern "${ROOT}/nix/modules/core/options.nix" "isolationProfiles"
need_pattern "${ROOT}/nix/modules/core/options.nix" "workflowBlueprints"
need_pattern "${ROOT}/nix/modules/core/options.nix" "schedulerPolicy"
need_pattern "${ROOT}/nix/modules/core/options.nix" "parityScorecard"

need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_RUN_DEFAULT_SAFETY_MODE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_RUN_DEFAULT_TOKEN_LIMIT="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "AI_RUN_DEFAULT_TOOL_CALL_LIMIT="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "RUNTIME_SAFETY_POLICY_FILE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "RUNTIME_ISOLATION_PROFILES_FILE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "WORKFLOW_BLUEPRINTS_FILE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "RUNTIME_SCHEDULER_POLICY_FILE="
need_pattern "${ROOT}/nix/modules/services/mcp-servers.nix" "PARITY_SCORECARD_FILE="

need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "AI_RUN_DEFAULT_SAFETY_MODE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "RUNTIME_SAFETY_POLICY_FILE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "RUNTIME_ISOLATION_PROFILES_FILE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "WORKFLOW_BLUEPRINTS_FILE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "RUNTIME_SCHEDULER_POLICY_FILE"
need_pattern "${ROOT}/ai-stack/mcp-servers/hybrid-coordinator/http_server.py" "PARITY_SCORECARD_FILE"

jq . "${ROOT}/config/runtime-safety-policy.json" >/dev/null
jq . "${ROOT}/config/runtime-isolation-profiles.json" >/dev/null
jq . "${ROOT}/config/workflow-blueprints.json" >/dev/null
jq . "${ROOT}/config/runtime-scheduler-policy.json" >/dev/null
jq . "${ROOT}/config/parity-scorecard.json" >/dev/null

pass "Declarative runtime wiring and fallback artifacts validated"
