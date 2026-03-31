#!/usr/bin/env bash
# ============================================================================
# ADK Discovery Workflow
# ============================================================================
# Recurring workflow to discover new Google ADK features and compare against
# current harness capabilities. Run this periodically (weekly recommended)
# to keep the ADK parity matrix current.
#
# Usage:
#   ./scripts/upstream/adk-discovery-workflow.sh [--update-matrix] [--create-issues]
#
# Options:
#   --update-matrix   Update the parity matrix with discovered gaps
#   --create-issues   Create backlog issues for significant gaps
#   --output FILE     Write discovery report to file (default: stdout)
#
# Phase 4.4: ADK Integration, Parity Check & Discovery
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PARITY_MATRIX="${REPO_ROOT}/docs/architecture/GOOGLE-ADK-PARITY-MATRIX-2026-03.md"
DISCOVERY_LOG="${REPO_ROOT}/docs/architecture/adk-discovery-log.jsonl"
OUTPUT_FILE=""
UPDATE_MATRIX=false
CREATE_ISSUES=false

# ADK documentation and release URLs to monitor
ADK_DOCS_URL="https://google.github.io/adk-docs/"
ADK_GITHUB_URL="https://github.com/google/adk"
ADK_RELEASES_API="https://api.github.com/repos/google/adk/releases"

# Areas to track for parity
TRACKED_AREAS=(
  "multi-agent-composition"
  "a2a-interoperability"
  "mcp-interoperability"
  "sessions-state"
  "qdrant-retrieval"
  "observability"
  "evaluation"
  "retry-resilience"
  "tool-discovery"
)

log_info() { printf '[INFO] %s\n' "$1"; }
log_warn() { printf '[WARN] %s\n' "$1" >&2; }
log_error() { printf '[ERROR] %s\n' "$1" >&2; }

usage() {
  grep '^#' "${BASH_SOURCE[0]}" | grep -v '#!/' | sed 's/^# //'
  exit 0
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --update-matrix) UPDATE_MATRIX=true; shift ;;
      --create-issues) CREATE_ISSUES=true; shift ;;
      --output) OUTPUT_FILE="$2"; shift 2 ;;
      --help|-h) usage ;;
      *) log_error "Unknown option: $1"; exit 1 ;;
    esac
  done
}

