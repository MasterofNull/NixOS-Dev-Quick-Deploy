#!/usr/bin/env bash
set -e

# Use hardcoded path for now to avoid command substitution in the cat command
TOOLS_DIR="./scripts/agent-tools"

echo "=== Testing als ==="
$TOOLS_DIR/als . -d 1 | grep "Shown"

echo -e "\n=== Testing agrep ==="
$TOOLS_DIR/agrep "PRD" . --max-total 1 | grep -E "Found|Total"

echo -e "\n=== Testing acat ==="
$TOOLS_DIR/acat README.md --head 5 | grep "Estimated tokens"

echo -e "\n=== Testing asum ==="
$TOOLS_DIR/asum .agent/GEMINI.md | grep "Summary"

echo -e "\n=== Testing adiff ==="
$TOOLS_DIR/adiff | head -n 5

echo -e "\n=== Testing alog ==="
echo "ERROR: test error" | $TOOLS_DIR/alog | grep "Errors: 1"

echo -e "\n=== Testing atest ==="
$TOOLS_DIR/atest echo "pass" | grep -i "Passed"

echo -e "\n=== Testing aenv ==="
$TOOLS_DIR/aenv "PATH" | grep "PATH"

echo -e "\n=== Testing aproc ==="
$TOOLS_DIR/aproc | head -n 5

echo -e "\n=== Testing ahist ==="
$TOOLS_DIR/ahist -n 1 | grep "|"

echo -e "\n✅ All tools basic smokes passed!"
