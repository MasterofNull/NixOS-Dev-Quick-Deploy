#!/usr/bin/env bash
#
# Import Project Knowledge into Qdrant
# Imports project documentation and scripts while skipping Claude Code internals
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
# shellcheck source=../config/service-endpoints.sh
source "${PROJECT_ROOT}/config/service-endpoints.sh"

echo "==================================================================="
echo "  Importing Project Knowledge into Qdrant"
echo "==================================================================="
echo ""

# Function to import with specific patterns
import_files() {
    local description="$1"
    local dir="$2"
    shift 2
    local extensions=("$@")

    echo "→ Importing $description from $dir"

    python3 "$SCRIPT_DIR/import-documents.py" \
        --directory "$PROJECT_ROOT/$dir" \
        --collection codebase-context \
        --extensions "${extensions[@]}" \
        --verbose 2>&1 | grep -E '(INFO|WARNING|ERROR|✓|Imported)'

    echo ""
}

# Check if Qdrant is running
if ! curl -s --max-time 5 --connect-timeout 3 "${QDRANT_URL}" > /dev/null 2>&1; then
    echo "ERROR: Qdrant is not running at ${QDRANT_URL}"
    echo "Please start the AI stack first:"
    echo "  sudo systemctl status ai-stack.target"
    exit 1
fi

echo "✓ Qdrant is running"
echo ""

# Import project documentation (markdown files)
echo "Phase 1: Project Documentation"
echo "------------------------------"

# Top-level documentation
import_files "Top-level documentation" "." .md

# AI stack documentation
import_files "AI stack documentation" "ai-stack" .md

# Documentation directory
if [ -d "$PROJECT_ROOT/docs" ]; then
    import_files "Docs directory" "docs" .md
fi

# Import scripts (shell and Python)
echo ""
echo "Phase 2: Scripts and Configuration"
echo "-----------------------------------"

# Shell scripts
import_files "Shell scripts" "scripts" .sh .bash

# Python scripts (excluding .agent internals)
import_files "Python tools" "scripts" .py

# Nix configurations
import_files "NixOS configurations" "." .nix

# Phase and library scripts
import_files "Phase scripts" "phases" .sh
import_files "Library scripts" "lib" .sh

# AI stack configuration and code
echo ""
echo "Phase 3: AI Stack Components"
echo "-----------------------------"

# MCP server code (Python and configs)
import_files "MCP server code" "ai-stack/mcp-servers" .py .yml .yaml

# Kubernetes manifests
import_files "Kubernetes manifests" "ai-stack/kubernetes" .yml .yaml

echo ""
echo "==================================================================="
echo "  Knowledge Base Import Complete"
echo "==================================================================="
echo ""
echo "Check Qdrant collection stats:"
echo "  curl ${QDRANT_URL}/collections/codebase-context | jq ."
echo ""
echo "Test context retrieval:"
echo "  curl -X POST ${HYBRID_URL}/augment_query \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\": \"How to deploy NixOS?\", \"agent_type\": \"remote\"}' | jq ."
echo ""
