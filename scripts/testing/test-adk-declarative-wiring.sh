#!/usr/bin/env bash
# Purpose: verify ADK declarative-first wiring requirements stay documented and validator-backed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

bash "${ROOT}/lib/adk/wiring-validator.sh" --dir "${ROOT}/lib/adk" --pattern "*.nix" >/dev/null

grep -q 'All ADK integrations must follow declarative-first wiring' "${ROOT}/docs/development/adk/implementation-discovery-guide.md"
grep -q 'No hardcoded ports' "${ROOT}/docs/development/adk/implementation-discovery-guide.md"
grep -q 'No hardcoded URLs' "${ROOT}/docs/development/adk/implementation-discovery-guide.md"
grep -q 'Environment injection patterns (no hardcoded ports/URLs)' "${ROOT}/lib/adk/declarative-wiring-spec.nix"

echo "PASS: ADK declarative-first wiring requirements remain documented and validator-backed"