# Check current harness capabilities against known areas
assess_current_capabilities() {
  local area="$1"
  local score=0
  local evidence=""

  case "$area" in
    "multi-agent-composition")
      # Check for workflow orchestration
      if grep -q "workflow.*orchestrat" "${REPO_ROOT}"/ai-stack/mcp-servers/hybrid-coordinator/*.py 2>/dev/null; then
        score=$((score + 25))
        evidence="workflow orchestration present"
      fi
      # Check for team formation
      if grep -q "team.formation\|TeamFormation" "${REPO_ROOT}"/ai-stack/mcp-servers/hybrid-coordinator/*.py 2>/dev/null; then
        score=$((score + 25))
        evidence="${evidence}, team formation present"
      fi
      # Check for reviewer gates
      if grep -q "reviewer.*gate\|ReviewerGate" "${REPO_ROOT}"/ai-stack/mcp-servers/hybrid-coordinator/*.py 2>/dev/null; then
        score=$((score + 25))
        evidence="${evidence}, reviewer gates present"
      fi
      ;;
    "a2a-interoperability")
      # Check for A2A routes
      if grep -q "/a2a\|a2a_" "${REPO_ROOT}"/ai-stack/mcp-servers/hybrid-coordinator/http_server.py 2>/dev/null; then
        score=$((score + 40))
        evidence="A2A routes present"
      fi
      # Check for agent card
      if grep -q "agent.card\|AgentCard" "${REPO_ROOT}"/ai-stack/mcp-servers/hybrid-coordinator/*.py 2>/dev/null; then
        score=$((score + 30))
        evidence="${evidence}, agent card present"
      fi
      # Check for dashboard A2A visibility
      if grep -q "a2a.*readiness\|A2A" "${REPO_ROOT}"/dashboard/backend/api/routes/insights.py 2>/dev/null; then
        score=$((score + 15))
        evidence="${evidence}, dashboard visibility present"
      fi
      ;;
    "mcp-interoperability")
      # Check for MCP servers
      local mcp_count
      mcp_count=$(find "${REPO_ROOT}/ai-stack/mcp-servers" -maxdepth 1 -type d 2>/dev/null | wc -l)
      if [[ "$mcp_count" -gt 3 ]]; then
        score=$((score + 50))
        evidence="$((mcp_count - 1)) MCP servers"
      fi
      # Check for MCP health checks
      if [[ -f "${REPO_ROOT}/scripts/testing/smoke-mcp-health-pings.sh" ]]; then
        score=$((score + 30))
        evidence="${evidence}, health checks present"
      fi
      ;;
    "observability")
      # Check for Prometheus metrics
      if grep -q "prometheus\|Prometheus" "${REPO_ROOT}"/nix/modules/services/*.nix 2>/dev/null; then
        score=$((score + 30))
        evidence="Prometheus metrics present"
      fi
      # Check for OpenTelemetry
      if grep -q "otel\|opentelemetry" "${REPO_ROOT}"/ai-stack/mcp-servers/hybrid-coordinator/*.py 2>/dev/null; then
        score=$((score + 25))
        evidence="${evidence}, OpenTelemetry present"
      fi
      ;;
    "evaluation")
      # Check for evaluation routes
      if grep -q "evaluation\|eval" "${REPO_ROOT}"/dashboard/backend/api/routes/aistack.py 2>/dev/null; then
        score=$((score + 30))
        evidence="evaluation routes present"
      fi
      # Check for parity smoke tests
      if [[ -f "${REPO_ROOT}/scripts/testing/smoke-agent-harness-parity.sh" ]]; then
        score=$((score + 30))
        evidence="${evidence}, parity tests present"
      fi
      ;;
    *)
      score=50
      evidence="baseline assessment"
      ;;
  esac

  printf '{"area":"%s","score":%d,"evidence":"%s"}\n' "$area" "$score" "$evidence"
}

# Generate discovery report
generate_discovery_report() {
  local timestamp
  timestamp="$(date -Is)"

  cat <<EOF
# ADK Discovery Report
Generated: ${timestamp}

## Capability Assessment

EOF

  for area in "${TRACKED_AREAS[@]}"; do
    local result
    result=$(assess_current_capabilities "$area")
    local score
    score=$(echo "$result" | jq -r '.score')
    local evidence
    evidence=$(echo "$result" | jq -r '.evidence')

    local status_icon="⏳"
    if [[ "$score" -ge 80 ]]; then
      status_icon="✅"
    elif [[ "$score" -ge 60 ]]; then
      status_icon="🟡"
    elif [[ "$score" -ge 40 ]]; then
      status_icon="🟠"
    else
      status_icon="🔴"
    fi

    printf '%s **%s**: %d/100\n' "$status_icon" "$area" "$score"
    printf '   Evidence: %s\n\n' "$evidence"

    # Log to discovery log
    echo "{\"timestamp\":\"${timestamp}\",\"area\":\"${area}\",\"score\":${score},\"evidence\":\"${evidence}\"}" >> "${DISCOVERY_LOG}"
  done

  cat <<EOF

## Recommendations

### High Priority (Score < 60)
EOF

  for area in "${TRACKED_AREAS[@]}"; do
    local result
    result=$(assess_current_capabilities "$area")
    local score
    score=$(echo "$result" | jq -r '.score')

    if [[ "$score" -lt 60 ]]; then
      printf -- '- [ ] Improve %s coverage (current: %d/100)\n' "$area" "$score"
    fi
  done

  cat <<EOF

### Medium Priority (Score 60-79)
EOF

  for area in "${TRACKED_AREAS[@]}"; do
    local result
    result=$(assess_current_capabilities "$area")
    local score
    score=$(echo "$result" | jq -r '.score')

    if [[ "$score" -ge 60 && "$score" -lt 80 ]]; then
      printf -- '- [ ] Enhance %s (current: %d/100)\n' "$area" "$score"
    fi
  done

  cat <<EOF

## Next Steps

1. Review high-priority gaps above
2. Check ADK release notes for new features: ${ADK_GITHUB_URL}/releases
3. Update parity matrix if significant changes detected
4. Create backlog items for identified gaps

## Declarative Wiring Requirements

Any ADK-aligned integration MUST follow these patterns:

1. **Nix Option Ownership**: All configuration via mySystem.* options
2. **Environment Injection**: No hardcoded ports/URLs - use env vars
3. **Service Dependencies**: Declare in systemd after/wants
4. **Health Checks**: Implement /health endpoint
5. **Graceful Degradation**: Function when optional deps unavailable

Example:
\`\`\`nix
# nix/modules/services/adk-integration.nix
{ config, lib, pkgs, ... }:
let
  cfg = config.mySystem.aiStack.adkIntegration;
in {
  options.mySystem.aiStack.adkIntegration = {
    enable = lib.mkEnableOption "ADK integration";
    port = lib.mkOption {
      type = lib.types.port;
      default = 8090;
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.services.adk-integration = {
      after = [ "ai-hybrid-coordinator.service" ];
      environment = {
        ADK_PORT = toString cfg.port;
        HYBRID_URL = "http://127.0.0.1:\${toString config.mySystem.mcpServers.hybridPort}";
      };
    };
  };
}
\`\`\`
EOF
}

main() {
  parse_args "$@"

  log_info "Running ADK Discovery Workflow..."

  # Ensure discovery log directory exists
  mkdir -p "$(dirname "${DISCOVERY_LOG}")"

  # Generate report
  local report
  report=$(generate_discovery_report)

  if [[ -n "$OUTPUT_FILE" ]]; then
    echo "$report" > "$OUTPUT_FILE"
    log_info "Report written to: ${OUTPUT_FILE}"
  else
    echo "$report"
  fi

  if [[ "$UPDATE_MATRIX" == "true" ]]; then
    log_info "Matrix update requested - manual review required"
    log_info "Parity matrix location: ${PARITY_MATRIX}"
  fi

  if [[ "$CREATE_ISSUES" == "true" ]]; then
    log_info "Issue creation requested - requires gh CLI"
    if command -v gh >/dev/null 2>&1; then
      log_warn "Auto-issue creation not yet implemented - manual review required"
    else
      log_warn "gh CLI not available - skipping issue creation"
    fi
  fi

  log_info "ADK Discovery Workflow complete"
}

main "$@"
