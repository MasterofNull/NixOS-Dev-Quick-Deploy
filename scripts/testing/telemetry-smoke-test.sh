#!/usr/bin/env bash
# compatibility shim over current observability smoke checks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

exec "${REPO_ROOT}/scripts/testing/validate-genai-observability.sh" "$@"
