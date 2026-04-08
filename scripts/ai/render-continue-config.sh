#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# render-continue-config.sh — Render Continue config.json with actual values
#
# Reads ai-stack/continue/config.json.template (or config.json with shell vars)
# and outputs a rendered config.json with literal values.
#
# Usage:
#   scripts/ai/render-continue-config.sh [--output PATH]
#
# Environment:
#   HYBRID_COORDINATOR_PORT  (default: 8003)
#   SWITCHBOARD_PORT         (default: 8085)
#   LLAMA_CPP_PORT           (default: 8080)
#   CONTINUE_CONFIG_OUTPUT   (default: ~/.continue/config.json)
# ---------------------------------------------------------------------------
set -euo pipefail

# Defaults
HYBRID_COORDINATOR_PORT="${HYBRID_COORDINATOR_PORT:-8003}"
SWITCHBOARD_PORT="${SWITCHBOARD_PORT:-8085}"
LLAMA_CPP_PORT="${LLAMA_CPP_PORT:-8080}"
OUTPUT_PATH="${CONTINUE_CONFIG_OUTPUT:-${HOME}/.continue/config.json}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --output) OUTPUT_PATH="$2"; shift 2;;
    --help) echo "Usage: $0 [--output PATH]"; exit 0;;
    *) echo "Unknown option: $1"; exit 1;;
  esac
done

# Find template
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TEMPLATE="${REPO_ROOT}/ai-stack/continue/config.json"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "ERROR: Template not found: $TEMPLATE" >&2
  exit 1
fi

# Create output directory
mkdir -p "$(dirname "$OUTPUT_PATH")"

# Render template
echo "Rendering Continue config..."
echo "  Template: $TEMPLATE"
echo "  Output:   $OUTPUT_PATH"
echo "  Ports:    hybrid=${HYBRID_COORDINATOR_PORT}, switchboard=${SWITCHBOARD_PORT}, llama=${LLAMA_CPP_PORT}"

# Replace shell variables with actual values
sed -e "s/\${HYBRID_COORDINATOR_PORT:-8003}/${HYBRID_COORDINATOR_PORT}/g" \
    -e "s/\${SWITCHBOARD_PORT:-8085}/${SWITCHBOARD_PORT}/g" \
    -e "s/\${LLAMA_CPP_PORT:-8080}/${LLAMA_CPP_PORT}/g" \
    "$TEMPLATE" > "$OUTPUT_PATH"

# Validate JSON
if python3 -m json.tool "$OUTPUT_PATH" > /dev/null 2>&1; then
  echo "✓ Rendered config is valid JSON"
else
  echo "✗ Rendered config is not valid JSON!" >&2
  exit 1
fi

echo "✓ Continue config rendered to $OUTPUT_PATH"
echo ""
echo "To use this config:"
echo "  1. Restart Continue extension in VSCode/VSCodium"
echo "  2. Or copy to ~/.continue/config.json manually"
echo ""
echo "Current config location: $OUTPUT_PATH"
