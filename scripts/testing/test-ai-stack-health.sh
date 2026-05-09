#!/usr/bin/env bash
# compatibility shim over check-ai-stack-health.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "${SCRIPT_DIR}/check-ai-stack-health.sh" "$@"
