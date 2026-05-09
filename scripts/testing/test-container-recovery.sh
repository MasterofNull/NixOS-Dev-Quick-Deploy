#!/usr/bin/env bash
# compatibility shim over aq-runtime-act and aq-system-act

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

"${REPO_ROOT}/scripts/ai/aq-runtime-act" --help >/dev/null
"${REPO_ROOT}/scripts/ai/aq-system-act" --help >/dev/null

echo "PASS: bounded runtime tooling is available for recovery actions"
