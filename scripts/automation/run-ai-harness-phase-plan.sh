#!/usr/bin/env bash
# Execute concrete harness optimization phases.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

phase() {
  local name="$1"
  shift
  echo
  echo "=== ${name} ==="
  "$@"
  echo "PASS: ${name}"
}

phase "Phase 1 - Risk-tiered Tool Policy" "${SCRIPT_DIR}/validate-tool-execution-policy.sh"
phase "Phase 2 - Prompt Injection Resilience" "${SCRIPT_DIR}/test-prompt-injection-resilience.sh"
phase "Phase 3 - Autonomous Capability Discovery" "${SCRIPT_DIR}/test-autonomous-capability-discovery.sh"
phase "Phase 4 - Agent Capability Contract" "${SCRIPT_DIR}/validate-agent-capability-contract.sh"
phase "Phase 5 - GenAI Observability" "${SCRIPT_DIR}/validate-genai-observability.sh"
phase "Phase 6 - Weekly Research Sync" "${SCRIPT_DIR}/sync-ai-research-knowledge.sh"

echo
echo "All AI harness optimization phases completed."
