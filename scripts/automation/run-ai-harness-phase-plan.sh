#!/usr/bin/env bash
# Execute concrete harness optimization phases.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TESTING_DIR="${REPO_ROOT}/scripts/testing"
DATA_DIR="${REPO_ROOT}/scripts/data"

phase() {
  local name="$1"
  shift
  echo
  echo "=== ${name} ==="
  "$@"
  echo "PASS: ${name}"
}

phase "Phase 1 - Risk-tiered Tool Policy" "${TESTING_DIR}/validate-tool-execution-policy.sh"
phase "Phase 2 - Prompt Injection Resilience" "${TESTING_DIR}/test-prompt-injection-resilience.sh"
phase "Phase 3 - Autonomous Capability Discovery" "${TESTING_DIR}/test-autonomous-capability-discovery.sh"
phase "Phase 4 - Agent Capability Contract" "${TESTING_DIR}/validate-agent-capability-contract.sh"
phase "Phase 5 - GenAI Observability" "${TESTING_DIR}/validate-genai-observability.sh"
phase "Phase 6 - Weekly Research Sync" "${DATA_DIR}/sync-ai-research-knowledge.sh"

echo
echo "All AI harness optimization phases completed."
