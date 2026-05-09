#!/usr/bin/env bash
# compatibility shim over ai-stack-health.sh and declarative health tooling

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

exec "${REPO_ROOT}/scripts/ai/ai-stack-health.sh" "$@"
