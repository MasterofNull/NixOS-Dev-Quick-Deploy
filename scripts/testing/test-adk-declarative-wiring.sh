#!/usr/bin/env bash
# Purpose: verify ADK declarative-first wiring requirements stay documented and validator-backed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

ADK_DATA_DIR="$(mktemp -d)"
export ADK_DATA_DIR
trap 'rm -rf "${ADK_DATA_DIR}"' EXIT

bash "${ROOT}/lib/l4-coord/adk/wiring-validator.sh" --dir "${ROOT}/lib/l4-coord/adk" --pattern "*.nix" >/dev/null

grep -q 'All ADK integrations must follow declarative-first wiring' "${ROOT}/docs/development/adk/implementation-discovery-guide.md"
grep -q 'No hardcoded ports' "${ROOT}/docs/development/adk/implementation-discovery-guide.md"
grep -q 'No hardcoded URLs' "${ROOT}/docs/development/adk/implementation-discovery-guide.md"
grep -q 'Environment injection patterns (no hardcoded ports/URLs)' "${ROOT}/lib/l4-coord/adk/declarative-wiring-spec.nix"

echo "PASS: ADK declarative-first wiring requirements remain documented and validator-backed"
