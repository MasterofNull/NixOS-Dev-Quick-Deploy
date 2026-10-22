#!/usr/bin/env bash
# Tier 0 Check: Instruction Line Budget (<200 lines per general instruction file)
# Slice: w4-s4 (Instruction files as compact indexes)
# Enforces that CLAUDE.md, AGENTS.md, .agent/CODEX.md, .agent/GEMINI.md, and .agent/LOCAL-AGENT.md
# remain compact progressive disclosure indexes strictly under 200 lines.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

MAX_LINES=200
TARGET_FILES=(
    "CLAUDE.md"
    "AGENTS.md"
    ".agent/CODEX.md"
    ".agent/GEMINI.md"
    ".agent/LOCAL-AGENT.md"
)

FAILED=0

for file in "${TARGET_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "::error file=$file::Required instruction file $file does not exist"
        FAILED=1
        continue
    fi

    LINE_COUNT=$(wc -l < "$file" | tr -d ' ')
    if (( LINE_COUNT > MAX_LINES )); then
        echo "::error file=$file::Instruction file $file exceeds budget ($LINE_COUNT > $MAX_LINES lines). Compact content or offload reference tables to .agent/lanes/."
        FAILED=1
    else
        echo "PASS: $file ($LINE_COUNT/$MAX_LINES lines)"
    fi
done

if (( FAILED != 0 )); then
    echo "FAILED: Instruction line budget check failed."
    exit 1
fi

echo "All instruction files are within line budget (<$MAX_LINES lines)."
exit 0
