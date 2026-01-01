#!/usr/bin/env bash
# Basic health checks for the local AI stack + dashboard services.
# Deprecated: use scripts/ai-stack-health.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/ai-stack-health.sh" "$@"
