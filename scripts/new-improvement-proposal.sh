#!/usr/bin/env bash
# Create a new improvement proposal from the template.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${SCRIPT_DIR}/docs/development/IMPROVEMENT-PROPOSAL-TEMPLATE.md"
OUT_DIR="${SCRIPT_DIR}/docs/development"

if [[ ! -f "$TEMPLATE" ]]; then
    echo "Template not found: $TEMPLATE" >&2
    exit 1
fi

title="${1:-}"
if [[ -z "$title" ]]; then
    echo "Usage: $(basename "$0") \"Proposal Title\"" >&2
    exit 1
fi

date_str=$(date +%Y-%m-%d)
slug=$(echo "$title" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')
out_file="${OUT_DIR}/${date_str}-${slug}.md"

cp "$TEMPLATE" "$out_file"
perl -0pi -e "s/\\*\\*Created:\\*\\* YYYY-MM-DD/**Created:** ${date_str}/" "$out_file"

echo "Created proposal: $out_file"
