#!/usr/bin/env bash
#
# Run all BATS unit tests
# Usage: ./tests/run-unit-tests.sh
#
# Requires: bats-core (installed via nix-shell or system package)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="$SCRIPT_DIR/unit"

# Try to find bats
if ! command -v bats >/dev/null 2>&1; then
    echo "bats not found in PATH. Attempting nix-shell..."
    exec nix-shell -p bats --run "bats --tap '$UNIT_DIR'"
fi

echo "Running unit tests..."
echo "======================================"
bats --tap "$UNIT_DIR"
